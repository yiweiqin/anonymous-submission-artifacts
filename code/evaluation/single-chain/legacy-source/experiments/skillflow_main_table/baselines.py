"""Run vanilla and the six SkillFlow baselines on development families.

Secrets stay in the environment. This does not change protocol.json, and it
does not schedule janus_full, gate, or locked.
"""

from __future__ import annotations

import json
import os
import shlex
import socket
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import baseline_updates
import harbor_bridge

REMOTE_ROOT = "/benchmark/skillflow-main-20261008"
REMOTE_TASKS = REMOTE_ROOT + "/SkillFlow/test_tasks"
REMOTE_JOBS = REMOTE_ROOT + "/baseline-jobs"
REMOTE_TRIAL = REMOTE_ROOT + "/remote_one_trial.py"
REMOTE_REFLECT = REMOTE_ROOT + "/remote_reflect.py"
REMOTE_KEY = REMOTE_ROOT + "/.secrets/deepseek.key"
RECORD = HERE / "baseline-record.jsonl"
ETA = HERE / "baseline-eta.txt"
RECORD_LOCK = threading.Lock()
PRINT_LOCK = threading.Lock()


def client(host, port, user, password):
    last = None
    for _ in range(4):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(host, port=int(port), username=user, password=password,
                        timeout=40, banner_timeout=40, auth_timeout=40)
            return ssh
        except Exception as exc:
            last = exc
            ssh.close()
    raise last


def light_client():
    return client(
        os.environ["LIGHTHOUSE_SSH_HOST"], 22,
        os.environ.get("LIGHTHOUSE_SSH_USER", "ubuntu"),
        os.environ["LIGHTHOUSE_SSH_PASSWORD"],
    )


def exec_text(ssh, command, timeout):
    """Drain both streams so a finished remote command cannot leave the channel open."""
    transport = ssh.get_transport()
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
        try:
            if channel.recv_ready():
                out.extend(channel.recv(65536))
            if channel.recv_stderr_ready():
                err.extend(channel.recv_stderr(65536))
        except socket.timeout:
            pass
        if channel.exit_status_ready():
            while channel.recv_ready():
                out.extend(channel.recv(65536))
            while channel.recv_stderr_ready():
                err.extend(channel.recv_stderr(65536))
            code = channel.recv_exit_status()
            return code, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")
        time.sleep(0.2)


def upload(sftp, local, remote):
    sftp.put(str(local), remote)


def ensure_remote_files(ssh):
    code, _out, err = exec_text(
        ssh,
        "mkdir -p " + REMOTE_ROOT + "/.secrets " + REMOTE_JOBS + " && chmod 700 " + REMOTE_ROOT + "/.secrets",
        30,
    )
    if code != 0:
        raise RuntimeError(err[-400:])
    sftp = ssh.open_sftp()
    upload(sftp, HERE / "remote_one_trial.py", REMOTE_TRIAL)
    upload(sftp, HERE / "remote_reflect.py", REMOTE_REFLECT)
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise RuntimeError("missing_api_key")
    with sftp.file(REMOTE_KEY, "w") as handle:
        handle.write(key + "\n")
    sftp.chmod(REMOTE_KEY, 0o600)
    sftp.close()


def ranking(ssh, family):
    sftp = ssh.open_sftp()
    with sftp.open(REMOTE_TASKS + "/" + family + "/ALL_TASK_DIFFICULTY_RANKING.json") as handle:
        names = harbor_bridge.ranking_names(json.loads(handle.read().decode("utf-8")))
    present = []
    missing = []
    for name in names:
        try:
            sftp.stat(REMOTE_TASKS + "/" + family + "/" + name + "/task.toml")
        except OSError:
            missing.append(name)
        else:
            present.append(name)
    sftp.close()
    return present, missing


def say(*parts):
    with PRINT_LOCK:
        print(*parts, flush=True)


def records():
    with RECORD_LOCK:
        if not RECORD.is_file():
            return []
        rows = []
        for line in RECORD.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows


