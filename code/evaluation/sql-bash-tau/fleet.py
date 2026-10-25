"""Upload the runner and start one benchmark supervisor on a host."""

from __future__ import annotations

import os
import sys
import tarfile
import tempfile
from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent
REMOTE = "/benchmark/robustness-baselines"
FILES = [
    "baseline_updates.py",
    "bash_one.py",
    "campaign.py",
    "common.py",
    "harbor_one.py",
    "order-lock.json",
    "prompts.json",
    "sql_one.py",
    "supervisor.py",
    "tau_one.py",
    "trial_entry.py",
]


def connect(host):
    password = os.environ["JANUS_SSH_PASSWORD"]
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username="ubuntu", password=password, timeout=30)
    return client


def upload(client):
    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as handle:
        archive = Path(handle.name)
    with tarfile.open(archive, "w") as tar:
        for name in FILES:
            tar.add(HERE / name, arcname=name)
    _stdin, stdout, _stderr = client.exec_command("mkdir -p " + REMOTE)
    stdout.channel.recv_exit_status()
    sftp = client.open_sftp()
    try:
        sftp.put(str(archive), "/tmp/robustness-baselines.tar")
    finally:
        sftp.close()
        archive.unlink(missing_ok=True)
    command = (
        "mkdir -p " + REMOTE +
        " && tar -xf /tmp/robustness-baselines.tar -C " + REMOTE +
        " && rm -f /tmp/robustness-baselines.tar"
    )
    _stdin, stdout, stderr = client.exec_command(command)
    stdout.channel.recv_exit_status()
    err = stderr.read().decode()
    if err.strip():
        raise SystemExit(err[:400])


def start(client, benchmark, scope, follow=""):
    python = "/benchmark/robustness-prep/venv/bin/python"
    log = f"{REMOTE}/logs/{benchmark}-{scope}-supervisor.log"
    pidfile = f"{REMOTE}/logs/{benchmark}-{scope}.pid"
    chain = python + " " + REMOTE + "/supervisor.py " + benchmark + " " + scope
    if follow:
        chain += "; " + python + " " + REMOTE + "/supervisor.py " + follow + " " + scope
    command = (
        "mkdir -p " + REMOTE + "/logs && "
        "if [ -f " + pidfile + " ] && kill -0 $(cat " + pidfile + ") 2>/dev/null; then echo already; else "
        "nohup bash -c " + "'" + chain + "' > " + log + " 2>&1 < /dev/null & echo $! > " + pidfile + "; echo started; fi"
    )
    _stdin, stdout, stderr = client.exec_command(command)
    print(stdout.read().decode().strip())
    err = stderr.read().decode().strip()
    if err:
        print(err[:400])


def main():
    host, benchmark, scope = sys.argv[1:4]
    action = sys.argv[4] if len(sys.argv) > 4 else "start"
    client = connect(host)
    try:
        if action in {"upload", "start"}:
            upload(client)
        if action == "start":
            follow = sys.argv[5] if len(sys.argv) > 5 else ""
            start(client, benchmark, scope, follow)
    finally:
        client.close()


if __name__ == "__main__":
    main()
