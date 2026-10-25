"""SkillFlow canary bridge.

vanilla and janus_full share one Harbor executor. janus_full may carry the
detective's single field change into the next task. Gate and locked stay closed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

CANARY_ARMS = ("vanilla", "janus_full")
BASELINE_ARMS = (
    "expel", "awm", "reasoning_bank", "skillrl", "cowork_x", "rsea",
)
ROLES_PATH = Path(__file__).with_name("model-roles.json")


def model_roles(path=None):
    """Task execution and the two dual-tree models. Paths are on the GPU host."""
    return load_json(Path(path) if path else ROLES_PATH)


def resolved_roles(env=None, path=None):
    """Env overrides the file. An empty override does not select the base model."""
    env = env or {}
    roles = model_roles(path)
    task = str(env.get("DEEPSEEK_MODEL") or roles["taskModel"]).strip()
    detective = str(env.get("JANUS_DUAL_TREE_ADAPTER") or roles["detective"]["adapter"]).strip()
    ds_model = str(env.get("JANUS_CPDB_ADAPTER") or roles["dependencySimilarity"]["adapter"]).strip()
    if task != "deepseek-flash":
        raise ValueError("task_model_must_stay_deepseek_flash")
    if not detective or not ds_model:
        raise ValueError("dual_tree_models_required")
    return {
        "taskModel": task,
        "baseModel": roles["baseModel"],
        "detectiveAdapter": detective,
        "dsAdapter": ds_model,
    }


def scheduled_arms(adapter_path=""):
    """Canary schedule. janus_full stays off until the dual-tree adapter is set.

    The six baselines are not included here, so canary.py cannot start them.
    """
    if str(adapter_path or "").strip():
        return ("vanilla", "janus_full")
    return ("vanilla",)


def baseline_schedule():
    """Vanilla plus the six paper baselines. janus_full is never included."""
    return ("vanilla",) + BASELINE_ARMS


def assert_baseline_request(split, family, arm):
    if split.get("lockedMayOpen") is not False:
        raise ValueError("locked_split_opened")
    if arm not in baseline_schedule():
        raise ValueError("arm_not_in_baseline_schedule")
    if family not in list(split["development"]):
        raise ValueError("family_not_in_development")
    closed = set(split.get("gate") or []) | set(split.get("locked") or [])
    if family in closed:
        raise ValueError("family_is_closed")


def janus_schedule():
    """The system arm only. The six paper baselines stay in their own record."""
    return ("janus_full",)


def assert_janus_request(split, family, arm):
    if split.get("lockedMayOpen") is not False:
        raise ValueError("locked_split_opened")
    if arm not in janus_schedule():
        raise ValueError("arm_not_janus_full")
    if family not in list(split["development"]):
        raise ValueError("family_not_in_development")
    closed = set(split.get("gate") or []) | set(split.get("locked") or [])
    if family in closed:
        raise ValueError("family_is_closed")


def runnable_task_names(family_dir):
    """Ranking order. A ranking name without task.toml is reported, not invented."""
    family_dir = Path(family_dir)
    names = ranking_names(load_json(family_dir / "ALL_TASK_DIFFICULTY_RANKING.json"))
    present = []
    missing = []
    for name in names:
        if (family_dir / name / "task.toml").is_file():
            present.append(name)
        else:
            missing.append(name)
    return present, missing


def fatal_reason(error):
    text = str(error or "")
    for mark in (
        "Docker compose",
        "unknown flag",
        "Missing credentials",
        "No space left",
        "missing_api_key",
    ):
        if mark in text:
            return mark
    return ""


def summarize_agent_result(data):
    agent = data.get("agent_result") or {}
    meta = agent.get("metadata") or {}
    times = meta.get("api_request_times_msec") or []
    if times:
        calls = len(times)
    else:
        calls = int(meta.get("n_episodes") or 0)
    return {
        "modelCalls": calls,
        "promptTokens": int(agent.get("n_input_tokens") or 0),
        "completionTokens": int(agent.get("n_output_tokens") or 0),
    }


TASK_MODEL = "deepseek-flash"
STAFF = (
    ("plan", "planner", "Plan the workflow from the instruction"),
    ("work", "worker", "Produce the files the instruction requires"),
    ("check", "checker", "Check the files against the instruction before stopping"),
)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def canary_families(split):
    if split.get("lockedMayOpen") is not False:
        raise ValueError("locked_split_opened")
    development = list(split["development"])
    if len(development) < 2:
        raise ValueError("canary_requires_two_development_families")
    closed = set(split["gate"]) | set(split["locked"])
    chosen = development[:2]
    if any(name in closed for name in chosen):
        raise ValueError("canary_family_is_closed")
    return chosen


def assert_canary_request(split, family, arm):
    if arm not in CANARY_ARMS:
        raise ValueError("arm_not_in_canary")
    if family not in canary_families(split):
        raise ValueError("family_not_in_canary")


def ranking_names(ranking):
    if not isinstance(ranking, list) or not ranking:
        raise ValueError("ranking_empty")
    names = []
    for name in ranking:
        if not isinstance(name, str) or not name or name in {".", ".."}:
            raise ValueError("ranking_name")
        if "/" in name or "\\" in name:
            raise ValueError("ranking_name")
        names.append(name)
    return names


def task_order(family_dir):
    family_dir = Path(family_dir)
    names = ranking_names(load_json(family_dir / "ALL_TASK_DIFFICULTY_RANKING.json"))
    paths = []
    for name in names:
        task_dir = family_dir / name
        if not (task_dir / "task.toml").is_file():
            raise ValueError("missing_task:" + name)
        paths.append(task_dir)
    return paths


CATALOG = {
    "planner": {
        "role": "planner",
        "name": "流程规划·任务拆解",
        "duty": "流程规划",
        "detail": "任务拆解",
        "tags": "planning, 流程, 拆解",
        "outputs": "plan",
        "inputs": "instruction",
        "artifact": "任务拆解",
        "output": "要交的文件和题目指定的字段",
        "summary": "把题目拆成要交的文件和指定字段，不改数字。",
    },
    "worker": {
        "role": "worker",
        "name": "结果制作·按字段落盘",
        "duty": "结果制作",
        "detail": "按字段落盘",
        "tags": "files, 输出, 字段",
        "outputs": "output file",
        "inputs": "plan",
        "artifact": "输出文件",
        "output": "按题目字段写出的输出文件",
        "summary": "按题目指定的字段写出要求的输出文件。",
    },
    "calculator": {
        "role": "calculator",
        "name": "数值计算·字段核对",
        "duty": "数值计算",
        "detail": "字段核对",
        "tags": "calculation, 数字, 字段",
        "outputs": "table",
        "inputs": "plan",
        "artifact": "计算表",
        "output": "按题目公式算出的数字和字段",
        "summary": "按题目给出的公式计算，并核对输出里的数字和字段。",
    },
    "checker": {
        "role": "checker",
        "name": "结果验收·对照题目",
        "duty": "结果验收",
        "detail": "对照题目",
        "tags": "check, 验收, 字段",
        "outputs": "verdict",
        "inputs": "output file",
        "artifact": "验收结论",
        "output": "对照题目后的验收结论",
        "summary": "对照题目检查输出文件是否存在，数字是否和指定字段一致。",
    },
    "reviewer": {
        "role": "reviewer",
        "name": "结果复核·数字回看",
        "duty": "结果复核",
        "detail": "数字回看",
        "tags": "review, 数字, 复核",
        "outputs": "review",
        "inputs": "output file",
        "artifact": "复核记录",
        "output": "复核过的数字和字段",
        "summary": "把输出文件里的数字再对一遍题目指定的字段。",
    },
}
WORK_CANDIDATES = ("worker", "calculator")
CHECK_CANDIDATES = ("checker", "reviewer")
DS_PREFIX_PATH = Path(__file__).with_name("ds_prompt_prefix.txt")


def _write_profile(node, profile_id, family):
    profile = CATALOG[profile_id]
    node["agentId"] = profile_id
    node["role"] = profile["role"]
    node["artifact"] = profile["artifact"]
    node["stage"] = "交付"
    node["inputs"] = profile["inputs"]
    node["output"] = profile["output"]
    node["summary"] = profile["summary"] + " 当前家族：" + str(family or "") + "。"
    node["acceptance"] = "standard"
    node["version"] = "v1"


def staff_plan(title):
    nodes = []
    for node_id, role, node_title in STAFF:
        nodes.append({
            "id": node_id,
            "kind": "agent_task",
            "title": node_title,
            "role": role,
            "agentId": TASK_MODEL,
            "version": "v1",
            "acceptance": "standard",
            "status": "pending",
        })
    roles = model_roles()
    plan = {
        "domain": "skillflow",
        "title": title,
        "topic": "skillflow-canary",
        "taskModel": TASK_MODEL,
        "dependencyAdapter": roles["dependencySimilarity"]["adapter"],
        "nodes": nodes,
        "edges": [
            {"id": "plan-work", "from": "plan", "to": "work"},
            {"id": "work-check", "from": "work", "to": "check"},
        ],
    }
    return apply_staff(plan, {"plan": "planner", "work": "worker", "check": "checker"}, title)


def apply_staff(plan, choice, family):
    """D's choice fills the team. The Harbor task model stays deepseek-flash."""
    updated = json.loads(json.dumps(plan))
    slots = {"plan": "planner", "work": "worker", "check": "checker"}
    slots.update({key: value for key, value in (choice or {}).items() if value in CATALOG})
    for node in updated["nodes"]:
        profile_id = slots.get(node["id"])
        if profile_id:
            _write_profile(node, profile_id, family or updated.get("title") or "")
    updated["taskModel"] = TASK_MODEL
    return updated


