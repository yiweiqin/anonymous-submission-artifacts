"""Run the SkillFlow canary: two development families, vanilla and janus_full.

Secrets stay in the environment. This does not change protocol.json.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harbor_bridge

REMOTE_ROOT = "/benchmark/skillflow-main-20261008"
REMOTE_TASKS = REMOTE_ROOT + "/SkillFlow/test_tasks"
REMOTE_JOBS = REMOTE_ROOT + "/canary-jobs"
REMOTE_TRIAL = REMOTE_ROOT + "/remote_one_trial.py"
REMOTE_KEY = REMOTE_ROOT + "/.secrets/deepseek.key"
GPU_DIR = "/data/modelstore/skillflow-canary"
GPU_PYTHON = "/data/modelstore/rdmd-env/bin/python"
GPU_MODEL = "Qwen/Qwen3-8B"
RECORD = HERE / "canary-record.jsonl"


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


def exec_text(ssh, command, timeout):
    _stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def upload(sftp, local, remote):
    sftp.put(str(local), remote)


def gpu_client():
    return client(
        os.environ["RDMD_SSH_HOST"], int(os.environ["RDMD_SSH_PORT"]),
        os.environ.get("RDMD_SSH_USER", "root"),
        os.environ["RDMD_SSH_PASSWORD"],
    )


def ensure_remote_files(light, gpu):
    code, _out, err = exec_text(
        light,
        "mkdir -p " + REMOTE_ROOT + "/.secrets " + REMOTE_JOBS + " && chmod 700 " + REMOTE_ROOT + "/.secrets",
        30,
    )
    if code != 0:
        raise RuntimeError(err[-400:])
    sftp = light.open_sftp()
    upload(sftp, HERE / "remote_one_trial.py", REMOTE_TRIAL)
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")
    with sftp.file(REMOTE_KEY, "w") as handle:
        handle.write(key + "\n")
    sftp.chmod(REMOTE_KEY, 0o600)
    sftp.close()
    if gpu is not None:
        code, _out, err = exec_text(gpu, "mkdir -p " + GPU_DIR, 30)
        if code != 0:
            raise RuntimeError(err[-400:])
        detective = HERE.parent / "detective-deploy"
        gsftp = gpu.open_sftp()
        upload(gsftp, detective / "predict.py", GPU_DIR + "/predict.py")
        upload(gsftp, detective / "rdmd_detective.py", GPU_DIR + "/rdmd_detective.py")
        gsftp.close()


def ranking(light, family):
    sftp = light.open_sftp()
    with sftp.open(REMOTE_TASKS + "/" + family + "/ALL_TASK_DIFFICULTY_RANKING.json") as handle:
        names = harbor_bridge.ranking_names(json.loads(handle.read().decode("utf-8")))
    sftp.close()
    return names


def finished(arm, family, task):
    if not RECORD.is_file():
        return False
    for line in RECORD.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("arm") == arm and row.get("family") == family and row.get("task") == task:
            if row.get("reward") is not None and not row.get("error"):
                return True
    return False


def scrub(text):
    value = str(text or "")
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        value = value.replace(key, "[redacted]")
    return value


def append(row):
    with RECORD.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_trial(light, family, task, arm, carry):
    job_name = "canary-" + arm + "-" + family + "-" + task
    job_name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in job_name)[:180]
    extra_remote = REMOTE_JOBS + "/" + job_name + ".txt"
    result_remote = REMOTE_JOBS + "/" + job_name + ".json"
    sftp = light.open_sftp()
    with sftp.file(extra_remote, "w") as handle:
        handle.write(carry)
    sftp.close()
    python = REMOTE_ROOT + "/SkillFlow/.venv/bin/python"
    command = " ".join([
        python, REMOTE_TRIAL,
        REMOTE_TASKS + "/" + family + "/" + task,
        REMOTE_JOBS,
        job_name,
        extra_remote,
        result_remote,
    ])
    code, out, err = exec_text(light, command, 7200)
    sftp = light.open_sftp()
    try:
        with sftp.open(result_remote) as handle:
            payload = json.loads(handle.read().decode("utf-8"))
    except OSError:
        payload = {"reward": None, "error": "no_result", "trace": (out + "\n" + err)[-2000:]}
    sftp.close()
    payload["exitCode"] = code
    return payload


def ask_detective(gpu, case, adapter):
    local_case = HERE / "_canary_case.json"
    local_out = HERE / "_canary_verdict.jsonl"
    local_case.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
    sftp = gpu.open_sftp()
    upload(sftp, local_case, GPU_DIR + "/case.json")
    sftp.close()
    local_case.unlink(missing_ok=True)
    command = " ".join([
        GPU_PYTHON, GPU_DIR + "/predict.py",
        "--input", GPU_DIR + "/case.json",
        "--output", GPU_DIR + "/verdict.jsonl",
        "--model", GPU_MODEL,
        "--adapter", adapter,
        "--device", "cuda:0",
    ])
    code, out, err = exec_text(gpu, command, 1800)
    sftp = gpu.open_sftp()
    try:
        with sftp.open(GPU_DIR + "/verdict.jsonl") as handle:
            text = handle.read().decode("utf-8")
    except OSError:
        text = ""
    sftp.close()
    local_out.unlink(missing_ok=True)
    if not text.strip():
        return {"status": "UNKNOWN", "valid": False, "warnings": ["detective_empty"], "stderr": err[-400:]}
    row = json.loads(text.splitlines()[-1])
    verdict = dict(row.get("verdict") or {})
    verdict["valid"] = row.get("valid")
    verdict["warnings"] = row.get("warnings") or []
    verdict["exitCode"] = code
    return verdict


def main():
    split = harbor_bridge.load_json(HERE / "family-split.json")
    families = harbor_bridge.canary_families(split)
    light = client(
        os.environ["LIGHTHOUSE_SSH_HOST"], 22,
        os.environ.get("LIGHTHOUSE_SSH_USER", "ubuntu"),
        os.environ["LIGHTHOUSE_SSH_PASSWORD"],
    )
    gpu = None
    try:
        ensure_remote_files(light, None)
        roles = harbor_bridge.resolved_roles(os.environ)
        arms = harbor_bridge.scheduled_arms(roles["detectiveAdapter"])
        for arm in arms:
            for family in families:
                harbor_bridge.assert_canary_request(split, family, arm)
                carry = ""
                plan = harbor_bridge.staff_plan(family)
                for task in ranking(light, family):
                    if finished(arm, family, task):
                        print("SKIP", arm, family, task, flush=True)
                        continue
                    print("RUN", arm, family, task, flush=True)
                    payload = run_trial(light, family, task, arm, carry if arm == "janus_full" else "")
                    payload["error"] = scrub(payload.get("error") or "")
                    payload["trace"] = scrub(payload.get("trace") or "")
                    verdict = {"status": "not_called"}
                    if arm == "janus_full" and payload.get("reward") is not None and not payload.get("error"):
                        if gpu is None:
                            gpu = gpu_client()
                            ensure_remote_files(light, gpu)
                        reward = 1 if float(payload["reward"]) >= 1 else 0
                        execution = harbor_bridge.execution_graph(plan, reward, payload.get("trace") or "")
                        case = harbor_bridge.detective_case(family + "/" + task, plan, execution)
                        verdict = ask_detective(gpu, case, roles["detectiveAdapter"])
                        carry = harbor_bridge.next_carry(carry, verdict)
                        plan = harbor_bridge.apply_replacement(plan, verdict)
                    row = {
                        "arm": arm,
                        "family": family,
                        "task": task,
                        "reward": payload.get("reward"),
                        "error": payload.get("error") or "",
                        "carry": carry if arm == "janus_full" else "",
                        "verdictStatus": verdict.get("status"),
                        "taskModel": roles["taskModel"],
                        "detective": roles["detectiveAdapter"],
                        "dependencySimilarity": roles["dsAdapter"],
                    }
                    append(row)
                    print("DONE", json.dumps(row, ensure_ascii=False), flush=True)
                    if "Docker compose" in row["error"] or "unknown flag" in row["error"]:
                        raise SystemExit(1)
    finally:
        light.close()
        if gpu is not None:
            gpu.close()


if __name__ == "__main__":
    main()
