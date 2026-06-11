from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

Vector3 = Tuple[float, float, float]
Quaternion = Tuple[float, float, float, float]
BBox3D = Tuple[float, float, float, float, float, float]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_list(value: Optional[Tuple[float, ...]], fallback: Tuple[float, ...]) -> Tuple[float, ...]:
    return fallback if value is None else value


@dataclass(slots=True)
class CategorySpec:
    name: str
    category: str
    material: str = ""
    risk_level: str = "unknown"
    fragility: str = "unknown"
    graspability: str = "unknown"
    pollution_level: str = "unknown"
    recyclability: str = "unknown"
    semantic_tags: List[str] = field(default_factory=list)
    confidence_prior: float = 0.0
    description: str = ""
    source_refs: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "material": self.material,
            "risk_level": self.risk_level,
            "fragility": self.fragility,
            "graspability": self.graspability,
            "pollution_level": self.pollution_level,
            "recyclability": self.recyclability,
            "semantic_tags": list(self.semantic_tags),
            "confidence_prior": self.confidence_prior,
            "description": self.description,
            "source_refs": list(self.source_refs),
            "notes": self.notes,
        }


@dataclass(slots=True)
class DetectedObject:
    temp_id: str
    class_name: str
    confidence: float
    center_xyz: Vector3 = (0.0, 0.0, 0.0)
    orientation: Quaternion = (0.0, 0.0, 0.0, 1.0)
    bbox_3d: Optional[BBox3D] = None
    risk_level: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DetectedRelation:
    source_temp_id: str
    relation: str
    target_temp_id: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Observation:
    frame_id: str
    source: str
    timestamp: datetime = field(default_factory=_utc_now)
    objects: List[DetectedObject] = field(default_factory=list)
    relations: List[DetectedRelation] = field(default_factory=list)
    camera_pose: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ObjectInstance:
    instance_id: str
    class_name: str
    center_xyz: Vector3 = (0.0, 0.0, 0.0)
    orientation: Quaternion = (0.0, 0.0, 0.0, 1.0)
    bbox_3d: Optional[BBox3D] = None
    confidence: float = 0.0
    priority: int = 0
    processed_flag: bool = False
    last_action: str = ""
    task_status: str = "pending"
    risk_level: str = "unknown"
    fragility_level: str = "unknown"
    graspability_level: str = "unknown"
    pollution_level: str = "unknown"
    occlusion_state: str = "unknown"
    contact_state: str = "unknown"
    support_state: str = "unknown"
    movable: bool = True
    graspable: bool = True
    processable: bool = True
    blocked_by: List[str] = field(default_factory=list)
    supports: List[str] = field(default_factory=list)
    task_relevance: float = 0.0
    observed_aliases: List[str] = field(default_factory=list)
    observation_count: int = 0
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    last_seen_frame: str = ""
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def touch(self, *, frame_id: str, source: str) -> None:
        self.updated_at = _utc_now()
        self.last_seen_frame = frame_id
        self.source = source
        self.observation_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "class_name": self.class_name,
            "center_xyz": self.center_xyz,
            "orientation": self.orientation,
            "bbox_3d": self.bbox_3d,
            "confidence": self.confidence,
            "priority": self.priority,
            "processed_flag": self.processed_flag,
            "last_action": self.last_action,
            "task_status": self.task_status,
            "risk_level": self.risk_level,
            "fragility_level": self.fragility_level,
            "graspability_level": self.graspability_level,
            "pollution_level": self.pollution_level,
            "occlusion_state": self.occlusion_state,
            "contact_state": self.contact_state,
            "support_state": self.support_state,
            "movable": self.movable,
            "graspable": self.graspable,
            "processable": self.processable,
            "blocked_by": list(self.blocked_by),
            "supports": list(self.supports),
            "task_relevance": self.task_relevance,
            "observed_aliases": list(self.observed_aliases),
            "observation_count": self.observation_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_seen_frame": self.last_seen_frame,
            "source": self.source,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class RelationEdge:
    source_id: str
    relation: str
    target_id: str
    confidence: float = 1.0
    active: bool = True
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def key(self) -> Tuple[str, str, str]:
        return self.source_id, self.relation, self.target_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "relation": self.relation,
            "target_id": self.target_id,
            "confidence": self.confidence,
            "active": self.active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class GraphEvent:
    event_type: str
    subject_id: str = ""
    relation: str = ""
    before_state: Dict[str, Any] = field(default_factory=dict)
    after_state: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    timestamp: datetime = field(default_factory=_utc_now)
    confidence_delta: float = 0.0
    event_id: str = field(default_factory=lambda: f"evt_{uuid4().hex[:12]}")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "subject_id": self.subject_id,
            "relation": self.relation,
            "before_state": dict(self.before_state),
            "after_state": dict(self.after_state),
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "confidence_delta": self.confidence_delta,
            "metadata": dict(self.metadata),
        }
