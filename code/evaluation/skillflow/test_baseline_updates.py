import unittest

import baseline_updates


class BaselineUpdateTest(unittest.TestCase):
    def test_expel_adds_an_insight_and_a_success_excerpt_only(self):
        failed = baseline_updates.apply_update(
            "expel", baseline_updates.empty_state(), 0, "TRAJECTORY-MARK", "watch the units")
        self.assertIn("watch the units", baseline_updates.carry_text(failed))
        self.assertNotIn("TRAJECTORY-MARK", baseline_updates.carry_text(failed))
        passed = baseline_updates.apply_update(
            "expel", baseline_updates.empty_state(), 1, "TRAJECTORY-MARK", "keep the margin")
        text = baseline_updates.carry_text(passed)
        self.assertIn("keep the margin", text)
        self.assertIn("TRAJECTORY-MARK", text)

    def test_awm_writes_a_workflow_only_after_success(self):
        failed = baseline_updates.apply_update(
            "awm", baseline_updates.empty_state(), 0, "trace", "do not store this")
        self.assertEqual(baseline_updates.carry_text(failed), "")
        passed = baseline_updates.apply_update(
            "awm", baseline_updates.empty_state(), 1, "trace", "1. read 2. compute")
        self.assertIn("1. read 2. compute", baseline_updates.carry_text(passed))

    def test_reasoning_bank_keeps_success_and_failure(self):
        state = baseline_updates.apply_update(
            "reasoning_bank", baseline_updates.empty_state(), 1, "trace", "did A")
        state = baseline_updates.apply_update(
            "reasoning_bank", state, 0, "trace", "missed B")
        text = baseline_updates.carry_text(state)
        self.assertIn("Success: did A", text)
        self.assertIn("Failure: missed B", text)

    def test_skillrl_adds_a_skill_only_after_failure(self):
        state = baseline_updates.apply_update(
            "skillrl", baseline_updates.empty_state(), 0, "trace", "check the units")
        self.assertIn("task: check the units", baseline_updates.carry_text(state))
        kept = baseline_updates.apply_update(
            "skillrl", state, 1, "trace", "task: should ignore")
        self.assertEqual(baseline_updates.carry_text(kept), baseline_updates.carry_text(state))

    def test_cowork_replaces_the_library(self):
        state = baseline_updates.apply_update(
            "cowork_x",
            {"entries": ["old skill"], "truncated": False},
            1,
            "trace",
            "new skill only",
        )
        text = baseline_updates.carry_text(state)
        self.assertIn("new skill only", text)
        self.assertNotIn("old skill", text)

    def test_rsea_rejects_a_worse_replay_and_skips_the_first_task(self):
        self.assertEqual(baseline_updates.rsea_keep("old", "new", 1, 0), "old")
        self.assertEqual(baseline_updates.rsea_keep("old", "new", 0, 0), "new")
        self.assertEqual(baseline_updates.rsea_keep("", "new", 1, None), "")
        self.assertEqual(baseline_updates.rsea_keep("old", "new", None, 1), "old")
        self.assertEqual(baseline_updates.official_error_after_replay("Failed to start tmux session"), "")
        self.assertEqual(baseline_updates.official_error_after_replay("No space left on device"), "No space left")

    def test_family_boundary_starts_empty(self):
        used = baseline_updates.apply_update(
            "expel", baseline_updates.empty_state(), 1, "trace", "from the previous family")
        self.assertNotEqual(baseline_updates.carry_text(used), "")
        self.assertEqual(baseline_updates.carry_text(baseline_updates.empty_state()), "")

    def test_overlong_memory_drops_the_oldest_entry(self):
        state = baseline_updates.empty_state()
        for index in range(20):
            state = baseline_updates.apply_update(
                "reasoning_bank", state, 0, "trace", ("F" * 500) + str(index))
        text = baseline_updates.carry_text(state)
        self.assertLessEqual(len(text), baseline_updates.MAX_CHARS)
        self.assertTrue(state["truncated"])
        self.assertNotIn(("F" * 500) + "0", text)
        self.assertIn("19", text)

    def test_prompts_do_not_call_the_network(self):
        for arm in ("expel", "awm", "reasoning_bank", "skillrl", "cowork_x", "rsea"):
            prompt = baseline_updates.reflection_prompt(arm, 0, "trace", "previous note")
            self.assertIn("failed", prompt)
            self.assertIn("previous note", prompt)

    def test_failure_after_long_log_prefix_is_visible(self):
        trace = ("Trajectory dumped to /logs/agent.json\n" * 100
                 + "E AssertionError: required numeric cache is missing\nFAILED test_formula_values")
        prompt = baseline_updates.reflection_prompt("reasoning_bank", 0, trace, "")
        self.assertIn("required numeric cache is missing", prompt)
        self.assertNotIn("Trajectory dumped", prompt)

    def test_rewrite_sees_the_whole_retained_library(self):
        previous = "earliest essential skill\n" + "x" * 5000 + "\nlatest skill"
        prompt = baseline_updates.reflection_prompt("cowork_x", 0, "trace", previous)
        self.assertIn("earliest essential skill", prompt)
        self.assertIn("latest skill", prompt)

    def test_single_oversized_entry_keeps_bounded_information(self):
        state = baseline_updates.state_from_text("x" * 7000 + "important ending")
        self.assertTrue(state["truncated"])
        self.assertEqual(len(baseline_updates.carry_text(state)), baseline_updates.MAX_CHARS)
        self.assertTrue(baseline_updates.carry_text(state).endswith("important ending"))


if __name__ == "__main__":
    unittest.main()
