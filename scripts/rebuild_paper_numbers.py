"""Recompute reported scores from the stored ledgers. Does not change them."""
import csv
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    1: {"passed": 39, "lift": 7.986},
    2: {"passed": 41, "lift": 11.458},
    3: {"passed": 42, "lift": 13.021},
    4: {"passed": 38, "lift": 6.424},
}


def family_lift(path):
    groups = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            groups[(row["kind"], int(row["round"]))].append(float(row["passRatePct"]))
    vanilla = sum(groups[("historical-selected-vanilla", 1)]) / len(groups[("historical-selected-vanilla", 1)])
    lifts = {}
    for kind, round_id in (
        ("historical-selected-janus", 1),
        ("c1-online", 2),
        ("c1-online", 3),
        ("c1-online", 4),
    ):
        lifts[round_id] = sum(groups[(kind, round_id)]) / len(groups[(kind, round_id)]) - vanilla
    return lifts


def summary_passes(path):
    found = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["kind"] == "historical-selected-janus" and int(row["round"]) == 1:
                found[1] = (int(row["n"]), int(row["passed"]))
            if row["kind"] == "c1-online":
                found[int(row["round"])] = (int(row["n"]), int(row["passed"]))
    return found


def online_passes(path):
    counts = defaultdict(lambda: [0, 0])
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["phase"] != "formal-online" or row["usedForPrimaryMetrics"] != "True":
                continue
            round_id = int(row["logicalId"].split("/")[2])
            counts[round_id][0] += 1
            counts[round_id][1] += int(row["passed"])
    return counts


def cost_calls(path):
    found = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["方法"] in {"Vanilla", "Janus"}:
                found[row["方法"]] = float(row["做题调用"])
    return found


def main():
    lifts = family_lift(ROOT / "results" / "single-chain-c1" / "family-summary.csv")
    passes = summary_passes(ROOT / "results" / "single-chain-c1" / "method-summary.csv")
    ledger = online_passes(ROOT / "results" / "single-chain-c1" / "task-ledger.csv")
    report = []
    for round_id, expected in EXPECTED.items():
        got_lift = lifts[round_id]
        got_n, got_passed = passes[round_id]
        if round_id > 1 and ledger[round_id] != [got_n, got_passed]:
            raise SystemExit("ledger_disagrees_with_summary:" + str(round_id))
        ok = got_n == 66 and got_passed == expected["passed"] and abs(got_lift - expected["lift"]) < 0.001
        report.append({"round": round_id, "n": got_n, "passed": got_passed, "lift": round(got_lift, 3), "ok": ok})
        if not ok:
            raise SystemExit("round_mismatch:" + json.dumps(report[-1]))
    calls = cost_calls(ROOT / "results" / "october19-tables" / "03A_主表成本.csv")
    if calls.get("Vanilla") != 707 or calls.get("Janus") != 860:
        raise SystemExit("cost_mismatch")
    verifier = subprocess.run(
        [sys.executable, str(ROOT / "results" / "main-table-20261025" / "核验主表.py")],
        cwd=ROOT, capture_output=True, text=True,
    )
    print(verifier.stdout)
    if verifier.returncode != 0:
        print(verifier.stderr)
        raise SystemExit("main_table_verifier_failed")
    print(json.dumps({"rounds": report, "costCalls": calls, "mainTable": "PASS"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
