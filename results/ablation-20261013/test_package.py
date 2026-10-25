"""The three canary packages differ before any Harbor reward exists."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import package
import harbor_bridge


class PackageTest(unittest.TestCase):
    def test_reference_plan_and_staff_texts_differ(self):
        plan = harbor_bridge.apply_staff(
            harbor_bridge.staff_plan("Healthcare-Cost-Benefit-Analysis"),
            {"plan": "planner", "work": "calculator", "check": "reviewer"},
            "Healthcare-Cost-Benefit-Analysis",
        )
        reference = package.harbor_text("Check the named fields.", plan, True, True)
        plan_only = package.harbor_text("Check the named fields.", plan, True, False)
        staff_only = package.harbor_text("Check the named fields.", plan, False, True)
        empty_plan = package.harbor_text("", plan, True, True)
        self.assertIn("已采用的规划更新：", reference)
        self.assertIn("当前三人组：", reference)
        self.assertIn("名称：", reference)
        self.assertIn("主职能：", reference)
        self.assertIn("技能摘要：", reference)
        self.assertNotIn("当前三人组：", plan_only)
        self.assertNotIn("已采用的规划更新：", staff_only)
        self.assertEqual(len({reference, plan_only, staff_only}), 3)
        self.assertNotEqual(empty_plan, staff_only)
        self.assertNotEqual(empty_plan, plan_only)
        self.assertEqual(len(package.text_sha256(reference)), 64)


if __name__ == "__main__":
    unittest.main()
