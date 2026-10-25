"""Text updates for the six SkillFlow baselines.

The Harbor executor stays the same as vanilla. These functions only decide
what text the next task is allowed to see. They do not call a model.
"""

from __future__ import annotations

MAX_CHARS = 6000
SEP = "\n---\n"
LAYERS = ("general:", "family:", "task:")


def empty_state():
    return {"entries": [], "truncated": False}


def passed(reward):
    if reward is None:
        return False
    try:
        return float(reward) >= 1
    except (TypeError, ValueError):
        return False


def carry_text(state):
    return SEP.join(state.get("entries") or [])


def _excerpt(trace):
    return " ".join(str(trace or "").split())[:400]


def _fit(entries, already=False):
    kept = [entry for entry in entries if str(entry).strip()]
    truncated = False
    while kept and len(SEP.join(kept)) > MAX_CHARS:
        kept.pop(0)
        truncated = True
    if kept and len(SEP.join(kept)) > MAX_CHARS:
        kept = [SEP.join(kept)[-MAX_CHARS:]]
        truncated = True
    return {"entries": kept, "truncated": truncated or already}


def _lines(text):
    parts = [part.strip() for part in str(text or "").split(SEP) if part.strip()]
    if parts:
        return parts
    return [line.strip() for line in str(text or "").splitlines() if line.strip()]


def reflection_prompt(arm, reward, trace, previous):
    status = "passed" if passed(reward) else "failed"
    instructions = {
        "expel": "Write one cross-task insight in under 80 words.",
        "awm": "If the task passed, write one reusable workflow as ordered steps. If it failed, reply NONE.",
        "reasoning_bank": "Write one reasoning memory about what worked or failed.",
        "skillrl": "If the task failed, write one skill line starting with general:, family:, or task:. If it passed, reply NONE.",
        "cowork_x": "Rewrite the shared skill library. You may delete stale lines. Return the full library only.",
        "rsea": "Propose the full replacement context for later tasks. Return that context only.",
    }
    if arm not in instructions:
        raise ValueError("arm_not_a_baseline_writer")
    return "\n".join([
        instructions[arm],
        "Status: " + status,
        "Previous:",
        str(previous or "")[-2000:],
        "Trace:",
        _excerpt(trace),
    ])


def apply_update(arm, state, reward, trace, reply):
    """Fold one fake or real model reply into the carry state."""
    current = {
        "entries": list((state or empty_state()).get("entries") or []),
        "truncated": bool((state or empty_state()).get("truncated")),
    }
    text = str(reply or "").strip()
    if arm == "expel":
        item = "Insight: " + (text or "unavailable")
        if passed(reward):
            excerpt = _excerpt(trace)
            if excerpt:
                item += "\nSuccessful trajectory excerpt: " + excerpt
        current["entries"].append(item)
    elif arm == "awm":
        if passed(reward) and text and text.upper() != "NONE":
            current["entries"].append("Workflow: " + text)
    elif arm == "reasoning_bank":
        label = "Success" if passed(reward) else "Failure"
        current["entries"].append(label + ": " + (text or "unavailable"))
    elif arm == "skillrl":
        if not passed(reward):
            line = text if text and text.upper() != "NONE" else "task: unavailable"
            if not line.startswith(LAYERS):
                line = "task: " + line
            current["entries"].append(line)
    elif arm == "cowork_x":
        if text:
            current["entries"] = _lines(text)
    elif arm == "rsea":
        raise ValueError("rsea_uses_rsea_keep")
    else:
        raise ValueError("arm_not_a_baseline_writer")
    return _fit(current["entries"], current["truncated"])


def rsea_keep(previous, candidate, official_reward, replay_reward):
    """Keep a rewrite only when a held-out replay did not get worse.

    The first task of a family has no replay, so the candidate is dropped and
    the carry stays empty. A worse replay keeps the previous text.
    """
    previous = str(previous or "")
    candidate = str(candidate or "").strip()
    if not candidate or official_reward is None or replay_reward is None:
        return previous
    try:
        if float(replay_reward) + 1e-9 >= float(official_reward):
            return candidate
    except (TypeError, ValueError):
        return previous
    return previous


def official_error_after_replay(replay_error):
    """A replay flake must not erase the official paired reward.

    Only credential and disk failures stop the sweep. A tmux or docker
    miss on the replay leaves the official score in place.
    """
    text = str(replay_error or "")
    for mark in ("Missing credentials", "No space left", "missing_api_key"):
        if mark in text:
            return mark
    return ""


def state_from_text(text, truncated=False):
    return _fit(_lines(text) if str(text or "").strip() else [], truncated)
