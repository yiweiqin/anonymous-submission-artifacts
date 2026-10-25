"""Backbone measurement for qwen3.8-flash and glm-5.3-flash.

Same development tasks, order, Harbor budget, and janus_full update rule as
the main table. Ledgers stay in this directory. protocol.json and
baseline-record.jsonl are not written.
"""

from __future__ import annotations

import json
import msvcrt
import os
import re
import shlex
import socket
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN = HERE.parents[2] / "code" / "evaluation" / "skillflow"
REMOTE_ROOT = "/benchmark/skillflow-main-20261008"
sys.path.insert(0, str(MAIN))

FAMILIES = [
    "Healthcare-Cost-Benefit-Analysis",
    "DMAIC-Quality-Analysis",
    "SEC-13F-Financial-Analysis",
    "Compensation-Scenario-Modeling",
    "Weighted-Risk-Assessment",
    "Embedded-Data-Repair",
    "Inventory-&-Finance-Integration",
    "Operational-Recovery-Planning",
]
MODELS = {
    "qwen": {
        "model": "qwen3.8-flash",
        "apiBase": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "keyFile": REMOTE_ROOT + "/.secrets/qwen.key",
        "enableThinking": False,
        "llmCallKwargs": {"extra_body": {"enable_thinking": False}},
        "modelInfo": {
            "max_input_tokens": 991808,
            "max_output_tokens": 131072,
            "input_cost_per_token": 0.8 / 1000000,
            "output_cost_per_token": 2.7 / 1000000,
        },
    },
    "glm": {
        "model": "glm-5.3-flash",
        "apiBase": "https://open.bigmodel.cn/api/paas/v4",
        "keyFile": REMOTE_ROOT + "/.secrets/glm.key",
        "enableThinking": True,
        "llmCallKwargs": {"extra_body": {"thinking": {"type": "enabled"}}},
        "modelInfo": {
            "max_input_tokens": 1000000,
            "max_output_tokens": 131072,
            "input_cost_per_token": 0,
            "output_cost_per_token": 0,
        },
    },
    "qwen-max": {
        "model": "qwen3.8-max",
        "apiBase": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "keyFile": REMOTE_ROOT + "/.secrets/qwen.key",
        "enableThinking": True,
        "llmCallKwargs": {"extra_body": {"enable_thinking": True}},
        "modelInfo": {
            "max_input_tokens": 991808,
            "max_output_tokens": 131072,
            "input_cost_per_token": 0,
            "output_cost_per_token": 0,
        },
    },
    "glm-max": {
        "model": "glm-5.3",
        "apiBase": "https://open.bigmodel.cn/api/paas/v4",
        "keyFile": REMOTE_ROOT + "/.secrets/glm.key",
        "enableThinking": True,
        "llmCallKwargs": {"extra_body": {"thinking": {"type": "enabled"}}},
        "modelInfo": {
            "max_input_tokens": 1000000,
            "max_output_tokens": 131072,
            "input_cost_per_token": 0,
            "output_cost_per_token": 0,
        },
    },
    "qwen-max-nt": {
        "model": "qwen3.8-max",
        "apiBase": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "keyFile": REMOTE_ROOT + "/.secrets/qwen.key",
        "enableThinking": False,
        "reasoningEffort": "",
        "llmCallKwargs": {"extra_body": {"enable_thinking": False}},
        "modelInfo": {
            "max_input_tokens": 991808,
            "max_output_tokens": 131072,
            "input_cost_per_token": 0,
            "output_cost_per_token": 0,
        },
    },
    "glm-low": {
        "model": "glm-5.3-flash",
        "apiBase": "https://open.bigmodel.cn/api/paas/v4",
        "keyFile": REMOTE_ROOT + "/.secrets/glm.key",
        "enableThinking": True,
        "reasoningEffort": "low",
        "llmCallKwargs": {"extra_body": {"thinking": {"type": "enabled"}, "reasoning_effort": "low"}},
        "modelInfo": {
            "max_input_tokens": 1000000,
            "max_output_tokens": 131072,
            "input_cost_per_token": 0,
            "output_cost_per_token": 0,
        },
    },
    "glm-max-low": {
        "model": "glm-5.3",
        "apiBase": "https://open.bigmodel.cn/api/paas/v4",
        "keyFile": REMOTE_ROOT + "/.secrets/glm.key",
        "enableThinking": True,
        "reasoningEffort": "low",
        "llmCallKwargs": {"extra_body": {"thinking": {"type": "enabled"}, "reasoning_effort": "low"}},
        "modelInfo": {
            "max_input_tokens": 1000000,
            "max_output_tokens": 131072,
            "input_cost_per_token": 0,
            "output_cost_per_token": 0,
        },
    },
}
ARMS = ("vanilla", "janus_full")
# The Harbor host is 2 cores. Six overlapping trials wait; eight dropped SSH banners.
HARBOR = threading.Semaphore(6)
LOCAL = threading.local()
SEEN = {}
LOCK = threading.RLock()
PLAN_LOCK = threading.RLock()


