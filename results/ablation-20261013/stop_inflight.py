"""Stop leftover Harbor trial containers. Prints no secrets."""
from __future__ import annotations

import base64
import os
import time

import paramiko


def main():
    ssh = None
    last = None
    for _attempt in range(6):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                os.environ["LIGHTHOUSE_SSH_HOST"],
                port=int(os.environ.get("LIGHTHOUSE_SSH_PORT", "22")),
                username=os.environ.get("LIGHTHOUSE_SSH_USER", "ubuntu"),
                password=os.environ["LIGHTHOUSE_SSH_PASSWORD"],
                timeout=60,
                banner_timeout=60,
                auth_timeout=60,
                allow_agent=False,
                look_for_keys=False,
            )
            ssh = client
            break
        except Exception as exc:
            last = exc
            client.close()
            time.sleep(5)
    if ssh is None:
        raise SystemExit("ssh_failed:" + type(last).__name__)
    script = r"""
import os, signal, subprocess, time
killed = []
for line in os.popen("ps -eo pid=,args=").read().splitlines():
    parts = line.strip().split(None, 1)
    if len(parts) < 2 or "skillflow-ablation-20261013" not in parts[1]:
        continue
    os.kill(int(parts[0]), signal.SIGTERM)
    killed.append(parts[0])
time.sleep(1)
names = subprocess.check_output(["docker", "ps", "--format", "{{.ID}} {{.Names}}"], text=True)
stopped = 0
for line in names.splitlines():
    if "__env-" not in line:
        continue
    cid = line.split()[0]
    subprocess.call(["docker", "kill", cid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    stopped += 1
print("killed", len(killed), "containers", stopped)
"""
    encoded = base64.b64encode(script.encode()).decode()
    command = "python3 -c \"import base64; exec(base64.b64decode('" + encoded + "'))\""
    _stdin, stdout, stderr = ssh.exec_command(command, timeout=60)
    print(stdout.read().decode("utf-8", "replace"))
    err = stderr.read().decode("utf-8", "replace").strip()
    if err:
        print("ERR", err[-300:])
    ssh.close()


if __name__ == "__main__":
    main()
