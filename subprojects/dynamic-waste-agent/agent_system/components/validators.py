"""确定性验证 Supervisor 与执行智能体不能绕过的硬约束。"""

from __future__ import annotations

from typing import Any, Iterable


def validate_action_plan(
    plan: dict[str, Any],
    *,
    current_scene_id: str,
    scene_is_fresh: bool,
    eligible_instance_ids: Iterable[str],
) -> list[str]:
    reasons: list[str] = []
    required = {"action_id", "scene_id", "action_type", "target_instance_id", "replan_after_execution"}
    missing = sorted(required - set(plan))
    if missing:
        reasons.append(f"missing_fields={','.join(missing)}")
        return reasons
    if str(plan.get("scene_id")) != current_scene_id:
        reasons.append("stale_scene")
    if not scene_is_fresh:
        reasons.append("scene_not_fresh")
    if plan.get("action_type") == "robot_grasp" and str(plan.get("target_instance_id")) not in set(eligible_instance_ids):
        reasons.append("target_not_eligible")
    if plan.get("action_type") not in {"robot_grasp", "request_human_review", "rescan", "no_action"}:
        reasons.append("unsupported_action_type")
    if plan.get("replan_after_execution") is not True:
        reasons.append("replan_after_execution_must_be_true")
    return reasons