class FileLock:
    """Cross-process lock. Three janus runs share one GPU and one summary file."""

    def __init__(self, path):
        self.path = path
        self.handle = None

    def __enter__(self):
        self.handle = open(self.path, "a+b")
        if self.handle.seek(0, 2) < 1:
            self.handle.write(b"\0")
            self.handle.flush()
        self.handle.seek(0)
        while True:
            try:
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_LOCK, 1)
                return self
            except OSError:
                time.sleep(0.2)

    def __exit__(self, *_exc):
        try:
            self.handle.seek(0)
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self.handle.close()
            self.handle = None


def load_env():
    missing = [name for name in ("RDMD_SSH_HOST", "RDMD_SSH_PORT", "RDMD_SSH_USER", "RDMD_SSH_PASSWORD") if not os.environ.get(name)]
    if missing:
        raise SystemExit("missing_environment:" + ",".join(missing))


def say(*parts):
    print(*parts, flush=True)


def ledger_path(slug, errors=False):
    return HERE / (slug + ("-errors.jsonl" if errors else ".jsonl"))


def roles_for(spec):
    import harbor_bridge
    roles_file = harbor_bridge.model_roles()
    return {
        "taskModel": spec["model"],
        "baseModel": os.environ.get("RDMD_BASE_MODEL") or roles_file["baseModel"],
        "detectiveAdapter": os.environ.get("JANUS_DUAL_TREE_ADAPTER") or roles_file["detective"]["adapter"],
        "dsAdapter": os.environ.get("JANUS_CPDB_ADAPTER") or roles_file["dependencySimilarity"]["adapter"],
    }


