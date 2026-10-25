import unittest

import lift_table


def row(arm, family, task, reward, error=""):
    return {"arm": arm, "family": family, "task": task, "reward": reward, "error": error}


class LiftTableTest(unittest.TestCase):
    def test_latest_success_replaces_an_earlier_failure(self):
        rows = [
            row("vanilla", "Health", "a", None, "tmux timeout"),
            row("vanilla", "Health", "a", 1),
            row("expel", "Health", "a", 0),
        ]
        report = lift_table.family_lifts(rows, ["Health"], ["vanilla", "expel"])
        self.assertTrue(report[0]["complete"])
        self.assertAlmostEqual(report[0]["arms"][0]["lift"], -1.0)
        self.assertAlmostEqual(report[0]["vanillaPassRate"], 1.0)

    def test_missing_directory_is_not_a_score(self):
        rows = [
            row("vanilla", "Ops", "ghost", None, "missing_task_dir"),
            row("vanilla", "Ops", "real", 0),
            row("expel", "Ops", "real", 1),
        ]
        report = lift_table.family_lifts(rows, ["Ops"], ["vanilla", "expel"])
        self.assertEqual(report[0]["tasks"], 1)
        self.assertAlmostEqual(report[0]["arms"][0]["lift"], 1.0)

    def test_mean_waits_until_every_family_is_complete(self):
        rows = [
            row("vanilla", "A", "t", 0),
            row("expel", "A", "t", 1),
            row("vanilla", "B", "t", 1),
        ]
        report = lift_table.family_lifts(rows, ["A", "B"], ["vanilla", "expel"])
        self.assertIsNone(lift_table.mean_lifts(report))

    def test_negative_lift_ranks_below_a_gain(self):
        rows = [
            row("vanilla", "A", "t1", 1),
            row("vanilla", "A", "t2", 1),
            row("expel", "A", "t1", 0),
            row("expel", "A", "t2", 1),
            row("awm", "A", "t1", 1),
            row("awm", "A", "t2", 1),
        ]
        report = lift_table.family_lifts(rows, ["A"], ["vanilla", "expel", "awm"])
        ranked = lift_table.mean_lifts(report)
        self.assertEqual([item["arm"] for item in ranked], ["awm", "expel"])
        self.assertAlmostEqual(ranked[1]["lift"], -0.5)

    def test_janus_full_uses_the_same_lift_and_keeps_a_negative(self):
        rows = []
        for index in range(8):
            rows.append(row("vanilla", "Easy", "e" + str(index), 1))
            rows.append(row("janus_full", "Easy", "e" + str(index), 1))
            rows.append(row("expel", "Easy", "e" + str(index), 0 if index < 2 else 1))
        rows.extend([
            row("vanilla", "Hard", "h", 0),
            row("janus_full", "Hard", "h", 0),
            row("expel", "Hard", "h", 1),
            row("vanilla", "Drop", "d", 1),
            row("janus_full", "Drop", "d", 0),
            row("expel", "Drop", "d", 1),
        ])
        report = lift_table.family_lifts(
            rows, ["Easy", "Hard", "Drop"], ["vanilla", "expel", "janus_full"])
        ranked = lift_table.mean_lifts(report)
        self.assertEqual([item["arm"] for item in ranked], ["expel", "janus_full"])
        self.assertAlmostEqual(ranked[0]["lift"], 0.25)
        self.assertAlmostEqual(ranked[1]["lift"], -1 / 3)
        self.assertLess(ranked[1]["lift"], 0)
        appendix = {item["arm"]: item["passRate"] for item in lift_table.appendix_pass_rates(report)}
        self.assertAlmostEqual(appendix["janus_full"], 0.8)
        self.assertAlmostEqual(appendix["expel"], 0.8)


if __name__ == "__main__":
    unittest.main()
