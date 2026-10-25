import tempfile
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

import baselines
import baseline_updates
import reflection_feedback


class BaselineRunnerTest(unittest.TestCase):
    def test_replay_and_kept_memory_use_same_bounded_candidate(self):
        oversized = 'x' * (baseline_updates.MAX_CHARS + 100)
        valid = {'reward': 1, 'error': ''}
        row = self.run_case('rsea', [valid, valid, valid],
                            {'text': oversized, 'error': '', 'modelCalls': 1},
                            '', ['first-task', 'second-task'])
        self.assertEqual(row['carry'], 'x' * baseline_updates.MAX_CHARS)
        self.assertEqual(self.last_harbor_calls[-1].args[3], row['carry'])
        self.assertTrue(row['truncated'])
        self.assertTrue(row['selectionTrials'][0]['kept'])

    def test_worker_limit(self):
        with patch.object(baselines.sys, "argv", ["baselines.py", "--workers", "10"]):
            self.assertEqual(baselines.worker_count(False), 4)

    def test_invalid_result_cannot_enter_formal_ledger(self):
        for row in [{"reward": None, "error": ""}, {"reward": 1, "error": "failed"}]:
            with self.assertRaises(ValueError):
                baselines.append(row)

    def run_case(self, arm, payloads, reflection=None, previous="", tasks=None):
        rows = []
        with patch.object(baselines.harbor_bridge, "assert_baseline_request"), \
             patch.object(baselines, "restored_state", return_value=baseline_updates.state_from_text(previous)), \
             patch.object(baselines, "finished", return_value=False), \
             patch.object(baselines, "wait_for_disk"), \
             patch.object(baselines, "say"), \
             patch.object(baselines.time, "sleep"), \
             patch.object(baselines, "run_harbor", side_effect=payloads) as harbor, \
             patch.object(baselines, "reflect", return_value=reflection or {},
                          side_effect=reflection if isinstance(reflection, Exception) else None), \
             patch.object(baselines, "append", side_effect=rows.append):
            baselines.run_arm({}, "test-family", arm, tasks or ["test-task"], threading.Event())
            self.last_harbor_calls = harbor.call_args_list
        return rows[-1]

    def test_reflection_transport_error_preserves_official_result(self):
        row = self.run_case('reasoning_bank', [{'reward': 1, 'error': ''}],
                            OSError('connection interrupted'), 'prior memory')
        self.assertEqual(row['reward'], 1)
        self.assertEqual(row['error'], '')
        self.assertEqual(row['carry'], 'prior memory')
        self.assertTrue(row['reflectionCallsUnknown'])

    def test_invalid_replay_does_not_replace_memory_or_official_reward(self):
        valid = {"reward": 0, "error": ""}
        invalid = {"reward": 1, "error": "artifact_error"}
        row = self.run_case('rsea', [valid, valid, invalid, invalid, invalid],
                            {'text': 'replacement', 'error': '', 'modelCalls': 1},
                            'prior context', ['first-task', 'second-task'])
        self.assertEqual(row['reward'], 0)
        self.assertEqual(row['error'], '')
        self.assertEqual(row['carry'], 'prior context')
        self.assertFalse(row['selectionTrials'][0]['kept'])
        self.assertEqual(row['harborTrials'], 4)

    def test_reflection_failure_preserves_existing_memory(self):
        row = self.run_case("reasoning_bank", [{"reward": 0, "error": "", "trace": "failure"}],
                            {"text": "", "error": "reflection_feedback_unavailable"}, "valid prior memory")
        self.assertEqual(row["reward"], 0)
        self.assertEqual(row["carry"], "valid prior memory")
        self.assertEqual(row["reflectError"], "reflection_feedback_unavailable")

    def test_retry_usage_includes_failed_attempts(self):
        payloads = [{"reward": reward, "error": "" if reward is not None else "setup_failure",
                     "modelCalls": 1, "promptTokens": 10, "completionTokens": 2, "wallSeconds": 5}
                    for reward in [None, None, 1]]
        row = self.run_case("vanilla", payloads)
        self.assertEqual(row["reward"], 1)
        self.assertEqual(row["harborTrials"], 3)
        self.assertEqual(row["wallSeconds"], 15)
        self.assertEqual(row["modelCalls"], 3)
        self.assertEqual(row["promptTokens"], 30)

    def test_structured_feedback_contains_outcome_and_executed_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            trial = Path(tmp) / "trial"
            (trial / "verifier").mkdir(parents=True)
            (trial / "agent").mkdir()
            (trial / "verifier/ctrf.json").write_text(json.dumps({"results": {"tests": [{
                "name": "test_numeric_result", "status": "failed",
                "failure": {"trace": "AssertionError: numeric cache missing"}}]}}))
            (trial / "agent/trajectory.json").write_text(json.dumps({"steps": [{"tool_calls": [{
                "function_name": "run_command", "arguments": {"command": "recalculate workbook"}}]}]}))
            feedback = reflection_feedback.collect(tmp)
            prompt = baseline_updates.reflection_prompt("reasoning_bank", 0, feedback["text"], "")
            self.assertIn("numeric cache missing", prompt)
            self.assertEqual(feedback["verifierTests"], 1)
            self.assertEqual(feedback["executedActions"], 1)
            self.assertIn("recalculate workbook", feedback["text"])


if __name__ == "__main__":
    unittest.main()
