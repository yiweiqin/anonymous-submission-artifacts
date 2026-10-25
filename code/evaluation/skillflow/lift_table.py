"""Paired lift table for the SkillFlow development baselines.

The latest successful row wins. A missing directory is not a score.
Absolute pass rate is reported beside lift and does not decide the order.
"""

from __future__ import annotations

import json
from pathlib import Path

import preflight


def passed(reward):
    try:
        return float(reward) >= 1
    except (TypeError, ValueError):
        return False


def successful_rows(rows):
    chosen = {}
    for row in rows:
        if row.get("error") == "missing_task_dir":
            continue
        if row.get("reward") is None or row.get("error"):
            continue
        chosen[(row["arm"], row["family"], row["task"])] = row
    return chosen


def task_order(rows, family):
    order = []
    seen = set()
    for row in rows:
        if row.get("arm") != "vanilla" or row.get("family") != family:
            continue
        if row.get("reward") is None or row.get("error"):
            continue
        task = row["task"]
        if task in seen:
            continue
        seen.add(task)
        order.append(task)
    return order


def family_lifts(rows, families, arms):
    chosen = successful_rows(rows)
    report = []
    for family in families:
        order = task_order(rows, family)
        vanilla = [passed(chosen[("vanilla", family, task)]["reward"]) for task in order] if order else []
        ready = bool(order)
        arm_rows = []
        for arm in arms:
            if arm == "vanilla":
                continue
            have = all(("vanilla", family, task) in chosen and (arm, family, task) in chosen for task in order)
            if not order or not have:
                ready = False
                arm_rows.append({"arm": arm, "lift": None, "passRate": None, "scored": sum((arm, family, task) in chosen for task in order)})
                continue
            evolved = [passed(chosen[(arm, family, task)]["reward"]) for task in order]
            arm_rows.append({
                "arm": arm,
                "lift": preflight.paired_lift(vanilla, evolved),
                "passRate": sum(evolved) / len(evolved),
                "scored": len(order),
            })
        vanilla_rate = sum(vanilla) / len(vanilla) if vanilla else None
        report.append({
            "family": family,
            "tasks": len(order),
            "complete": ready,
            "vanillaPassRate": vanilla_rate,
            "arms": arm_rows,
        })
    return report


def mean_lifts(report):
    if not report or any(not family["complete"] for family in report):
        return None
    totals = {}
    for family in report:
        for arm in family["arms"]:
            totals.setdefault(arm["arm"], []).append(arm["lift"])
    ranked = [{"arm": arm, "lift": sum(values) / len(values)} for arm, values in totals.items()]
    ranked.sort(key=lambda row: (-row["lift"], row["arm"]))
    return ranked


def load_rows(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def appendix_pass_rates(report):
    """Task-weighted pass counts. They do not change lift or the ranking."""
    if not report or any(not family["complete"] for family in report):
        return None
    totals = {}
    for family in report:
        weight = family["tasks"]
        for arm in family["arms"]:
            bucket = totals.setdefault(arm["arm"], {"passed": 0, "scored": 0})
            bucket["scored"] += weight
            bucket["passed"] += arm["passRate"] * weight
    appendix = []
    for arm, bucket in totals.items():
        appendix.append({
            "arm": arm,
            "passed": bucket["passed"],
            "scored": bucket["scored"],
            "passRate": bucket["passed"] / bucket["scored"] if bucket["scored"] else None,
        })
    appendix.sort(key=lambda row: row["arm"])
    return appendix


def main():
    here = Path(__file__).resolve().parent
    split = json.loads((here / "family-split.json").read_text(encoding="utf-8-sig"))
    protocol = preflight.load_protocol()
    families = list(split["development"])
    arms = ["vanilla"] + [arm["id"] for arm in protocol["baselines"]] + ["janus_full"]
    rows = load_rows(here / "baseline-record.jsonl")
    report = family_lifts(rows, families, arms)
    ranked = mean_lifts(report)
    print(json.dumps({
        "complete": ranked is not None,
        "families": report,
        "meanLift": ranked,
        "appendixPassRate": appendix_pass_rates(report),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
