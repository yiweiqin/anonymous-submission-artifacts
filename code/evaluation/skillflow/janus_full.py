"""Run janus_full on the eight SkillFlow development families.

The six paper baselines stay in baseline-record.jsonl and are not repeated.
Gate and locked stay closed. protocol.json is not modified.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import baseline_updates
import baselines
import harbor_bridge
import preflight

GPU_DIR = os.environ.get("JANUS_GPU_DIR", "janus-runtime")
GPU_PYTHON = os.environ.get("JANUS_GPU_PYTHON", "python")
EXPECTED_HOST = os.environ.get("JANUS_EXPECTED_HOST", "")
REQUIRED_GPU = os.environ.get("JANUS_REQUIRED_GPU", "")
MODEL_STORE = os.environ.get("JANUS_MODEL_STORE", "/data/modelstore")
SKILLFLOW_REMOTE = os.environ.get("JANUS_SKILLFLOW_REMOTE", "")
ETA = HERE / "janus-eta.txt"
TABLE = HERE / "janus-lift.json"


def gpu_client():
    return baselines.client(
        os.environ["RDMD_SSH_HOST"], int(os.environ["RDMD_SSH_PORT"]),
        os.environ.get("RDMD_SSH_USER", "root"),
        os.environ["RDMD_SSH_PASSWORD"],
    )


def remote_exists(ssh, path):
    code, out, _err = baselines.exec_text(
        ssh, "test -e " + shlex.quote(path) + " && echo OK || echo MISSING", 30)
    return code == 0 and out.strip() == "OK"


def weight_ready(ssh, directory):
    for name in ("adapter_model.safetensors", "adapter_model.bin"):
        if remote_exists(ssh, directory.rstrip("/") + "/" + name):
            return True
    return False


def preflight_model_host(roles):
    """Read-only check. A missing weight stops the run and is not copied back."""
    ssh = gpu_client()
    try:
        code, out, err = baselines.exec_text(ssh, "hostname", 30)
        host = out.strip()
        baselines.say("HOST", host)
        if code != 0 or (EXPECTED_HOST and host != EXPECTED_HOST):
            raise SystemExit("unexpected_host")
        code, out, err = baselines.exec_text(
            ssh, "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader", 30)
        baselines.say("GPU", out.strip() or err.strip())
        if code != 0 or (REQUIRED_GPU and REQUIRED_GPU not in out):
            raise SystemExit("unexpected_gpu")
        code, out, _err = baselines.exec_text(ssh, "df -h " + shlex.quote(MODEL_STORE), 30)
        baselines.say(out.strip())
        code, avail, _err = baselines.exec_text(
            ssh, "df -B1 --output=avail " + shlex.quote(MODEL_STORE) + " | tail -1", 30)
        if code != 0 or int(avail.strip()) < 6 * 1024 ** 3:
            raise SystemExit("model_disk_below_6gb")
        required = [
            (roles["baseModel"].rstrip("/") + "/config.json", "qwen"),
            (roles["detectiveAdapter"].rstrip("/") + "/adapter_config.json", "detective"),
            (roles["dsAdapter"].rstrip("/") + "/adapter_config.json", "dependency_similarity"),
            *(((SKILLFLOW_REMOTE, "skillflow_data"),) if SKILLFLOW_REMOTE else ()),
        ]
        for path, label in required:
            if not remote_exists(ssh, path):
                baselines.say("MISSING", label)
                raise SystemExit("missing_on_model_host")
            baselines.say("OK", label)
        if not remote_exists(ssh, GPU_PYTHON):
            baselines.say("MISSING", "rdmd_python")
            raise SystemExit("missing_on_model_host")
        baselines.say("OK", "rdmd_python")
        if not weight_ready(ssh, roles["detectiveAdapter"]):
            baselines.say("MISSING", "detective_weight")
            raise SystemExit("missing_on_model_host")
        if not weight_ready(ssh, roles["dsAdapter"]):
            baselines.say("MISSING", "dependency_similarity_weight")
            raise SystemExit("missing_on_model_host")
        baselines.say("OK", "detective_weight")
        baselines.say("OK", "dependency_similarity_weight")
    finally:
        ssh.close()


class Detective:
    """One Qwen3-8B + detective LoRA call at a time. The base model is not used alone."""

    def __init__(self, model, adapter):
        self.model = model
        self.adapter = adapter
        self.ssh = None
        self.ready = False
        self.lock = threading.Lock()

    def close(self):
        if self.ssh is not None:
            try:
                self.ssh.close()
            except Exception:
                pass
        self.ssh = None
        self.ready = False

    def _connect(self):
        if self.ssh is None:
            self.ssh = gpu_client()
        if self.ready:
            return
        code, _out, err = baselines.exec_text(self.ssh, "mkdir -p " + shlex.quote(GPU_DIR), 30)
        if code != 0:
            raise RuntimeError(err[-200:])
        detective = HERE.parent / "detective-deploy"
        sftp = self.ssh.open_sftp()
        sftp.get_channel().settimeout(60)
        baselines.upload(sftp, detective / "predict.py", GPU_DIR + "/predict.py")
        baselines.upload(sftp, detective / "rdmd_detective.py", GPU_DIR + "/rdmd_detective.py")
        baselines.upload(sftp, HERE / "ds_remote.py", GPU_DIR + "/ds_remote.py")
        sftp.get_channel().close()
        self.ready = True

    def ask(self, case, slug, adapter=None):
        with self.lock:
            last = None
            chosen = self.adapter if adapter is None else adapter
            for attempt in range(6):
                try:
                    self._connect()
                    return self._predict(case, slug, chosen)
                except SystemExit:
                    raise
                except Exception as exc:
                    last = exc
                    self.close()
                    if attempt < 5:
                        time.sleep(min(60, 5 * (attempt + 1)))
            raise SystemExit("detective_unavailable:" + type(last).__name__)

    def _predict(self, case, slug, adapter=None):
        remote_case = GPU_DIR + "/" + slug + ".json"
        remote_out = GPU_DIR + "/" + slug + ".jsonl"
        local = HERE / ("_janus_case_" + slug + ".json")
        local.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
        try:
            sftp = self.ssh.open_sftp()
            sftp.get_channel().settimeout(60)
            baselines.upload(sftp, local, remote_case)
            sftp.get_channel().close()
        finally:
            local.unlink(missing_ok=True)
        command = " ".join(shlex.quote(part) for part in [
            GPU_PYTHON, GPU_DIR + "/predict.py",
            "--input", remote_case,
            "--output", remote_out,
            "--model", self.model,
            "--adapter", self.adapter if adapter is None else adapter,
            "--device", "cuda:0",
        ])
        code, out, err = baselines.exec_text(self.ssh, command, 1800)
        if "CUDA out of memory" in err or "No space left" in err:
            raise SystemExit(harbor_bridge.fatal_reason(err) or "detective_failed")
        sftp = self.ssh.open_sftp()
        sftp.get_channel().settimeout(60)
        try:
            with sftp.open(remote_out) as handle:
                text = handle.read().decode("utf-8")
        except OSError:
            text = ""
        sftp.get_channel().close()
        if code == 2 or not text.strip():
            tail = " ".join(str(err or "").split())[-240:]
            raise SystemExit("detective_failed:" + baselines.scrub(tail))
        row = json.loads(text.splitlines()[-1])
        verdict = dict(row.get("verdict") or {})
        verdict["valid"] = row.get("valid")
        verdict["warnings"] = row.get("warnings") or []
        verdict["exitCode"] = code
        verdict["raw"] = row.get("raw") or ""
        verdict["promptTokens"] = row.get("promptTokens")
        verdict["completionTokens"] = row.get("completionTokens")
        return verdict

    def score_pairs(self, pairs, adapter, slug):
        """One CPDB load scores every pair. Dependency staffs; similarity replaces."""
        with self.lock:
            last = None
            for attempt in range(6):
                try:
                    self._connect()
                    return self._score(pairs, adapter, slug)
                except SystemExit:
                    raise
                except Exception as exc:
                    last = exc
                    self.close()
                    if attempt < 5:
                        time.sleep(min(60, 5 * (attempt + 1)))
            raise SystemExit("ds_unavailable:" + type(last).__name__)

    def _score(self, pairs, adapter, slug):
        remote_in = GPU_DIR + "/" + slug + ".jsonl"
        remote_out = GPU_DIR + "/" + slug + ".scores.jsonl"
        local = HERE / ("_janus_pairs_" + slug + ".jsonl")
        local.write_text(
            "".join(json.dumps({"id": pair["id"], "prompt": pair["prompt"]}, ensure_ascii=False) + "\n" for pair in pairs),
            encoding="utf-8",
        )
        try:
            sftp = self.ssh.open_sftp()
            sftp.get_channel().settimeout(60)
            baselines.upload(sftp, local, remote_in)
            sftp.get_channel().close()
        finally:
            local.unlink(missing_ok=True)
        command = " ".join(shlex.quote(part) for part in [
            GPU_PYTHON, GPU_DIR + "/ds_remote.py", self.model, adapter, remote_in, remote_out,
        ])
        _code, _out, err = baselines.exec_text(self.ssh, command, 1800)
        if "CUDA out of memory" in err or "No space left" in err:
            raise SystemExit("ds_failed")
        sftp = self.ssh.open_sftp()
        sftp.get_channel().settimeout(60)
        try:
            with sftp.open(remote_out) as handle:
                text = handle.read().decode("utf-8")
        except OSError:
            text = ""
        sftp.get_channel().close()
        if not text.strip():
            tail = " ".join(str(err or "").split())[-240:]
            raise SystemExit("ds_failed:" + baselines.scrub(tail))
        return [json.loads(line) for line in text.splitlines() if line.strip()]


def restored(family):
    carry = ""
    staff = []
    staff_source = ""
    for row in baselines.records():
        if row.get("arm") != "janus_full" or row.get("family") != family:
            continue
        if row.get("error") == "missing_task_dir" or not baselines.row_done(row):
            continue
        carry = row.get("carry") or ""
        if row.get("staff"):
            staff = row["staff"]
        if row.get("staffSource"):
            staff_source = row["staffSource"]
    plan = harbor_bridge.staff_plan(family)
    by_id = {
        item.get("id"): item.get("agentId")
        for item in staff
        if isinstance(item, dict) and item.get("id") and item.get("agentId")
    }
    for node in plan["nodes"]:
        profile_id = by_id.get(node["id"])
        if profile_id in harbor_bridge.CATALOG:
            harbor_bridge._write_profile(node, profile_id, family)
    return carry, plan, staff_source


def staff_family(detective, roles, family):
    pairs = harbor_bridge.staffing_pairs(family)
    raw = detective.score_pairs(pairs, roles["dsAdapter"], baselines.job_name_for("staff", "janus", family, "team"))
    by_id = {row.get("id"): row for row in raw}
    scores = []
    for pair in pairs:
        got = by_id.get(pair["id"]) or {}
        scores.append({
            "left": pair["left"],
            "right": pair["right"],
            "dependency": got.get("dependency"),
            "similarity": got.get("similarity"),
        })
    if not any(row["dependency"] is not None for row in scores):
        raise SystemExit("ds_unscored")
    choice = harbor_bridge.choose_staff(scores)
    baselines.say("STAFF", family, choice["work"], choice["check"])
    return harbor_bridge.apply_staff(harbor_bridge.staff_plan(family), choice, family)


def staff_of(plan):
    return [{"id": node["id"], "agentId": node["agentId"]} for node in plan["nodes"]]


def harbor_once(family, task, carry, kind):
    payload = None
    for attempt in range(3):
        payload = baselines.run_harbor(family, task, "janus_full", carry, kind)
        trial_error = baselines.scrub(payload.get("error") or "")
        reason = harbor_bridge.fatal_reason(trial_error)
        if payload.get("reward") is not None and reason not in {
            "Missing credentials", "No space left", "missing_api_key",
        }:
            return payload
        if reason in {"Missing credentials", "No space left", "missing_api_key"}:
            return payload
        if attempt < 2:
            baselines.say("RETRY", "janus_full", family, task, kind, attempt + 1)
            time.sleep(15 * (attempt + 1))
    return payload


def note_missing(split, family, missing):
    for name in missing:
        harbor_bridge.assert_janus_request(split, family, "janus_full")
        if baselines.finished("janus_full", family, name):
            baselines.say("SKIP", "janus_full", family, name)
            continue
        baselines.append({
            "arm": "janus_full",
            "family": family,
            "task": name,
            "reward": None,
            "error": "missing_task_dir",
            "carry": "",
            "truncated": False,
            "staff": [],
            "taskModel": harbor_bridge.TASK_MODEL,
            "modelCalls": 0,
            "promptTokens": 0,
            "completionTokens": 0,
            "wallSeconds": 0,
            "harborTrials": 0,
            "selectionTrials": [],
        })
        baselines.say("MISSING", "janus_full", family, name)


def run_family(split, family, tasks, detective, roles, stop):
    harbor_bridge.assert_janus_request(split, family, "janus_full")
    carry = ""
    plan = harbor_bridge.staff_plan(family)
    staff_source = ""
    resumed = False
    for task in tasks:
        if stop.is_set():
            return
        if baselines.finished("janus_full", family, task):
            baselines.say("SKIP", "janus_full", family, task)
            continue
        if not resumed:
            carry, plan, staff_source = restored(family)
            if staff_source != "ds":
                plan = staff_family(detective, roles, family)
                staff_source = "ds"
            resumed = True
        baselines.say("RUN", "janus_full", family, task)
        baselines.wait_for_disk()
        payload = harbor_once(family, task, carry, "janus")
        usage = {"modelCalls": 0, "promptTokens": 0, "completionTokens": 0, "wallSeconds": 0}
        baselines.add_usage(usage, payload)
        harbor_trials = 1
        error = baselines.scrub(payload.get("error") or "")
        reward = payload.get("reward")
        verdict = {"status": "not_called", "valid": False, "changedFields": []}
        selection = []
        replay_reward = None
        if reward is not None and not error:
            started = time.monotonic()
            execution = harbor_bridge.execution_graph(
                plan,
                1 if harbor_bridge._reward_passed(reward) else 0,
                baselines.scrub(payload.get("trace") or ""),
            )
            case = harbor_bridge.detective_case(family + "/" + task, plan, execution)
            slug = baselines.job_name_for("detective", "janus", family, task)
            verdict = detective.ask(case, slug)
            verdict = harbor_bridge.recover_verdict(
                verdict,
                [node["id"] for node in plan["nodes"]],
                harbor_bridge.changed_fields_by_node(plan, execution),
            )
            usage["wallSeconds"] += time.monotonic() - started
            replacement = ""
            fields_now = verdict.get("changedFields") or []
            if verdict.get("type") == "wrong_agent" and fields_now and str(fields_now[0]) == "agentId":
                current = ""
                for node in plan["nodes"]:
                    if node["id"] == verdict.get("nodeId"):
                        current = node.get("agentId") or ""
                if current in harbor_bridge.CATALOG:
                    pairs = harbor_bridge.replacement_pairs(current, family)
                    raw = detective.score_pairs(
                        pairs, roles["dsAdapter"], baselines.job_name_for("swap", "janus", family, task))
                    by_id = {row.get("id"): row for row in raw}
                    similarity_scores = []
                    for pair in pairs:
                        got = by_id.get(pair["id"]) or {}
                        similarity_scores.append({
                            "left": pair["left"],
                            "right": pair["right"],
                            "similarity": got.get("similarity"),
                        })
                    replacement = harbor_bridge.choose_replacement(current, similarity_scores)
                    baselines.say("REPLACE", family, current, replacement or "none")
            plan = harbor_bridge.apply_replacement(plan, verdict, replacement)
            trace = baselines.scrub(payload.get("trace") or "")
            candidate = harbor_bridge.one_update(verdict, trace, family)
            if candidate and candidate != carry and not harbor_bridge._reward_passed(reward):
                baselines.wait_for_disk()
                replay = harbor_once(family, task, candidate, "janus-replay")
                baselines.add_usage(usage, replay)
                harbor_trials += 1
                replay_reward = replay.get("reward")
                replay_error = baselines.scrub(replay.get("error") or "")
                reason = harbor_bridge.fatal_reason(replay_error)
                if reason in {"Missing credentials", "No space left", "missing_api_key"}:
                    error = reason
                elif replay_reward is None:
                    error = baseline_updates.official_error_after_replay(replay_error)
                else:
                    replay_error = ""
                carry = harbor_bridge.next_carry(
                    carry, verdict, family=family, reward=reward, replay_reward=replay_reward, trace=trace)
                selection.append({
                    "task": task,
                    "reward": replay_reward,
                    "kept": carry == candidate and harbor_bridge._reward_passed(replay_reward),
                    "error": "" if replay_reward is not None else replay_error[-200:],
                })
            else:
                carry = harbor_bridge.next_carry(
                    carry, verdict, family=family, reward=reward, replay_reward=None, trace=trace)
        official = harbor_bridge.recorded_reward(reward, replay_reward)
        fields = verdict.get("changedFields") or []
        row = {
            "arm": "janus_full",
            "family": family,
            "task": task,
            "reward": official,
            "error": error,
            "carry": carry,
            "truncated": False,
            "staff": staff_of(plan),
            "staffSource": staff_source,
            "taskModel": roles["taskModel"],
            "detective": roles["detectiveAdapter"],
            "dependencySimilarity": roles["dsAdapter"],
            "verdictStatus": verdict.get("status"),
            "nodeId": verdict.get("nodeId") or "",
            "field": str(fields[0]) if fields else "",
            "modelCalls": usage["modelCalls"],
            "promptTokens": usage["promptTokens"],
            "completionTokens": usage["completionTokens"],
            "wallSeconds": round(usage["wallSeconds"], 3),
            "harborTrials": harbor_trials,
            "selectionTrials": selection,
        }
        baselines.append(row)
        baselines.say("DONE", json.dumps({
            "arm": "janus_full",
            "family": family,
            "task": task,
            "reward": official,
            "replay": replay_reward,
            "verdict": verdict.get("status"),
            "field": row["field"],
            "carryChars": len(carry),
            "wallSeconds": row["wallSeconds"],
        }, ensure_ascii=False))
        reason = harbor_bridge.fatal_reason(error)
        if reason or reward is None:
            stop.set()
            raise SystemExit(reason or error or "no_reward")


def write_eta(task_total):
    done_wall = 0.0
    done_tasks = 0
    done_trials = 0
    for row in baselines.records():
        if row.get("arm") != "janus_full" or row.get("error") == "missing_task_dir":
            continue
        if not baselines.row_done(row):
            continue
        done_wall += float(row.get("wallSeconds") or 0)
        done_trials += int(row.get("harborTrials") or 0)
        done_tasks += 1
    if done_tasks <= 0:
        return
    remaining = max(0, task_total - done_tasks)
    hours = remaining * (done_wall / done_tasks) / 3600
    text = (
        "janus_full 已完成 %d/%d 题，Harbor %d 次，平均每题 %.1f 分钟。"
        "剩余正式题 %d，按已完成的每题耗时估计还要 %.1f 小时。"
        % (done_tasks, task_total, done_trials, done_wall / done_tasks / 60, remaining, hours)
    )
    ETA.write_text(text + "\n", encoding="utf-8")
    baselines.say("ETA " + text)


def worker_count():
    workers = 4
    if "--workers" in sys.argv:
        index = sys.argv.index("--workers")
        workers = int(sys.argv[index + 1])
    return max(1, min(4, workers))


def publish_table():
    split = harbor_bridge.load_json(HERE / "family-split.json")
    protocol = preflight.load_protocol()
    families = list(split["development"])
    arms = ["vanilla"] + [arm["id"] for arm in protocol["baselines"]] + ["janus_full"]
    import lift_table
    rows = lift_table.load_rows(baselines.RECORD)
    report = lift_table.family_lifts(rows, families, arms)
    ranked = lift_table.mean_lifts(report)
    payload = {
        "complete": ranked is not None,
        "families": report,
        "meanLift": ranked,
        "appendixPassRate": lift_table.appendix_pass_rates(report),
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    TABLE.write_text(text + "\n", encoding="utf-8")
    print(text, flush=True)
    return payload


def main():
    protocol = preflight.load_protocol()
    if protocol.get("paperReady") is not False or protocol.get("realRunAllowed") is not False:
        raise SystemExit("protocol_flags_opened")
    split = harbor_bridge.load_json(HERE / "family-split.json")
    if split.get("lockedMayOpen") is not False:
        raise SystemExit("locked_split_opened")
    roles = harbor_bridge.resolved_roles(os.environ)
    if roles["taskModel"] != "deepseek-flash":
        raise SystemExit("task_model_must_stay_deepseek_flash")
    preflight_model_host(roles)
    families = list(split["development"])
    workers = worker_count()
    baselines.say("WORKERS", workers)
    plans = []
    task_total = 0
    ssh = baselines.light_client()
    try:
        baselines.ensure_remote_files(ssh)
        for family in families:
            harbor_bridge.assert_janus_request(split, family, "janus_full")
            present, missing = baselines.ranking(ssh, family)
            plans.append((family, present, missing))
            task_total += len(present)
    finally:
        ssh.close()
    for family, _present, missing in plans:
        note_missing(split, family, missing)
    detective = Detective(roles["baseModel"], roles["detectiveAdapter"])
    stop = threading.Event()
    errors = []
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(run_family, split, family, present, detective, roles, stop)
                for family, present, _missing in plans
            ]
            pending = set(futures)
            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    try:
                        future.result()
                    except BaseException as exc:
                        stop.set()
                        errors.append(exc)
                if not errors:
                    write_eta(task_total)
    finally:
        detective.close()
    if errors:
        raise SystemExit(str(errors[0]))
    publish_table()


if __name__ == "__main__":
    main()