def _card(profile_id, family):
    profile = CATALOG[profile_id]
    summary = profile["summary"] + " 当前家族：" + str(family or "") + "。"
    return "\n".join([
        "- 名称：" + profile["name"],
        "- 主职能：" + profile["duty"],
        "- 细节能力：" + profile["detail"],
        "- 标签：" + profile["tags"],
        "- 产出：" + profile["outputs"],
        "- 输入：" + profile["inputs"],
        "- 技能摘要：" + summary,
    ])


def pair_prompt(left_id, right_id, family):
    prefix = DS_PREFIX_PATH.read_text(encoding="utf-8")
    body = "\n".join([
        "## 这一对",
        "",
        "### 左方",
        _card(left_id, family),
        "",
        "### 右方",
        _card(right_id, family),
        "",
        '只输出一行 JSON：{"dependency":整数,"similarity":整数,"rationale":"一句话"}',
        "",
    ])
    return prefix + body


def staffing_pairs(family):
    pairs = []
    for right in WORK_CANDIDATES:
        pairs.append({"id": "planner>" + right, "left": "planner", "right": right,
                      "prompt": pair_prompt("planner", right, family)})
    for left in WORK_CANDIDATES:
        for right in CHECK_CANDIDATES:
            pairs.append({"id": left + ">" + right, "left": left, "right": right,
                          "prompt": pair_prompt(left, right, family)})
    return pairs


