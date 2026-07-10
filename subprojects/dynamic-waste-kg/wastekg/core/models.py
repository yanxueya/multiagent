"""定义 Word 版知识图谱规范对应的核心节点、关系和事件模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

Vector3 = Tuple[float, float, float]
Quaternion = Tuple[float, float, float, float]
BBox3D = Tuple[float, float, float, float, float, float]
BBox2D = Tuple[float, float, float, float]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class CategorySpec:
    """长期知识层 WasteCategory 节点；字段严格对应权威文档。"""

    name: str
    risk_level: str = "medium"
    fragility: str = "low"
    graspability_prior: str = "medium"
    vlm_review_policy: str = "threshold_based"
    default_handling_policy: str = "human_confirmation_required"
    visual_prototype: Dict[str, List[str]] = field(default_factory=dict)

    @property
    def category_name(self) -> str:
        return self.name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category_name": self.name,
            "risk_level": self.risk_level,
            "fragility": self.fragility,
            "graspability_prior": self.graspability_prior,
            "vlm_review_policy": self.vlm_review_policy,
            "default_handling_policy": self.default_handling_policy,
            "visual_prototype": {key: list(values) for key, values in self.visual_prototype.items()},
        }


@dataclass(slots=True)
class DetectedObject:
    """进入 KG 前的感知记录；这些字段不等同于持久化节点属性。"""

    temp_id: str
    class_name: str
    confidence: float
    yolo_confidence: float = 0.0
    bbox_2d: Optional[BBox2D] = None
    mask_ref: str = ""
    crop_ref: str = ""
    center_xyz: Vector3 = (0.0, 0.0, 0.0)
    observed_extent_3d: Vector3 = (0.0, 0.0, 0.0)
    depth_valid_ratio: float = 0.0
    occlusion_state: str = "unknown"
    llm_confidence: float = 0.0
    final_confidence: float = 0.0
    review_status: str = "not_reviewed"
    orientation: Quaternion = (0.0, 0.0, 0.0, 1.0)
    bbox_3d: Optional[BBox3D] = None
    risk_level: str = "unknown"
    mask_polygon: List[Tuple[float, float]] = field(default_factory=list)
    boundary_points: List[Tuple[float, float]] = field(default_factory=list)
    visible_area_ratio: float = 1.0
    grasp_candidates: List[Dict[str, Any]] = field(default_factory=list)
    safe_grasp_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DetectedRelation:
    """单帧关系提示；KG 关系本身不保存独立属性。"""

    source_temp_id: str
    relation: str
    target_temp_id: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Observation:
    """一次 RGB-D 场景观测。"""

    frame_id: str
    source: str
    timestamp: datetime = field(default_factory=_utc_now)
    objects: List[DetectedObject] = field(default_factory=list)
    relations: List[DetectedRelation] = field(default_factory=list)
    camera_pose: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Scene:
    """短期记忆中的一次场景观测节点。"""

    scene_id: str
    captured_at: datetime = field(default_factory=_utc_now)
    rgb_ref: str = ""
    depth_ref: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "captured_at": self.captured_at.isoformat(),
            "rgb_ref": self.rgb_ref,
            "depth_ref": self.depth_ref,
        }


@dataclass(slots=True)
class ObjectInstance:
    """短期 ObjectInstance 节点；类别仅通过关系持久化。"""

    instance_id: str
    yolo_confidence: float = 0.0
    recognition_status: str = "review_required"
    bbox_2d: Optional[BBox2D] = None
    mask_ref: str = ""
    crop_ref: str = ""
    center_xyz_camera: Vector3 = (0.0, 0.0, 0.0)
    depth_valid_ratio: float = 0.0
    observed_extent_3d: Vector3 = (0.0, 0.0, 0.0)
    occlusion_state: str = "unknown"
    vlm_consistency: str = "not_checked"
    current_handling_policy: str = "human_review_required"
    task_status: str = "pending"
    attempt_count: int = 0
    # 仅用于内存匹配，不会出现在 to_dict、JSON 或 Neo4j 节点属性中。
    class_name: str = field(default="", repr=False)
    created_at: datetime = field(default_factory=_utc_now, repr=False)
    updated_at: datetime = field(default_factory=_utc_now, repr=False)
    last_seen_scene: str = field(default="", repr=False)

    def touch(self, *, scene_id: str) -> None:
        self.updated_at = _utc_now()
        self.last_seen_scene = scene_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "yolo_confidence": self.yolo_confidence,
            "recognition_status": self.recognition_status,
            "bbox_2d": list(self.bbox_2d) if self.bbox_2d is not None else None,
            "mask_ref": self.mask_ref,
            "crop_ref": self.crop_ref,
            "center_xyz_camera": list(self.center_xyz_camera),
            "depth_valid_ratio": self.depth_valid_ratio,
            "observed_extent_3d": list(self.observed_extent_3d),
            "occlusion_state": self.occlusion_state,
            "vlm_consistency": self.vlm_consistency,
            "current_handling_policy": self.current_handling_policy,
            "task_status": self.task_status,
            "attempt_count": self.attempt_count,
        }


@dataclass(slots=True)
class UnknownSample:
    """无法可靠分类的单个未知样本。"""

    sample_id: str
    crop_ref: str = ""
    mask_ref: str = ""
    yolo_topk: Dict[str, float] = field(default_factory=dict)
    vlm_attributes: Dict[str, Any] = field(default_factory=dict)
    review_status: str = "pending"
    human_label: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "crop_ref": self.crop_ref,
            "mask_ref": self.mask_ref,
            "yolo_topk": dict(self.yolo_topk),
            "vlm_attributes": dict(self.vlm_attributes),
            "review_status": self.review_status,
            "human_label": self.human_label,
        }


@dataclass(slots=True)
class UnknownCluster:
    """多次出现的相似未知对象聚类。"""

    cluster_id: str
    member_count: int = 0
    prototype_attributes: Dict[str, Any] = field(default_factory=dict)
    representative_crop_ref: str = ""
    review_status: str = "pending"
    candidate_category_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "member_count": self.member_count,
            "prototype_attributes": dict(self.prototype_attributes),
            "representative_crop_ref": self.representative_crop_ref,
            "review_status": self.review_status,
            "candidate_category_name": self.candidate_category_name,
        }


@dataclass(slots=True, frozen=True)
class RelationEdge:
    """无独立属性的图关系。"""

    source_id: str
    relation: str
    target_id: str

    def key(self) -> Tuple[str, str, str]:
        return self.source_id, self.relation, self.target_id

    def to_dict(self) -> Dict[str, Any]:
        return {"source_id": self.source_id, "relation": self.relation, "target_id": self.target_id}


EVENT_SOURCES = {
    "DetectionEvent": "yolo_detector",
    "VLMReviewEvent": "vlm_service",
    "DepthUpdateEvent": "depth_processor",
    "HumanReviewEvent": "human_reviewer",
    "PlanningEvent": "task_planner",
    "ExecutionEvent": "robot_controller",
    "KnowledgeEvolutionEvent": "knowledge_updater",
}

EVENT_ATTRIBUTE_FIELDS = {
    "DetectionEvent": {"yolo_confidence", "bbox_2d", "mask_ref", "crop_ref"},
    "VLMReviewEvent": {"image_quality", "visual_attributes", "consistency", "reason"},
    "DepthUpdateEvent": {"center_xyz_camera", "depth_valid_ratio", "observed_extent_3d", "occlusion_state"},
    "HumanReviewEvent": {"review_action", "reason"},
    "PlanningEvent": {"planned_action", "reason"},
    "ExecutionEvent": {"execution_result", "failure_reason"},
    "KnowledgeEvolutionEvent": {"evolution_action", "reason"},
}


@dataclass(slots=True)
class GraphEvent:
    """七类事件节点的统一容器，字段集合由事件类型严格约束。"""

    event_type: str
    event_source: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    event_time: datetime = field(default_factory=_utc_now)
    event_id: str = field(default_factory=lambda: f"evt_{uuid4().hex[:12]}")

    def __post_init__(self) -> None:
        if self.event_type not in EVENT_SOURCES:
            raise ValueError(f"Unsupported event_type: {self.event_type}")
        expected_source = EVENT_SOURCES[self.event_type]
        if not self.event_source:
            self.event_source = expected_source
        if self.event_source != expected_source:
            raise ValueError(f"{self.event_type} must use event_source={expected_source}")
        unsupported = set(self.attributes) - EVENT_ATTRIBUTE_FIELDS[self.event_type]
        if unsupported:
            raise ValueError(f"Unsupported {self.event_type} attributes: {sorted(unsupported)}")

    @property
    def timestamp(self) -> datetime:
        return self.event_time

    @property
    def source(self) -> str:
        return self.event_source

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_time": self.event_time.isoformat(),
            "event_source": self.event_source,
            **dict(self.attributes),
        }
