from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from .store import KnowledgeGraph


def build_planning_context(graph: KnowledgeGraph, task: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    # 这个函数的职责很简单：把图谱整理成“规划器可以直接读取的视图”。
    task = task or {}
    target_categories = set(task.get("target_categories", []))
    max_candidates = int(task.get("max_candidates", 10))

    active_instances = [instance for instance in graph.instances.values() if not instance.processed_flag]
    if target_categories:
        active_instances = [
            instance
            for instance in active_instances
            if instance.class_name in target_categories or instance.risk_level in target_categories
        ]

    active_instances.sort(
        key=lambda item: (
            item.processable and item.task_status != "needs_review",
            item.priority,
            item.confidence,
            item.observation_count,
        ),
        reverse=True,
    )
    candidates = [instance.to_dict() for instance in active_instances[:max_candidates]]

    blocked = [
        instance.to_dict()
        for instance in active_instances
        if not instance.processable or instance.blocked_by or instance.task_status == "blocked"
    ]
    risky = [
        instance.to_dict()
        for instance in active_instances
        if instance.risk_level in {"high", "critical", "hazardous"}
    ]
    review_required = [
        instance.to_dict()
        for instance in active_instances
        if instance.task_status == "needs_review" or not instance.processable
    ]
    relations = [
        edge.to_dict()
        for edge in graph.edges.values()
        if edge.source_id in {item["instance_id"] for item in candidates}
        or edge.target_id in {item["instance_id"] for item in candidates}
    ]

    return {
        "task": task,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "blocked": blocked,
        "risky": risky,
        "review_required": review_required,
        "relations": relations,
        "graph_summary": {
            "category_count": len(graph.categories),
            "instance_count": len(graph.instances),
            "edge_count": len(graph.edges),
            "event_count": len(graph.events),
        },
    }