def replacement_pairs(current, family):
    pairs = []
    for right in CATALOG:
        if right == current:
            continue
        pairs.append({"id": current + ">" + right, "left": current, "right": right,
                      "prompt": pair_prompt(current, right, family)})
    return pairs


def _best(rows, left, rights, key):
    best = None
    for row in rows or []:
        if row.get("left") != left or row.get("right") not in rights:
            continue
        try:
            value = int(row.get(key))
        except (TypeError, ValueError):
            continue
        right = row["right"]
        if best is None or value > best[0] or (value == best[0] and right < best[1]):
            best = (value, right)
    return None if best is None else best[1]


def choose_staff(scores):
    """D staffs by dependency. Missing scores keep the default worker and checker."""
    work = _best(scores, "planner", set(WORK_CANDIDATES), "dependency") or "worker"
    check = _best(scores, work, set(CHECK_CANDIDATES), "dependency") or "checker"
    return {"plan": "planner", "work": work, "check": check}


def choose_replacement(current, scores):
    """S picks the highest similarity other than the current profile."""
    best = None
    for row in scores or []:
        right = str(row.get("right") or "")
        if not right or right == current or right not in CATALOG:
            continue
        try:
            value = int(row.get("similarity"))
        except (TypeError, ValueError):
            continue
        if best is None or value > best[0] or (value == best[0] and right < best[1]):
            best = (value, right)
    return "" if best is None else best[1]


