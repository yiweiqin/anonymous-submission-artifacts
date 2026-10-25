"""Harbor extra text for the SkillFlow ablation.

The learning rules stay where they are. This only decides which adopted
planning update and which three-person summary the next task receives.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN = HERE.parents[2] / "code" / "evaluation" / "skillflow"
sys.path.insert(0, str(MAIN))
import harbor_bridge


def staff_block(plan):
    lines = []
    for node in plan.get("nodes") or []:
        profile_id = node.get("agentId")
        profile = harbor_bridge.CATALOG.get(profile_id)
        if profile is None:
            raise ValueError("staff_profile_missing")
        summary = node.get("summary") or profile["summary"]
        lines.append(
            "- 名称：" + profile["name"]
            + "；主职能：" + profile["duty"]
            + "；技能摘要：" + summary
        )
    if len(lines) != 3:
        raise ValueError("staff_card_requires_three")
    return "当前三人组：\n" + "\n".join(lines)


def harbor_text(plan_update, plan, include_plan, include_staff):
    """Labeled sections stay present for an included factor, even when empty."""
    parts = []
    if include_plan:
        parts.append("已采用的规划更新：\n" + ("" if plan_update is None else str(plan_update)))
    if include_staff:
        parts.append(staff_block(plan))
    return "\n\n".join(parts)


def text_sha256(text):
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()
