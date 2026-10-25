import unittest

import preflight


class PreflightTest(unittest.TestCase):
    def setUp(self):
        self.protocol = preflight.load_protocol()

    def test_main_table_is_skillflow_lift_against_six_papers(self):
        self.assertEqual(self.protocol["benchmark"]["name"], "SkillFlow")
        self.assertEqual(self.protocol["benchmark"]["primaryMetric"], "family_mean_paired_lift")
        self.assertEqual([arm["id"] for arm in self.protocol["baselines"]], [
            "expel", "awm", "reasoning_bank", "skillrl", "cowork_x", "rsea",
        ])
        self.assertEqual([arm["year"] for arm in self.protocol["baselines"]], [
            2024, 2025, 2025, 2026, 2026, 2026,
        ])
        self.assertEqual(self.protocol["systemUnderTest"], "janus_full")
        self.assertFalse(self.protocol["realRunAllowed"])
        self.assertIn("AppWorld", " ".join(self.protocol["retiredMainTables"]))

    def test_lift_not_absolute_score_decides_the_ranking(self):
        vanilla = [True, True, False, False]
        arms = {
            "high_absolute_low_lift": [True, True, False, False],
            "lower_absolute_higher_lift": [False, True, True, True],
        }
        ranked = preflight.rank_by_lift(arms, vanilla)
        self.assertEqual(ranked[0]["arm"], "lower_absolute_higher_lift")
        self.assertAlmostEqual(ranked[0]["lift"], 0.25)
        self.assertAlmostEqual(ranked[1]["lift"], 0.0)

    def test_negative_lift_is_visible(self):
        self.assertAlmostEqual(preflight.paired_lift([True, True], [True, False]), -0.5)

    def test_split_stays_closed_and_deterministic(self):
        ids = ["family-%02d" % i for i in range(20)]
        first = preflight.assign_split(ids, self.protocol)
        second = preflight.assign_split(ids, self.protocol)
        self.assertEqual(first, second)
        self.assertEqual(len(first["development"]), 8)
        self.assertEqual(len(first["gate"]), 4)
        self.assertEqual(len(first["locked"]), 8)

    def test_doctor_refuses_to_open_the_real_run(self):
        report = preflight.doctor()
        self.assertEqual(report["realRun"], "CLOSED")
        self.assertFalse(report["paperReady"])


if __name__ == "__main__":
    unittest.main()