def install_runtime():
    import baselines
    import harbor_bridge
    import janus_full

    original_staff = harbor_bridge.staff_plan
    original_apply = harbor_bridge.apply_staff

    def staff_plan(title):
        with PLAN_LOCK:
            harbor_bridge.TASK_MODEL = MODELS[LOCAL.slug]["model"]
            return original_staff(title)

    def apply_staff(plan, choice, family):
        with PLAN_LOCK:
            harbor_bridge.TASK_MODEL = MODELS[LOCAL.slug]["model"]
            return original_apply(plan, choice, family)

    harbor_bridge.staff_plan = staff_plan
    harbor_bridge.apply_staff = apply_staff

    original_ask = janus_full.Detective.ask
    original_score = janus_full.Detective.score_pairs

    def ask(self, case, slug, adapter=None):
        with FileLock(HERE / ".gpu-detective.lock"):
            return original_ask(self, case, LOCAL.slug + "-" + str(slug), adapter)

    def score_pairs(self, pairs, adapter, slug):
        with FileLock(HERE / ".gpu-detective.lock"):
            return original_score(self, pairs, adapter, LOCAL.slug + "-" + str(slug))

    janus_full.Detective.ask = ask
    janus_full.Detective.score_pairs = score_pairs

    def records():
        path = ledger_path(LOCAL.slug)
        with LOCK:
            if not path.is_file():
                return []
            rows = []
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                if line.strip():
                    rows.append(json.loads(line))
            return rows

    def append(row):
        spec = MODELS[LOCAL.slug]
        extra = SEEN.get((LOCAL.slug, row.get("arm"), row.get("family"), row.get("task"))) or {}
        row["taskModel"] = spec["model"]
        row["requestedModel"] = spec["model"]
        row["apiBase"] = spec["apiBase"]
        row["enableThinking"] = spec["enableThinking"]
        row["reasoningEffort"] = spec.get("reasoningEffort") or ""
        row["returnedModel"] = extra.get("returned") or ""
        row["truncations"] = extra.get("truncations") or 0
        if row.get("error") != "missing_task_dir" and (row.get("reward") is None or row.get("error")):
            raise ValueError("invalid_formal_result")
        path = ledger_path(LOCAL.slug)
        with LOCK:
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def append_error(row):
        path = ledger_path(LOCAL.slug, errors=True)
        with LOCK:
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def run_harbor(family, task, arm, carry, kind):
        spec = MODELS[LOCAL.slug]
        kind = LOCAL.slug + "-" + kind
        provider = REMOTE_ROOT + "/.secrets/backbone-" + LOCAL.slug + ".json"
        with HARBOR:
            ssh = baselines.light_client()
            try:
                name = baselines.job_name_for(kind, arm, family, task)
                extra_remote = baselines.REMOTE_JOBS + "/" + name + ".txt"
                result_remote = baselines.REMOTE_JOBS + "/" + name + ".json"
                sftp = ssh.open_sftp()
                with sftp.file(extra_remote, "w") as handle:
                    handle.write(carry)
                sftp.close()
                try:
                    code, out, err = baselines.remote_python(ssh, baselines.REMOTE_TRIAL, [
                        baselines.REMOTE_TASKS + "/" + family + "/" + task,
                        baselines.REMOTE_JOBS,
                        name,
                        extra_remote,
                        result_remote,
                        provider,
                    ], 10800)
                except Exception as exc:
                    code, out, err = 1, "", type(exc).__name__ + ": " + str(exc)
                try:
                    payload = baselines.read_json(ssh, result_remote)
                except Exception:
                    ssh.close()
                    ssh = baselines.light_client()
                    payload = baselines.read_json(ssh, result_remote)
                if payload.get("error") == "no_result":
                    payload["trace"] = (out + "\n" + err)[-2000:]
                payload["exitCode"] = code
                returned = str(payload.get("returnedModel") or "")
                if returned and spec["model"] not in returned:
                    payload["error"] = "model_name_mismatch"
                with LOCK:
                    bucket = SEEN.setdefault((LOCAL.slug, arm, family, task), {"truncations": 0, "returned": ""})
                    bucket["truncations"] += int(payload.get("truncations") or 0)
                    if returned:
                        bucket["returned"] = returned
                return payload
            finally:
                ssh.close()

    disk_checked = {"at": 0.0}

    def exec_text(ssh, command, timeout):
        transport = ssh.get_transport()
        if transport is None or not transport.is_active():
            raise ConnectionError("ssh_transport_dead")
        transport.set_keepalive(15)
        channel = transport.open_session(timeout=40)
        channel.settimeout(20)
        channel.exec_command(command)
        out = bytearray()
        err = bytearray()
        deadline = time.monotonic() + timeout
        while True:
            if time.monotonic() > deadline:
                channel.close()
                raise TimeoutError("remote_timeout")
            if not transport.is_active():
                channel.close()
                raise ConnectionError("ssh_transport_dead")
            try:
                if channel.recv_ready():
                    out.extend(channel.recv(65536))
                if channel.recv_stderr_ready():
                    err.extend(channel.recv_stderr(65536))
            except socket.timeout:
                pass
            except OSError as exc:
                raise ConnectionError("ssh_transport_dead") from exc
            if channel.exit_status_ready():
                while channel.recv_ready():
                    out.extend(channel.recv(65536))
                while channel.recv_stderr_ready():
                    err.extend(channel.recv_stderr(65536))
                code = channel.recv_exit_status()
                return code, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")
            time.sleep(0.2)

    def wait_for_disk():
        now = time.monotonic()
        if now - disk_checked["at"] < 60:
            return
        with LOCK:
            if time.monotonic() - disk_checked["at"] < 60:
                return
            ssh = baselines.light_client()
            try:
                if not baselines.disk_ok(ssh):
                    raise SystemExit("No space left on device or disk check unavailable")
                disk_checked["at"] = time.monotonic()
            finally:
                ssh.close()

    baselines.records = records
    baselines.append = append
    baselines.append_error = append_error
    baselines.run_harbor = run_harbor
    baselines.exec_text = exec_text
    baselines.wait_for_disk = wait_for_disk
    return baselines, harbor_bridge, janus_full


