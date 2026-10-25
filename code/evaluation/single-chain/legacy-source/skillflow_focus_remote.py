"""Remote-only focused janus_full rerun; credentials arrive through stdin.

Deploy beside an isolated snapshot of skillflow_main_table modules on Lighthouse.
The unchanged run_family body supplies detective, D/S, and replay semantics.
"""
from __future__ import annotations

import inspect
import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parent
HERE = ROOT / "experiments" / "skillflow_main_table"
sys.path.insert(0, str(ROOT / "deps"))
sys.path.insert(0, str(HERE))
import baselines
import harbor_bridge
import janus_full
import preflight

TASKS = {
    "Compensation-Scenario-Modeling": [
        "05_property_management_model", "07_airline_crew_model",
        "08_construction_union_model", "01_orchestra_foundation_model",
        "02_orchestra_archive_refresh_model", "03_university_faculty_model",
        "04_university_termload_refresh_model", "06_property_portfolio_refresh_model",
    ],
    "DMAIC-Quality-Analysis": [
        "harbor_soc_alert_analyze_01", "harbor_hospital_safety_01",
        "harbor_devops_pipeline_02", "harbor_logistics_chain_03", "harbor_gdpval_37",
    ],
    "Weighted-Risk-Assessment": ["weighted-hospital-bedflow-calc"],
}
RUN_ID = ROOT.name
STATUS = ROOT / "status.json"
EVENTS = ROOT / "events.jsonl"
ALLOWED = {(f, t) for f, tasks in TASKS.items() for t in tasks}
STATUS_DATA = {"runId": RUN_ID, "phase": "starting"}
STATUS_LOCK = threading.RLock()


def status(**values):
    with STATUS_LOCK:
        STATUS_DATA.update(values)
        if values.get("family"):
            STATUS_DATA.setdefault("families", {}).setdefault(values["family"], {}).update(values)
        temporary = STATUS.with_suffix(".tmp")
        temporary.write_text(json.dumps(STATUS_DATA, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(STATUS)


def latest(arm, family, task):
    found = None
    for row in baselines.records():
        if (row.get("arm"), row.get("family"), row.get("task")) == (arm, family, task) and baselines.row_done(row):
            found = row
    return found


def already_passed(arm, family, task):
    row = latest(arm, family, task)
    return bool(row and not row.get("error") and harbor_bridge._reward_passed(row.get("reward")))


def disk_check():
    if shutil.disk_usage("/").free < 6 * 1024 ** 3:
        raise SystemExit("harbor_disk_below_6gb")


def local_harbor(family, task, arm, carry, kind):
    if arm != "janus_full" or (family, task) not in ALLOWED:
        raise SystemExit("task_outside_allowlist")
    if already_passed(arm, family, task):
        raise SystemExit("refusing_to_rerun_passed_task")
    disk_check()
    # A unique suffix also protects original jobs if harbor_once retries.
    kind = kind + "-" + str(time.time_ns())
    name = baselines.job_name_for(kind, arm, family, task)
    jobs = Path(baselines.REMOTE_JOBS)
    extra = jobs / (name + ".txt")
    result = jobs / (name + ".json")
    extra.write_text(carry, encoding="utf-8")
    status(phase="harbor", family=family, task=task, jobName=name, carryChars=len(carry), reward=None, error="")
    started = time.monotonic()
    try:
        process = subprocess.run([
            baselines.REMOTE_ROOT + "/SkillFlow/.venv/bin/python",
            str(HERE / "remote_one_trial.py"),
            baselines.REMOTE_TASKS + "/" + family + "/" + task,
            str(jobs), name, str(extra), str(result),
        ], timeout=10800, capture_output=True, text=True)
        payload = json.loads(result.read_text(encoding="utf-8")) if result.is_file() else {
            "reward": None, "error": "no_result", "trace": baselines.scrub(process.stderr[-2000:]),
        }
        payload["exitCode"] = process.returncode
    except subprocess.TimeoutExpired:
        # Stop the run rather than starting another trial over uncertain children.
        raise SystemExit("remote_trial_timeout")
    payload["wallSeconds"] = payload.get("wallSeconds", time.monotonic() - started)
    with STATUS_LOCK:
        with EVENTS.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"kind": kind, "family": family, "task": task, **payload}, ensure_ascii=False) + "\n")
    status(phase="harbor_done", family=family, task=task, jobName=name,
           reward=payload.get("reward"), error=payload.get("error", ""))
    return payload


original_append = baselines.append


def append_valid(row):
    if row.get("reward") is None or row.get("error"):
        status(phase="invalid_result", error=row.get("error") or "null_reward")
        raise SystemExit("invalid_result_not_appended")
    if row.get("arm") != "janus_full" or (row.get("family"), row.get("task")) not in ALLOWED:
        raise SystemExit("append_outside_allowlist")
    if already_passed(row["arm"], row["family"], row["task"]):
        raise SystemExit("refusing_to_replace_passed_score")
    row["focusRunId"] = RUN_ID
    row["kind"] = RUN_ID + "-official"
    original_append(row)
    status(phase="recorded", family=row["family"], task=row["task"], reward=row["reward"], carryChars=len(row.get("carry") or ""))


original_next_carry = harbor_bridge.next_carry
original_one_update = harbor_bridge.one_update
WEIGHTED_ORIGINAL = "Before you submit, confirm the output meets every acceptance condition named in the task."
WEIGHTED_CACHE = WEIGHTED_ORIGINAL + " Recalculate the saved workbook with a spreadsheet engine and reopen it in both formula and value modes to verify that every required formula remains present and its numeric result is populated."
WEIGHTED_CACHE_AUTHORIZED = False


