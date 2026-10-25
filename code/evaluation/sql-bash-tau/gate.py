"""Score the 8-task gate.

A cohort passes when Janus is strictly above every other method, or when
Janus is tied at the maximum score of 8. Any lower tie does not pass.
"""

from __future__ import annotations

import json
from pathlib import Path

from common import ARMS, HERE, load_lock, load_prompts

ARMS_ORDER = list(ARMS)


def rows_for(benchmark, prompt_hash):
    found = []
    root = HERE / "runs" / benchmark / prompt_hash
    if not root.exists():
        return found
    for arm in ARMS_ORDER:
        path = root / arm / "receipts.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                found.append(json.loads(line))
    return found


def summarize(benchmark):
    lock = load_lock()
    prompts = load_prompts()["benchmarks"][benchmark]
    pilot = lock["benchmarks"][benchmark]["pilot"]
    official = [
        row for row in rows_for(benchmark, prompts["sha256"])
        if row.get("official") is True and row.get("promptSha256") == prompts["sha256"] and row.get("task") in pilot
    ]
    by_arm = {arm: [] for arm in ARMS_ORDER}
    for row in official:
        by_arm[row["arm"]].append(row)
    table = {}
    for arm, rows in by_arm.items():
        # One official row per task. If a resume wrote two, keep the first.
        chosen = {}
        for row in rows:
            chosen.setdefault(row["task"], row)
        ordered = [chosen[task] for task in pilot if task in chosen]
        table[arm] = {
            "n": len(ordered),
            "sum": round(sum(row["reward"] for row in ordered), 4) if ordered else None,
            "infraFailures": sum(int(row.get("infraFailures") or 0) for row in ordered),
            "tasks": {row["task"]: row["reward"] for row in ordered},
        }
    complete = all(table[arm]["n"] == len(pilot) for arm in ARMS_ORDER)
    janus = table["janus"]["sum"]
    passed = False
    if complete and janus is not None:
        others = [table[arm]["sum"] for arm in ARMS_ORDER if arm != "janus"]
        strictly_higher = all(janus > value for value in others)
        tied_at_ceiling = janus >= 8 and all(janus >= value for value in others)
        passed = strictly_higher or tied_at_ceiling
    return {
        "benchmark": benchmark,
        "promptSha256": prompts["sha256"],
        "orderSha256": lock["sha256"],
        "pilot": pilot,
        "complete": complete,
        "passed": passed,
        "arms": table,
    }


def main():
    reports = []
    gates = HERE / "gates"
    gates.mkdir(exist_ok=True)
    for benchmark in ("terminal", "bash", "sql", "tau"):
        report = summarize(benchmark)
        reports.append(report)
        if report["passed"]:
            (gates / (benchmark + ".json")).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(reports, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
