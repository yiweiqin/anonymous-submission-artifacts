"""One method, one benchmark, tasks in the frozen order."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import baseline_updates
from common import (
    ARMS,
    FATAL,
    HERE,
    TB_TASKS,
    WRITERS,
    fatal_reason,
    load_lock,
    load_prompts,
    scrub,
    wait_for_capacity,
    chat,
)

TIMEOUT = {"terminal": 3600, "bash": 1800, "sql": 1200, "tau": 1800}


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def job_name(kind, arm, task, attempt):
    raw = f"{kind}-{arm}-{task}-{attempt}"
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in raw)
    if len(safe) > 70:
        safe = safe[:58] + "-" + hashlib.sha256(raw.encode()).hexdigest()[:8]
    return safe.lower()


def visible(arm, prompts, carry):
    base = prompts["janus"] if arm == "janus" else prompts["vanilla"]
    if arm in WRITERS and str(carry or "").strip():
        return base.rstrip() + "\n\nExperience from earlier tasks:\n" + str(carry).strip() + "\n"
    return base


def preflight(benchmark, ids):
    if benchmark == "terminal":
        missing = [task for task in ids if not (TB_TASKS / task / "instruction.md").is_file()]
        if missing:
            raise SystemExit("missing_task_dir")
    elif benchmark == "bash":
        from bash_one import load_bash

        have = load_bash()
        if any(task not in have for task in ids):
            raise SystemExit("bash_id_mismatch")
    elif benchmark == "sql":
        from sql_one import load_records

        records = load_records()
        if len(records) != 1034:
            raise SystemExit("sql_data_count")
        for task in ids:
            record = records[int(task.split("-")[1])]
            if not record.get("query") or not record.get("db") or not record.get("db_tables"):
                raise SystemExit("sql_record_incomplete")
    elif benchmark == "tau":
        for task in ids:
            domain, index = task.split("-")
            if domain not in {"airline", "retail"}:
                raise SystemExit("tau_id")
            limit = 50 if domain == "airline" else 115
            if not 0 <= int(index) < limit:
                raise SystemExit("tau_id")
    else:
        raise SystemExit("unknown_benchmark")


def read_rows(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_trial(benchmark, task, arm, text, kind, work, attempt):
    name = job_name(kind, arm, task, attempt)
    extra = work / (name + ".txt")
    result = work / (name + ".json")
    extra.write_text(text, encoding="utf-8")
    command = [
        sys.executable,
        str(HERE / "trial_entry.py"),
        benchmark,
        task,
        str(extra),
        str(result),
        name,
        str(work),
    ]
    try:
        subprocess.run(command, cwd=str(HERE), timeout=TIMEOUT[benchmark], check=False)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "ps", "-aq", "--filter", "name=" + name], text=True, capture_output=True, timeout=30)
        listed = subprocess.run(["docker", "ps", "-aq", "--filter", "name=" + name], text=True, capture_output=True, timeout=30)
        ids = [line.strip() for line in (listed.stdout or "").splitlines() if line.strip()]
        if ids:
            subprocess.run(["docker", "rm", "-f", *ids], text=True, capture_output=True, timeout=60)
        return {"reward": None, "error": "timeout", "trace": "", "modelCalls": 0, "promptTokens": 0, "completionTokens": 0, "wallSeconds": TIMEOUT[benchmark]}
    if not result.exists():
        return {"reward": None, "error": "result_missing", "trace": "", "modelCalls": 0, "promptTokens": 0, "completionTokens": 0, "wallSeconds": 0}
    return json.loads(result.read_text(encoding="utf-8"))


def reflect(arm, reward, trace, previous):
    started = time.monotonic()
    prompt = baseline_updates.reflection_prompt(arm, reward, trace, previous)
    try:
        text, usage = chat([{"role": "user", "content": prompt}], 1024)
        return {
            "text": text,
            "error": "",
            "promptTokens": int(usage.get("prompt_tokens") or 0),
            "completionTokens": int(usage.get("completion_tokens") or 0),
            "wallSeconds": round(time.monotonic() - started, 3),
        }
    except Exception as exc:
        return {"text": "", "error": type(exc).__name__ + ":" + scrub(str(exc))[:240], "promptTokens": 0, "completionTokens": 0, "wallSeconds": round(time.monotonic() - started, 3)}


def main():
    benchmark, arm, scope = sys.argv[1:4]
    if arm not in ARMS or scope not in {"pilot", "full"}:
        raise SystemExit("bad_args")
    lock = load_lock()
    prompts = load_prompts()["benchmarks"][benchmark]
    item = lock["benchmarks"][benchmark]
    if scope == "full":
        gate_path = HERE / "gates" / (benchmark + ".json")
        if not gate_path.is_file():
            raise SystemExit("pilot_gate_closed")
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        if gate.get("passed") is not True or gate.get("promptSha256") != prompts["sha256"]:
            raise SystemExit("pilot_gate_closed")
    ids = item["ids"] if scope == "full" else item["pilot"]
    preflight(benchmark, ids)
    work = HERE / "runs" / benchmark / prompts["sha256"] / arm
    work.mkdir(parents=True, exist_ok=True)
    receipts = work / "receipts.jsonl"
    rows = read_rows(receipts)
    done = {row["task"] for row in rows if row.get("official") is True}
    state = baseline_updates.empty_state()
    for row in rows:
        if row.get("official") is True:
            state = baseline_updates.state_from_text(row.get("carry") or "", bool(row.get("truncated")))
    status = work / "status.json"
    for task in ids:
        if task in done:
            continue
        earlier_done = any(previous in done for previous in ids if previous != task and ids.index(previous) < ids.index(task))
        wait_for_capacity()
        carry = baseline_updates.carry_text(state)
        text = visible(arm, prompts, carry)
        payload = None
        infra = 0
        for attempt in range(3):
            print("RUN", benchmark, arm, task, attempt, flush=True)
            payload = run_trial(benchmark, task, arm, text, "official", work, attempt)
            reason = fatal_reason(payload.get("error"))
            if finite(payload.get("reward")) and reason not in FATAL:
                break
            infra += 1
            if reason in FATAL:
                break
            if attempt < 2:
                time.sleep(15 * (attempt + 1))
        reward = payload.get("reward") if finite(payload.get("reward")) else None
        error = "" if reward is not None and fatal_reason(payload.get("error")) not in FATAL else scrub(payload.get("error") or "")
        if reward is None:
            error = error or "no_reward"
        usage = {
            "modelCalls": int(payload.get("modelCalls") or 0),
            "promptTokens": int(payload.get("promptTokens") or 0),
            "completionTokens": int(payload.get("completionTokens") or 0),
            "wallSeconds": float(payload.get("wallSeconds") or 0),
        }
        reply = ""
        reflect_error = ""
        selection = []
        if reward is not None and arm in WRITERS and fatal_reason(error) not in FATAL:
            reflected = reflect(arm, reward, payload.get("trace") or "", carry)
            reply = reflected.get("text") or ""
            reflect_error = reflected.get("error") or ""
            usage["modelCalls"] += 1
            usage["promptTokens"] += int(reflected.get("promptTokens") or 0)
            usage["completionTokens"] += int(reflected.get("completionTokens") or 0)
            usage["wallSeconds"] += float(reflected.get("wallSeconds") or 0)
            if fatal_reason(reflect_error):
                error = fatal_reason(reflect_error)
        if reward is not None and not fatal_reason(error) and arm in WRITERS and arm != "rsea":
            state = baseline_updates.apply_update(arm, state, reward, payload.get("trace") or "", reply)
        elif reward is not None and not fatal_reason(error) and arm == "rsea":
            replay_reward = None
            replay_error = ""
            if earlier_done and reply.strip():
                for attempt in range(3):
                    wait_for_capacity()
                    replay = run_trial(benchmark, task, arm, visible(arm, prompts, reply.strip()), "replay", work, attempt)
                    usage["modelCalls"] += int(replay.get("modelCalls") or 0)
                    usage["promptTokens"] += int(replay.get("promptTokens") or 0)
                    usage["completionTokens"] += int(replay.get("completionTokens") or 0)
                    usage["wallSeconds"] += float(replay.get("wallSeconds") or 0)
                    replay_error = scrub(replay.get("error") or "")
                    if fatal_reason(replay_error) in FATAL:
                        break
                    if finite(replay.get("reward")):
                        replay_reward = replay.get("reward")
                        replay_error = ""
                        break
                    infra += 1
                    if attempt < 2:
                        time.sleep(15 * (attempt + 1))
                if not fatal_reason(error):
                    marked = baseline_updates.official_error_after_replay(replay_error)
                    if marked:
                        error = marked
            kept = baseline_updates.rsea_keep(carry, reply, reward, replay_reward)
            state = baseline_updates.state_from_text(kept, state.get("truncated"))
            selection.append({"task": task, "reward": replay_reward, "kept": kept == reply.strip() and bool(reply.strip()) and replay_reward is not None})
        official = reward is not None
        row = {
            "benchmark": benchmark,
            "arm": arm,
            "task": task,
            "reward": reward,
            "error": error,
            "official": official,
            "infraFailures": infra,
            "carry": baseline_updates.carry_text(state) if official else carry,
            "truncated": bool(state.get("truncated")),
            "modelCalls": usage["modelCalls"],
            "promptTokens": usage["promptTokens"],
            "completionTokens": usage["completionTokens"],
            "wallSeconds": round(usage["wallSeconds"], 3),
            "selectionTrials": selection,
            "reflectError": reflect_error,
            "orderSha256": lock["sha256"],
            "promptSha256": prompts["sha256"],
            "scope": scope,
        }
        with receipts.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        if official:
            done.add(task)
        status.write_text(json.dumps({"phase": "running", "arm": arm, "benchmark": benchmark, "done": len(done), "tasks": len(ids), "last": task, "reward": reward, "error": error}, ensure_ascii=False), encoding="utf-8")
        print("DONE", json.dumps({"arm": arm, "benchmark": benchmark, "task": task, "reward": reward, "error": error, "done": len(done)}, ensure_ascii=False), flush=True)
        if not official or fatal_reason(error):
            status.write_text(json.dumps({"phase": "stopped", "arm": arm, "benchmark": benchmark, "done": len(done), "tasks": len(ids), "last": task, "error": error}, ensure_ascii=False), encoding="utf-8")
            raise SystemExit(error or "no_reward")
    status.write_text(json.dumps({"phase": "complete", "arm": arm, "benchmark": benchmark, "done": len(done), "tasks": len(ids)}, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
