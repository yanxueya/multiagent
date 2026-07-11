"""执行硬约束过滤并以字典序生成唯一一个下一步动作。"""

from __future__ import annotations

from typing import Any, Iterable
from uuid import uuid4

from agent_system.schemas.decision import ActionPlan, CandidateSnapshot

HISTORY_RANKING_ENABLED = False


def rank_candidates(candidates: Iterable[CandidateSnapshot], *, use_execution_history: bool = False) -> list[CandidateSnapshot]:
    """第一阶段只做工程字典序；历史统计接口保留但不启用。"""

    if use_execution_history:
        raise RuntimeError("Execution-history ranking is not enabled in phase one")
    return sorted(candidates, key=CandidateSnapshot.ranking_key)


def build_single_action_plan(
    candidates: Iterable[CandidateSnapshot | dict[str, Any]],
    *,
    scene_id: str,
    user_goal: dict[str, Any] | None = None,
    scene_is_fresh: bool = True,
    review_instance_ids: Iterable[str] = (),
    max_attempts: int = 2,
    depth_threshold: float = 0.30,
) -> ActionPlan:
    """返回一个 robot_grasp、request_human_review、rescan 或 no_action。"""

    goal = dict(user_goal or {})
    if not scene_id or not scene_is_fresh:
        return _control_plan(scene_id, "rescan", "Current scene is missing or stale.")
    review_ids = [str(item) for item in review_instance_ids]
    if review_ids:
        return ActionPlan(_action_id(), scene_id, "request_human_review", review_ids[0], "", "A review-required object affects the current task.")

    snapshots = [item if isinstance(item, CandidateSnapshot) else CandidateSnapshot.from_mapping(item, default_scene_id=scene_id) for item in candidates]
    target_categories = {str(item) for item in goal.get("target_categories", [])}
    if target_categories:
        snapshots = [item for item in snapshots if item.class_name in target_categories]
    eligible = [item for item in snapshots if _is_robot_eligible(item, scene_id=scene_id, max_attempts=max_attempts, depth_threshold=depth_threshold)]
    ranked = rank_candidates(eligible)
    if not ranked:
        return _control_plan(scene_id, "no_action", "No object satisfies every robot eligibility constraint.")

    target = ranked[0]
    destination_map = dict(goal.get("destination_by_category", {}))
    destination = str(destination_map.get(target.class_name, f"{target.class_name}_bin"))
    return ActionPlan(
        _action_id(),
        scene_id,
        "robot_grasp",
        target.instance_id,
        destination,
        "Selected by lexicographic order: depth validity, graspability, NEAR count, motion distance, then attempt count.",
    )


def _is_robot_eligible(candidate: CandidateSnapshot, *, scene_id: str, max_attempts: int, depth_threshold: float) -> bool:
    return (
        candidate.scene_id == scene_id
        and candidate.recognition_status == "accepted"
        and candidate.current_handling_policy == "auto_allowed"
        and candidate.task_status == "pending"
        and candidate.attempt_count < max_attempts
        and candidate.depth_valid_ratio >= depth_threshold
        and candidate.occlusion_state == "none"
    )


def _control_plan(scene_id: str, action_type: str, reason: str) -> ActionPlan:
    return ActionPlan(_action_id(), scene_id, action_type, "", "", reason)


def _action_id() -> str:
    return f"action_{uuid4().hex[:12]}"
