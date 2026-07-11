"""定义多智能体和 ROS2 对接契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from wastekg.core.models import BBox2D, BBox3D, Observation, Quaternion, Vector3, DetectedObject, DetectedRelation
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
    bbox_2d: Optional[BBox2D] = None
    mask_ref: str = ""
    crop_ref: str = ""
    center_xyz: Vector3 = (0.0, 0.0, 0.0)
    depth_valid_ratio: float = 0.0
    observed_extent_3d: Vector3 = (0.0, 0.0, 0.0)
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

    def has_review_conflict(self) -> bool:
        return self.metadata.get("review_decision") == "conflict" or (
            bool(self.llm_class_name)
            and self.llm_class_name != self.yolo_class_name
            and self.llm_class_name not in UNKNOWN_REVIEW_CLASSES
        )

    def resolved_class_name(self) -> str:
        # 类别节点通过 CANDIDATE_OF/CONFIRMED_AS 表达；VLM 冲突只改变识别状态。
        return self.yolo_class_name

    def recognition_status(self) -> str:
        decision = str(self.metadata.get("review_decision", "")).lower()
        if self.has_hazard_review() or self.has_review_conflict() or decision in {"unknown", "conflict"}:
            return "unknown"
        if self.metadata.get("need_human_review") or decision in {"insufficient", "uncertain", "review_error"}:
            return "review_required"
        return "accepted"

    def resolved_confidence(self) -> float:
        if self.has_hazard_review():
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
    operation_mode: str = "human_collaboration"
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
    physical_attempt_started: bool = False
    message: str = ""
    observed_changes: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

# 将感知边界契约转换为知识图谱内部 Observation。
def vision_packet_to_observation(packet: VisionPacket) -> Observation:
    objects = [
        DetectedObject(
            temp_id=detection.temp_id,
            class_name=detection.yolo_class_name,
            confidence=detection.yolo_confidence,
            yolo_confidence=detection.yolo_confidence,
            bbox_2d=detection.bbox_2d,
            mask_ref=detection.mask_ref,
            crop_ref=detection.crop_ref,
            llm_confidence=detection.llm_confidence,
            final_confidence=detection.resolved_confidence(),
            review_status=detection.review_status(),
            center_xyz=detection.center_xyz,
            depth_valid_ratio=detection.depth_valid_ratio,
            observed_extent_3d=detection.observed_extent_3d,
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
                "candidate_class": detection.metadata.get("candidate_class", detection.yolo_class_name),
                "recognition_status": detection.recognition_status(),
                "bbox_2d": list(detection.bbox_2d) if detection.bbox_2d is not None else detection.metadata.get("bbox_2d"),
                "mask_ref": detection.mask_ref or detection.metadata.get("mask_ref", ""),
                "crop_ref": detection.crop_ref or detection.metadata.get("crop_ref", ""),
                "depth_valid_ratio": detection.depth_valid_ratio,
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

# 为 LangGraph 多智能体层组装线程级控制状态，不复制完整 KG。
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
    if request.operation_mode not in {"exploration", "supervised_execution", "human_collaboration"}:
        raise ValueError(f"Unsupported operation_mode: {request.operation_mode}")
    current_scene_id = next(reversed(graph.scenes), "")
    review_ids = [str(item["instance_id"]) for item in planning_context["review_required"]]
    return {
        "task_id": request.task_id,
        "operation_mode": request.operation_mode,
        "user_goal": {
            "goal_type": str(request.metadata.get("goal_type", "sort")),
            "objective": request.objective,
            "target_categories": list(request.target_categories),
            "human_confirmation_required": request.human_confirmation_required,
        },
        "current_scene_id": current_scene_id,
        "scene_is_fresh": bool(current_scene_id),
        "perception_completed": bool(current_scene_id),
        "review_instance_ids": review_ids,
        "eligible_instance_ids": list(planning_context["eligible_instance_ids"]),
        "current_plan": {},
        "plan_validated": False,
        "replan_required": True,
        "task_completed": False,
        "error_message": "",
        "kg_summary_ref": f"kg://scene/{current_scene_id}" if current_scene_id else "kg://empty",
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
    # 只有真实机械臂执行才增加 attempt_count，并生成 ExecutionEvent。
    status = feedback.status.lower()
    if not feedback.physical_attempt_started:
        return {
            "action_id": feedback.action_id,
            "target_instance_id": feedback.target_instance_id,
            "status": feedback.status,
            "event_recorded": False,
        }
    if status not in {"success", "failure", "failed"}:
        raise ValueError("A physical attempt must finish with success or failure")
    result = "success" if status == "success" else "failure"
    instance = graph.instances[feedback.target_instance_id]
    scene_id = str(feedback.metadata.get("scene_id") or instance.last_seen_scene or "scene_unknown")
    graph.record_execution_event(
        scene_id,
        feedback.target_instance_id,
        action_id=feedback.action_id,
        physical_attempt_started=True,
        execution_result=result,
        failure_reason="" if result == "success" else (feedback.message or status),
    )
    return {
        "action_id": feedback.action_id,
        "target_instance_id": feedback.target_instance_id,
        "status": feedback.status,
        "event_recorded": True,
    }