def upload(baselines, slug, spec):
    remote = REMOTE_ROOT + "/.secrets/backbone-" + slug + ".json"
    ssh = baselines.light_client()
    try:
        code, out, _err = baselines.exec_text(
            ssh, "mkdir -p " + baselines.REMOTE_JOBS + " " + REMOTE_ROOT + "/.secrets && test -s " + shlex.quote(spec["keyFile"]) + " && echo KEY",
            30,
        )
        if code != 0 or "KEY" not in out:
            raise SystemExit("missing_remote_key")
        body = {
            "model": spec["model"],
            "apiBase": spec["apiBase"],
            "keyFile": spec["keyFile"],
            "llmCallKwargs": spec["llmCallKwargs"],
            "modelInfo": spec["modelInfo"],
        }
        sftp = ssh.open_sftp()
        with sftp.file(remote, "w") as handle:
            handle.write(json.dumps(body))
        sftp.chmod(remote, 0o600)
        baselines.upload(sftp, MAIN / "remote_one_trial.py", baselines.REMOTE_TRIAL)
        sftp.close()
        baselines.wait_for_disk()
    finally:
        ssh.close()


def plans_for(baselines, harbor_bridge, task_limit):
    split = harbor_bridge.load_json(MAIN / "family-split.json")
    if split.get("lockedMayOpen") is not False:
        raise SystemExit("locked_split_opened")
    families = list(split["development"])
    if families != FAMILIES:
        raise SystemExit("development_order_changed")
    ssh = baselines.light_client()
    plans = []
    try:
        for family in families:
            present, missing = baselines.ranking(ssh, family)
            if task_limit is not None:
                present = present[:task_limit]
            plans.append((family, present, missing))
            if task_limit is not None:
                break
    finally:
        ssh.close()
    return split, plans


def pending(baselines, plans, arms):
    total = 0
    for family, present, _missing in plans:
        for arm in arms:
            for task in present:
                if not baselines.finished(arm, family, task):
                    total += 1
    return total


def one_round(baselines, janus_full, split, plans, arms, slugs, detective, workers):
    stop = threading.Event()
    errors = []

    def bound(slug, fn, args):
        def work():
            LOCAL.slug = slug
            return fn(*args)
        return work

    futures = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        roles = {slug: roles_for(MODELS[slug]) for slug in slugs}
        waves = []
        if "vanilla" in arms:
            waves.append("vanilla")
        if "janus_full" in arms:
            waves.append("janus_full")
        for arm in waves:
            for family, present, _missing in plans:
                for slug in slugs:
                    if arm == "vanilla":
                        futures.append(pool.submit(bound(
                            slug, baselines.run_arm, (split, family, "vanilla", present, stop))))
                    else:
                        futures.append(pool.submit(bound(
                            slug, janus_full.run_family,
                            (split, family, present, detective, roles[slug], stop))))
        waiting = set(futures)
        while waiting:
            done, waiting = wait(waiting, return_when=FIRST_COMPLETED)
            for future in done:
                try:
                    future.result()
                except BaseException as exc:
                    errors.append(exc)
                    say("FAIL", type(exc).__name__, str(exc)[:300])
    if errors:
        raise errors[0]


