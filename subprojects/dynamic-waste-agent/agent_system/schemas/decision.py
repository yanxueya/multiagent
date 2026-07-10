"""定义知识图谱状态投影与规划期动态决策的边界结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GraphFeasibilityState:
    """图谱投影提供当前可行性与类别先验，不包含规划优先级评分。"""

    instance_id: str
    class_name: str
    can_attempt_now: bool
    requires_review: bool
    blocked: bool
    yolo_confidence: float = 0.0
    recognition_status: str = "review_required"
    current_handling_policy: str = "human_confirmation_required"
    attempt_count: int = 0
    blocked_by: list[str] = field(default_factory=list)
    feasibility_reasons: list[str] = field(default_factory=list)
    reachable: bool = True
    visible: str = "unknown"
    grasp_pose_feasible: bool = True
    motion_path_collision_free: bool = True
    risk_level: str = "unknown"
    task_status: str = "active"
    review_status: str = "not_reviewed"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "GraphFeasibilityState":
        return cls(
            instance_id=str(value["instance_id"]),
            class_name=str(value.get("candidate_class", value.get("class_name", "unknown"))),
            can_attempt_now=bool(value.get("can_attempt_now", False)),
            requires_review=bool(value.get("requires_review", False)),
            blocked=bool(value.get("blocked", False)),
            yolo_confidence=float(value.get("yolo_confidence", 0.0) or 0.0),
            recognition_status=str(value.get("recognition_status", "review_required")),
            current_handling_policy=str(value.get("current_handling_policy", "human_confirmation_required")),
            attempt_count=int(value.get("attempt_count", 0) or 0),
            blocked_by=[str(item) for item in value.get("blocked_by", [])],
            feasibility_reasons=[str(item) for item in value.get("feasibility_reasons", [])],
            reachable=bool(value.get("reachable", True)),
            visible=str(value.get("visible", "unknown")),
            grasp_pose_feasible=bool(value.get("grasp_pose_feasible", True)),
            motion_path_collision_free=bool(value.get("motion_path_collision_free", True)),
            risk_level=str(value.get("risk_level", "unknown")),
            task_status=str(value.get("task_status", "active")),
            review_status=str(value.get("review_status", "not_reviewed")),
            metadata=dict(value.get("metadata", {})),
        )


@dataclass(frozen=True)
class PlannedStep:
    """规划器输出的动作、前置条件和预期效果。"""

    step_id: str
    action_type: str
    target_instance_id: str
    priority_tier: str
    dynamic_priority_score: float
    preconditions: list[str] = field(default_factory=list)
    effects: list[str] = field(default_factory=list)
    failure_recovery: str = "replan_after_failure"


@dataclass(frozen=True)
class PlanDecision:
    """规划器依据 graph_state 动态计算优先级后生成任务序列。"""

    objective: str
    steps: list[PlannedStep]
    deferred: list[dict[str, Any]] = field(default_factory=list)
    failure_policy: dict[str, Any] = field(default_factory=dict)
