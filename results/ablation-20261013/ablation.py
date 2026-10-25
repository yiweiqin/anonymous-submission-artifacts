"""SkillFlow development ablation.

Reference sends the adopted planning update and the current three-person
summary into the next Harbor task. Each other arm changes one declared
factor. Ledgers stay in this directory. The main-table record is not written.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys
import threading
import time
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MAIN = REPO / "code" / "evaluation" / "skillflow"
DETECTIVE = REPO / "code" / "evaluation" / "detective-deploy"
sys.path.insert(0, str(MAIN))
sys.path.insert(0, str(DETECTIVE))
sys.path.insert(0, str(HERE))

import baselines
import harbor_bridge
import janus_full
import package
from rdmd_detective import build_case_prompt

LEDGERS = HERE / "ledgers"
SUMMARY = HERE / "summary.json"
MANIFEST = HERE / "manifest.json"
RANDOM_SEED = 20261013
STRENGTH = ("calculator", "checker", "reviewer", "worker", "planner")
KIND = "skillflow-ablation-20261013"
TEXT_FIELDS = ("title", "role", "artifact", "stage", "inputs", "output", "summary", "acceptance")

ARMS = {
    "reference": {"plan": True, "staff": True, "evolve": True, "writer": "rule", "graph": "full", "locate": True, "minimum": True, "select": "reference"},
    "m9-plan": {"plan": True, "staff": False, "evolve": True, "writer": "rule", "graph": "full", "locate": True, "minimum": True, "select": "reference"},
    "m9-staff": {"plan": False, "staff": True, "evolve": True, "writer": "rule", "graph": "full", "locate": True, "minimum": True, "select": "reference"},
    "m9-neither": {"plan": False, "staff": False, "evolve": False, "writer": "rule", "graph": "full", "locate": True, "minimum": True, "select": "reference"},
    "m3-redundant": {"plan": True, "staff": True, "evolve": True, "writer": "rule", "graph": "full", "locate": True, "minimum": False, "select": "reference"},
    "m1-no-plan": {"plan": True, "staff": True, "evolve": True, "writer": "rule", "graph": "no-plan", "locate": True, "minimum": True, "select": "reference"},
    "m1-no-exec": {"plan": True, "staff": True, "evolve": True, "writer": "rule", "graph": "no-exec", "locate": True, "minimum": True, "select": "reference"},
    "m1-outcome": {"plan": True, "staff": True, "evolve": True, "writer": "rule", "graph": "outcome", "locate": True, "minimum": True, "select": "reference"},
    "m2-no-locate": {"plan": True, "staff": True, "evolve": True, "writer": "trace", "graph": "full", "locate": False, "minimum": True, "select": "reference"},
    "m4-similarity": {"plan": True, "staff": True, "evolve": True, "writer": "rule", "graph": "full", "locate": True, "minimum": True, "select": "similarity"},
    "m4-random": {"plan": True, "staff": True, "evolve": True, "writer": "rule", "graph": "full", "locate": True, "minimum": True, "select": "random"},
    "m4-strongest": {"plan": True, "staff": True, "evolve": True, "writer": "rule", "graph": "full", "locate": True, "minimum": True, "select": "strongest"},
    "m4-dependency": {"plan": True, "staff": True, "evolve": True, "writer": "rule", "graph": "full", "locate": True, "minimum": True, "select": "dependency"},
    "m8-rule": {"plan": True, "staff": True, "evolve": True, "writer": "rule", "graph": "full", "locate": True, "minimum": True, "select": "reference"},
    "m8-trained": {"plan": True, "staff": True, "evolve": True, "writer": "trained", "graph": "full", "locate": True, "minimum": True, "select": "reference"},
    "m8-base": {"plan": True, "staff": True, "evolve": True, "writer": "base", "graph": "full", "locate": True, "minimum": True, "select": "reference"},
    "m8-api": {"plan": True, "staff": True, "evolve": True, "writer": "api", "graph": "full", "locate": True, "minimum": True, "select": "reference"},
}
PROOF = ("reference", "m9-plan", "m9-staff")
LEDGER_LOCK = threading.Lock()
# Containers on the Harbor host use about 30MB and mostly wait on the task API.
# Six overlaps that wait. Eight made sshd drop banners on this 2-core host.
# The 6GB disk stop in wait_for_disk is unchanged.
HARBOR_LIMIT = 6
HARBOR = threading.Semaphore(HARBOR_LIMIT)
FAMILY_WORKERS = 8


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ledger_path(arm):
    return LEDGERS / (arm + ".jsonl")


def read_rows(arm):
    path = ledger_path(arm)
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def append_row(arm, row):
    LEDGERS.mkdir(parents=True, exist_ok=True)
    with LEDGER_LOCK:
        with ledger_path(arm).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        write_summary()


def prefix_state(rows, family, tasks):
    by_task = {}
    for row in rows:
        if row.get("family") != family or row.get("record") != "task":
            continue
        if row.get("reward") is None or row.get("error"):
            continue
        by_task[row["task"]] = row
    done = []
    carry = ""
    staff = None
    scores = None
    for task in tasks:
        row = by_task.get(task)
        if row is None:
            break
        done.append(task)
        carry = row.get("carry") or ""
        staff = row.get("staff") or staff
        scores = row.get("staffScores") or scores
    return done, carry, staff, scores


def mask_fields(graph, label):
    updated = json.loads(json.dumps(graph))
    for node in updated.get("nodes") or []:
        for field in TEXT_FIELDS:
            node[field] = label
    return updated


def detective_case(family, task, plan, execution, mode, reward):
    plan_seen, exec_seen = plan, execution
    if mode == "no-plan":
        plan_seen = mask_fields(plan, "masked")
    elif mode == "no-exec":
        exec_seen = mask_fields(execution, "masked")
    elif mode == "outcome":
        label = "passed" if harbor_bridge._reward_passed(reward) else "failed"
        plan_seen = mask_fields(plan, label)
        exec_seen = mask_fields(execution, label)
    return harbor_bridge.detective_case(family + "/" + task, plan_seen, exec_seen)


def rng_for(family, task, slot):
    digest = hashlib.sha256(f"{RANDOM_SEED}|{family}|{task}|{slot}".encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def strongest(candidates):
    for profile in STRENGTH:
        if profile in candidates:
            return profile
    return candidates[0]


def choose_initial(spec, scores, family):
    if spec["select"] == "strongest":
        return {"plan": "planner", "work": strongest(harbor_bridge.WORK_CANDIDATES), "check": strongest(harbor_bridge.CHECK_CANDIDATES)}
    if spec["select"] == "random":
        return {
            "plan": "planner",
            "work": rng_for(family, "team", "work").choice(harbor_bridge.WORK_CANDIDATES),
            "check": rng_for(family, "team", "check").choice(harbor_bridge.CHECK_CANDIDATES),
        }
    if spec["select"] == "similarity":
        work = harbor_bridge._best(scores, "planner", set(harbor_bridge.WORK_CANDIDATES), "similarity") or "worker"
        check = harbor_bridge._best(scores, work, set(harbor_bridge.CHECK_CANDIDATES), "similarity") or "checker"
        return {"plan": "planner", "work": work, "check": check}
    return harbor_bridge.choose_staff(scores)


def argmax_same(scores):
    work_d = harbor_bridge._best(scores, "planner", set(harbor_bridge.WORK_CANDIDATES), "dependency")
    work_s = harbor_bridge._best(scores, "planner", set(harbor_bridge.WORK_CANDIDATES), "similarity")
    check_left = work_d or "worker"
    check_d = harbor_bridge._best(scores, check_left, set(harbor_bridge.CHECK_CANDIDATES), "dependency")
    check_s = harbor_bridge._best(scores, check_left, set(harbor_bridge.CHECK_CANDIDATES), "similarity")
    return {"work": work_d == work_s, "check": check_d == check_s, "workDependency": work_d, "workSimilarity": work_s}


def replacement_for(spec, current, scores, family, task):
    if spec["select"] == "dependency":
        return ""
    if spec["select"] == "random":
        pool = [profile for profile in harbor_bridge.CATALOG if profile != current]
        return rng_for(family, task, current).choice(pool)
    if spec["select"] == "strongest":
        for profile in STRENGTH:
            if profile != current and profile in harbor_bridge.CATALOG:
                return profile
        return ""
    return harbor_bridge.choose_replacement(current, scores)


def rule_candidate(verdict, trace, family, spec):
    if spec["writer"] == "trace":
        text = harbor_bridge.check_from_trace(trace)
        if spec["minimum"] and not harbor_bridge._sentence_ok(text):
            return ""
        return text
    if not spec["minimum"]:
        if not harbor_bridge._drift_ready(verdict):
            return ""
        field = str((verdict.get("changedFields") or [""])[0])
        text = harbor_bridge.check_from_trace(trace)
        if not text and family not in harbor_bridge.HIGH_VANILLA_FAMILIES:
            text = harbor_bridge.CONCRETE_CHECKS.get(field, "")
        return text
    return harbor_bridge.one_update(verdict, trace, family)


def adopt_carry(previous, candidate, family, reward, replay_reward, spec, verdict):
    if spec["writer"] == "rule" and spec["minimum"] and spec["locate"]:
        return harbor_bridge.next_carry(
            previous, verdict, family=family, reward=reward, replay_reward=replay_reward, trace="")
    previous = "" if previous is None else str(previous)
    if harbor_bridge._reward_passed(reward):
        return previous
    if candidate and candidate != previous and harbor_bridge._reward_passed(replay_reward):
        return candidate
    if (
        spec["writer"] == "rule"
        and family in harbor_bridge.HIGH_VANILLA_FAMILIES
        and harbor_bridge._reward_failed(reward)
        and harbor_bridge._drift_ready(verdict)
        and not candidate
    ):
        return ""
    return previous


def blank_usage():
    return {
        "harborCalls": 0, "harborPromptTokens": 0, "harborCompletionTokens": 0, "harborWallSeconds": 0.0,
        "detectiveCalls": 0, "detectivePromptTokens": None, "detectiveCompletionTokens": None,
        "dsCalls": 0, "dsPromptTokens": None, "dsCompletionTokens": None,
        "apiCalls": 0, "apiPromptTokens": None, "apiCompletionTokens": None,
    }


def add_harbor(usage, payload):
    usage["harborCalls"] += int(payload.get("modelCalls") or 0)
    usage["harborPromptTokens"] += int(payload.get("promptTokens") or 0)
    usage["harborCompletionTokens"] += int(payload.get("completionTokens") or 0)
    usage["harborWallSeconds"] += float(payload.get("wallSeconds") or 0)


def add_pair(usage, prefix, prompt, completion):
    calls_key = prefix + "Calls"
    prompt_key = prefix + "PromptTokens"
    completion_key = prefix + "CompletionTokens"
    missing_key = prefix + "TokensMissing"
    usage[calls_key] += 1
    if usage.get(missing_key) or prompt is None or completion is None:
        usage[missing_key] = True
        usage[prompt_key] = None
        usage[completion_key] = None
        return
    usage[prompt_key] = int(usage[prompt_key] or 0) + int(prompt)
    usage[completion_key] = int(usage[completion_key] or 0) + int(completion)


def add_ds(usage, rows):
    for row in rows or []:
        add_pair(usage, "ds", row.get("promptTokens"), row.get("completionTokens"))


def startup_race(payload):
    """Several Harbor processes importing litellm together can fail once. The trial did not score."""
    if payload.get("reward") is not None:
        return False
    error = payload.get("error") or ""
    needles = (
        "ImportError", "circular import", "DeadlockError", "SSH protocol banner",
        "no_result", "Connection reset", "10054", "RewardFileNotFound",
    )
    return any(needle in error for needle in needles)


def connection_failure(exc):
    """The Harbor or GPU host dropped before a score was written."""
    text = type(exc).__name__ + " " + str(exc)
    needles = (
        "NoValidConnectionsError", "Unable to connect", "gaierror",
        "Connection reset", "10054", "10051", "SSH protocol banner", "timed out",
        "Connection aborted", "Connection refused", "Error reading SSH",
    )
    return any(needle in text for needle in needles)


def harbor_call(family, task, arm, text, kind):
    with HARBOR:
        payload = None
        for attempt in range(8):
            if attempt:
                time.sleep(min(60, 5 * attempt))
            try:
                baselines.wait_for_disk()
                payload = baselines.run_harbor(family, task, arm, text, kind)
            except Exception as exc:
                if attempt < 7 and connection_failure(exc):
                    baselines.say("RETRY", arm, family, task, attempt + 1)
                    continue
                raise
            if not startup_race(payload):
                return payload
            baselines.say("RETRY", arm, family, task, attempt + 1)
        return payload


def api_completion(case):
    requested = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
    prompt = build_case_prompt(case)
    body = json.dumps({
        "model": requested,
        "temperature": 0,
        "max_tokens": 160,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    base = os.environ["DEEPSEEK_API_BASE"].rstrip("/")
    request = urllib.request.Request(
        base + "/chat/completions",
        data=body,
        headers={
            "Authorization": "Bearer " + os.environ["DEEPSEEK_API_KEY"],
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = json.loads(response.read().decode("utf-8"))
    choice = payload["choices"][0]["message"]["content"]
    usage = payload.get("usage") or {}
    returned = str(payload.get("model") or "")
    return {
        "text": choice,
        "promptTokens": usage.get("prompt_tokens"),
        "completionTokens": usage.get("completion_tokens"),
        "requested": requested,
        "returned": returned,
        "nameMatch": requested == returned or returned.endswith(requested),
    }


def model_sentence(text, spec):
    raw = str(text or "").strip()
    if spec["minimum"] and not harbor_bridge._sentence_ok(raw):
        return "", True
    if not raw:
        return "", True
    return raw, False


def plan_from_staff(family, staff):
    plan = harbor_bridge.staff_plan(family)
    by_id = {item.get("id"): item.get("agentId") for item in staff or [] if isinstance(item, dict)}
    for node in plan["nodes"]:
        profile_id = by_id.get(node["id"])
        if profile_id in harbor_bridge.CATALOG:
            harbor_bridge._write_profile(node, profile_id, family)
    return plan


def run_family(arm, family, tasks, detective, roles, stop, canary_only):
    spec = ARMS[arm]
    done, carry, staff, saved_scores = prefix_state(read_rows(arm), family, tasks)
    if canary_only:
        pass
    plan = plan_from_staff(family, staff) if staff else harbor_bridge.staff_plan(family)
    scores = saved_scores
    if spec["evolve"] and not staff:
        if spec["select"] == "strongest":
            choice = choose_initial(spec, [], family)
            plan = harbor_bridge.apply_staff(plan, choice, family)
        elif spec["select"] == "random":
            choice = choose_initial(spec, [], family)
            plan = harbor_bridge.apply_staff(plan, choice, family)
        else:
            pairs = harbor_bridge.staffing_pairs(family)
            raw = detective.score_pairs(pairs, roles["dsAdapter"], baselines.job_name_for("staff", arm, family, "team"))
            by_id = {row.get("id"): row for row in raw}
            scores = []
            for pair in pairs:
                got = by_id.get(pair["id"]) or {}
                scores.append({
                    "left": pair["left"], "right": pair["right"],
                    "dependency": got.get("dependency"), "similarity": got.get("similarity"),
                    "promptTokens": got.get("promptTokens"), "completionTokens": got.get("completionTokens"),
                })
            if not any(row["dependency"] is not None for row in scores):
                raise SystemExit("ds_unscored")
            choice = choose_initial(spec, scores, family)
            plan = harbor_bridge.apply_staff(plan, choice, family)
        staff = janus_full.staff_of(plan)
    count_staff = bool(scores) and not done
    for task in tasks:
        if stop.is_set() or task in done:
            continue
        started = time.monotonic()
        usage = blank_usage()
        if count_staff:
            add_ds(usage, scores)
            count_staff = False
        text = package.harbor_text(carry if spec["plan"] else "", plan, spec["plan"], spec["staff"])
        baselines.say("RUN", arm, family, task, package.text_sha256(text)[:12])
        payload = harbor_call(family, task, arm, text, KIND)
        add_harbor(usage, payload)
        error = baselines.scrub(payload.get("error") or "")
        reward = payload.get("reward")
        verdict = {"status": "not_called", "valid": False, "changedFields": [], "raw": ""}
        replay_reward = None
        selection = []
        coverage = False
        same = argmax_same(scores or [])
        if spec["evolve"] and reward is not None and not error:
            execution = harbor_bridge.execution_graph(
                plan, 1 if harbor_bridge._reward_passed(reward) else 0, baselines.scrub(payload.get("trace") or ""))
            case = detective_case(family, task, plan, execution, spec["graph"], reward)
            verdict = detective.ask(case, baselines.job_name_for("detective", arm, family, task))
            add_pair(usage, "detective", verdict.get("promptTokens"), verdict.get("completionTokens"))
            sentence_raw = verdict.get("raw") or ""
            if spec["writer"] == "base":
                base = detective.ask(case, baselines.job_name_for("base", arm, family, task), adapter="")
                add_pair(usage, "detective", base.get("promptTokens"), base.get("completionTokens"))
                sentence_raw = base.get("raw") or ""
            elif spec["writer"] == "api":
                written = api_completion(case)
                add_pair(usage, "api", written["promptTokens"], written["completionTokens"])
                sentence_raw = written["text"]
                if not written["nameMatch"]:
                    error = "model_name_mismatch"
            verdict = harbor_bridge.recover_verdict(
                verdict, [node["id"] for node in plan["nodes"]], harbor_bridge.changed_fields_by_node(plan, execution))
            trace = baselines.scrub(payload.get("trace") or "")
            fields_now = verdict.get("changedFields") or []
            if spec["select"] != "dependency" and verdict.get("type") == "wrong_agent" and fields_now and str(fields_now[0]) == "agentId":
                current = ""
                for node in plan["nodes"]:
                    if node["id"] == verdict.get("nodeId"):
                        current = node.get("agentId") or ""
                if current in harbor_bridge.CATALOG:
                    pairs = harbor_bridge.replacement_pairs(current, family)
                    raw = detective.score_pairs(pairs, roles["dsAdapter"], baselines.job_name_for("swap", arm, family, task))
                    add_ds(usage, raw)
                    similarity_scores = []
                    for pair in pairs:
                        got = {row.get("id"): row for row in raw}.get(pair["id"]) or {}
                        similarity_scores.append({
                            "left": pair["left"], "right": pair["right"], "similarity": got.get("similarity"),
                        })
                    replacement = replacement_for(spec, current, similarity_scores, family, task)
                    plan = harbor_bridge.apply_replacement(plan, verdict, replacement)
            if spec["writer"] in {"trained", "base", "api"}:
                candidate, coverage = model_sentence(sentence_raw, spec)
            else:
                candidate = rule_candidate(verdict, trace, family, spec)
            replay_reward = None
            if candidate and candidate != carry and not harbor_bridge._reward_passed(reward) and not error:
                replay_text = package.harbor_text(candidate, plan, spec["plan"], spec["staff"])
                replay = harbor_call(family, task, arm, replay_text, KIND + "-replay")
                add_harbor(usage, replay)
                replay_reward = replay.get("reward")
                replay_error = baselines.scrub(replay.get("error") or "")
                reason = harbor_bridge.fatal_reason(replay_error)
                if reason in {"Missing credentials", "No space left", "missing_api_key"}:
                    error = reason
                elif replay_reward is None:
                    error = replay_error[-200:]
            next_carry = adopt_carry(carry, candidate, family, reward, replay_reward, spec, verdict if spec["locate"] else {"status": "drift", "valid": False})
            if spec["writer"] == "rule" and spec["minimum"] and spec["locate"]:
                next_carry = harbor_bridge.next_carry(
                    carry, verdict, family=family, reward=reward, replay_reward=replay_reward, trace=trace)
            carry = next_carry
            staff = janus_full.staff_of(plan)
            if candidate:
                selection.append({"task": task, "reward": replay_reward, "kept": carry == candidate})
        official = harbor_bridge.recorded_reward(reward, replay_reward)
        row = {
            "record": "task",
            "kind": KIND,
            "exploratory": True,
            "significanceClaim": False,
            "arm": arm,
            "family": family,
            "task": task,
            "reward": official,
            "error": error,
            "carry": carry,
            "staff": staff or [],
            "staffScores": scores,
            "harborTextSha256": package.text_sha256(text),
            "harborTextChars": len(text),
            "coverageFailure": coverage,
            "argmaxSame": same,
            "graph": spec["graph"],
            "executionGraph": "terminal projection, not stepwise tool events",
            "verdictStatus": verdict.get("status"),
            "selectionTrials": selection,
            "wallSeconds": round(time.monotonic() - started, 3),
            **usage,
        }
        append_row(arm, row)
        baselines.say("DONE", arm, family, task, official, row["harborTextSha256"][:12])
        reason = harbor_bridge.fatal_reason(error)
        if reason:
            stop.set()
            raise SystemExit(reason)
        if error or reward is None:
            return


def _passed(reward):
    try:
        return float(reward) >= 1
    except (TypeError, ValueError):
        return False


def _sum_cost(rows, key):
    calls = {
        "detectivePromptTokens": "detectiveCalls",
        "detectiveCompletionTokens": "detectiveCalls",
        "dsPromptTokens": "dsCalls",
        "dsCompletionTokens": "dsCalls",
        "apiPromptTokens": "apiCalls",
        "apiCompletionTokens": "apiCalls",
    }[key]
    relevant = [row for row in rows if row.get(calls)]
    if any(row.get(key) is None for row in relevant):
        return None
    return sum(row.get(key) or 0 for row in relevant)


def write_summary():
    """Called with LEDGER_LOCK held. Development numbers stay exploratory."""
    loaded = {arm: [row for row in read_rows_unlocked(arm) if row.get("record") == "task"] for arm in ARMS}
    reference = loaded["reference"]
    ref_hash = {(row["family"], row["task"]): row.get("harborTextSha256") for row in reference if not row.get("error")}
    neither = loaded["m9-neither"]
    families = sorted({row["family"] for row in reference})
    arms = {}
    for arm, rows in loaded.items():
        effect_path = HERE / "effects" / (arm + ".json")
        zero = json.loads(effect_path.read_text(encoding="utf-8")) if effect_path.is_file() else None
        paired = 0
        triggered = 0
        for row in rows:
            if row.get("error"):
                continue
            key = (row["family"], row["task"])
            if key in ref_hash:
                paired += 1
                if row.get("harborTextSha256") != ref_hash[key]:
                    triggered += 1
        worse = None
        difference = 0 if zero else None
        if zero is None and reference and neither:
            worse = 0
            ref_lifts = []
            arm_lifts = []
            for family in families:
                tasks = [row["task"] for row in reference if row["family"] == family and not row.get("error")]
                def rate(source):
                    by = {row["task"]: row for row in source if row["family"] == family and not row.get("error") and row.get("reward") is not None}
                    if any(task not in by for task in tasks):
                        return None
                    if not tasks:
                        return None
                    return sum(_passed(by[task]["reward"]) for task in tasks) / len(tasks)
                ref_rate, arm_rate, base_rate = rate(reference), rate(rows), rate(neither)
                if None in (ref_rate, arm_rate, base_rate):
                    worse = None
                    ref_lifts = []
                    break
                ref_lifts.append(ref_rate - base_rate)
                arm_lifts.append(arm_rate - base_rate)
                if arm_rate < ref_rate:
                    worse += 1
            if ref_lifts:
                difference = (sum(ref_lifts) / len(ref_lifts)) - (sum(arm_lifts) / len(arm_lifts))
        arms[arm] = {
            "exploratory": True,
            "significanceClaim": False,
            "tasks": len(rows),
            "scored": sum(1 for row in rows if row.get("reward") is not None and not row.get("error")),
            "infrastructureFailures": sum(1 for row in rows if row.get("error") and row.get("error") != "missing_task_dir"),
            "liftDifference": difference,
            "triggerRate": 0 if zero else (triggered / paired if paired else None),
            "worseFamilies": 0 if zero else worse,
            "harborCalls": sum(row.get("harborCalls") or 0 for row in rows),
            "harborPromptTokens": sum(row.get("harborPromptTokens") or 0 for row in rows),
            "harborCompletionTokens": sum(row.get("harborCompletionTokens") or 0 for row in rows),
            "harborWallSeconds": round(sum(row.get("harborWallSeconds") or 0 for row in rows), 3),
            "detectiveCalls": sum(row.get("detectiveCalls") or 0 for row in rows),
            "detectivePromptTokens": _sum_cost(rows, "detectivePromptTokens"),
            "detectiveCompletionTokens": _sum_cost(rows, "detectiveCompletionTokens"),
            "dsCalls": sum(row.get("dsCalls") or 0 for row in rows),
            "dsPromptTokens": _sum_cost(rows, "dsPromptTokens"),
            "dsCompletionTokens": _sum_cost(rows, "dsCompletionTokens"),
            "apiCalls": sum(row.get("apiCalls") or 0 for row in rows),
            "apiPromptTokens": _sum_cost(rows, "apiPromptTokens"),
            "apiCompletionTokens": _sum_cost(rows, "apiCompletionTokens"),
            "wallSeconds": round(sum(row.get("wallSeconds") or 0 for row in rows), 3),
            "estimatedUsd": None,
            "zeroFromIdenticalCanary": bool(zero),
        }
    payload = {"exploratory": True, "significanceClaim": False, "kind": KIND, "arms": arms}
    SUMMARY.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_rows_unlocked(arm):
    path = ledger_path(arm)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def task_hashes(arm, families):
    found = {}
    for row in read_rows(arm):
        if row.get("record") != "task" or row.get("family") not in families or row.get("error"):
            continue
        found[(row["family"], row["task"])] = row.get("harborTextSha256")
    return found


def proof_differs(families, present):
    needed = {(family, task) for family in families for task in present[family]}
    texts = {arm: task_hashes(arm, set(families)) for arm in PROOF}
    if any(set(texts[arm]) != needed for arm in PROOF):
        return False
    return all(len({texts[arm][key] for arm in PROOF}) == 3 for key in needed)


def same_as_reference(arm, families, present):
    needed = {(family, task) for family in families for task in present[family]}
    ref = task_hashes("reference", set(families))
    got = task_hashes(arm, set(families))
    if set(ref) != needed or set(got) != needed:
        return None
    return all(ref[key] == got[key] for key in needed)


def write_zero_effect(arm, families, present):
    path = HERE / "effects" / (arm + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    needed = [(family, task) for family in families for task in present[family]]
    ref = task_hashes("reference", set(families))
    got = task_hashes(arm, set(families))
    payload = {
        "arm": arm,
        "exploratory": True,
        "significanceClaim": False,
        "effect": 0,
        "triggerRate": 0,
        "worseFamilies": 0,
        "reason": "canary harbor text matches the reference byte for byte",
        "hashes": [{"family": family, "task": task, "sha256": got[(family, task)], "referenceSha256": ref[(family, task)]} for family, task in needed],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def preflight(roles):
    ssh = janus_full.gpu_client()
    try:
        code, out, _err = baselines.exec_text(ssh, "hostname", 30)
        host = out.strip()
        baselines.say("HOST", host)
        if code != 0:
            raise SystemExit("model_host_unreachable")
        code, out, _err = baselines.exec_text(ssh, "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader", 30)
        baselines.say("GPU", out.strip())
        required_gpu = os.environ.get("JANUS_REQUIRED_GPU", "")
        if code != 0 or (required_gpu and required_gpu not in out):
            raise SystemExit("unexpected_gpu")
        store = os.environ.get("JANUS_MODEL_STORE", "/data/modelstore")
        code, avail, _err = baselines.exec_text(ssh, "df -B1 --output=avail " + store + " | tail -1", 30)
        if code != 0 or int(avail.strip()) < 6 * 1024 ** 3:
            raise SystemExit("model_disk_below_6gb")
        for path, label in (
            (roles["baseModel"].rstrip("/") + "/config.json", "qwen"),
            (roles["detectiveAdapter"].rstrip("/") + "/adapter_config.json", "detective"),
            (roles["dsAdapter"].rstrip("/") + "/adapter_config.json", "dependency_similarity"),
        ):
            if not janus_full.remote_exists(ssh, path):
                baselines.say("MISSING", label)
                raise SystemExit("missing_on_model_host")
            baselines.say("OK", label)
        if not janus_full.weight_ready(ssh, roles["detectiveAdapter"]):
            raise SystemExit("missing_on_model_host")
        if not janus_full.weight_ready(ssh, roles["dsAdapter"]):
            raise SystemExit("missing_on_model_host")
    finally:
        ssh.close()


def write_manifest(split, roles):
    files = [
        HERE / "ablation.py", HERE / "package.py",
        MAIN / "harbor_bridge.py", MAIN / "janus_full.py", MAIN / "remote_one_trial.py",
        DETECTIVE / "rdmd_detective.py",
    ]
    payload = {
        "kind": KIND,
        "exploratory": True,
        "significanceClaim": False,
        "randomSeed": RANDOM_SEED,
        "strengthOrder": list(STRENGTH),
        "development": list(split["development"]),
        "canary": harbor_bridge.canary_families(split),
        "gateClosed": True,
        "lockedClosed": True,
        "taskModel": roles["taskModel"],
        "temperature": 0,
        "harborConcurrency": HARBOR_LIMIT,
        "detectiveAdapter": roles["detectiveAdapter"],
        "dsAdapter": roles["dsAdapter"],
        "baseModel": roles["baseModel"],
        "fileSha256": {path.name: sha_file(path) for path in files},
        "executionGraph": "terminal projection, not stepwise tool events",
    }
    MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_plans(split):
    families = list(split["development"])
    plans = []
    ssh = baselines.light_client()
    try:
        baselines.ensure_remote_files(ssh)
        for family in families:
            harbor_bridge.assert_janus_request(split, family, "janus_full")
            present, missing = baselines.ranking(ssh, family)
            plans.append((family, present, missing))
    finally:
        ssh.close()
    return plans


def pool_map(jobs, detective, roles, stop):
    errors = []
    with ThreadPoolExecutor(max_workers=FAMILY_WORKERS) as pool:
        futures = [
            pool.submit(run_family, arm, family, tasks, detective, roles, stop, False)
            for arm, family, tasks in jobs
        ]
        pending = set(futures)
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                try:
                    future.result()
                except BaseException as exc:
                    errors.append(type(exc).__name__ + ":" + str(exc)[:240])
                    baselines.say("FAMILY_STOP", errors[-1])
    return errors


def main():
    split = harbor_bridge.load_json(MAIN / "family-split.json")
    if split.get("lockedMayOpen") is not False:
        raise SystemExit("locked_split_opened")
    roles = harbor_bridge.resolved_roles(os.environ)
    if roles["taskModel"] != "deepseek-flash":
        raise SystemExit("task_model_must_stay_deepseek_flash")
    write_manifest(split, roles)
    preflight(roles)
    plans = load_plans(split)
    present = {family: tasks for family, tasks, _missing in plans}
    for family, _tasks, missing in plans:
        for name in missing:
            append_row("reference", {
                "record": "task", "kind": KIND, "exploratory": True, "arm": "reference",
                "family": family, "task": name, "reward": None, "error": "missing_task_dir",
            })
    canary = harbor_bridge.canary_families(split)
    detective = janus_full.Detective(roles["baseModel"], roles["detectiveAdapter"])
    stop = threading.Event()
    jobs = [(arm, family, present[family]) for arm in PROOF for family in canary]
    errors = pool_map(jobs, detective, roles, stop)
    if errors or not proof_differs(canary, present):
        baselines.say("CANARY_TEXT_NOT_DISTINCT")
        raise SystemExit("canary_text_not_distinct")
    baselines.say("CANARY_TEXT_DISTINCT", " ".join(canary))
    rest = [family for family in split["development"] if family not in canary]
    others = [arm for arm in ARMS if arm not in PROOF]
    expand = [(arm, family, present[family]) for arm in PROOF for family in rest]
    expand += [(arm, family, present[family]) for arm in others for family in canary]
    errors.extend(pool_map(expand, detective, roles, stop))
    if errors:
        baselines.say("ERRORS", len(errors))
        raise SystemExit("family_errors")
    follow = []
    for arm in others:
        same = same_as_reference(arm, canary, present)
        if same is None:
            raise SystemExit("canary_incomplete:" + arm)
        if same:
            write_zero_effect(arm, canary, present)
            baselines.say("EFFECT_ZERO", arm)
            continue
        follow.extend((arm, family, present[family]) for family in rest)
    if follow:
        errors.extend(pool_map(follow, detective, roles, stop))
    if errors:
        baselines.say("ERRORS", len(errors))
        raise SystemExit("family_errors")


if __name__ == "__main__":
    main()
