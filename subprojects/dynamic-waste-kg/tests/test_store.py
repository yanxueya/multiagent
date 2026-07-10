"""验证 test store 相关功能。"""

import unittest

from wastekg.core.models import CategorySpec, Observation
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


if __name__ == "__main__":
    unittest.main()
