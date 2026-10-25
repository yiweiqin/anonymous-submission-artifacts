"""List Harbor ablation trials. Stop only those older than the current runner."""
from __future__ import annotations

import os
import paramiko

MAX_AGE = 180


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        os.environ["LIGHTHOUSE_SSH_HOST"], port=int(os.environ.get("LIGHTHOUSE_SSH_PORT", "22")),
        username=os.environ["LIGHTHOUSE_SSH_USER"], password=os.environ["LIGHTHOUSE_SSH_PASSWORD"],
        timeout=20, allow_agent=False, look_for_keys=False,
    )
    script = r"""
import os, time
now = time.time()
rows = []
for line in os.popen("ps -eo pid=,etimes=,args=").read().splitlines():
    parts = line.split(None, 2)
    if len(parts) < 3 or "skillflow-ablation-20261013" not in parts[2]:
        continue
    pid, age = int(parts[0]), int(parts[1])
    name = parts[2].split("skillflow-ablation-20261013")[-1][:80]
    rows.append((pid, age, name))
print("alive", len(rows))
for pid, age, name in rows:
    print(pid, age, name)
"""
    import base64
    encoded = base64.b64encode(script.encode()).decode()
    _stdin, stdout, stderr = client.exec_command(
        "python3 -c \"import base64; exec(base64.b64decode('" + encoded + "'))\"", timeout=30)
    text = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    client.close()
    print(text)
    if code != 0:
        print("probe_failed", err[-200:])


if __name__ == "__main__":
    main()
