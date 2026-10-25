"""Freeze the pilot roster, then start tau on benchmark-host-c and bash on benchmark-host-a. Never print secrets."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent
ROOT = "/benchmark/janus-rerun-20261025"
PY = "/benchmark/robustness-prep/venv/bin/python"
ASSIGNMENT = {"benchmark-host-c": "tau", "benchmark-host-a": "bash"}


def lighthouse():
    return os.environ["LIGHTHOUSE_SSH_PASSWORD"]


def secrets_for(host):
    found = []
    for path in Path(os.environ.get("TEMP", ".")).glob("janus_*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        for secret in re.findall(re.escape(host) + r"\"\s*,\s*\"([^\"]+)\"", text):
            if secret not in found and len(secret) >= 12:
                found.append(secret)
    return found


def connect(host):
    secrets = [lighthouse()] if host == "benchmark-host-c" else secrets_for(host)
    last = "auth"
    for secret in secrets:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(host, username="ubuntu", password=secret, timeout=25, banner_timeout=25, auth_timeout=25)
            return client
        except Exception as exc:
            last = type(exc).__name__
            client.close()
    raise SystemExit(host + " " + last)


def remote_python(client, script, timeout):
    stdin, stdout, stderr = client.exec_command("python3 -", timeout=timeout)
    stdin.write(script)
    stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace").strip()
    return out, err


def write_freeze():
    selection = json.loads((HERE / "selection.json").read_text(encoding="utf-8"))
    prompts = {}
    for bench in ("bash", "tau"):
        text = (HERE / selection[bench]["promptFile"]).read_text(encoding="utf-8")
        prompts[bench] = hashlib.sha256(text.encode()).hexdigest()
        selection[bench]["promptSha256"] = prompts[bench]
        selection[bench]["fullAllowed"] = False
    (HERE / "selection.json").write_text(json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    freeze = {
        "frozenBeforeModelCall": True,
        "countableRoot": ROOT,
        "ignoredRoot": "/benchmark/janus-rerun-20261024",
        "orderSha256": selection["orderSha256"],
        "prompts": prompts,
        "pilots": {"bash": selection["bash"]["pilot"], "tau": selection["tau"]["pilot"]},
        "hosts": {"tau": "benchmark-host-c", "bash": "benchmark-host-a"},
        "oneTaskAtATime": True,
        "gates": {"bash": selection["bash"]["gate"], "tau": selection["tau"]["gate"]},
    }
    (HERE / "pilot-freeze.json").write_text(json.dumps(freeze, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return selection


PREP = r"""
import os, pathlib, signal, time, subprocess
root = pathlib.Path("/benchmark/janus-rerun-20261025")
old = pathlib.Path("/benchmark/janus-rerun-20261024")
pids = []
for entry in pathlib.Path("/proc").iterdir():
    if not entry.name.isdigit():
        continue
    try:
        text = (entry / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "replace")
    except OSError:
        continue
    if "remote_one_trial.py" in text or "rerun.py" in text or "trial_entry.py" in text:
        pids.append(int(entry.name))
        print("TERM", entry.name, text[:120])
for pid in pids:
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
if pids:
    time.sleep(1)
listed = subprocess.run(["docker", "ps", "--format", "{{.ID}} {{.Names}}"], text=True, capture_output=True, timeout=30)
for line in listed.stdout.splitlines():
    if not line.strip():
        continue
    cid, name = line.split(" ", 1)
    if "intercode-sql" in name or "mysql" in name.lower():
        print("KEEP", name)
        continue
    if name.startswith("rerun-") or "env-main" in name:
        subprocess.run(["docker", "stop", "-t", "5", cid], text=True, capture_output=True, timeout=40)
        print("STOP", name)
print("OLD_KEEP", old.exists())
print("READY")
"""

LAUNCH = r"""
import os, pathlib, subprocess
root = pathlib.Path("/benchmark/janus-rerun-20261025")
root.joinpath("logs").mkdir(parents=True, exist_ok=True)
bench = "BENCH"
log = root / "logs" / (bench + "-pilot.log")
pid_path = root / "logs" / (bench + "-pilot.pid")
if pid_path.exists():
    pid = pid_path.read_text().strip()
    if pid.isdigit() and pathlib.Path("/proc/" + pid).exists():
        print("ALREADY", bench, pid)
        raise SystemExit(0)
env = os.environ.copy()
env["JANUS_RERUN_ROOT"] = str(root)
proc = subprocess.Popen(
    ["/benchmark/robustness-prep/venv/bin/python", "-u", str(root / "rerun.py"), bench, "pilot", "PROMPT"],
    cwd=str(root),
    env=env,
    stdout=log.open("a", encoding="utf-8"),
    stderr=subprocess.STDOUT,
    start_new_session=True,
)
pid_path.write_text(str(proc.pid))
print("STARTED", bench, proc.pid)
"""


def main():
    selection = write_freeze()
    files = ["rerun.py", "selection.json", "pilot-freeze.json", "prompt-bash.txt", "prompt-tau.txt"]
    for host in ("benchmark-host-d", "benchmark-host-b"):
        print("====", host, "idle", flush=True)
        client = connect(host)
        try:
            out, err = remote_python(client, PREP, 60)
            print(out, flush=True)
            if err:
                print("ERR", err[-200:], flush=True)
        finally:
            client.close()
    for host, bench in ASSIGNMENT.items():
        print("====", host, bench, flush=True)
        client = connect(host)
        try:
            out, err = remote_python(client, PREP, 60)
            print(out, flush=True)
            if err:
                print("ERR", err[-200:], flush=True)
            if "READY" not in out:
                raise SystemExit("not_ready")
            _stdin, stdout, _stderr = client.exec_command("mkdir -p " + ROOT + "/logs")
            stdout.channel.recv_exit_status()
            sftp = client.open_sftp()
            for name in files:
                sftp.put(str(HERE / name), ROOT + "/" + name)
            sftp.close()
            prompt = selection[bench]["promptFile"]
            script = LAUNCH.replace("BENCH", bench).replace("PROMPT", prompt)
            out, err = remote_python(client, script, 30)
            print(out, flush=True)
            if err:
                print("ERR", err[-200:], flush=True)
        finally:
            client.close()


if __name__ == "__main__":
    main()