def row_done(row):
    if row.get("error") == "missing_task_dir":
        return True
    return row.get("reward") is not None and not row.get("error")


def finished(arm, family, task):
    for row in records():
        if row.get("arm") == arm and row.get("family") == family and row.get("task") == task:
            if row_done(row):
                return True
    return False


def restored_state(arm, family):
    text = ""
    truncated = False
    for row in records():
        if row.get("arm") == arm and row.get("family") == family and row_done(row):
            if row.get("error") == "missing_task_dir":
                continue
            text = row.get("carry") or ""
            truncated = bool(row.get("truncated"))
    return baseline_updates.state_from_text(text, truncated)


def scrub(text):
    value = str(text or "")
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        value = value.replace(key, "[redacted]")
    return value


def append(row):
    with RECORD_LOCK:
        with RECORD.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def job_name_for(kind, arm, family, task):
    raw = kind + "-" + arm + "-" + family + "-" + task
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in raw)[:180]


def remote_python(ssh, script, args, timeout):
    python = REMOTE_ROOT + "/SkillFlow/.venv/bin/python"
    command = " ".join(shlex.quote(part) for part in [python, script, *args])
    return exec_text(ssh, command, timeout)


def read_json(ssh, remote):
    sftp = ssh.open_sftp()
    try:
        with sftp.open(remote) as handle:
            payload = json.loads(handle.read().decode("utf-8"))
    except OSError:
        payload = {"reward": None, "error": "no_result", "trace": ""}
    sftp.close()
    return payload


def run_harbor(family, task, arm, carry, kind):
    ssh = light_client()
    try:
        name = job_name_for(kind, arm, family, task)
        extra_remote = REMOTE_JOBS + "/" + name + ".txt"
        result_remote = REMOTE_JOBS + "/" + name + ".json"
        sftp = ssh.open_sftp()
        with sftp.file(extra_remote, "w") as handle:
            handle.write(carry)
        sftp.close()
        try:
            code, out, err = remote_python(ssh, REMOTE_TRIAL, [
                REMOTE_TASKS + "/" + family + "/" + task,
                REMOTE_JOBS,
                name,
                extra_remote,
                result_remote,
            ], 10800)
        except Exception as exc:
            code, out, err = 1, "", type(exc).__name__ + ": " + str(exc)
        try:
            payload = read_json(ssh, result_remote)
        except Exception:
            ssh.close()
            ssh = light_client()
            payload = read_json(ssh, result_remote)
        if payload.get("error") == "no_result":
            payload["trace"] = (out + "\n" + err)[-2000:]
        payload["exitCode"] = code
        return payload
    finally:
        ssh.close()


def reflect(arm, family, task, reward, trace, previous):
    prompt = baseline_updates.reflection_prompt(arm, reward, trace, previous)
    ssh = light_client()
    try:
        slug = job_name_for("reflect", arm, family, task)
        prompt_remote = REMOTE_JOBS + "/" + slug + ".txt"
        result_remote = REMOTE_JOBS + "/" + slug + ".json"
        sftp = ssh.open_sftp()
        with sftp.file(prompt_remote, "w") as handle:
            handle.write(prompt)
        sftp.close()
        started = time.monotonic()
        _code, out, err = remote_python(ssh, REMOTE_REFLECT, [prompt_remote, result_remote], 240)
        payload = read_json(ssh, result_remote)
        payload["wallSeconds"] = round(time.monotonic() - started, 3)
        if not payload.get("text") and payload.get("error") == "no_result":
            payload["error"] = (out + "\n" + err)[-400:]
        return payload
    finally:
        ssh.close()


def add_usage(total, part):
    total["modelCalls"] += int(part.get("modelCalls") or 0)
    total["promptTokens"] += int(part.get("promptTokens") or 0)
    total["completionTokens"] += int(part.get("completionTokens") or 0)
    total["wallSeconds"] += float(part.get("wallSeconds") or 0)


def expected_trials(counts):
    official = sum(counts) * len(harbor_bridge.baseline_schedule())
    extra = sum(max(0, count - 1) for count in counts)
    return official + extra


