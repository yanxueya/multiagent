from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .models import BBox3D, GraphEvent, Observation, Quaternion, Vector3, DetectedObject, DetectedRelation
from .query import build_planning_context
from .store import KnowledgeGraph

UNKNOWN_REVIEW_CLASSES = {"unknown"}
UNKNOWN_REVIEW_MIN_CONFIDENCE = 0.50

#物体检测结果的中间表示，包含了来自视觉检测和大模型推理的类别名称和置信度，以及物体的空间位置、朝向、三维边界框等信息。该类还提供了一个方法来解析最终的类别名称和置信度，优先采用大模型的结果（如果其置信度更高），否则采用视觉检测的结果。这种设计允许系统在初筛阶段利用视觉检测的快速响应，同时在复核阶段利用大模型的更强推理能力来提高分类准确性。
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

#物体间关系提示的中间表示，包含了关系的源临时ID、关系类型、目标临时ID、置信度以及其他可选的元数据。这些关系提示可以来自视觉检测的直接观测，也可以来自基于空间位置推断出的关系。通过将这些关系提示与检测结果结合起来，系统可以构建一个更丰富的知识图谱，支持更复杂的推理和决策。
@dataclass(slots=True)
class VisionRelationHint:
    source_temp_id: str
    relation: str
    target_temp_id: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

#视觉数据包的中间表示，包含了一个视频帧的ID、数据来源、检测结果列表、关系提示列表、相机位姿以及其他可选的元数据。该类还提供了一个方法来将视觉数据包转换为知识图谱中的观测对象，以便后续的处理和推理使用。通过这种设计，系统可以将来自不同来源的视觉信息统一表示，并与知识图谱中的实例和关系进行关联和更新。
@dataclass(slots=True)
class VisionPacket:
    frame_id: str
    source: str
    detections: List[VisionDetection] = field(default_factory=list)
    relation_hints: List[VisionRelationHint] = field(default_factory=list)
    camera_pose: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

#任务请求，包含了任务ID、目标、目标类别列表、最大候选实例数量、是否需要人工确认以及其他可选的元数据。该类用于向规划器传递任务相关的信息，以便规划器能够根据当前的知识图谱状态和任务需求生成合适的行动计划。
@dataclass(slots=True)
class PlannerRequest:
    task_id: str
    objective: str
    target_categories: List[str] = field(default_factory=list)
    max_candidates: int = 10
    human_confirmation_required: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

# ROS2行动命令，包含了一个唯一的动作ID、动作类型、目标实例ID、参数字典以及是否需要人工确认的标志。该类用于向ROS2执行器传递具体的行动指令，以便机器人能够执行相应的操作。
@dataclass(slots=True)
class Ros2ActionCommand:
    action_id: str
    action_type: str
    target_instance_id: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = True

#执行反馈，包含了动作ID、目标实例ID、执行状态、消息、观察到的变化以及其他可选的元数据。该类用于从ROS2执行器接收执行结果，以便将这些结果应用到知识图谱中，形成一个闭环的反馈机制。
@dataclass(slots=True)
class ExecutionFeedback:
    action_id: str
    target_instance_id: str
    status: str
    message: str = ""
    observed_changes: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

#统一了感知输出的格式
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

#以下是一些预定义的类别规范，用于指导知识图谱中实例的属性推断和风险评估。这些规范涵盖了常见的建筑废弃物和危险废弃物类别，并提供了相关的属性信息、语义标签、描述以及参考来源等。这些规范可以帮助系统在处理视觉检测结果时，根据类别名称自动填充实例的属性，从而支持更准确的风险评估和行动决策。
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