def preflight_gpu(baselines, janus_full, roles):
    """The live GPU host replaced the hostname frozen in the main-table runner."""
    ssh = janus_full.gpu_client()
    try:
        code, out, err = baselines.exec_text(ssh, "hostname", 30)
        host = out.strip()
        baselines.say("HOST", host)
        if code != 0 or not host:
            raise SystemExit("unexpected_host")
        code, out, err = baselines.exec_text(
            ssh, "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader", 30)
        baselines.say("GPU", out.strip() or err.strip())
        required_gpu = os.environ.get("JANUS_REQUIRED_GPU", "")
        if code != 0 or (required_gpu and required_gpu not in out):
            raise SystemExit("unexpected_gpu")
        store = os.environ.get("JANUS_MODEL_STORE", "/data/modelstore")
        code, avail, _err = baselines.exec_text(
            ssh, "df -B1 --output=avail " + store + " | tail -1", 30)
        if code != 0 or int(avail.strip()) < 6 * 1024 ** 3:
            raise SystemExit("model_disk_below_6gb")
        required = [
            roles["baseModel"].rstrip("/") + "/config.json",
            roles["detectiveAdapter"].rstrip("/") + "/adapter_config.json",
            roles["detectiveAdapter"].rstrip("/") + "/adapter_model.safetensors",
            roles["dsAdapter"].rstrip("/") + "/adapter_config.json",
            roles["dsAdapter"].rstrip("/") + "/adapter_model.safetensors",
            janus_full.GPU_PYTHON,
        ]
        for path in required:
            if not janus_full.remote_exists(ssh, path):
                baselines.say("MISSING", path)
                raise SystemExit("missing_on_model_host")
            baselines.say("OK", path.rsplit("/", 1)[-1])
    finally:
        ssh.close()


def _round_record(slug, spec, model_rows):
    import lift_table
    report = lift_table.family_lifts(model_rows, FAMILIES, ["vanilla", "janus_full"])
    ranked = lift_table.mean_lifts(report)
    appendix = lift_table.appendix_pass_rates(report)
    scored = 0
    mismatch = 0
    truncations = 0
    outgoing_checks = 0
    replays = 0
    replays_kept = 0
    for row in model_rows:
        if row.get("arm") not in ARMS:
            continue
        requested = row.get("requestedModel") or row.get("taskModel") or ""
        returned = row.get("returnedModel") or ""
        if row.get("reward") is None or row.get("error") or (returned and requested and requested not in returned):
            mismatch += 1
            continue
        scored += 1
        truncations += int(row.get("truncations") or 0)
        if row.get("arm") == "janus_full" and str(row.get("carry") or "").strip():
            outgoing_checks += 1
        for trial in row.get("selectionTrials") or []:
            if not isinstance(trial, dict):
                continue
            replays += 1
            if trial.get("kept") is True:
                replays_kept += 1
    lift = None
    if ranked:
        lift = next((item["lift"] for item in ranked if item.get("arm") == "janus_full"), None)
    return {
        "slug": slug,
        "ledger": slug + ".jsonl",
        "taskModel": spec["model"],
        "complete": ranked is not None and mismatch == 0,
        "scored": scored,
        "invalidRows": mismatch,
        "families": report,
        "meanLift": ranked,
        "familyMeanLift": lift,
        "appendixPassRate": appendix,
        "enableThinking": spec["enableThinking"],
        "reasoningEffort": spec.get("reasoningEffort") or "",
        "apiBase": spec["apiBase"],
        "truncations": truncations,
        "janusOutgoingNonemptyChecks": outgoing_checks,
        "selectionReplays": replays,
        "selectionReplaysKept": replays_kept,
        "replayReplacesOfficialReward": False,
    }


