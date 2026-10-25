"""Readiness gate for the SkillFlow main table. It does not call a model."""

from __future__ import annotations

import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL_PATH = HERE / "protocol.json"


def load_protocol():
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8-sig"))
    if protocol.get("paperReady") is not False:
        raise ValueError("paper_ready_must_stay_false")
    if protocol.get("realRunAllowed") is not False:
        raise ValueError("real_run_must_stay_closed_until_data_and_model_are_locked")
    years = {}
    for arm in protocol["baselines"]:
        years[arm["year"]] = years.get(arm["year"], 0) + 1
    if years != {int(k): v for k, v in protocol["yearCount"].items()}:
        raise ValueError("baseline_year_count_mismatch")
    if protocol["benchmark"]["name"] != "SkillFlow":
        raise ValueError("main_benchmark_must_be_skillflow")
    if protocol["systemUnderTest"] != "janus_full":
        raise ValueError("system_arm_changed")
    return protocol


def paired_lift(vanilla, evolved):
    if len(vanilla) != len(evolved) or not vanilla:
        raise ValueError("paired_tasks_required")
    return sum((1 if e else 0) - (1 if v else 0) for v, e in zip(vanilla, evolved)) / len(vanilla)


def rank_by_lift(arm_passes, vanilla):
    """Higher lift ranks first. Absolute pass rate does not break ties."""
    ranked = []
    for arm, passes in arm_passes.items():
        ranked.append({"arm": arm, "lift": paired_lift(vanilla, passes)})
    ranked.sort(key=lambda row: (-row["lift"], row["arm"]))
    return ranked


def assign_split(family_ids, protocol):
    ids = sorted(set(family_ids))
    spec = protocol["split"]
    if len(ids) < spec["development"] + spec["gate"] + 1:
        raise ValueError("not_enough_families")
    order = ids[:]
    random.Random(spec["assignmentSeed"]).shuffle(order)
    dev_n = spec["development"]
    gate_n = spec["gate"]
    groups = {
        "development": order[:dev_n],
        "gate": order[dev_n:dev_n + gate_n],
        "locked": order[dev_n + gate_n:],
    }
    if spec["lockedMayOpen"] is not False:
        raise ValueError("locked_split_opened")
    return groups


def doctor():
    protocol = load_protocol()
    return {
        "protocol": protocol["version"],
        "benchmark": "SkillFlow",
        "primaryMetric": protocol["benchmark"]["primaryMetric"],
        "baselines": [arm["id"] for arm in protocol["baselines"]],
        "systemUnderTest": protocol["systemUnderTest"],
        "realRun": "CLOSED",
        "reason": protocol["blockedReason"],
        "paperReady": False,
    }


def main():
    print(json.dumps(doctor(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
