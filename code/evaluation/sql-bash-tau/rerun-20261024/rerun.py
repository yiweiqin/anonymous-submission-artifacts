"""Janus-only rerun. Writes under /benchmark/janus-rerun-20261024 and nowhere else."""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("JANUS_RERUN_ROOT", "/benchmark/janus-rerun-20261025"))
OLD = Path("/benchmark/robustness-baselines")
PY = "/benchmark/robustness-prep/venv/bin/python"
TIMEOUT = {"bash": 1800, "tau": 1800}

sys.path.insert(0, str(OLD))
from common import fatal_reason, scrub, wait_for_capacity  # noqa: E402


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def job_name(bench, task, attempt, digest=""):
    tag = (digest or "")[:8]
    raw = f"rerun-{tag}-{bench}-{task}-{attempt}" if tag else f"rerun-{bench}-{task}-{attempt}"
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in raw)
    if len(safe) > 70:
        safe = safe[:58] + "-" + hashlib.sha256(raw.encode()).hexdigest()[:8]
    return safe.lower()


def read_rows(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_trial(bench, task, text, work, attempt, digest):
    name = job_name(bench, task, attempt, digest)
    extra = work / (name + ".txt")
    result = work / (name + ".json")
    extra.write_text(text, encoding="utf-8")
    command = [PY, str(OLD / "trial_entry.py"), bench, task, str(extra), str(result), name, str(work)]
    try:
        subprocess.run(command, cwd=str(OLD), timeout=TIMEOUT[bench], check=False)
    except subprocess.TimeoutExpired:
        listed = subprocess.run(
            ["docker", "ps", "-aq", "--filter", "name=" + name],
            text=True,
            capture_output=True,
            timeout=30,
        )
        ids = [line.strip() for line in (listed.stdout or "").splitlines() if line.strip()]
        if ids:
            subprocess.run(["docker", "rm", "-f", *ids], text=True, capture_output=True, timeout=60)
        return {"reward": None, "error": "timeout", "modelCalls": 0, "promptTokens": 0, "completionTokens": 0, "wallSeconds": TIMEOUT[bench]}
    if not result.exists():
        return {"reward": None, "error": "result_missing", "modelCalls": 0, "promptTokens": 0, "completionTokens": 0, "wallSeconds": 0}
    return json.loads(result.read_text(encoding="utf-8"))


def main():
    bench, scope, prompt_name = sys.argv[1:4]
    if bench not in {"bash", "tau"} or scope not in {"pilot", "full"}:
        raise SystemExit("bad_args")
    selection = json.loads((ROOT / "selection.json").read_text(encoding="utf-8"))
    lock = json.loads((OLD / "order-lock.json").read_text(encoding="utf-8"))
    if lock.get("sha256") != selection["orderSha256"]:
        raise SystemExit("order_hash")
    if scope == "full" and selection[bench].get("fullAllowed") is not True:
        raise SystemExit("pilot_gate_closed")
    ids_all = lock["benchmarks"][bench]["ids"]
    ids = list(ids_all) if scope == "full" else list(selection[bench]["pilot"])
    if [task for task in ids if task not in ids_all]:
        raise SystemExit("unknown_task")
    if ids != sorted(ids, key=ids_all.index):
        raise SystemExit("order")
    shard = os.environ.get("JANUS_SHARD", "")
    shards = os.environ.get("JANUS_SHARDS", "")
    if scope == "full" and shard.isdigit() and shards.isdigit():
        width = int(shards)
        which = int(shard)
        if width < 1 or not 0 <= which < width:
            raise SystemExit("shard")
        ids = [task for index, task in enumerate(ids) if index % width == which]
    prompt_path = ROOT / prompt_name
    prompt = prompt_path.read_text(encoding="utf-8")
    digest = hashlib.sha256(prompt.encode()).hexdigest()
    if digest != selection[bench]["promptSha256"]:
        raise SystemExit("prompt_hash")
    freeze_path = ROOT / "pilot-freeze.json"
    if not freeze_path.is_file():
        raise SystemExit("pilot_not_frozen")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze["prompts"][bench] != digest:
        raise SystemExit("freeze_hash")
    if scope == "pilot" and freeze["pilots"][bench] != ids:
        raise SystemExit("freeze_ids")
    work = ROOT / "runs" / bench / digest / scope / "janus"
    work.mkdir(parents=True, exist_ok=True)
    receipts = work / "receipts.jsonl"
    done = {row["task"] for row in read_rows(receipts) if row.get("official") is True}
    status = work / "status.json"
    for task in ids:
        if task in done:
            continue
        wait_for_capacity()
        payload = None
        infra = 0
        for attempt in range(3):
            print("RUN", bench, scope, task, attempt, flush=True)
            payload = run_trial(bench, task, prompt, work, attempt, digest)
            reason = fatal_reason(payload.get("error"))
            if finite(payload.get("reward")) and reason not in {"Missing credentials", "No space left", "missing_api_key"}:
                break
            infra += 1
            if reason in {"Missing credentials", "No space left", "missing_api_key"}:
                break
            if attempt < 2:
                time.sleep(15 * (attempt + 1))
        reward = payload.get("reward") if finite(payload.get("reward")) else None
        error = "" if reward is not None else scrub(payload.get("error") or "") or "no_reward"
        row = {
            "benchmark": bench,
            "arm": "janus",
            "task": task,
            "reward": reward,
            "error": error,
            "official": reward is not None,
            "infraFailures": infra,
            "modelCalls": int(payload.get("modelCalls") or 0),
            "promptTokens": int(payload.get("promptTokens") or 0),
            "completionTokens": int(payload.get("completionTokens") or 0),
            "wallSeconds": round(float(payload.get("wallSeconds") or 0), 3),
            "orderSha256": lock["sha256"],
            "promptSha256": digest,
            "scope": scope,
        }
        with receipts.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        if reward is not None:
            done.add(task)
        status.write_text(
            json.dumps(
                {"phase": "running", "benchmark": bench, "scope": scope, "done": len(done), "tasks": len(ids), "last": task, "reward": reward, "error": error},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print("DONE", json.dumps({"benchmark": bench, "task": task, "reward": reward, "error": error, "done": len(done)}, ensure_ascii=False), flush=True)
        if fatal_reason(error) in {"Missing credentials", "No space left", "missing_api_key"}:
            status.write_text(
                json.dumps({"phase": "stopped", "benchmark": bench, "scope": scope, "done": len(done), "tasks": len(ids), "last": task, "error": error}, ensure_ascii=False),
                encoding="utf-8",
            )
            raise SystemExit(error)
    status.write_text(
        json.dumps({"phase": "complete", "benchmark": bench, "scope": scope, "done": len(done), "tasks": len(ids)}, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
