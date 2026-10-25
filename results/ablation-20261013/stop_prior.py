"""Stop the unfinished native-contract repair smoke and the official oracle.

Reads SSH settings from the environment. Does not print hosts, passwords, or keys.
"""
from __future__ import annotations

import os
import paramiko


def connect(prefix):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        os.environ[prefix + "_SSH_HOST"],
        port=int(os.environ.get(prefix + "_SSH_PORT", "22")),
        username=os.environ[prefix + "_SSH_USER"],
        password=os.environ[prefix + "_SSH_PASSWORD"],
        timeout=20,
        allow_agent=False,
        look_for_keys=False,
    )
    return client


def run(client, script):
    import base64
    encoded = base64.b64encode(script.encode()).decode()
    command = "python3 -c \"import base64; exec(base64.b64decode('" + encoded + "'))\""
    _stdin, stdout, stderr = client.exec_command(command, timeout=40)
    text = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if code != 0:
        raise RuntimeError("remote_stop_failed:" + err[-180:].replace("\n", " "))
    return text


LIGHT = """
import os, signal
wanted = {952357, 939994}
patterns = ("native-contract-repair-smoke", "official-oracle-", "native-interface-1791897089830181500")
found = []
for line in os.popen("ps -eo pid=,args=").read().splitlines():
    parts = line.strip().split(None, 1)
    if len(parts) < 2:
        continue
    pid = int(parts[0])
    args = parts[1]
    if pid in wanted or any(item in args for item in patterns):
        found.append(pid)
print("lighthouse", len(set(found)))
for pid in sorted(set(found)):
    try:
        os.kill(pid, signal.SIGTERM)
        print("term", pid)
    except OSError:
        print("miss", pid)
"""

GPU = """
import os, signal
patterns = ("skillflow-native-rpc-1791897091558091700", "native-contract-repair-smoke")
found = []
for line in os.popen("ps -eo pid=,args=").read().splitlines():
    parts = line.strip().split(None, 1)
    if len(parts) < 2:
        continue
    pid = int(parts[0])
    if any(item in parts[1] for item in patterns):
        found.append(pid)
print("gpu", len(set(found)))
for pid in sorted(set(found)):
    try:
        os.kill(pid, signal.SIGTERM)
        print("term", pid)
    except OSError:
        print("miss", pid)
"""


def main():
    light = connect("LIGHTHOUSE")
    try:
        print(run(light, LIGHT).strip())
    finally:
        light.close()
    gpu = connect("RDMD")
    try:
        command = "ps -eo pid=,args= | grep -E 'skillflow-native-rpc-1791897091558091700|native-contract-repair-smoke' | grep -v grep || true"
        _stdin, stdout, _stderr = gpu.exec_command(command, timeout=30)
        text = stdout.read().decode("utf-8", "replace")
        stdout.channel.recv_exit_status()
        pids = []
        for line in text.splitlines():
            parts = line.strip().split(None, 1)
            if parts and parts[0].isdigit():
                pids.append(parts[0])
        print("gpu", len(pids))
        if pids:
            _stdin, stdout, _stderr = gpu.exec_command("kill -TERM " + " ".join(pids), timeout=20)
            stdout.channel.recv_exit_status()
            print("term", " ".join(pids))
    finally:
        gpu.close()


if __name__ == "__main__":
    main()