def protected_update(verdict, trace="", family=""):
    if family == "DMAIC-Quality-Analysis":
        # Filter before replay; an incompatible short sentence cannot be retained.
        return ""
    if family == "Weighted-Risk-Assessment":
        if (WEIGHTED_CACHE_AUTHORIZED and harbor_bridge._drift_ready(verdict)
                and "got None" in trace):
            return WEIGHTED_CACHE
        return ""
    return original_one_update(verdict, trace, family)


def protected_carry(previous, verdict, **kwargs):
    proposed = original_next_carry(previous, verdict, **kwargs)
    if kwargs.get("family") == "DMAIC-Quality-Analysis" and proposed != previous:
        return previous  # Preserve the entire existing 515-character check.
    if kwargs.get("family") == "Weighted-Risk-Assessment" and proposed != previous:
        if not (WEIGHTED_CACHE_AUTHORIZED and proposed == WEIGHTED_CACHE
                and harbor_bridge._reward_passed(kwargs.get("replay_reward"))):
            return previous
    return proposed


def main():
    global RUN_ID, STATUS, EVENTS, WEIGHTED_CACHE_AUTHORIZED
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=[f + "/" + t for f, t in sorted(ALLOWED)])
    parser.add_argument("--run-suffix", default="")
    parser.add_argument("--families", nargs="+", choices=list(TASKS))
    parser.add_argument("--workers", type=int, choices=[1, 2, 3], default=1)
    parser.add_argument("--weighted-cache-check", action="store_true")
    args = parser.parse_args()
    WEIGHTED_CACHE_AUTHORIZED = args.weighted_cache_check
    if args.run_suffix:
        if any(not (char.isalnum() or char == "-") for char in args.run_suffix):
            raise SystemExit("invalid_run_suffix")
        RUN_ID += "-" + args.run_suffix
        STATUS = ROOT / ("status-" + args.run_suffix + ".json")
        EVENTS = ROOT / ("events-" + args.run_suffix + ".jsonl")
        STATUS_DATA["runId"] = RUN_ID
    tasks_to_run = TASKS
    if args.task:
        family, task = args.task.split("/", 1)
        tasks_to_run = {family: [task]}
    elif args.families:
        tasks_to_run = {family: TASKS[family] for family in args.families}
    credentials = json.load(sys.stdin)
    os.environ.update(credentials)
    del credentials
    if os.environ.get("JANUS_DUAL_TREE_ADAPTER"):
        raise SystemExit("adapter_bypass_forbidden")
    preflight.load_protocol()
    split = harbor_bridge.load_json(HERE / "family-split.json")
    roles = harbor_bridge.resolved_roles(os.environ)
    baselines.run_harbor = local_harbor
    baselines.finished = already_passed
    baselines.wait_for_disk = disk_check
    baselines.append = append_valid
    harbor_bridge.next_carry = protected_carry
    harbor_bridge.one_update = protected_update
    source = inspect.getsource(janus_full.run_family)
    assert source.count('"janus-replay"') == 1 and source.count('"janus"') >= 1
    source = source.replace('"janus-replay"', repr(RUN_ID + "-replay"))
    source = source.replace('"janus"', repr(RUN_ID + "-official"))
    exec(compile(source, str(HERE / "janus_full.py"), "exec"), janus_full.__dict__)
    for family, tasks in tasks_to_run.items():
        harbor_bridge.assert_janus_request(split, family, "janus_full")
        carry, plan, staff_source = janus_full.restored(family)
        assert staff_source == "ds", "missing_restored_ds_staff"
        expected = {"DMAIC-Quality-Analysis": 515}
        if family in expected:
            assert len(carry) == expected[family], "unexpected_initial_carry"
        elif family == "Weighted-Risk-Assessment" and carry == WEIGHTED_ORIGINAL:
            pass
        elif carry:
            if family == "Weighted-Risk-Assessment":
                assert WEIGHTED_CACHE_AUTHORIZED and carry == WEIGHTED_CACHE, "unauthorized_weighted_carry"
            # A resume must use a sentence actually kept by a passing replay.
            assert any(row.get("arm") == "janus_full" and row.get("family") == family
                       and row.get("carry") == carry
                       and any(item.get("kept") and harbor_bridge._reward_passed(item.get("reward"))
                               and not item.get("error") for item in row.get("selectionTrials", []))
                       for row in baselines.records()), "unvalidated_resumed_carry"
            assert "service should be +1" not in carry and "organization name in Summary" not in carry
        for task in tasks:
            assert (Path(baselines.REMOTE_TASKS) / family / task / "task.toml").is_file()
    detective = janus_full.Detective(roles["baseModel"], roles["detectiveAdapter"])
    stop = threading.Event()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = [pool.submit(janus_full.run_family, split, family, tasks, detective, roles, stop)
                   for family, tasks in tasks_to_run.items()]
        for future in as_completed(pending):
            try:
                future.result()
            except BaseException:
                stop.set()
                raise
    status(phase="complete")


if __name__ == "__main__":
    exit_code = 0
    try:
        main()
    except BaseException as exc:
        exit_code = 1
        status(phase="stopped", error=baselines.scrub(type(exc).__name__ + ": " + str(exc)))
        print(STATUS_DATA["error"], flush=True)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
