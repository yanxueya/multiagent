"""基于 KG graph_state 动态计算优先级并生成动作序列。"""

from __future__ import annotations

from typing import Any, Iterable

from agent_system.schemas.decision import GraphFeasibilityState, PlanDecision, PlannedStep


def build_ordered_plan(
    graph_state: Iterable[GraphFeasibilityState | dict[str, Any]],
    *,
    objective: str,
    max_steps: int = 5,
) -> PlanDecision:
    """先执行可行性硬过滤，再在规划程序内计算动态优先级。"""

    states = [_as_state(item) for item in graph_state]
    score_by_id = {state.instance_id: _dynamic_priority_score(state, objective) for state in states}
    state_by_id = {state.instance_id: state for state in states}
    steps: list[PlannedStep] = []
    planned_targets: set[str] = set()

    blocked_targets = [state for state in states if state.blocked_by]
    blocked_targets.sort(key=lambda state: score_by_id[state.instance_id], reverse=True)
    for target in blocked_targets:
        for blocker_id in target.blocked_by:
            blocker = state_by_id.get(blocker_id)
            if blocker is None or not blocker.can_attempt_now or blocker.instance_id in planned_targets:
                continue
            steps.append(_remove_blocker_step(len(steps) + 1, blocker, target, score_by_id[blocker.instance_id]))
            planned_targets.add(blocker.instance_id)
            if len(steps) >= max_steps:
                return _decision(objective, steps, states, score_by_id, planned_targets)

    ready = [state for state in states if state.can_attempt_now and state.instance_id not in planned_targets]
    ready.sort(key=lambda state: score_by_id[state.instance_id], reverse=True)
    for state in ready:
        steps.append(_auto_grasp_step(len(steps) + 1, state, score_by_id[state.instance_id]))
        planned_targets.add(state.instance_id)
        if len(steps) >= max_steps:
            break
    return _decision(objective, steps, states, score_by_id, planned_targets)


def _dynamic_priority_score(state: GraphFeasibilityState, objective: str) -> float:
    """规划期评分：目标匹配、检测证据、处理权限和尝试次数共同决定。"""

    target_match = 1.0 if state.class_name and state.class_name in objective else 0.0
    accepted_bonus = 0.2 if state.recognition_status == "accepted" else 0.0
    auto_bonus = 0.2 if state.current_handling_policy == "auto_allowed" else 0.0
    attempt_penalty = min(state.attempt_count, 3) * 0.15
    return round(max(0.0, target_match + state.yolo_confidence + accepted_bonus + auto_bonus - attempt_penalty), 4)


def _priority_tier(score: float) -> str:
    if score >= 1.5:
        return "high"
    if score >= 0.75:
        return "medium"
    return "low"


def _remove_blocker_step(index: int, blocker: GraphFeasibilityState, target: GraphFeasibilityState, score: float) -> PlannedStep:
    return PlannedStep(
        step_id=f"step_{index:02d}",
        action_type="remove_blocking_object",
        target_instance_id=blocker.instance_id,
        priority_tier=_priority_tier(score),
        dynamic_priority_score=score,
        preconditions=[f"{blocker.instance_id}.can_attempt_now=true", f"{blocker.instance_id}.blocks={target.instance_id}", "ros2_executor_ready"],
        effects=[f"{target.instance_id}.blocked=false"],
        failure_recovery="mark_failed_and_replan",
    )


def _auto_grasp_step(index: int, state: GraphFeasibilityState, score: float) -> PlannedStep:
    return PlannedStep(
        step_id=f"step_{index:02d}",
        action_type="robot_grasp",
        target_instance_id=state.instance_id,
        priority_tier=_priority_tier(score),
        dynamic_priority_score=score,
        preconditions=[
            f"{state.instance_id}.recognition_status=accepted",
            f"{state.instance_id}.current_handling_policy=auto_allowed",
            f"{state.instance_id}.can_attempt_now=true",
            "ros2_executor_ready",
        ],
        effects=[f"{state.instance_id}.task_status=completed"],
        failure_recovery="retry_once_then_replan_or_human_review",
    )


def _decision(
    objective: str,
    steps: list[PlannedStep],
    states: list[GraphFeasibilityState],
    score_by_id: dict[str, float],
    planned_targets: set[str],
) -> PlanDecision:
    deferred = [
        {
            "instance_id": state.instance_id,
            "class_name": state.class_name,
            "priority_tier": _priority_tier(score_by_id[state.instance_id]),
            "dynamic_priority_score": score_by_id[state.instance_id],
            "reasons": list(state.feasibility_reasons),
        }
        for state in states
        if state.instance_id not in planned_targets and not state.can_attempt_now
    ]
    deferred.sort(key=lambda item: float(item["dynamic_priority_score"]), reverse=True)
    return PlanDecision(
        objective=objective,
        steps=steps,
        deferred=deferred,
        failure_policy={
            "replan_after_failure": True,
            "write_execution_event": True,
            "request_new_scene_after_execution": True,
            "retry_policy": "retry_once_then_human_review",
        },
    )


def _as_state(value: GraphFeasibilityState | dict[str, Any]) -> GraphFeasibilityState:
    return value if isinstance(value, GraphFeasibilityState) else GraphFeasibilityState.from_mapping(value)
