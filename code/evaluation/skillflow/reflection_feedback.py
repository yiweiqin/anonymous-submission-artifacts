"""Read baseline feedback from completed Harbor artifacts; never change rewards."""
from __future__ import annotations

import json
from pathlib import Path
import sys


def collect(job_dir):
    job_dir = Path(job_dir)
    failures = []
    outcomes = []
    actions = []
    for path in sorted(job_dir.glob("*/verifier/ctrf*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for test in (data.get("results") or {}).get("tests", []):
            status = test.get("status", "unknown")
            outcomes.append(str(test.get("name", "test")) + ": " + status)
            if status == "failed":
                failure = test.get("failure") or {}
                if isinstance(failure, dict):
                    failure = failure.get("trace") or failure.get("message") or str(failure)
                failures.append(str(failure)[-3500:])
    for path in sorted(job_dir.glob("*/verifier/test-stdout.txt")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if text.strip():
            failures.append(text[-4500:])
    for path in sorted(job_dir.glob("*/agent/trajectory.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for step in data.get("steps", []):
            for call in step.get("tool_calls") or []:
                actions.append(json.dumps({"tool": call.get("function_name"),
                                           "arguments": call.get("arguments")}, ensure_ascii=False)[:1400])
    sections = []
    if outcomes:
        sections.append("Verifier results:\n" + "\n".join(outcomes)[-1500:])
    if failures:
        sections.append("Verifier feedback:\n" + "\n".join(failures)[-6000:])
    if actions:
        sections.append("Executed task actions:\n" + "\n".join(actions[-12:])[-4500:])
    return {"text": "\n\n".join(sections), "verifierTests": len(outcomes),
            "executedActions": len(actions)}


if __name__ == "__main__":
    path = Path(sys.argv[1]).resolve()
    root = Path("/benchmark/skillflow-main-20261008/baseline-jobs").resolve()
    if root not in path.parents:
        raise SystemExit("job_outside_baseline_artifacts")
    print(json.dumps(collect(path), ensure_ascii=False))
