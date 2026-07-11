"""验证 test store 相关功能。"""

import unittest

from wastekg.core.models import CategorySpec, DetectedObject, Observation
from wastekg.graph.store import KnowledgeGraph


class StoreTests(unittest.TestCase):
    def test_register_category_and_ingest_observation(self) -> None:
        graph = KnowledgeGraph()
        graph.register_category(CategorySpec(name="brick"))
        summary = graph.apply_observation(Observation(frame_id="f1", source="realsense"))

        self.assertIn("brick", graph.categories)
        self.assertEqual(summary["frame_id"], "f1")
        self.assertIn("f1", graph.scenes)

    def test_create_instances_from_observation(self) -> None:
        graph = KnowledgeGraph()
        graph.register_category(CategorySpec(name="brick"))
        summary = graph.apply_observation(
            Observation(
                frame_id="f2",
                source="realsense",
            )
        )
        self.assertEqual(summary["relation_count"], 0)

    def test_same_class_without_depth_creates_distinct_instances(self) -> None:
        graph = KnowledgeGraph()
        graph.register_category(CategorySpec(name="glass"))

        graph.apply_observation(
            Observation(
                frame_id="f3",
                source="annotation",
                objects=[
                    DetectedObject("glass_a", "glass", 0.9),
                    DetectedObject("glass_b", "glass", 0.9),
                ],
            )
        )

        self.assertEqual(set(graph.instances), {"glass_01", "glass_02"})
        self.assertFalse(any(edge.relation == "NEAR" for edge in graph.edges.values()))


if __name__ == "__main__":
    unittest.main()
