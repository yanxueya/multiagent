from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import timedelta
from math import sqrt
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .models import (
    CategorySpec,
    DetectedObject,
    DetectedRelation,
    GraphEvent,
    ObjectInstance,
    Observation,
    RelationEdge,
)


class KnowledgeGraph:
    def __init__(self, *, match_distance_threshold: float = 0.25, stale_after_seconds: int = 30) -> None:
        self.match_distance_threshold = match_distance_threshold
        self.stale_after_seconds = stale_after_seconds
        self.categories: Dict[str, CategorySpec] = {}
        self.instances: Dict[str, ObjectInstance] = {}
        self.edges: Dict[Tuple[str, str, str], RelationEdge] = {}
        self.events: List[GraphEvent] = []
        self._track_map: Dict[str, str] = {}
        self._class_counters: Dict[str, int] = defaultdict(int)

    def register_category(self, category: CategorySpec) -> None:
        self.categories[category.name] = category
        self.events.append(
            GraphEvent(
                event_type="category_register",
                subject_id=category.name,
                after_state={
                    "category": category.category,
                    "risk_level": category.risk_level,
                    "fragility": category.fragility,
                    "graspability": category.graspability,
                    "pollution_level": category.pollution_level,
                },
                source="system",
            )
        )

    def generate_instance_id(self, class_name: str) -> str:
        self._class_counters[class_name] += 1
        return f"{class_name}_{self._class_counters[class_name]:02d}"

    def upsert_instance(self, instance: ObjectInstance, *, source: str = "system") -> ObjectInstance:
        before = self.instances.get(instance.instance_id)
        if before is None:
            instance.touch(frame_id=instance.last_seen_frame, source=source)
            self.instances[instance.instance_id] = instance
            self.events.append(
                GraphEvent(
                    event_type="instance_create",
                    subject_id=instance.instance_id,
                    after_state=instance.to_dict(),
                    source=source,
                )
            )
            return instance

        merged = replace(
            before,
            class_name=instance.class_name or before.class_name,
            center_xyz=instance.center_xyz or before.center_xyz,
            orientation=instance.orientation or before.orientation,
            bbox_3d=instance.bbox_3d if instance.bbox_3d is not None else before.bbox_3d,
            confidence=max(before.confidence, instance.confidence),
            priority=max(before.priority, instance.priority),
            processed_flag=before.processed_flag or instance.processed_flag,
            last_action=instance.last_action or before.last_action,
            task_status=instance.task_status or before.task_status,
            risk_level=instance.risk_level or before.risk_level,
            fragility_level=instance.fragility_level or before.fragility_level,
            graspability_level=instance.graspability_level or before.graspability_level,
            pollution_level=instance.pollution_level or before.pollution_level,
            occlusion_state=instance.occlusion_state or before.occlusion_state,
            contact_state=instance.contact_state or before.contact_state,
            support_state=instance.support_state or before.support_state,
            movable=before.movable and instance.movable,
            graspable=before.graspable and instance.graspable,
            processable=before.processable and instance.processable,
            blocked_by=list(sorted(set(before.blocked_by + instance.blocked_by))),
            supports=list(sorted(set(before.supports + instance.supports))),
            task_relevance=max(before.task_relevance, instance.task_relevance),
            observed_aliases=list(sorted(set(before.observed_aliases + instance.observed_aliases))),
            observation_count=before.observation_count,
            last_seen_frame=instance.last_seen_frame or before.last_seen_frame,
            source=instance.source or before.source,
            metadata={**before.metadata, **instance.metadata},
        )
        merged.touch(frame_id=instance.last_seen_frame or before.last_seen_frame, source=source)
        self.instances[instance.instance_id] = merged
        self.events.append(
            GraphEvent(
                event_type="instance_update",
                subject_id=instance.instance_id,
                before_state=before.to_dict(),
                after_state=merged.to_dict(),
                source=source,
            )
        )
        return merged

    def add_relation(self, edge: RelationEdge, *, source: str = "system") -> RelationEdge:
        key = edge.key()
        before = self.edges.get(key)
        if before is None:
            self.edges[key] = edge
            self._refresh_instance_links(edge)
            self.events.append(
                GraphEvent(
                    event_type="relation_create",
                    subject_id=edge.source_id,
                    relation=edge.relation,
                    after_state=edge.to_dict(),
                    source=source,
                )
            )
            return edge

        updated = RelationEdge(
            source_id=edge.source_id,
            relation=edge.relation,
            target_id=edge.target_id,
            confidence=max(before.confidence, edge.confidence),
            active=edge.active,
            created_at=before.created_at,
            updated_at=edge.updated_at,
            metadata={**before.metadata, **edge.metadata},
        )
        self.edges[key] = updated
        self._refresh_instance_links(updated)
        self.events.append(
            GraphEvent(
                event_type="relation_update",
                subject_id=edge.source_id,
                relation=edge.relation,
                before_state=before.to_dict(),
                after_state=updated.to_dict(),
                source=source,
            )
        )
        return updated

    def apply_observation(self, observation: Observation) -> Dict[str, Any]:
        resolved_ids: Dict[str, str] = {}
        created: List[str] = []
        updated: List[str] = []

        for detected in observation.objects:
            # 先把每个检测框映射成图谱中的“实例节点”
            # 规则是：同一个 temp_id 优先视为同一对象；否则再尝试按空间位置匹配旧实例。
            instance, created_flag = self._resolve_detection(detected, observation.frame_id, observation.source)
            resolved_ids[detected.temp_id] = instance.instance_id
            if created_flag:
                created.append(instance.instance_id)
            else:
                updated.append(instance.instance_id)
            self._track_map[detected.temp_id] = instance.instance_id
            self.upsert_instance(instance, source=observation.source)
            self._update_category_from_instance(instance)

        inferred_relations = list(observation.relations)
        inferred_relations.extend(self._infer_relations(observation.objects))
        for relation in inferred_relations:
            source_id = resolved_ids.get(relation.source_temp_id)
            target_id = resolved_ids.get(relation.target_temp_id)
            if not source_id or not target_id:
                continue
            self.add_relation(
                RelationEdge(
                    source_id=source_id,
                    relation=relation.relation,
                    target_id=target_id,
                    confidence=relation.confidence,
                    metadata=dict(relation.metadata),
                ),
                source=observation.source,
            )

        self._refresh_temporal_states()
        event = GraphEvent(
            event_type="observation",
            subject_id=observation.frame_id,
            after_state={
                "created_instances": created,
                "updated_instances": updated,
                "resolved_ids": resolved_ids,
            },
            source=observation.source,
            metadata=dict(observation.metadata),
        )
        self.events.append(event)
        return {
            "frame_id": observation.frame_id,
            "created_instances": created,
            "updated_instances": updated,
            "resolved_ids": resolved_ids,
            "relation_count": len(inferred_relations),
        }

    def mark_processed(self, instance_id: str, *, action: str, source: str = "executor") -> None:
        instance = self.instances[instance_id]
        before = instance.to_dict()
        instance.processed_flag = True
        instance.last_action = action
        instance.task_status = "completed"
        instance.priority = max(0, instance.priority - 1)
        instance.touch(frame_id=instance.last_seen_frame, source=source)
        self.events.append(
            GraphEvent(
                event_type="state_change",
                subject_id=instance_id,
                before_state=before,
                after_state=instance.to_dict(),
                source=source,
            )
        )

    def list_active_instances(self) -> List[ObjectInstance]:
        return [instance for instance in self.instances.values() if instance.task_status != "expired"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "categories": {name: self._category_to_dict(spec) for name, spec in self.categories.items()},
            "instances": {instance_id: instance.to_dict() for instance_id, instance in self.instances.items()},
            "edges": [edge.to_dict() for edge in self.edges.values()],
            "events": [event.to_dict() for event in self.events],
        }

    def _category_to_dict(self, spec: CategorySpec) -> Dict[str, Any]:
        return {
            "name": spec.name,
            "category": spec.category,
            "material": spec.material,
            "risk_level": spec.risk_level,
            "fragility": spec.fragility,
            "graspability": spec.graspability,
            "pollution_level": spec.pollution_level,
            "recyclability": spec.recyclability,
            "semantic_tags": list(spec.semantic_tags),
            "confidence_prior": spec.confidence_prior,
            "description": spec.description,
            "source_refs": list(spec.source_refs),
            "notes": spec.notes,
        }

    def _resolve_detection(self, detected: DetectedObject, frame_id: str, source: str) -> Tuple[ObjectInstance, bool]:
        if detected.temp_id in self._track_map:
            instance_id = self._track_map[detected.temp_id]
            existing = self.instances[instance_id]
            return self._merge_detection(existing, detected, frame_id, source), False

        candidate_id = self._match_existing(detected)
        if candidate_id is None:
            instance_id = self.generate_instance_id(detected.class_name)
            return (
                ObjectInstance(
                    instance_id=instance_id,
                    class_name=detected.class_name,
                    center_xyz=detected.center_xyz,
                    orientation=detected.orientation,
                    bbox_3d=detected.bbox_3d,
                    confidence=detected.confidence,
                    risk_level=detected.risk_level,
                    fragility_level="unknown",
                    graspability_level="unknown",
                    pollution_level="unknown",
                    task_status="active",
                    observed_aliases=[detected.temp_id],
                    last_seen_frame=frame_id,
                    source=source,
                    metadata=dict(detected.metadata),
                    priority=self._infer_priority(detected),
                ),
                True,
            )

        existing = self.instances[candidate_id]
        return self._merge_detection(existing, detected, frame_id, source), False

    def _merge_detection(self, existing: ObjectInstance, detected: DetectedObject, frame_id: str, source: str) -> ObjectInstance:
        # 短期记忆更新：保留旧状态，但用新观测覆盖位置、置信度和任务相关属性。
        merged = replace(
            existing,
            class_name=detected.class_name or existing.class_name,
            center_xyz=self._blend_vector(existing.center_xyz, detected.center_xyz),
            orientation=detected.orientation or existing.orientation,
            bbox_3d=detected.bbox_3d if detected.bbox_3d is not None else existing.bbox_3d,
            confidence=max(existing.confidence, detected.confidence),
            risk_level=detected.risk_level if detected.risk_level != "unknown" else existing.risk_level,
            task_status="active" if not existing.processed_flag else existing.task_status,
            observed_aliases=list(sorted(set(existing.observed_aliases + [detected.temp_id]))),
            last_seen_frame=frame_id,
            priority=max(existing.priority, self._infer_priority(detected)),
            task_relevance=max(existing.task_relevance, detected.confidence),
            metadata={**existing.metadata, **detected.metadata},
            source=source or existing.source,
            fragility_level=existing.fragility_level,
            graspability_level=existing.graspability_level,
            pollution_level=existing.pollution_level,
        )
        return merged

    def _match_existing(self, detected: DetectedObject) -> Optional[str]:
        best_id: Optional[str] = None
        best_distance = float("inf")
        for instance in self.instances.values():
            if instance.class_name != detected.class_name:
                continue
            distance = self._distance(instance.center_xyz, detected.center_xyz)
            if distance < best_distance:
                best_distance = distance
                best_id = instance.instance_id
        if best_id is not None and best_distance <= self.match_distance_threshold:
            return best_id
        return None

    def _infer_priority(self, detected: DetectedObject) -> int:
        score = 1
        risk = (detected.risk_level or "").lower()
        if risk in {"high", "critical", "dangerous", "hazardous"}:
            score += 4
        elif risk in {"medium"}:
            score += 2
        if detected.confidence >= 0.85:
            score += 1
        return score

    def _update_category_from_instance(self, instance: ObjectInstance) -> None:
        spec = self.categories.get(instance.class_name)
        if spec is None:
            return
        # 长期知识层只提供稳定先验，不应该被一次观测完全改写。
        # 这里做的是“先验 -> 实例”的投影，而不是反向覆盖类别知识。
        instance.risk_level = instance.risk_level if instance.risk_level != "unknown" else spec.risk_level
        instance.fragility_level = spec.fragility if instance.fragility_level == "unknown" else instance.fragility_level
        instance.graspability_level = spec.graspability if instance.graspability_level == "unknown" else instance.graspability_level
        instance.pollution_level = spec.pollution_level if instance.pollution_level == "unknown" else instance.pollution_level
        instance.graspable = instance.graspability_level in {"low", "medium"}
        instance.processable = instance.processable and spec.risk_level not in {"high", "critical", "hazardous"}

    def _infer_relations(self, detected_objects: Iterable[DetectedObject]) -> List[DetectedRelation]:
        objects = list(detected_objects)
        relations: List[DetectedRelation] = []
        for i, source in enumerate(objects):
            for j, target in enumerate(objects):
                if i == j:
                    continue
                dx = source.center_xyz[0] - target.center_xyz[0]
                dy = source.center_xyz[1] - target.center_xyz[1]
                dz = source.center_xyz[2] - target.center_xyz[2]
                planar_distance = sqrt(dx * dx + dy * dy)
                full_distance = sqrt(dx * dx + dy * dy + dz * dz)
                if planar_distance <= 0.12 and dz >= 0.03:
                    relations.append(
                        DetectedRelation(
                            source_temp_id=source.temp_id,
                            relation="on_top_of",
                            target_temp_id=target.temp_id,
                            confidence=min(source.confidence, target.confidence),
                        )
                    )
                elif full_distance <= 0.08:
                    relations.append(
                        DetectedRelation(
                            source_temp_id=source.temp_id,
                            relation="touching",
                            target_temp_id=target.temp_id,
                            confidence=min(source.confidence, target.confidence),
                        )
                    )
                elif full_distance <= 0.30:
                    relations.append(
                        DetectedRelation(
                            source_temp_id=source.temp_id,
                            relation="near",
                            target_temp_id=target.temp_id,
                            confidence=min(source.confidence, target.confidence) * 0.8,
                        )
                    )
        return relations

    def _refresh_instance_links(self, edge: RelationEdge) -> None:
        source = self.instances.get(edge.source_id)
        target = self.instances.get(edge.target_id)
        if source is None or target is None:
            return
        # 关系边不仅是“连线”，还会反过来改变实例的可处理性和阻塞状态。
        if edge.relation == "blocked_by":
            if target.instance_id not in source.blocked_by:
                source.blocked_by.append(target.instance_id)
            source.processable = False
        elif edge.relation == "supports":
            if target.instance_id not in source.supports:
                source.supports.append(target.instance_id)
        elif edge.relation == "on_top_of":
            source.support_state = "on_top_of"
            target.support_state = "supporting"
            if target.instance_id not in source.blocked_by:
                source.blocked_by.append(target.instance_id)
                source.processable = False
        elif edge.relation == "touching":
            source.contact_state = "touching"
            target.contact_state = "touching"
        elif edge.relation == "occluding":
            source.occlusion_state = "occluding"
            if target.instance_id not in source.blocked_by:
                source.blocked_by.append(target.instance_id)
        elif edge.relation == "requires_prior_action":
            if target.instance_id not in source.blocked_by:
                source.blocked_by.append(target.instance_id)
                source.processable = False

    def _refresh_temporal_states(self) -> None:
        now = max((event.timestamp for event in self.events), default=None)
        if now is None:
            return
        stale_threshold = now - timedelta(seconds=self.stale_after_seconds)
        for instance in self.instances.values():
            if instance.updated_at < stale_threshold and not instance.processed_flag:
                instance.task_status = "weak_memory"

    def _distance(self, a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
        dx = a[0] - b[0]
        dy = a[1] - b[1]
        dz = a[2] - b[2]
        return sqrt(dx * dx + dy * dy + dz * dz)

    def _blend_vector(self, a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
        return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, (a[2] + b[2]) / 2.0)