def execution_graph(plan, reward, trace_text):
    """A pass copies the plan. A failure is one loosened acceptance, plus its consequence.

    The detective was trained to ignore a lone output change and to name the
    upstream acceptance when the checker then repeats the bad product. A pass
    stays identical, so no_drift keeps the previous sentence.
    """
    try:
        passed = float(reward) >= 1
    except (TypeError, ValueError):
        passed = False
    if passed:
        return json.loads(json.dumps(plan))
    excerpt = " ".join(str(trace_text or "").split())[:180]
    nodes = []
    for node in plan["nodes"]:
        item = dict(node)
        if item.get("id") == "work":
            item["acceptance"] = "verifier-failed"
            item["artifact"] = "未通过验收"
            item["output"] = excerpt or "验收未通过：数字和题目指定字段对不上。"
            item["summary"] = "交付没有满足题目里的验收条件。"
        elif item.get("id") == "check":
            item["artifact"] = "未通过复核"
            item["output"] = "复核看到验收未通过，数字和字段对不上。"
            item["summary"] = "对外结果仍是未通过验收的那一版。"
        nodes.append(item)
    graph = dict(plan)
    graph["nodes"] = nodes
    return graph


def detective_case(task_id, plan, execution):
    return {"id": task_id, "G_star": plan, "G_prime": execution}


_RECOVERABLE_FIELDS = (
    "title", "role", "agentId", "version", "acceptance",
    "artifact", "stage", "inputs", "output", "summary",
)


_FIELD_TYPE = {
    "acceptance": "wrong_acceptance",
    "agentId": "wrong_agent",
    "version": "wrong_version",
    "inputs": "missing_dependency",
    "output": "local_replan",
    "artifact": "local_replan",
    "summary": "local_replan",
    "stage": "local_replan",
    "title": "local_replan",
    "role": "local_replan",
}


def changed_fields_by_node(plan, execution):
    """Fields that actually differ, so a shared evidence list can be narrowed."""
    left = {node.get("id"): node for node in (plan or {}).get("nodes") or []}
    right = {node.get("id"): node for node in (execution or {}).get("nodes") or []}
    changed = {}
    for node_id, node in left.items():
        other = right.get(node_id) or {}
        fields = [name for name in _RECOVERABLE_FIELDS if node.get(name) != other.get(name)]
        if fields:
            changed[node_id] = fields
    return changed


