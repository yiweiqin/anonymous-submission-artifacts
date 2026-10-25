"""Import and schema checks. Does not load a model or call an API."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code" / "evaluation" / "detective-deploy"))
sys.path.insert(0, str(ROOT / "code" / "training" / "minimal-evolution"))
sys.path.insert(0, str(ROOT / "code" / "training" / "dependency-similarity" / "scripts"))
sys.path.insert(0, str(ROOT / "code" / "evaluation" / "single-chain"))

import rdmd_detective
import engine
import tdb_completion
import aggregate_results


def main():
    rounds = ROOT / "code" / "evaluation" / "rounds"
    old_results = ROOT / "results" / "rounds-20261019"
    if rounds.exists() or old_results.exists():
        raise SystemExit("three_chain_tree_still_present")
    detective = rdmd_detective.parse_completion(
        '{"status":"drift","nodeId":"n1","edgeId":"","type":"wrong_agent","changedFields":["agentId"],"evidenceNodeIds":["n1"]}'
    )
    if detective["status"] != "drift" or detective["nodeId"] != "n1":
        raise SystemExit("detective_parser_failed")
    prompt_file = (ROOT / "code" / "evaluation" / "detective-deploy" / "prompt.txt").read_text(encoding="utf-8").strip()
    if prompt_file != rdmd_detective.DETECTIVE_INSTRUCTION:
        raise SystemExit("detective_prompt_mismatch")
    sample = engine.answer({"G_plan": {"nodes": []}, "G_exec": {"nodes": []}}, decision="abstain")
    if set(sample) != {"decision", "direction", "sourceNodeIds", "edits"}:
        raise SystemExit("minimal_schema_changed")
    if not callable(tdb_completion.encode_completion):
        raise SystemExit("missing_encode_completion")
    if not callable(aggregate_results.family_mean):
        raise SystemExit("missing_single_chain_aggregate")
    native = ROOT / "code" / "evaluation" / "robustness-native" / "native_workflow.py"
    text = native.read_text(encoding="utf-8")
    if "rdmd_minimal_evolution" in text or "assets" in text:
        raise SystemExit("native_workflow_still_uses_a_private_path")
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "test_engine"],
        cwd=ROOT / "code" / "training" / "minimal-evolution",
        capture_output=True, text=True,
    )
    print(tests.stdout)
    if tests.returncode != 0:
        print(tests.stderr)
        raise SystemExit("minimal_engine_tests_failed")
    print(json.dumps({
        "layout": "PASS",
        "detectiveParser": "PASS",
        "detectivePrompt": "PASS",
        "dependencyEncoderImport": "PASS",
        "singleChainImport": "PASS",
        "adapterLoad": "NOT_EXECUTED",
        "paidEvaluation": "NOT_EXECUTED",
    }, indent=2))


if __name__ == "__main__":
    main()
