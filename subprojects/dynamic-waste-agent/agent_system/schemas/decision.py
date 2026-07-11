"""定义 Supervisor、单步规划和执行反馈的结构化契约。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import inf
from typing import Any


@dataclass(frozen=True)
class SupervisorDecision:
    next_step: str
    target_instance_ids: list[str]
    reason: str
    replan_required: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateSnapshot:
    """规划节点临时读取的 KG 投影，不写入 LangGraph checkpoint。"""

    instance_id: str
    scene_id: str
    class_name: str
    recognition_status: str
    current_handling_policy: str
    task_status: str
    attempt_count: int
    depth_valid_ratio: float
    occlusion_state: str
    graspability_prior: str
    near_neighbor_count: int = 0
    motion_distance_estimate: float | None = None

    @classmethod
    def from_mapping(cls, value: dict[str, Any], *, default_scene_id: str = "") -> "CandidateSnapshot":
        return cls(
            instance_id=str(value["instance_id"]),
            scene_id=str(value.get("scene_id", default_scene_id)),
            class_name=str(value.get("candidate_class", value.get("class_name", "unknown"))),
            recognition_status=str(value.get("recognition_status", "review_required")),
            current_handling_policy=str(value.get("current_handling_policy", "human_review_required")),
            task_status=str(value.get("task_status", "pending")),
            attempt_count=int(value.get("attempt_count", 0) or 0),
            depth_valid_ratio=float(value.get("depth_valid_ratio", 0.0) or 0.0),
            occlusion_state=str(value.get("occlusion_state", "unknown")),
            graspability_prior=str(value.get("graspability_prior", "low")),
            near_neighbor_count=int(value.get("near_neighbor_count", 0) or 0),
            motion_distance_estimate=(float(value["motion_distance_estimate"]) if value.get("motion_distance_estimate") is not None else None),
        )

    def ranking_key(self) -> tuple[float, int, int, float, int, str]:
        grasp_rank = {"high": 0, "medium": 1, "low": 2}.get(self.graspability_prior, 3)
        motion_distance = self.motion_distance_estimate if self.motion_distance_estimate is not None else inf
        return (-self.depth_valid_ratio, grasp_rank, self.near_neighbor_count, motion_distance, self.attempt_count, self.instance_id)


@dataclass(frozen=True)
class ActionPlan:
    action_id: str
    scene_id: str
    action_type: str
    target_instance_id: str
    destination: str
    reason: str
    replan_after_execution: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionResult:
    action_id: str
    execution_status: str
    physical_attempt_started: bool
    failure_reason: str
    new_scene_required: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
