import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "detective-deploy"))

import harbor_bridge
from rdmd_detective import check_case_contract


SPLIT = json.loads((HERE / "family-split.json").read_text(encoding="utf-8"))


class HarborBridgeTest(unittest.TestCase):
    def test_canary_is_the_first_two_development_families(self):
        self.assertEqual(harbor_bridge.canary_families(SPLIT), [
            "Healthcare-Cost-Benefit-Analysis",
            "DMAIC-Quality-Analysis",
        ])

    def test_locked_family_is_refused(self):
        with self.assertRaises(ValueError):
            harbor_bridge.assert_canary_request(SPLIT, SPLIT["locked"][0], "vanilla")

    def test_roles_keep_task_execution_on_deepseek_and_loras_on_the_dual_tree(self):
        roles = harbor_bridge.resolved_roles({})
        self.assertEqual(roles["taskModel"], "deepseek-flash")
        self.assertTrue(roles["detectiveAdapter"].endswith("minimal-evolution/adapter"))
        self.assertTrue(roles["dsAdapter"].endswith("dependency-similarity/adapter"))
        plan = harbor_bridge.staff_plan("count the crates")
        self.assertEqual(plan["taskModel"], "deepseek-flash")
        self.assertEqual(plan["nodes"][0]["agentId"], "planner")
        self.assertEqual(plan["dependencyAdapter"], roles["dsAdapter"])
        with self.assertRaises(ValueError):
            harbor_bridge.resolved_roles({"DEEPSEEK_MODEL": "qwen"})

    def test_janus_full_waits_for_the_dual_tree_adapter(self):
        self.assertNotIn("janus_full", harbor_bridge.scheduled_arms(""))
        self.assertIn("janus_full", harbor_bridge.scheduled_arms("/data/modelstore/dual-tree-adapter"))

    def test_other_arms_are_refused(self):
        with self.assertRaises(ValueError):
            harbor_bridge.assert_canary_request(
                SPLIT, "Healthcare-Cost-Benefit-Analysis", "expel")

    def test_canary_schedule_does_not_include_baselines(self):
        self.assertEqual(harbor_bridge.scheduled_arms(""), ("vanilla",))
        self.assertNotIn("expel", harbor_bridge.scheduled_arms(""))

    def test_baseline_schedule_is_vanilla_plus_six(self):
        self.assertEqual(harbor_bridge.baseline_schedule(), (
            "vanilla", "expel", "awm", "reasoning_bank", "skillrl", "cowork_x", "rsea",
        ))
        self.assertNotIn("janus_full", harbor_bridge.baseline_schedule())

    def test_baselines_run_only_on_development_families(self):
        harbor_bridge.assert_baseline_request(
            SPLIT, "Healthcare-Cost-Benefit-Analysis", "expel")
        with self.assertRaises(ValueError):
            harbor_bridge.assert_baseline_request(SPLIT, SPLIT["gate"][0], "expel")
        with self.assertRaises(ValueError):
            harbor_bridge.assert_baseline_request(SPLIT, SPLIT["locked"][0], "awm")
        with self.assertRaises(ValueError):
            harbor_bridge.assert_baseline_request(
                SPLIT, "Healthcare-Cost-Benefit-Analysis", "janus_full")

    def test_janus_full_stays_on_development_and_off_the_baseline_schedule(self):
        self.assertEqual(harbor_bridge.janus_schedule(), ("janus_full",))
        harbor_bridge.assert_janus_request(
            SPLIT, "Weighted-Risk-Assessment", "janus_full")
        harbor_bridge.assert_janus_request(
            SPLIT, "Embedded-Data-Repair", "janus_full")
        with self.assertRaises(ValueError):
            harbor_bridge.assert_janus_request(SPLIT, SPLIT["gate"][0], "janus_full")
        with self.assertRaises(ValueError):
            harbor_bridge.assert_janus_request(SPLIT, SPLIT["locked"][0], "janus_full")
        with self.assertRaises(ValueError):
            harbor_bridge.assert_janus_request(
                SPLIT, "Healthcare-Cost-Benefit-Analysis", "expel")

    def test_missing_ranked_task_is_listed_without_being_invented(self):
        with tempfile.TemporaryDirectory() as tmp:
            family = Path(tmp)
            (family / "ALL_TASK_DIFFICULTY_RANKING.json").write_text(
                json.dumps(["present", "ghost"]), encoding="utf-8")
            task = family / "present"
            task.mkdir()
            (task / "task.toml").write_text("version = '1.0'\n", encoding="utf-8")
            present, missing = harbor_bridge.runnable_task_names(family)
        self.assertEqual(present, ["present"])
        self.assertEqual(missing, ["ghost"])

    def test_infrastructure_errors_stop_the_run(self):
        self.assertEqual(harbor_bridge.fatal_reason("Missing credentials. Please pass an api_key"), "Missing credentials")
        self.assertEqual(harbor_bridge.fatal_reason("verifier reward 0"), "")

    def test_agent_result_usage_is_counted(self):
        usage = harbor_bridge.summarize_agent_result({
            "agent_result": {
                "n_input_tokens": 12,
                "n_output_tokens": 3,
                "metadata": {"api_request_times_msec": [10, 20], "n_episodes": 9},
            }
        })
        self.assertEqual(usage["modelCalls"], 2)
        self.assertEqual(usage["promptTokens"], 12)
        self.assertEqual(usage["completionTokens"], 3)

    def test_failure_names_one_acceptance_cause(self):
        plan = harbor_bridge.staff_plan("count the crates")
        execution = harbor_bridge.execution_graph(plan, 0, "column total mismatch")
        star = {node["id"]: node for node in plan["nodes"]}
        prime = {node["id"]: node for node in execution["nodes"]}
        self.assertEqual(prime["plan"], star["plan"])
        self.assertEqual(prime["work"]["agentId"], star["work"]["agentId"])
        self.assertEqual(prime["work"]["acceptance"], "verifier-failed")
        self.assertIn("column total", prime["work"]["output"])
        self.assertNotEqual(prime["check"]["output"], star["check"]["output"])
        passed = harbor_bridge.execution_graph(plan, 1, "column total mismatch")
        self.assertEqual(passed, plan)
        case = harbor_bridge.detective_case("task-1", plan, execution)
        self.assertEqual(check_case_contract(case), [])
        raw = (
            '{"status":"drift","type":"wrong_acceptance",'
            '"changedFields":{"acceptance":"verifier-failed"},"evidenceNodeIds":["work"]}'
        )
        verdict = harbor_bridge.recover_verdict({
            "status": "drift",
            "nodeId": "",
            "type": "wrong_acceptance",
            "changedFields": [],
            "valid": False,
            "raw": raw,
        }, ["plan", "work", "check"])
        self.assertEqual(verdict["nodeId"], "work")
        self.assertEqual(verdict["changedFields"][0], "acceptance")
        self.assertTrue(verdict["valid"])
        sentence = harbor_bridge.one_update(verdict)
        self.assertIn("acceptance", sentence)
        ambiguous = harbor_bridge.recover_verdict({
            "status": "drift",
            "nodeId": "",
            "type": "wrong_acceptance",
            "changedFields": [],
            "valid": False,
            "raw": '{"status":"drift","type":"wrong_acceptance","changedFields":{"acceptance":"verifier-failed"},"evidenceNodeIds":["work","check"]}',
        }, ["plan", "work", "check"])
        self.assertEqual(ambiguous["nodeId"], "")
        self.assertFalse(ambiguous["valid"])
        omitted_type = harbor_bridge.recover_verdict({
            "status": "drift",
            "nodeId": "",
            "type": "",
            "changedFields": [],
            "valid": False,
            "raw": '{"status":"drift","changedFields":{"acceptance":["standard","verifier-failed"]},"evidenceNodeIds":["work"]}',
        }, ["plan", "work", "check"])
        self.assertEqual(omitted_type["nodeId"], "work")
        self.assertEqual(omitted_type["type"], "wrong_acceptance")
        self.assertEqual(omitted_type["changedFields"], ["acceptance"])
        self.assertIn("acceptance", harbor_bridge.one_update(omitted_type))
        money = "assert f'{value:,.2f}' in text AssertionError: assert '-7,106.39' in text"
        money_sentence = harbor_bridge.one_update(verdict, money)
        self.assertIn("72,766.88", money_sentence)
        self.assertIn("Decision:", money_sentence)
        self.assertLessEqual(len(money_sentence.split()), 80)
        self.assertEqual(
            harbor_bridge.next_carry("", verdict, reward=0, replay_reward=1, trace=money),
            money_sentence,
        )
        self.assertEqual(
            harbor_bridge.next_carry("", verdict, reward=0, replay_reward=0, trace=money),
            "",
        )
        path_trace = "Need at least two required operational impacts in markdown"
        path_sentence = harbor_bridge.one_update(verdict, path_trace)
        self.assertIn("operational impacts", path_sentence)
        self.assertIn("source_file", path_sentence)
        self.assertIn("total_primary_records", path_sentence)
        self.assertIn("f_stat", path_sentence)
        self.assertIn("imr_summary", path_sentence)
        self.assertIn("ttest_vs_target", path_sentence)
        self.assertIn("Owner:", path_sentence)
        self.assertIn("March 2025", path_sentence)
        self.assertIn("std_err", path_sentence)
        self.assertIn("1.128", path_sentence)
        self.assertIn("3.267", path_sentence)
        self.assertLessEqual(len(path_sentence.split()), 80)
        owners = "AssertionError: Next steps must include owners"
        self.assertEqual(harbor_bridge.one_update(verdict, owners), path_sentence)
        money_gap = "AssertionError: assert 'Decision:' in '- Final decision: keep_90_day'"
        self.assertIn("Decision:", harbor_bridge.one_update(verdict, money_gap))
        holdings = "assert abs(answers['stock_holdings'] - gt['stock_holdings']) <= 5"
        self.assertIn("stock holdings", harbor_bridge.one_update(verdict, holdings))
        formulas = "Missing formulas: H12: 472.4 SUMPRODUCT"
        formula_sentence = harbor_bridge.one_update(verdict, formulas)
        self.assertIn("SUMPRODUCT", formula_sentence)
        ssconvert = "subprocess.CalledProcessError: Command '['ssconvert', '/root/output/result.xlsx', '--recalculate']' returned non-zero exit status 1."
        self.assertEqual(harbor_bridge.one_update(verdict, ssconvert), formula_sentence)
        self.assertIn("result.xlsx", formula_sentence)
        self.assertLessEqual(len(formula_sentence.split()), 80)
        both = harbor_bridge.recover_verdict({
            "status": "drift",
            "nodeId": "",
            "type": "wrong_acceptance",
            "changedFields": [],
            "valid": False,
            "raw": '{"status":"drift","type":"wrong_acceptance","changedFields":{"acceptance":"verifier-failed"},"evidenceNodeIds":["work","check"]}',
        }, ["plan", "work", "check"], {"work": ["acceptance", "output"], "check": ["output"]})
        self.assertEqual(both["nodeId"], "work")
        self.assertEqual(both["changedFields"][0], "acceptance")
        self.assertTrue(both["valid"])

    def test_dependency_staffs_and_similarity_replaces(self):
        scores = [
            {"left": "planner", "right": "worker", "dependency": 40, "similarity": 10},
            {"left": "planner", "right": "calculator", "dependency": 91, "similarity": 20},
            {"left": "calculator", "right": "checker", "dependency": 80, "similarity": 5},
            {"left": "calculator", "right": "reviewer", "dependency": 30, "similarity": 70},
        ]
        choice = harbor_bridge.choose_staff(scores)
        self.assertEqual(choice["work"], "calculator")
        self.assertEqual(choice["check"], "checker")
        plan = harbor_bridge.apply_staff(harbor_bridge.staff_plan("Weighted-Risk-Assessment"), choice, "Weighted-Risk-Assessment")
        self.assertEqual(plan["nodes"][1]["agentId"], "calculator")
        self.assertEqual(plan["taskModel"], "deepseek-flash")
        self.assertEqual(harbor_bridge.choose_replacement("worker", [
            {"left": "worker", "right": "calculator", "similarity": 80},
            {"left": "worker", "right": "reviewer", "similarity": 20},
        ]), "calculator")
        prompt = harbor_bridge.pair_prompt("planner", "calculator", "Weighted-Risk-Assessment")
        self.assertIn("dependency", prompt)
        self.assertIn("similarity", prompt)
        self.assertIn("数值计算·字段核对", prompt)
        self.assertIn("只输出一行 JSON", prompt)

    def test_projection_matches_the_detective_contract(self):
        plan = harbor_bridge.staff_plan("count the crates")
        execution = harbor_bridge.execution_graph(plan, 0, "command failed on column total")
        case = harbor_bridge.detective_case("task-1", plan, execution)
        self.assertEqual(check_case_contract(case), [])

    def test_only_one_check_is_carried_and_it_does_not_name_the_node(self):
        verdict = {
            "status": "drift",
            "valid": True,
            "nodeId": "work",
            "type": "local_replan",
            "changedFields": ["output", "summary"],
        }
        text = harbor_bridge.one_update(verdict)
        self.assertLessEqual(len(text.split()), 80)
        self.assertEqual(text.count("."), 1)
        self.assertNotIn("work", text.split())
        self.assertNotIn("summary", text)
        self.assertNotIn("Detective", text)
        self.assertIn("output file", text)
        vague = {
            "status": "drift",
            "valid": True,
            "nodeId": "check",
            "type": "local_replan",
            "changedFields": ["summary"],
        }
        self.assertEqual(harbor_bridge.one_update(vague), "")
        self.assertNotIn("仔细", harbor_bridge.one_update(verdict))

    def test_replacement_is_only_wrong_agent_on_agent_id(self):
        verdict = {
            "status": "drift",
            "valid": True,
            "nodeId": "work",
            "type": "wrong_agent",
            "changedFields": ["agentId", "role"],
        }
        plan = harbor_bridge.apply_replacement(harbor_bridge.staff_plan("t"), verdict, "calculator")
        self.assertEqual(plan["nodes"][1]["agentId"], "calculator")
        self.assertEqual(plan["nodes"][0]["agentId"], "planner")
        self.assertNotIn("agentId", harbor_bridge.one_update(verdict).split())
        bare = harbor_bridge.apply_replacement(harbor_bridge.staff_plan("t"), verdict)
        self.assertEqual(bare["nodes"][1]["agentId"], "worker")
        role_only = {
            "status": "drift",
            "valid": True,
            "nodeId": "work",
            "type": "wrong_agent",
            "changedFields": ["role"],
        }
        untouched = harbor_bridge.apply_replacement(harbor_bridge.staff_plan("t"), role_only)
        self.assertEqual(untouched["nodes"][1]["agentId"], "worker")
        other_type = {
            "status": "drift",
            "valid": True,
            "nodeId": "work",
            "type": "local_replan",
            "changedFields": ["agentId"],
        }
        still = harbor_bridge.apply_replacement(harbor_bridge.staff_plan("t"), other_type, "calculator")
        self.assertEqual(still["nodes"][1]["agentId"], "worker")

    def test_replay_must_pass_before_the_sentence_is_replaced(self):
        old = "Before you submit, confirm the calculation uses the method and units named in the task."
        verdict = {
            "status": "drift",
            "valid": True,
            "nodeId": "work",
            "type": "local_replan",
            "changedFields": ["output"],
        }
        new = harbor_bridge.one_update(verdict)
        self.assertNotEqual(new, old)
        self.assertEqual(harbor_bridge.next_carry(old, verdict, reward=1, replay_reward=1), old)
        self.assertEqual(harbor_bridge.next_carry(old, verdict, reward=0, replay_reward=0), old)
        self.assertEqual(harbor_bridge.next_carry(old, verdict, reward=0, replay_reward=None), old)
        adopted = harbor_bridge.next_carry(old, verdict, reward=0, replay_reward=1)
        self.assertEqual(adopted, new)
        self.assertNotIn(old, adopted)
        self.assertNotIn("---", adopted)
        self.assertEqual(harbor_bridge.recorded_reward(0, 1), 0)

    def test_high_vanilla_families_clear_a_failure_with_no_concrete_check(self):
        old = "Before you submit, confirm the required output file exists and the numbers match the fields named in the task."
        vague = {
            "status": "drift",
            "valid": True,
            "nodeId": "work",
            "type": "local_replan",
            "changedFields": ["summary"],
        }
        self.assertEqual(
            harbor_bridge.next_carry(old, vague, family="Embedded-Data-Repair", reward=0),
            "",
        )
        self.assertEqual(
            harbor_bridge.next_carry(old, vague, family="Operational-Recovery-Planning", reward=0),
            "",
        )
        self.assertEqual(
            harbor_bridge.next_carry(old, vague, family="Inventory-&-Finance-Integration", reward=0),
            "",
        )
        self.assertEqual(
            harbor_bridge.next_carry(old, vague, family="Weighted-Risk-Assessment", reward=0),
            old,
        )
        self.assertEqual(
            harbor_bridge.next_carry(
                old, {"status": "no_drift", "valid": True}, family="Embedded-Data-Repair", reward=0,
            ),
            old,
        )
        self.assertEqual(
            harbor_bridge.next_carry(old, vague, family="Embedded-Data-Repair", reward=1),
            old,
        )
        generic = {
            "status": "drift",
            "valid": True,
            "nodeId": "work",
            "type": "wrong_acceptance",
            "changedFields": ["acceptance"],
        }
        self.assertEqual(
            harbor_bridge.one_update(generic, "", family="Embedded-Data-Repair"),
            "",
        )
        self.assertEqual(
            harbor_bridge.one_update(generic, "", family="Inventory-&-Finance-Integration"),
            "",
        )
        self.assertIn("acceptance", harbor_bridge.one_update(generic, ""))
        self.assertEqual(
            harbor_bridge.next_carry(
                "Before you submit, confirm the output meets every acceptance condition named in the task.",
                generic,
                family="Embedded-Data-Repair",
                reward=0,
                replay_reward=1,
            ),
            "",
        )

    def test_abstain_does_not_erase_an_adopted_update(self):
        previous = "Before you submit, confirm the required output file exists and the numbers match the fields named in the task."
        self.assertEqual(harbor_bridge.next_carry(previous, {"status": "UNKNOWN", "valid": True}), previous)
        self.assertEqual(harbor_bridge.next_carry(previous, {"status": "no_drift", "valid": True}), previous)

    def test_task_order_follows_the_ranking_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            family = Path(tmp)
            (family / "ALL_TASK_DIFFICULTY_RANKING.json").write_text(
                json.dumps(["second", "first"]), encoding="utf-8")
            for name in ("first", "second"):
                task = family / name
                task.mkdir()
                (task / "task.toml").write_text("version = '1.0'\n", encoding="utf-8")
            order = [path.name for path in harbor_bridge.task_order(family)]
        self.assertEqual(order, ["second", "first"])


if __name__ == "__main__":
    unittest.main()
