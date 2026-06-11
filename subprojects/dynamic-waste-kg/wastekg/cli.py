from __future__ import annotations

import argparse
import json
from typing import Any, Dict

from .knowledge_base import seed_default_categories
from .models import DetectedObject, Observation
from .query import build_planning_context
from .store import KnowledgeGraph


def build_demo_graph() -> KnowledgeGraph:
    # 这是一个最小演示图谱，用来帮助你理解“长期知识 + 短期记忆 + 关系”的整体结构。
    graph = KnowledgeGraph()
    seed_default_categories(graph)

    observation = Observation(
        frame_id="demo_frame_001",
        source="demo_sensor",
        objects=[
            DetectedObject(temp_id="t1", class_name="brick", confidence=0.96, center_xyz=(0.10, 0.10, 0.00)),
            DetectedObject(temp_id="t2", class_name="waste_paint_can", confidence=0.91, center_xyz=(0.11, 0.11, 0.08), risk_level="high"),
            DetectedObject(temp_id="t3", class_name="metal", confidence=0.88, center_xyz=(0.30, 0.20, 0.02)),
        ],
    )
    graph.apply_observation(observation)
    return graph


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dynamic waste knowledge graph demo")
    parser.add_argument("--json", action="store_true", help="Print the graph snapshot as JSON")
    parser.add_argument("--task", default="", help="Optional task label for planning-context extraction")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    graph = build_demo_graph()
    context = build_planning_context(
        graph,
        task={"name": args.task} if args.task else {},
    )
    if args.json:
        print(json.dumps({"graph": graph.to_dict(), "planning_context": context}, ensure_ascii=False, indent=2))
        return 0

    print("Dynamic Waste Knowledge Graph Demo")
    print(f"Categories: {len(graph.categories)}")
    print(f"Instances: {len(graph.instances)}")
    print(f"Relations: {len(graph.edges)}")
    print(f"Events: {len(graph.events)}")
    print("Top planning candidates:")
    for item in context["candidates"]:
        print(f"- {item['instance_id']} | {item['class_name']} | priority={item['priority']} | status={item['task_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
