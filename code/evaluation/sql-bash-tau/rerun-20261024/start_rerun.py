"""Upload the Janus rerun and start it on benchmark-host-a. Never print secrets."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOST = "benchmark-host-a"
REMOTE = "/benchmark/janus-rerun-20261024"

spec = importlib.util.spec_from_file_location(
    "images", str(Path(os.environ.get("TEMP", ".")) / "janus_holdout_images.py")
)
images = importlib.util.module_from_spec(spec)
spec.loader.exec_module(images)


def refresh_hashes():
    selection_path = HERE / "selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    for bench in ("bash", "tau"):
        text = (HERE / selection[bench]["promptFile"]).read_text(encoding="utf-8")
        selection[bench]["promptSha256"] = hashlib.sha256(text.encode()).hexdigest()
    selection_path.write_text(json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return selection


def remote_python(client, script, timeout):
    stdin, stdout, stderr = client.exec_command("python3 -", timeout=timeout)
    stdin.write(script)
    stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace").strip()
    return out, err


def main():
    scopes = sys_scopes()
    selection = refresh_hashes()
    client = images.connect(HOST)
    try:
        out, err = remote_python(client, PREFLIGHT, 40)
        print(out, flush=True)
        if err:
            print("ERR", err[-240:], flush=True)
        if "PROCS 0" not in out or "IDLE_OK" not in out:
            raise SystemExit("host_not_idle")
        if "NL2BASH_OK" not in out or "TAU_OK" not in out:
            raise SystemExit("runtime_missing")
        _stdin, stdout, _stderr = client.exec_command("mkdir -p " + REMOTE + "/logs")
        stdout.channel.recv_exit_status()
        sftp = client.open_sftp()
        for name in ("rerun.py", "selection.json", selection["bash"]["promptFile"], selection["tau"]["promptFile"]):
            sftp.put(str(HERE / name), REMOTE + "/" + name)
        sftp.close()
        launch = LAUNCH.format(scopes=" ".join(scopes))
        out, err = remote_python(client, launch, 30)
        print(out, flush=True)
        if err:
            print("ERR", err[-240:], flush=True)
    finally:
        client.close()


def sys_scopes():
    import sys

    scopes = [item for item in sys.argv[1:] if item in {"pilot", "full"}]
    return scopes or ["pilot"]


PREFLIGHT = r"""
import pathlib
hits = []
for entry in pathlib.Path("/proc").iterdir():
    if not entry.name.isdigit():
        continue
    try:
        text = (entry / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "replace")
    except OSError:
        continue
    if any(token in text for token in ("supervisor.py", "campaign.py", "remote_one_trial", "holdout_baselines")):
        hits.append(text[:160])
print("PROCS", len(hits))
for line in hits:
    print("PROC", line)
if not hits:
    print("IDLE_OK")
images = __import__("os").popen("docker images --format '{{.Repository}}:{{.Tag}}'").read()
print("NL2BASH_OK" if "intercode-nl2bash" in images else "NL2BASH_MISSING")
tau = pathlib.Path("/benchmark/robustness-prep/src/tau-bench-59a200c6d575d595120f1cb70fea53cef0632f6b")
print("TAU_OK" if tau.is_dir() else "TAU_MISSING")
print("MYSQL", __import__("os").popen("docker ps --filter name=intercode-sql-spider_ic_ctr --format '{{.Names}} {{.Status}}'").read().strip())
"""

LAUNCH = r"""
import os, pathlib, subprocess
root = pathlib.Path("/benchmark/janus-rerun-20261024")
selection = __import__("json").loads((root / "selection.json").read_text())
scopes = "{scopes}".split()
py = "/benchmark/robustness-prep/venv/bin/python"
for bench in ("bash", "tau"):
    if selection[bench].get("fullAllowed") is True and "full" in scopes:
        scope = "full"
    else:
        scope = "pilot"
    if scope not in scopes and not (scope == "pilot" and "pilot" in scopes):
        continue
    if scope == "full" and selection[bench].get("fullAllowed") is not True:
        print("SKIP", bench, "gate")
        continue
    log = root / "logs" / (bench + "-" + scope + ".log")
    pid_path = root / "logs" / (bench + "-" + scope + ".pid")
    if pid_path.exists():
        pid = pid_path.read_text().strip()
        if pid.isdigit() and pathlib.Path("/proc/" + pid).exists():
            print("ALREADY", bench, scope, pid)
            continue
    prompt = selection[bench]["promptFile"]
    proc = subprocess.Popen(
        [py, "-u", str(root / "rerun.py"), bench, scope, prompt],
        cwd=str(root),
        stdout=log.open("a", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    pid_path.write_text(str(proc.pid))
    print("STARTED", bench, scope, proc.pid, selection[bench]["promptSha256"][:12])
"""


if __name__ == "__main__":
    main()