def write_summary(baselines, harbor_bridge):
    """Keep every ledger. The comparison map uses the higher family-mean lift."""
    rounds = {}
    for slug, spec in MODELS.items():
        path = HERE / (slug + ".jsonl")
        if not path.is_file():
            rounds[slug] = {
                "slug": slug,
                "taskModel": spec["model"],
                "complete": False,
                "scored": 0,
                "familyMeanLift": None,
            }
            continue
        model_rows = []
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                model_rows.append(json.loads(line))
        rounds[slug] = _round_record(slug, spec, model_rows)
    selected = {}
    for slug, record in rounds.items():
        name = record["taskModel"]
        current = selected.get(name)
        lift = record.get("familyMeanLift")
        if current is None or (
            lift is not None and (current.get("familyMeanLift") is None or lift > current["familyMeanLift"])
        ):
            selected[name] = record
    payload = {
        "savedAt": "2026-10-17",
        "paperReady": False,
        "selectionRule": "When one requested model has two finished rounds, the comparison uses the higher family-mean lift. Official reward is never replaced by a replay.",
        "rounds": rounds,
        "models": {
            name: {key: value for key, value in record.items() if key != "slug"}
            for name, record in selected.items()
        },
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with FileLock(HERE / ".summary.lock"):
        (HERE / "summary.json").write_text(text, encoding="utf-8")
    return payload


def run_all(slugs, arms, task_limit, workers):
    import preflight
    baselines, harbor_bridge, janus_full = install_runtime()
    protocol = preflight.load_protocol()
    if protocol.get("paperReady") is not False or protocol.get("realRunAllowed") is not False:
        raise SystemExit("protocol_flags_opened")
    for slug in slugs:
        upload(baselines, slug, MODELS[slug])
    roles = roles_for(MODELS[slugs[0]])
    if "janus_full" in arms:
        preflight_gpu(baselines, janus_full, roles)
    split, plans = plans_for(baselines, harbor_bridge, task_limit)
    detective = None
    if "janus_full" in arms:
        detective = janus_full.Detective(roles["baseModel"], roles["detectiveAdapter"])
    for slug in slugs:
        LOCAL.slug = slug
        say("START", MODELS[slug]["model"], "pending", pending(baselines, plans, arms), "harbor", workers)
    stalls = 0
    try:
        while True:
            left = 0
            for slug in slugs:
                LOCAL.slug = slug
                left += pending(baselines, plans, arms)
            write_summary(baselines, harbor_bridge)
            if left == 0:
                say("ALL_MODELS_FINISHED")
                return
            before = left
            try:
                one_round(baselines, janus_full, split, plans, arms, slugs, detective, workers)
            except BaseException as exc:
                say("ROUND", type(exc).__name__, str(exc)[:400])
            left = 0
            for slug in slugs:
                LOCAL.slug = slug
                left += pending(baselines, plans, arms)
            write_summary(baselines, harbor_bridge)
            say("LEFT", left)
            if left == 0:
                say("ALL_MODELS_FINISHED")
                return
            if left >= before:
                stalls += 1
                say("STALL", left, stalls)
                time.sleep(min(300, 30 * stalls))
            else:
                stalls = 0
    finally:
        if detective is not None:
            detective.close()


def main():
    load_env()
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    canary = "--canary" in sys.argv
    slugs = ["qwen"] if canary else ["qwen", "glm"]
    arms = ("vanilla",) if canary else ARMS
    task_limit = 1 if canary else None
    workers = 1 if canary else 6
    if "--model" in sys.argv:
        slugs = [sys.argv[sys.argv.index("--model") + 1]]
    if "--arms" in sys.argv:
        arms = tuple(part for part in sys.argv[sys.argv.index("--arms") + 1].split(",") if part)
    if "--workers" in sys.argv:
        workers = int(sys.argv[sys.argv.index("--workers") + 1])
    unknown = [slug for slug in slugs if slug not in MODELS]
    if unknown:
        raise SystemExit("unknown_model")
    run_all(slugs, arms, task_limit, workers)


if __name__ == "__main__":
    main()
