"""把 LangGraph 工具契约映射到内存 KnowledgeGraph，不新增 KG 属性。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class WasteKgRuntimeAdapter:
    """为候选读取、人工复核和四类受控写入提供统一 KG 后端。"""

    graph: Any
    transient_objects: dict[str, Any]

    def candidate_loader(self, scene_id: str, instance_ids: list[str], goal: dict[str, Any]) -> list[dict[str, Any]]:
        context = self._planning_context(goal, scene_id=scene_id)
        allowed = set(instance_ids)
        return [item for item in context["candidates"] if item["instance_id"] in allowed and item["scene_id"] == scene_id]

    def review_payload_loader(self, instance_ids: list[str], state: dict[str, Any]) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for instance_id in instance_ids:
            instance = self.graph.instances.get(instance_id)
            if instance is None:
                continue
            payload.append(
                {
                    "instance_id": instance_id,
                    "candidate_class": self.graph.resolve_instance_category(instance_id),
                    "recognition_status": instance.recognition_status,
                    "current_handling_policy": instance.current_handling_policy,
                    "crop_ref": instance.crop_ref,
                    "mask_ref": instance.mask_ref,
                }
            )
        return payload

    def knowledge_query_runner(self, goal: dict[str, Any]) -> dict[str, Any]:
        query = str(goal.get("query", "summary"))
        return {
            "status": "complete",
            "result_ref": f"kg://history/{query}",
            "summary": {
                "scene_count": len(self.graph.scenes),
                "instance_count": len(self.graph.instances),
                "event_count": len(self.graph.events),
            },
        }

    def action_already_executed(self, action_id: str) -> bool:
        return bool(self.graph.has_execution_action(action_id))

    def write_backend(self, request: dict[str, Any]) -> dict[str, Any]:
        write_type = str(request["write_type"])
        payload = dict(request["payload"])
        if write_type == "perception":
            return self._write_perception(payload)
        if write_type == "planning":
            return self._write_planning(payload)
        if write_type == "human_review":
            return self._write_human_review(payload)
        if write_type == "execution":
            return self._write_execution(payload)
        raise ValueError(f"Unsupported KG write_type: {write_type}")

    def _write_perception(self, payload: dict[str, Any]) -> dict[str, Any]:
        observation_ref = str(payload.get("observation_ref", ""))
        if not observation_ref or observation_ref not in self.transient_objects:
            raise ValueError("Perception KG write requires a resolvable observation_ref")
        observation = self.transient_objects.pop(observation_ref)
        applied = self.graph.apply_observation(observation)
        context = self._planning_context({}, scene_id=str(applied["scene_id"]))
        return {
            "status": "committed",
            "kg_summary_ref": f"kg://scene/{applied['scene_id']}",
            "eligible_instance_ids": list(context["eligible_instance_ids"]),
            "review_instance_ids": [item["instance_id"] for item in context["review_required"]],
            "created_instance_ids": list(applied["created_instances"]),
            "updated_instance_ids": list(applied["updated_instances"]),
        }

    def _write_planning(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan = dict(payload["action_plan"])
        event = self.graph.record_planning_event(
            str(plan["scene_id"]),
            str(plan.get("target_instance_id", "")),
            planned_action=str(payload["planned_action"]),
            reason=str(payload.get("reason", "")),
            action_id=str(plan.get("action_id", "")),
        )
        return {"status": "committed", "event_id": event.event_id}

    def _write_human_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        for item in payload.get("review_results", []):
            self.graph.apply_human_review(
                str(item["instance_id"]),
                review_action=str(item["review_action"]),
                reason=str(item.get("reason", "")),
                confirmed_category=item.get("confirmed_category"),
            )
        context = self._planning_context({}, scene_id=str(payload.get("scene_id", "")))
        return {
            "status": "committed",
            "remaining_review_instance_ids": [item["instance_id"] for item in context["review_required"]],
            "eligible_instance_ids": list(context["eligible_instance_ids"]),
        }

    def _write_execution(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = dict(payload["execution_result"])
        event = self.graph.record_execution_event(
            str(result["scene_id"]),
            str(result["target_instance_id"]),
            action_id=str(result["action_id"]),
            physical_attempt_started=bool(result["physical_attempt_started"]),
            execution_result=str(result["execution_status"]),
            failure_reason=str(result.get("failure_reason", "")),
        )
        return {"status": "committed", "event_id": event.event_id}

    def _planning_context(self, goal: dict[str, Any], *, scene_id: str = "") -> dict[str, Any]:
        from wastekg.graph.query import build_planning_context

        return build_planning_context(
            self.graph,
            task={
                "target_categories": list(goal.get("target_categories", [])),
                "max_candidates": int(goal.get("max_candidates", 100)),
                "scene_id": scene_id,
            },
        )
