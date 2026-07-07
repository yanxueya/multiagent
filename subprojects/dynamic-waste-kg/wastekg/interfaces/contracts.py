"""定义多智能体和 ROS2 对接契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from wastekg.core.models import BBox3D, GraphEvent, Observation, Quaternion, Vector3, DetectedObject, DetectedRelation
from wastekg.graph.query import build_planning_context
from wastekg.graph.store import KnowledgeGraph

UNKNOWN_REVIEW_CLASSES = {"unknown"}
UNKNOWN_REVIEW_MIN_CONFIDENCE = 0.50

# 视觉检测结果的边界契约：同时保留 YOLO 初筛、大模型复核和空间几何信息。
@dataclass(slots=True)
class VisionDetection:
    temp_id: str
    yolo_class_name: str
    yolo_confidence: float
    llm_class_name: str = ""
    llm_confidence: float = 0.0
    center_xyz: Vector3 = (0.0, 0.0, 0.0)
    orientation: Quaternion = (0.0, 0.0, 0.0, 1.0)
    bbox_3d: Optional[BBox3D] = None
    risk_hint: str = "unknown"
    mask_polygon: List[tuple[float, float]] = field(default_factory=list)
    boundary_points: List[tuple[float, float]] = field(default_factory=list)
    visible_area_ratio: float = 1.0
    occlusion_state: str = "unknown"
    grasp_candidates: List[Dict[str, Any]] = field(default_factory=list)
    safe_grasp_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_hazard_review(self) -> bool:
        return (
            self.llm_class_name in UNKNOWN_REVIEW_CLASSES
            and self.llm_confidence >= UNKNOWN_REVIEW_MIN_CONFIDENCE
        )

    def resolved_class_name(self) -> str:
        # unknown 是系统生成的人工复核状态，不是 YOLO 训练类别。
        if self.has_hazard_review():
            return self.llm_class_name
        # YOLO 负责初筛，大模型负责复核。若大模型有更强置信度，优先采用其结果。
        if self.llm_class_name and self.llm_confidence >= self.yolo_confidence:
            return self.llm_class_name
        return self.yolo_class_name

    def resolved_confidence(self) -> float:
        if self.has_hazard_review():
            return self.llm_confidence
        if self.llm_class_name and self.llm_confidence >= self.yolo_confidence:
            return self.llm_confidence
        return self.yolo_confidence

    def review_status(self) -> str:
        if self.has_hazard_review():
            return "human_review_required"
        if self.metadata.get("need_human_review"):
            return "human_review_required"
        if not self.llm_class_name:
            return "not_reviewed"
        if self.llm_class_name == self.yolo_class_name:
            return "review_agreed"
        if self.llm_confidence >= self.yolo_confidence:
            return "llm_override"
        return "review_conflict"

# 感知层只提交临时关系提示，实例级关系由知识图谱解析后落库。
@dataclass(slots=True)
class VisionRelationHint:
    source_temp_id: str
    relation: str
    target_temp_id: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

# VisionPacket 是感知层交给知识图谱的统一帧级输入。
@dataclass(slots=True)
class VisionPacket:
    frame_id: str
    source: str
    detections: List[VisionDetection] = field(default_factory=list)
    relation_hints: List[VisionRelationHint] = field(default_factory=list)
    camera_pose: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

# PlannerRequest 限定规划器可见的任务目标和候选范围。
@dataclass(slots=True)
class PlannerRequest:
    task_id: str
    objective: str
    target_categories: List[str] = field(default_factory=list)
    max_candidates: int = 10
    human_confirmation_required: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

# ROS2 只接收结构化动作命令，不接收大模型自由文本。
@dataclass(slots=True)
class Ros2ActionCommand:
    action_id: str
    action_type: str
    target_instance_id: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = True

# ExecutionFeedback 把执行结果写回图谱，形成感知-执行闭环。
@dataclass(slots=True)
class ExecutionFeedback:
    action_id: str
    target_instance_id: str
    status: str
    message: str = ""
    observed_changes: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

# 将感知边界契约转换为知识图谱内部 Observation。
def vision_packet_to_observation(packet: VisionPacket) -> Observation:
    objects = [
        DetectedObject(
            temp_id=detection.temp_id,
            class_name=detection.resolved_class_name(),
            confidence=detection.resolved_confidence(),
            yolo_confidence=detection.yolo_confidence,
            llm_confidence=detection.llm_confidence,
            final_confidence=detection.resolved_confidence(),
            review_status=detection.review_status(),
            center_xyz=detection.center_xyz,
            orientation=detection.orientation,
            bbox_3d=detection.bbox_3d,
            risk_level=detection.risk_hint,
            mask_polygon=list(detection.mask_polygon),
            boundary_points=list(detection.boundary_points),
            visible_area_ratio=detection.visible_area_ratio,
            occlusion_state=detection.occlusion_state,
            grasp_candidates=list(detection.grasp_candidates),
            safe_grasp_score=detection.safe_grasp_score,
            metadata={
                **dict(detection.metadata),
                "yolo_confidence": detection.yolo_confidence,
                "llm_confidence": detection.llm_confidence,
                "final_confidence": detection.resolved_confidence(),
                "review_status": detection.review_status(),
            },
        )
        for detection in packet.detections
    ]
    relations = [
        DetectedRelation(
            source_temp_id=relation.source_temp_id,
            relation=relation.relation,
            target_temp_id=relation.target_temp_id,
            confidence=relation.confidence,
            metadata=dict(relation.metadata),
        )
        for relation in packet.relation_hints
    ]
    return Observation(
        frame_id=packet.frame_id,
        source=packet.source,
        objects=objects,
        relations=relations,
        camera_pose=packet.camera_pose,
        metadata=dict(packet.metadata),
    )

# 为 LangGraph 多智能体层组装只读规划上下文。
def build_langgraph_state(graph: KnowledgeGraph, request: Optional[PlannerRequest] = None) -> Dict[str, Any]:
    request = request or PlannerRequest(task_id=f"task_{uuid4().hex[:8]}", objective="unassigned")
    planning_context = build_planning_context(
        graph,
        task={
            "task_id": request.task_id,
            "objective": request.objective,
            "target_categories": list(request.target_categories),
            "max_candidates": request.max_candidates,
            "human_confirmation_required": request.human_confirmation_required,
        },
    )
    return {
        "request": {
            "task_id": request.task_id,
            "objective": request.objective,
            "target_categories": list(request.target_categories),
            "max_candidates": request.max_candidates,
            "human_confirmation_required": request.human_confirmation_required,
            "metadata": dict(request.metadata),
        },
        "planning_context": planning_context,
        "long_term_knowledge": {name: spec.to_dict() for name, spec in graph.categories.items()},
    }


def build_ros2_action_command(action_type: str, target_instance_id: str, parameters: Optional[Dict[str, Any]] = None, *, requires_confirmation: bool = True) -> Ros2ActionCommand:
    return Ros2ActionCommand(
        action_id=f"action_{uuid4().hex[:10]}",
        action_type=action_type,
        target_instance_id=target_instance_id,
        parameters=dict(parameters or {}),
        requires_confirmation=requires_confirmation,
    )


def apply_execution_feedback(graph: KnowledgeGraph, feedback: ExecutionFeedback) -> Dict[str, Any]:
    # ROS2 执行后的反馈写回图谱，让短期记忆真正形成闭环。
    status = feedback.status.lower()
    if status == "success":
        graph.mark_processed(feedback.target_instance_id, action=feedback.message or feedback.action_id, source="ros2_executor")
    else:
        instance = graph.instances.get(feedback.target_instance_id)
        before = instance.to_dict() if instance is not None else {}
        after = dict(before)
        after["task_status"] = "blocked" if status in {"blocked", "failed"} else status
        if instance is not None:
            instance.task_status = after["task_status"]
            instance.last_action = feedback.message or feedback.action_id
            instance.touch(frame_id=instance.last_seen_frame, source="ros2_executor")
        graph.events.append(
            GraphEvent(
                event_type="execution_feedback",
                subject_id=feedback.target_instance_id,
                before_state=before,
                after_state=after,
                source="ros2_executor",
                metadata={
                    "action_id": feedback.action_id,
                    "message": feedback.message,
                    **dict(feedback.metadata),
                },
            )
        )
    return {
        "action_id": feedback.action_id,
        "target_instance_id": feedback.target_instance_id,
        "status": feedback.status,
    }
