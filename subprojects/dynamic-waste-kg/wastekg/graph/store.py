"""维护文档定义的三层动态知识图谱、关系和追加式事件日志。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from math import sqrt
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

from wastekg.core.models import (
    CategorySpec,
    DetectedObject,
    DetectedRelation,
    GraphEvent,
    ObjectInstance,
    Observation,
    RelationEdge,
    Scene,
    UnknownCluster,
    UnknownSample,
)
from wastekg.core.taxonomy import UNKNOWN_CATEGORY, canonicalize_category_name


ALLOWED_RELATIONS = {
    "CONTAINS",
    "CANDIDATE_OF",
    "CONFIRMED_AS",
    "NEAR",
    "RECORDED_AS",
    "MEMBER_OF",
    "IN_SCENE",
    "DETECTED",
    "PROPOSED",
    "REVIEWS",
    "CHECKS_AGAINST",
    "CONFIRMS",
    "UPDATES",
    "SELECTS",
    "EXECUTES_ON",
    "CREATES",
}


class KnowledgeGraph:
    """三层 KG：长期类别、短期场景记忆、七类事件节点。"""

    def __init__(self, *, match_distance_threshold: float = 0.25, stale_after_seconds: int = 30) -> None:
        self.match_distance_threshold = match_distance_threshold
        self.stale_after_seconds = stale_after_seconds
        self.categories: Dict[str, CategorySpec] = {}
        self.scenes: Dict[str, Scene] = {}
        self.instances: Dict[str, ObjectInstance] = {}
        self.unknown_samples: Dict[str, UnknownSample] = {}
        self.unknown_clusters: Dict[str, UnknownCluster] = {}
        self.edges: Dict[Tuple[str, str, str], RelationEdge] = {}
        self.events: List[GraphEvent] = []
        self._track_map: Dict[str, str] = {}
        self._class_counters: Dict[str, int] = defaultdict(int)
        self._unknown_counter = 0
        self._executed_action_ids: set[str] = set()

    def register_category(self, category: CategorySpec) -> None:
        """注册长期 WasteCategory；初始种子不产生事件。"""

        self.categories[category.name] = category

    def generate_instance_id(self, candidate_class: str) -> str:
        candidate_class = canonicalize_category_name(candidate_class)
        prefix = candidate_class if candidate_class != UNKNOWN_CATEGORY else "unknown"
        self._class_counters[prefix] += 1
        return f"{prefix}_{self._class_counters[prefix]:02d}"

    def upsert_instance(self, instance: ObjectInstance, *, source: str = "system") -> ObjectInstance:
        """合并实例状态，不产生文档之外的通用 create/update 事件。"""

        before = self.instances.get(instance.instance_id)
        if before is None:
            instance.touch(scene_id=instance.last_seen_scene)
            self.instances[instance.instance_id] = instance
            return instance

        merged = replace(
            before,
            yolo_confidence=max(before.yolo_confidence, instance.yolo_confidence),
            recognition_status=instance.recognition_status or before.recognition_status,
            bbox_2d=instance.bbox_2d if instance.bbox_2d is not None else before.bbox_2d,
            mask_ref=instance.mask_ref or before.mask_ref,
            crop_ref=instance.crop_ref or before.crop_ref,
            center_xyz_camera=instance.center_xyz_camera,
            depth_valid_ratio=instance.depth_valid_ratio if instance.depth_valid_ratio > 0 else before.depth_valid_ratio,
            observed_extent_3d=instance.observed_extent_3d if any(instance.observed_extent_3d) else before.observed_extent_3d,
            occlusion_state=instance.occlusion_state if instance.occlusion_state != "unknown" else before.occlusion_state,
            vlm_consistency=instance.vlm_consistency if instance.vlm_consistency != "not_checked" else before.vlm_consistency,
            current_handling_policy=instance.current_handling_policy or before.current_handling_policy,
            task_status=instance.task_status or before.task_status,
            attempt_count=max(before.attempt_count, instance.attempt_count),
            class_name=instance.class_name or before.class_name,
            last_seen_scene=instance.last_seen_scene or before.last_seen_scene,
        )
        merged.touch(scene_id=instance.last_seen_scene or before.last_seen_scene)
        self.instances[instance.instance_id] = merged
        return merged

    def add_relation(self, edge: RelationEdge, *, source: str = "system") -> RelationEdge:
        """写入无属性关系；关系类型必须来自权威文档。"""

        relation = edge.relation.upper()
        if relation not in ALLOWED_RELATIONS:
            raise ValueError(f"Unsupported KG relation: {edge.relation}")
        normalized = RelationEdge(edge.source_id, relation, edge.target_id)
        self.edges[normalized.key()] = normalized
        return normalized

    def apply_observation(self, observation: Observation) -> Dict[str, Any]:
        """创建 Scene、ObjectInstance、检测/复核/深度事件及文档定义关系。"""

        scene_id = str(observation.metadata.get("scene_id") or observation.frame_id)
        scene = Scene(
            scene_id=scene_id,
            captured_at=observation.timestamp,
            rgb_ref=str(observation.metadata.get("rgb_ref", "")),
            depth_ref=str(observation.metadata.get("depth_ref", "")),
        )
        self.scenes[scene_id] = scene

        resolved_ids: Dict[str, str] = {}
        created: List[str] = []
        updated: List[str] = []
        for detected in observation.objects:
            candidate_class = self._candidate_class(detected)
            instance, created_flag = self._resolve_detection(detected, candidate_class, scene_id)
            resolved_ids[detected.temp_id] = instance.instance_id
            (created if created_flag else updated).append(instance.instance_id)
            self._track_map[detected.temp_id] = instance.instance_id
            self.upsert_instance(instance, source=observation.source)

            self.add_relation(RelationEdge(scene_id, "CONTAINS", instance.instance_id))
            if candidate_class in self.categories:
                self.add_relation(RelationEdge(instance.instance_id, "CANDIDATE_OF", candidate_class))
            detection_event = GraphEvent(
                event_type="DetectionEvent",
                attributes={
                    "yolo_confidence": instance.yolo_confidence,
                    "bbox_2d": list(instance.bbox_2d) if instance.bbox_2d is not None else None,
                    "mask_ref": instance.mask_ref,
                    "crop_ref": instance.crop_ref,
                },
            )
            self._append_event(
                detection_event,
                [
                    ("IN_SCENE", scene_id),
                    ("DETECTED", instance.instance_id),
                    *(([("PROPOSED", candidate_class)]) if candidate_class in self.categories else []),
                ],
            )

            review_decision = str(detected.metadata.get("review_decision", "not_checked")).lower()
            if review_decision not in {"", "not_checked", "unknown"}:
                vlm_event = GraphEvent(
                    event_type="VLMReviewEvent",
                    attributes={
                        "image_quality": str(detected.metadata.get("image_quality", "limited")),
                        "visual_attributes": dict(detected.metadata.get("visual_attributes", {})),
                        "consistency": review_decision,
                        "reason": str(detected.metadata.get("review_reason", "")),
                    },
                )
                self._append_event(
                    vlm_event,
                    [
                        ("REVIEWS", instance.instance_id),
                        *(([("CHECKS_AGAINST", candidate_class)]) if candidate_class in self.categories else []),
                    ],
                )

            if instance.recognition_status == "accepted" and candidate_class in self.categories:
                self.add_relation(RelationEdge(instance.instance_id, "CONFIRMED_AS", candidate_class))
            if instance.recognition_status == "unknown":
                self._ensure_unknown_sample(instance, detected)

            if self._has_depth_update(detected):
                depth_event = GraphEvent(
                    event_type="DepthUpdateEvent",
                    attributes={
                        "center_xyz_camera": list(instance.center_xyz_camera),
                        "depth_valid_ratio": instance.depth_valid_ratio,
                        "observed_extent_3d": list(instance.observed_extent_3d),
                        "occlusion_state": instance.occlusion_state,
                    },
                )
                self._append_event(depth_event, [("IN_SCENE", scene_id), ("UPDATES", instance.instance_id)])

        relation_hints = list(observation.relations)
        relation_hints.extend(self._infer_near_relations(observation.objects))
        for relation in relation_hints:
            if relation.relation.lower() != "near":
                continue
            source_id = resolved_ids.get(relation.source_temp_id)
            target_id = resolved_ids.get(relation.target_temp_id)
            if source_id and target_id and source_id != target_id:
                self.add_relation(RelationEdge(source_id, "NEAR", target_id))

        return {
            "frame_id": observation.frame_id,
            "scene_id": scene_id,
            "created_instances": created,
            "updated_instances": updated,
            "resolved_ids": resolved_ids,
            "relation_count": len([edge for edge in self.edges.values() if edge.relation == "NEAR"]),
        }

    def apply_human_review(
        self,
        target_id: str,
        *,
        review_action: str,
        reason: str = "",
        confirmed_category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """应用文档列出的五种人工审核操作。"""

        allowed = {"confirm_existing", "mark_unknown", "approve_robot", "forbid_robot", "discard_detection"}
        if review_action not in allowed:
            raise ValueError(f"Unsupported review_action: {review_action}")
        event = GraphEvent("HumanReviewEvent", attributes={"review_action": review_action, "reason": reason})
        relations = [("REVIEWS", target_id)]
        instance = self.instances.get(target_id)
        if instance is not None:
            if review_action == "confirm_existing":
                if not confirmed_category:
                    raise ValueError("confirm_existing requires confirmed_category")
                category = canonicalize_category_name(confirmed_category)
                if category not in self.categories:
                    raise ValueError(f"Unknown confirmed_category: {category}")
                instance.class_name = category
                instance.recognition_status = "accepted"
                instance.current_handling_policy = self.categories[category].default_handling_policy
                self.add_relation(RelationEdge(instance.instance_id, "CONFIRMED_AS", category))
                relations.append(("CONFIRMS", category))
            elif review_action == "mark_unknown":
                instance.recognition_status = "unknown"
                instance.current_handling_policy = "robot_forbidden"
                self._ensure_unknown_sample(instance, None)
            elif review_action == "approve_robot":
                instance.current_handling_policy = "auto_allowed"
            elif review_action == "forbid_robot":
                instance.current_handling_policy = "robot_forbidden"
            elif review_action == "discard_detection":
                instance.current_handling_policy = "robot_forbidden"
                instance.task_status = "completed"
                self._track_map = {key: value for key, value in self._track_map.items() if value != target_id}
        self._append_event(event, relations)
        return {"event_id": event.event_id, "target_id": target_id, "review_action": review_action}

    def record_planning_event(
        self,
        scene_id: str,
        instance_id: str,
        *,
        planned_action: str,
        reason: str = "",
        action_id: str = "",
    ) -> GraphEvent:
        allowed = {"robot_grasp", "request_human_review", "rescan", "complete", "no_action"}
        if planned_action not in allowed:
            raise ValueError(f"Unsupported planned_action: {planned_action}")
        event_kwargs = {"event_id": action_id} if action_id else {}
        event = GraphEvent("PlanningEvent", attributes={"planned_action": planned_action, "reason": reason}, **event_kwargs)
        relations = [("IN_SCENE", scene_id)]
        if instance_id:
            relations.append(("SELECTS", instance_id))
        self._append_event(event, relations)
        return event

    def record_execution_event(
        self,
        scene_id: str,
        instance_id: str,
        *,
        action_id: str,
        physical_attempt_started: bool,
        execution_result: str,
        failure_reason: str = "",
    ) -> GraphEvent:
        if not action_id:
            raise ValueError("ExecutionEvent requires action_id")
        if action_id in self._executed_action_ids:
            raise ValueError(f"Duplicate physical action_id: {action_id}")
        if not physical_attempt_started:
            raise ValueError("ExecutionEvent is only valid after a physical attempt starts")
        if execution_result not in {"success", "failure"}:
            raise ValueError("execution_result must be success or failure")
        instance = self.instances[instance_id]
        instance.attempt_count += 1
        instance.task_status = "completed" if execution_result == "success" else "failed"
        event = GraphEvent(
            "ExecutionEvent",
            attributes={
                "action_id": action_id,
                "physical_attempt_started": True,
                "execution_result": execution_result,
                "failure_reason": failure_reason if execution_result == "failure" else "",
            },
        )
        self._append_event(event, [("EXECUTES_ON", instance_id), ("IN_SCENE", scene_id)])
        self._executed_action_ids.add(action_id)
        return event

    def record_knowledge_evolution(
        self,
        target_id: str,
        *,
        evolution_action: str,
        reason: str,
        creates_category: Optional[CategorySpec] = None,
    ) -> GraphEvent:
        allowed = {"assign_existing_category", "create_unknown_cluster", "propose_new_category", "promote_new_category", "discard_unknown"}
        if evolution_action not in allowed:
            raise ValueError(f"Unsupported evolution_action: {evolution_action}")
        event = GraphEvent("KnowledgeEvolutionEvent", attributes={"evolution_action": evolution_action, "reason": reason})
        relations = [("UPDATES", target_id)]
        if creates_category is not None:
            if evolution_action != "promote_new_category":
                raise ValueError("WasteCategory creation requires promote_new_category")
            self.register_category(creates_category)
            relations.append(("CREATES", creates_category.name))
        self._append_event(event, relations)
        return event

    def create_unknown_cluster(
        self,
        cluster: UnknownCluster,
        *,
        member_sample_ids: Iterable[str] = (),
    ) -> UnknownCluster:
        members = [sample_id for sample_id in member_sample_ids if sample_id in self.unknown_samples]
        cluster.member_count = len(members)
        self.unknown_clusters[cluster.cluster_id] = cluster
        for sample_id in members:
            self.add_relation(RelationEdge(sample_id, "MEMBER_OF", cluster.cluster_id))
        return cluster

    def mark_processed(self, instance_id: str, *, action: str, source: str = "executor") -> None:
        """兼容入口：按真实执行成功记录 ExecutionEvent。"""

        instance = self.instances[instance_id]
        scene_id = instance.last_seen_scene or next(reversed(self.scenes), "scene_unknown")
        self.record_execution_event(
            scene_id,
            instance_id,
            action_id=f"legacy_action_{uuid4().hex[:10]}",
            physical_attempt_started=True,
            execution_result="success",
        )

    def list_active_instances(self) -> List[ObjectInstance]:
        return [instance for instance in self.instances.values() if instance.task_status != "completed"]

    def has_execution_action(self, action_id: str) -> bool:
        """查询动作是否已有真实 ExecutionEvent，用于执行前幂等门控。"""

        return action_id in self._executed_action_ids or any(
            event.event_type == "ExecutionEvent" and event.attributes.get("action_id") == action_id
            for event in self.events
        )

    def resolve_instance_category(self, instance_id: str) -> str:
        """优先读取 CONFIRMED_AS，其次读取 CANDIDATE_OF。"""

        confirmed = [edge.target_id for edge in self.edges.values() if edge.source_id == instance_id and edge.relation == "CONFIRMED_AS"]
        if confirmed:
            return confirmed[-1]
        candidates = [edge.target_id for edge in self.edges.values() if edge.source_id == instance_id and edge.relation == "CANDIDATE_OF"]
        if candidates:
            return candidates[-1]
        instance = self.instances.get(instance_id)
        return instance.class_name if instance is not None else UNKNOWN_CATEGORY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "categories": {name: spec.to_dict() for name, spec in self.categories.items()},
            "scenes": {scene_id: scene.to_dict() for scene_id, scene in self.scenes.items()},
            "instances": {instance_id: instance.to_dict() for instance_id, instance in self.instances.items()},
            "unknown_samples": {sample_id: sample.to_dict() for sample_id, sample in self.unknown_samples.items()},
            "unknown_clusters": {cluster_id: cluster.to_dict() for cluster_id, cluster in self.unknown_clusters.items()},
            "edges": [edge.to_dict() for edge in self.edges.values()],
            "events": [event.to_dict() for event in self.events],
        }

    def _resolve_detection(
        self,
        detected: DetectedObject,
        candidate_class: str,
        scene_id: str,
    ) -> Tuple[ObjectInstance, bool]:
        recognition_status = self._recognition_status(detected)
        vlm_consistency = self._vlm_consistency(detected)
        handling_policy = self._handling_policy(candidate_class, recognition_status)
        if detected.temp_id in self._track_map and self._track_map[detected.temp_id] in self.instances:
            existing = self.instances[self._track_map[detected.temp_id]]
            return self._merge_detection(existing, detected, candidate_class, recognition_status, vlm_consistency, handling_policy, scene_id), False
        candidate_id = self._match_existing(detected, candidate_class)
        if candidate_id is not None:
            return self._merge_detection(self.instances[candidate_id], detected, candidate_class, recognition_status, vlm_consistency, handling_policy, scene_id), False
        instance = ObjectInstance(
            instance_id=self.generate_instance_id(candidate_class if recognition_status != "unknown" else UNKNOWN_CATEGORY),
            yolo_confidence=float(detected.yolo_confidence or detected.confidence),
            recognition_status=recognition_status,
            bbox_2d=detected.bbox_2d or self._bbox_from_metadata(detected.metadata),
            mask_ref=detected.mask_ref or str(detected.metadata.get("mask_ref", "")),
            crop_ref=detected.crop_ref or str(detected.metadata.get("crop_ref", "")),
            center_xyz_camera=detected.center_xyz,
            depth_valid_ratio=float(detected.depth_valid_ratio or detected.metadata.get("depth_valid_ratio", 0.0) or 0.0),
            observed_extent_3d=detected.observed_extent_3d,
            occlusion_state=self._normalize_occlusion(detected.occlusion_state),
            vlm_consistency=vlm_consistency,
            current_handling_policy=handling_policy,
            task_status="pending",
            attempt_count=0,
            class_name=candidate_class,
            last_seen_scene=scene_id,
        )
        return instance, True

    def _merge_detection(
        self,
        existing: ObjectInstance,
        detected: DetectedObject,
        candidate_class: str,
        recognition_status: str,
        vlm_consistency: str,
        handling_policy: str,
        scene_id: str,
    ) -> ObjectInstance:
        return replace(
            existing,
            yolo_confidence=max(existing.yolo_confidence, float(detected.yolo_confidence or detected.confidence)),
            recognition_status=recognition_status,
            bbox_2d=detected.bbox_2d or self._bbox_from_metadata(detected.metadata) or existing.bbox_2d,
            mask_ref=detected.mask_ref or str(detected.metadata.get("mask_ref", "")) or existing.mask_ref,
            crop_ref=detected.crop_ref or str(detected.metadata.get("crop_ref", "")) or existing.crop_ref,
            center_xyz_camera=self._blend_vector(existing.center_xyz_camera, detected.center_xyz),
            depth_valid_ratio=float(detected.depth_valid_ratio or detected.metadata.get("depth_valid_ratio", 0.0) or existing.depth_valid_ratio),
            observed_extent_3d=detected.observed_extent_3d if any(detected.observed_extent_3d) else existing.observed_extent_3d,
            occlusion_state=self._normalize_occlusion(detected.occlusion_state) if detected.occlusion_state != "unknown" else existing.occlusion_state,
            vlm_consistency=vlm_consistency if vlm_consistency != "not_checked" else existing.vlm_consistency,
            current_handling_policy=handling_policy,
            task_status="pending" if existing.task_status != "completed" else existing.task_status,
            class_name=candidate_class,
            last_seen_scene=scene_id,
        )

    def _candidate_class(self, detected: DetectedObject) -> str:
        original = detected.metadata.get("original_yolo_class_name") or detected.metadata.get("candidate_class") or detected.class_name
        return canonicalize_category_name(str(original))

    def _recognition_status(self, detected: DetectedObject) -> str:
        explicit = str(detected.metadata.get("recognition_status", "")).lower()
        if explicit in {"accepted", "review_required", "unknown"}:
            return explicit
        decision = str(detected.metadata.get("review_decision", "")).lower()
        if detected.class_name == UNKNOWN_CATEGORY or decision in {"unknown", "conflict"}:
            return "unknown"
        if bool(detected.metadata.get("need_human_review")) or decision in {"insufficient", "review_error", "uncertain"}:
            return "review_required"
        return "accepted"

    def _vlm_consistency(self, detected: DetectedObject) -> str:
        raw = str(detected.metadata.get("vlm_consistency_status") or detected.metadata.get("review_decision") or "not_checked").lower()
        return raw if raw in {"support", "conflict"} else "not_checked"

    def _handling_policy(self, candidate_class: str, recognition_status: str) -> str:
        if recognition_status == "unknown":
            return "robot_forbidden"
        if recognition_status == "review_required":
            return "human_review_required"
        spec = self.categories.get(candidate_class)
        return spec.default_handling_policy if spec is not None else "human_review_required"

    def _ensure_unknown_sample(self, instance: ObjectInstance, detected: Optional[DetectedObject]) -> UnknownSample:
        existing = [edge.target_id for edge in self.edges.values() if edge.source_id == instance.instance_id and edge.relation == "RECORDED_AS"]
        if existing:
            return self.unknown_samples[existing[-1]]
        self._unknown_counter += 1
        sample = UnknownSample(
            sample_id=f"unknown_sample_{self._unknown_counter:03d}",
            crop_ref=instance.crop_ref,
            mask_ref=instance.mask_ref,
            yolo_topk=dict((detected.metadata.get("yolo_topk") if detected else {}) or {instance.class_name: instance.yolo_confidence}),
            vlm_attributes=dict((detected.metadata.get("visual_attributes") if detected else {}) or {}),
        )
        self.unknown_samples[sample.sample_id] = sample
        self.add_relation(RelationEdge(instance.instance_id, "RECORDED_AS", sample.sample_id))
        return sample

    def _append_event(self, event: GraphEvent, relations: Iterable[Tuple[str, str]]) -> None:
        self.events.append(event)
        for relation, target_id in relations:
            self.add_relation(RelationEdge(event.event_id, relation, target_id))

    def _match_existing(self, detected: DetectedObject, candidate_class: str) -> Optional[str]:
        best_id: Optional[str] = None
        best_distance = float("inf")
        for instance in self.instances.values():
            if self.resolve_instance_category(instance.instance_id) != candidate_class:
                continue
            distance = self._distance(instance.center_xyz_camera, detected.center_xyz)
            if distance < best_distance:
                best_distance = distance
                best_id = instance.instance_id
        return best_id if best_id is not None and best_distance <= self.match_distance_threshold else None

    def _infer_near_relations(self, detected_objects: Iterable[DetectedObject]) -> List[DetectedRelation]:
        objects = list(detected_objects)
        relations: List[DetectedRelation] = []
        for index, source in enumerate(objects):
            for target in objects[index + 1 :]:
                if self._distance(source.center_xyz, target.center_xyz) <= 0.30:
                    relations.append(DetectedRelation(source.temp_id, "near", target.temp_id))
        return relations

    @staticmethod
    def _has_depth_update(detected: DetectedObject) -> bool:
        return bool(
            detected.depth_valid_ratio
            or detected.metadata.get("depth_valid_ratio") is not None
            or any(detected.center_xyz)
            or any(detected.observed_extent_3d)
        )

    @staticmethod
    def _bbox_from_metadata(metadata: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
        value = metadata.get("bbox_2d")
        if isinstance(value, (list, tuple)) and len(value) == 4:
            return tuple(float(item) for item in value)  # type: ignore[return-value]
        return None

    @staticmethod
    def _normalize_occlusion(value: str) -> str:
        normalized = str(value or "unknown").lower()
        return normalized if normalized in {"none", "partial", "unknown"} else "unknown"

    @staticmethod
    def _distance(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
        return sqrt(sum((left - right) ** 2 for left, right in zip(a, b)))

    @staticmethod
    def _blend_vector(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
        return tuple((left + right) / 2.0 for left, right in zip(a, b))  # type: ignore[return-value]
