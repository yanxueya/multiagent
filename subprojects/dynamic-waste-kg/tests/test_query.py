"""验证 test query 相关功能。"""

import unittest

from wastekg.core.models import DetectedObject, Observation
from wastekg.graph.query import build_planning_context
from wastekg.graph.store import KnowledgeGraph


class QueryTests(unittest.TestCase):
    def test_build_planning_context_returns_task_ready_view(self) -> None:
        graph = KnowledgeGraph()
        graph.apply_observation(
            Observation(
                frame_id="f1",
                source="realsense",
                objects=[
                    DetectedObject(temp_id="t1", class_name="brick", confidence=0.95, center_xyz=(0.0, 0.0, 0.0)),
                    DetectedObject(temp_id="t2", class_name="paint_can", confidence=0.90, center_xyz=(0.1, 0.1, 0.0), risk_level="high"),
                ],
            )
        )

        context = build_planning_context(graph, task={"target_categories": ["paint_can"], "max_candidates": 5})

        self.assertIn("candidates", context)
        self.assertGreaterEqual(context["candidate_count"], 1)
        self.assertTrue(any(item["class_name"] == "paint_can" for item in context["candidates"]))
        self.assertIn("graph_summary", context)


if __name__ == "__main__":
    unittest.main()