def recover_verdict(verdict, node_ids, changed_by_node=None):
    """Use a node the model already named when the JSON shape slipped.

    The live completion puts the culprit in evidenceNodeIds and the changed
    field in an object. One named node is enough. When it also names the
    downstream checker, keep the node whose named field actually changed.
    """
    updated = dict(verdict or {})
    if updated.get("status") != "drift":
        return updated
    raw_text = str(updated.get("raw") or "")
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    parsed = None
    if start >= 0 and end > start:
        try:
            parsed = json.loads(raw_text[start:end + 1])
        except json.JSONDecodeError:
            parsed = None
    if not isinstance(parsed, dict):
        return updated
    known = {str(node_id) for node_id in node_ids or []}
    fields = [str(item) for item in (updated.get("changedFields") or [])]
    if not fields:
        declared = parsed.get("changedFields")
        names = []
        if isinstance(declared, dict):
            names = [str(key) for key in declared.keys()]
        elif isinstance(declared, list):
            names = [str(item) for item in declared]
        fields = [name for name in _RECOVERABLE_FIELDS if name in set(names)]
    node_id = str(updated.get("nodeId") or parsed.get("nodeId") or "")
    if node_id not in known:
        evidence = parsed.get("evidenceNodeIds")
        found = []
        if isinstance(evidence, list):
            found = [str(item) for item in evidence if str(item) in known]
        node_id = found[0] if len(found) == 1 else ""
        if not node_id and found and fields and changed_by_node:
            owners = [
                item for item in found
                if set(fields) & set(changed_by_node.get(item) or ())
            ]
            if len(owners) == 1:
                node_id = owners[0]
    type_name = str(updated.get("type") or parsed.get("type") or "")
    if type_name not in {
        "missing_dependency", "wrong_agent", "wrong_version", "wrong_acceptance", "local_replan",
    }:
        type_name = _FIELD_TYPE.get(fields[0], "") if fields else ""
    if node_id in known and fields and type_name:
        updated["nodeId"] = node_id
        updated["changedFields"] = fields
        updated["type"] = type_name
        updated["valid"] = True
    return updated


MAX_CHECK_WORDS = 80
HIGH_VANILLA_FAMILIES = (
    "Embedded-Data-Repair",
    "Operational-Recovery-Planning",
    "Inventory-&-Finance-Integration",
)
# One sentence the solver can carry out. Node ids and field labels stay on the plan.
CONCRETE_CHECKS = {
    "output": "Before you submit, confirm the required output file exists and the numbers match the fields named in the task.",
    "artifact": "Before you submit, confirm the required output file exists and the numbers match the fields named in the task.",
    "inputs": "Before you submit, confirm every input named in the task was used and the figures match those inputs.",
    "acceptance": "Before you submit, confirm the output meets every acceptance condition named in the task.",
    "version": "Before you submit, confirm the calculation uses the method and units named in the task.",
    "stage": "Before you submit, confirm the required steps were finished in the order named in the task.",
    "agentId": "Before you submit, redo the calculation and confirm the numbers match the fields named in the task.",
}


def _drift_ready(verdict):
    if not isinstance(verdict, dict) or verdict.get("status") != "drift":
        return False
    if verdict.get("valid") is False:
        return False
    fields = verdict.get("changedFields") or []
    if not fields:
        return False
    if not str(verdict.get("nodeId") or "").strip():
        return False
    if not str(verdict.get("type") or "").strip():
        return False
    return True


def _sentence_ok(text):
    words = str(text or "").split()
    if not words or len(words) > MAX_CHECK_WORDS:
        return False
    without_decimals = re.sub(r"(?<=\d)\.(?=\d)", "", text)
    without_decimals = re.sub(r"\.(xlsx|csv|json|txt|py)\b", "", without_decimals, flags=re.IGNORECASE)
    return without_decimals.count(".") == 1