def write_eta(family_counts):
    done_wall = 0.0
    done_trials = 0
    for row in records():
        if row.get("error") == "missing_task_dir":
            continue
        done_wall += float(row.get("wallSeconds") or 0)
        done_trials += int(row.get("harborTrials") or 0)
    remaining = expected_trials(family_counts) - done_trials
    if done_trials <= 0:
        return
    mean = done_wall / done_trials
    hours = remaining * mean / 3600
    text = (
        "已完成 Harbor %d 次，平均 %.1f 分钟。"
        "剩余约 %d 次，预计还要 %.1f 小时（%.1f 天）。"
        % (done_trials, mean / 60, max(0, remaining), max(0, hours), max(0, hours) / 24)
    )
    ETA.write_text(text + "\n", encoding="utf-8")
    say("ETA " + text)


def disk_ok(ssh):
    code, out, _err = exec_text(ssh, "df -B1 --output=avail / | tail -1", 30)
    if code != 0:
        return True
    try:
        return int(out.strip()) >= 6 * 1024 ** 3
    except ValueError:
        return True


def wait_for_disk():
    for _ in range(40):
        ssh = light_client()
        try:
            if disk_ok(ssh):
                return
        finally:
            ssh.close()
        time.sleep(15)
    raise SystemExit("No space left on device")


def note_missing(split, family, arms, missing):
    for name in missing:
        for arm in arms:
            harbor_bridge.assert_baseline_request(split, family, arm)
            if finished(arm, family, name):
                say("SKIP", arm, family, name)
                continue
            append({
                "arm": arm,
                "family": family,
                "task": name,
                "reward": None,
                "error": "missing_task_dir",
                "carry": "",
                "truncated": False,
                "taskModel": harbor_bridge.TASK_MODEL,
                "modelCalls": 0,
                "promptTokens": 0,
                "completionTokens": 0,
                "wallSeconds": 0,
                "harborTrials": 0,
                "selectionTrials": [],
            })
            say("MISSING", arm, family, name)


