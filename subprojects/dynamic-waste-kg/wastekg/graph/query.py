"""把 KG 事实投影为规划器可读状态，不在 KG 中保存优先级或评分。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from wastekg.core.models import ObjectInstance
from wastekg.graph.store import KnowledgeGraph


def build_planning_context(graph: KnowledgeGraph, task: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """返回只读 graph_state；动态优先级必须由 action planning agent 计算。"""

    task = task or {}
    target_categories = {str(item) for item in task.get("target_categories", [])}
    max_candidates = int(task.get("max_candidates", 10))
    active = [instance for instance in graph.instances.values() if instance.task_status != "completed"]
    if target_categories:
        active = [instance for instance in active if graph.resolve_instance_category(instance.instance_id) in target_categories]

    # 这里只做稳定排序以便输出可复现，不产生 priority_tier 或 dynamic_priority_score。
    active.sort(key=lambda item: (item.recognition_status == "accepted", item.yolo_confidence, item.instance_id), reverse=True)
    active = active[:max_candidates]
    graph_state = [_instance_state(graph, instance) for instance in active]
    candidates = [dict(state) for state in graph_state]
    candidate_ids = {item["instance_id"] for item in candidates}

    return {
        "task": dict(task),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "graph_state": graph_state,
        "blocked": [item for item in graph_state if item["blocked"]],
        "risky": [item for item in graph_state if item["risk_level"] == "high"],
        "review_required": [item for item in graph_state if item["requires_review"]],
        "relations": [
            edge.to_dict()
            for edge in graph.edges.values()
            if edge.source_id in candidate_ids or edge.target_id in candidate_ids
        ],
        "graph_summary": {
            "category_count": len(graph.categories),
            "scene_count": len(graph.scenes),
            "instance_count": len(graph.instances),
            "unknown_sample_count": len(graph.unknown_samples),
            "unknown_cluster_count": len(graph.unknown_clusters),
            "edge_count": len(graph.edges),
            "event_count": len(graph.events),
        },
    }


def _instance_state(graph: KnowledgeGraph, instance: ObjectInstance) -> Dict[str, Any]:
    category_name = graph.resolve_instance_category(instance.instance_id)
    category = graph.categories.get(category_name)
    risk_level = category.risk_level if category is not None else "high"
    graspability_prior = category.graspability_prior if category is not None else "low"
    requires_review = (
        instance.recognition_status != "accepted"
        or instance.current_handling_policy != "auto_allowed"
        or category_name == "unknown"
    )
    depth_ready = instance.depth_valid_ratio >= 0.30
    reachable = instance.occlusion_state != "partial"
    grasp_feasible = depth_ready and reachable and graspability_prior in {"medium", "high"}
    blocked = instance.task_status == "failed" or instance.current_handling_policy == "robot_forbidden"
    can_attempt_now = not requires_review and not blocked and grasp_feasible and instance.attempt_count < 2
    reasons: list[str] = []
    if instance.recognition_status != "accepted":
        reasons.append(f"recognition_status={instance.recognition_status}")
    if instance.current_handling_policy != "auto_allowed":
        reasons.append(f"current_handling_policy={instance.current_handling_policy}")
    if not depth_ready:
        reasons.append("depth_valid_ratio<0.30")
    if not reachable:
        reasons.append("occlusion_state=partial")
    if graspability_prior == "low":
        reasons.append("graspability_prior=low")
    if instance.attempt_count >= 2:
        reasons.append("attempt_count>=2")
    return {
        "instance_id": instance.instance_id,
        "candidate_class": category_name,
        "recognition_status": instance.recognition_status,
        "current_handling_policy": instance.current_handling_policy,
        "task_status": instance.task_status,
        "attempt_count": instance.attempt_count,
        "yolo_confidence": instance.yolo_confidence,
        "center_xyz_camera": list(instance.center_xyz_camera),
        "depth_valid_ratio": instance.depth_valid_ratio,
        "observed_extent_3d": list(instance.observed_extent_3d),
        "occlusion_state": instance.occlusion_state,
        "vlm_consistency": instance.vlm_consistency,
        "risk_level": risk_level,
        "fragility": category.fragility if category is not None else "unknown",
        "graspability_prior": graspability_prior,
        "can_attempt_now": can_attempt_now,
        "requires_review": requires_review,
        "blocked": blocked,
        "reachable": reachable,
        "grasp_feasibility": grasp_feasible,
        "grasp_pose_feasible": grasp_feasible,
        "motion_path_collision_free": reachable,
        "feasibility_reasons": reasons,
    }