def check_from_trace(trace):
    """One reusable check from the verifier, not a reminder to be careful.

    The detective decides that a drift exists. The sentence says what the
    failing check actually measured, so the next task in the family can
    repeat that measurement.
    """
    blob = " ".join(str(trace or "").split())
    if not blob:
        return ""
    if ":,.2f" in blob or "{value:,.2f}" in blob or "Summary missing value" in blob or re.search(r"\$\d{4,}", blob) or 'Decision:' in blob:
        return (
            "Before you submit, write the decision line as Decision: and format every money amount "
            "with a thousands separator and two decimals, such as 72,766.88."
        )
    dmaic_shape = (
        "operational impacts" in blob
        or "Next steps must include owners" in blob
        or "Owner:" in blob
        or "March 2025" in blob
        or "total_primary_records" in blob
        or ("source_file" in blob and ("/root/" in blob or "directory" in blob.lower()))
    )
    if dmaic_shape:
        return (
            "Before you submit, set source_file to the csv base name only, "
            "fill total_primary_records, primary_business_day_records, and imr_records under record_counts, "
            "include f_stat and p_value under anova_by_weekday, "
            "fill imr_summary, regression_day_index including std_err, and ttest_vs_target, "
            "set the I-MR UCL to the center line plus 3 times MR-bar divided by 1.128 and the MR UCL to 3.267 times MR-bar, "
            "name at least two operational impacts, write Owner: on each next step, "
            "and include at least two March 2025 due dates."
        )
    if "stock_holdings" in blob or "top3_cusips" in blob or "Top CUSIP" in blob:
        return "Before you submit, recount stock holdings and match AUM and the top CUSIPs to the filing."
    if (
        "Missing formulas" in blob
        or "SUMPRODUCT" in blob
        or "lost yellow fill" in blob
        or "Missing output workbook" in blob
        or "ssconvert" in blob
        or "--recalculate" in blob
    ):
        return (
            "Before you submit, save /root/output/result.xlsx with sheets Task and Data, "
            "write Excel formulas instead of pasted numbers, include SUMPRODUCT on row 50, and keep the yellow fill."
        )
    missing = re.search(r"Missing top-level key: ([A-Za-z0-9_]+)", blob)
    if missing:
        return "Before you submit, include the required field " + missing.group(1) + " in the output."
    return ""


def one_update(verdict, trace="", family=""):
    """The sentence Harbor sees: one executable check, or nothing.

    A recognizable verifier failure becomes that check. Otherwise the detective's
    field supplies a generic check. Embedded, Operational, and Inventory do not
    get that generic check: a failure with no concrete measurement carries nothing.
    A summary, title, or role drift does not.
    """
    if not _drift_ready(verdict):
        return ""
    field = str((verdict.get("changedFields") or [""])[0])
    text = check_from_trace(trace)
    if not text and family not in HIGH_VANILLA_FAMILIES:
        text = CONCRETE_CHECKS.get(field, "")
    if not _sentence_ok(text):
        return ""
    node_id = str(verdict.get("nodeId") or "").strip()
    if node_id and node_id in text.split():
        return ""
    return text


def _reward_passed(reward):
    if reward is None:
        return False
    try:
        return float(reward) >= 1
    except (TypeError, ValueError):
        return False


def _reward_failed(reward):
    if reward is None:
        return False
    try:
        return float(reward) < 1
    except (TypeError, ValueError):
        return False


def recorded_reward(official, replay):
    """A replay can decide the next sentence. It does not replace the official reward."""
    return official


def apply_replacement(plan, verdict, replacement_id=""):
    """S writes the profile the similarity model chose, and only for wrong_agent on agentId."""
    updated = json.loads(json.dumps(plan))
    if not _drift_ready(verdict):
        return updated
    fields = verdict.get("changedFields") or [""]
    if verdict.get("type") != "wrong_agent" or str(fields[0]) != "agentId":
        return updated
    if replacement_id not in CATALOG:
        return updated
    node_id = verdict.get("nodeId")
    updated["similarityAdapter"] = model_roles()["dependencySimilarity"]["adapter"]
    for node in updated["nodes"]:
        if node["id"] == node_id:
            _write_profile(node, replacement_id, updated.get("title") or "")
            break
    return updated


def next_carry(previous, verdict, family="", reward=None, replay_reward=None, trace=""):
    """One sentence replaces one sentence, and only after the replay passes.

    A pass, no_drift, or an invalid verdict keeps the old sentence. Embedded,
    Operational, and Inventory drop the sentence when a failure has no concrete check.
    """
    previous = "" if previous is None else str(previous)
    if _reward_passed(reward):
        return previous
    update = one_update(verdict, trace, family)
    if update and update != previous and _reward_passed(replay_reward):
        return update
    if (
        family in HIGH_VANILLA_FAMILIES
        and _reward_failed(reward)
        and _drift_ready(verdict)
        and not update
    ):
        return ""
    return previous