def run_arm(split, family, arm, tasks, stop):
    """One arm stays in ranking order. Other arms and families run beside it."""
    harbor_bridge.assert_baseline_request(split, family, arm)
    state = restored_state(arm, family)
    earlier_done = False
    for task in tasks:
        if stop.is_set():
            return
        if finished(arm, family, task):
            earlier_done = True
            say("SKIP", arm, family, task)
            continue
        say("RUN", arm, family, task)
        wait_for_disk()
        carry = baseline_updates.carry_text(state)
        payload = None
        for attempt in range(3):
            payload = run_harbor(family, task, arm, carry, "baseline")
            trial_error = scrub(payload.get("error") or "")
            reason = harbor_bridge.fatal_reason(trial_error)
            if payload.get("reward") is not None and reason not in {
                "Missing credentials", "No space left", "missing_api_key",
            }:
                break
            if reason in {"Missing credentials", "No space left", "missing_api_key"}:
                break
            if attempt < 2:
                say("RETRY", arm, family, task, attempt + 1)
                time.sleep(15 * (attempt + 1))
        usage = {
            "modelCalls": 0,
            "promptTokens": 0,
            "completionTokens": 0,
            "wallSeconds": 0,
        }
        add_usage(usage, payload)
        harbor_trials = 1
        selection = []
        error = scrub(payload.get("error") or "")
        reward = payload.get("reward")
        reply = ""
        reflect_error = ""
        if reward is not None and not error and arm != "vanilla":
            reflected = reflect(arm, family, task, reward, scrub(payload.get("trace") or ""), carry)
            reply = scrub(reflected.get("text") or "")
            add_usage(usage, {
                "modelCalls": 1,
                "promptTokens": reflected.get("promptTokens") or 0,
                "completionTokens": reflected.get("completionTokens") or 0,
                "wallSeconds": reflected.get("wallSeconds") or 0,
            })
            reflect_error = scrub(reflected.get("error") or "")
            if harbor_bridge.fatal_reason(reflect_error):
                error = reflect_error
        if arm == "vanilla" or reward is None or error:
            pass
        elif arm == "rsea":
            replay_reward = None
            replay_error = ""
            if earlier_done and reply.strip():
                for attempt in range(3):
                    wait_for_disk()
                    replay = run_harbor(family, task, arm, reply.strip(), "baseline-replay")
                    replay_reward = replay.get("reward")
                    add_usage(usage, replay)
                    harbor_trials += 1
                    replay_error = scrub(replay.get("error") or "")
                    reason = harbor_bridge.fatal_reason(replay_error)
                    if reason in {"Missing credentials", "No space left", "missing_api_key"}:
                        break
                    if replay_reward is not None:
                        replay_error = ""
                        break
                    if attempt < 2:
                        say("RETRY", arm, family, task, "replay", attempt + 1)
                        time.sleep(15 * (attempt + 1))
                if not error:
                    error = baseline_updates.official_error_after_replay(replay_error)
            kept = baseline_updates.rsea_keep(carry, reply, reward, replay_reward)
            state = baseline_updates.state_from_text(kept, state.get("truncated"))
            selection.append({
                "task": task,
                "reward": replay_reward,
                "kept": kept == reply.strip() and bool(reply.strip()) and replay_reward is not None,
                "error": "" if replay_reward is not None else replay_error[-200:],
            })
        else:
            state = baseline_updates.apply_update(arm, state, reward, scrub(payload.get("trace") or ""), reply)
        earlier_done = True
        row = {
            "arm": arm,
            "family": family,
            "task": task,
            "reward": reward,
            "error": error,
            "carry": baseline_updates.carry_text(state),
            "truncated": bool(state.get("truncated")),
            "taskModel": harbor_bridge.TASK_MODEL,
            "modelCalls": usage["modelCalls"],
            "promptTokens": usage["promptTokens"],
            "completionTokens": usage["completionTokens"],
            "wallSeconds": round(usage["wallSeconds"], 3),
            "harborTrials": harbor_trials,
            "selectionTrials": selection,
            "reflectError": reflect_error,
        }
        append(row)
        say("DONE", json.dumps({
            "arm": arm,
            "family": family,
            "task": task,
            "reward": reward,
            "error": error,
            "carryChars": len(row["carry"]),
            "wallSeconds": row["wallSeconds"],
        }, ensure_ascii=False))
        reason = harbor_bridge.fatal_reason(error)
        if reason or reward is None:
            stop.set()
            raise SystemExit(reason or error or "no_reward")


def worker_count(smoke):
    if smoke:
        return 1
    if "--workers" in sys.argv:
        index = sys.argv.index("--workers")
        return max(1, int(sys.argv[index + 1]))
    return 4


def main():
    smoke = "--smoke" in sys.argv
    split = harbor_bridge.load_json(HERE / "family-split.json")
    if split.get("lockedMayOpen") is not False:
        raise SystemExit("locked_split_opened")
    families = list(split["development"])
    arms = list(harbor_bridge.baseline_schedule())
    task_limit = None
    workers = worker_count(smoke)
    if smoke:
        families = families[:1]
        arms = ["vanilla", "expel"]
        task_limit = 1
    say("WORKERS", workers)
    counts = []
    plans = []
    ssh = light_client()
    try:
        ensure_remote_files(ssh)
        for family in families:
            present, missing = ranking(ssh, family)
            if task_limit is not None:
                present = present[:task_limit]
            plans.append((family, present, missing))
            counts.append(len(present))
    finally:
        ssh.close()
    for family, _present, missing in plans:
        note_missing(split, family, arms, missing)
    stop = threading.Event()
    errors = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(run_arm, split, family, arm, present, stop)
            for family, present, _missing in plans
            for arm in arms
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except BaseException as exc:
                stop.set()
                errors.append(exc)
    if not smoke and not errors:
        write_eta(counts)
        import lift_table
        lift_table.main()
    if errors:
        raise SystemExit(str(errors[0]))


if __name__ == "__main__":
    main()
