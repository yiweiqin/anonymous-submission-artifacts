"""Run the sealed gate and locked families on a new ledger.

The on-disk split and the development ledger stay untouched. This process
only redirects the record path and passes an in-memory list of the twelve
held-out families. lockedMayOpen stays false. janus_full is not started here.
"""
import json
import os
import re
import shlex
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent
MAIN = HERE.parents[2] / "code" / "evaluation" / "skillflow"
sys.path.insert(0, str(MAIN))

import baselines  # noqa: E402
import harbor_bridge  # noqa: E402

def option(name, default=None):
    if name not in sys.argv:
        return default
    return sys.argv[sys.argv.index(name) + 1]


def password_for(host, lighthouse_password):
    if host == "benchmark-host-c":
        return lighthouse_password
    found = []
    for path in Path(os.environ.get("TEMP", ".")).glob("janus_*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        for secret in re.findall(re.escape(host) + r"\"\s*,\s*\"([^\"]+)\"", text):
            if secret not in found:
                found.append(secret)
    for secret in found:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(host, username="ubuntu", password=secret, timeout=20, banner_timeout=20, auth_timeout=20)
        except Exception:
            ssh.close()
            continue
        ssh.close()
        return secret
    raise SystemExit("auth " + host)


def load_env():
    for key in (
        "DEEPSEEK_API_KEY",
        "LIGHTHOUSE_SSH_HOST",
        "LIGHTHOUSE_SSH_USER",
        "LIGHTHOUSE_SSH_PASSWORD",
    ):
        if not os.environ.get(key):
            raise SystemExit("missing " + key)


def holdout_split():
    source = harbor_bridge.load_json(MAIN / "family-split.json")
    if source.get("lockedMayOpen") is not False:
        raise SystemExit("source_split_opened")
    families = list(source["gate"]) + list(source["locked"])
    if len(families) != 12 or len(set(families)) != 12:
        raise SystemExit("holdout_family_count")
    return {
        "lockedMayOpen": False,
        "development": families,
        "gate": [],
        "locked": [],
    }, families


def remote_python(ssh, script, args, timeout):
    python = baselines.REMOTE_ROOT + "/SkillFlow/.venv/bin/python"
    command = " ".join(shlex.quote(part) for part in [python, script, *args])
    return baselines.exec_text(ssh, command, timeout)


def main():
    load_env()
    host = option("--host", os.environ["LIGHTHOUSE_SSH_HOST"])
    os.environ["LIGHTHOUSE_SSH_HOST"] = host
    os.environ["LIGHTHOUSE_SSH_PASSWORD"] = password_for(host, os.environ["LIGHTHOUSE_SSH_PASSWORD"])
    workers = int(option("--workers", "2"))
    record_name = option("--record", "holdout-record.jsonl")
    selected = option("--families")
    selected_arms = option("--arms")
    baselines.remote_python = remote_python
    baselines.RECORD = HERE / record_name
    baselines.ERROR_RECORD = HERE / record_name.replace("record", "errors")
    baselines.ETA = HERE / record_name.replace("record", "eta").replace(".jsonl", ".txt")
    split, families = holdout_split()
    if selected:
        wanted = [name for name in selected.split(",") if name]
        unknown = [name for name in wanted if name not in families]
        if unknown:
            raise SystemExit("unknown_family " + ",".join(unknown))
        families = wanted
        split = dict(split)
        split["development"] = list(wanted)
    arms = list(harbor_bridge.baseline_schedule())
    if selected_arms:
        arms = [arm for arm in selected_arms.split(",") if arm]
        unknown_arms = [arm for arm in arms if arm not in harbor_bridge.baseline_schedule()]
        if unknown_arms:
            raise SystemExit("unknown_arm " + ",".join(unknown_arms))
    ssh = baselines.light_client()
    plans = []
    try:
        baselines.ensure_remote_files(ssh)
        for family in families:
            present, missing = baselines.ranking(ssh, family)
            plans.append((family, present, missing))
            baselines.say("PLAN", family, len(present), "missing", len(missing))
    finally:
        ssh.close()
    label = host.split(".")[0]
    (HERE / ("holdout-plan-" + label + ".json")).write_text(json.dumps({
        "families": families,
        "arms": arms,
        "workers": workers,
        "host": host,
        "counts": {family: len(present) for family, present, _missing in plans},
        "missing": {family: missing for family, _present, missing in plans if missing},
        "record": record_name,
        "forceBuild": True,
        "janusFull": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for family, _present, missing in plans:
        baselines.note_missing(split, family, arms, missing)
    stop = baselines.threading.Event()
    errors = []
    baselines.say("HOLDOUT", host, len(families), "families", len(plans) * len(arms), "chains", "workers", workers)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(baselines.run_arm, split, family, arm, present, baselines.threading.Event())
            for arm in arms
            for family, present, _missing in plans
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except BaseException as exc:
                stop.set()
                errors.append(baselines.scrub(str(exc))[-300:])
    if errors:
        baselines.say("HOLDOUT", "stopped", errors[0])
        raise SystemExit(errors[0])
    baselines.say("HOLDOUT", "chains finished")


if __name__ == "__main__":
    main()
