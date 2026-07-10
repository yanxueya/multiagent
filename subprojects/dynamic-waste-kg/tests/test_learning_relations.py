"""验证文档允许的无属性关系集合。"""

import unittest

from wastekg import seed_default_categories
from wastekg.core.models import DetectedObject, DetectedRelation, Observation, RelationEdge
from wastekg.graph.store import KnowledgeGraph


class LearningRelationTests(unittest.TestCase):
    def test_near_is_recomputed_as_relation_without_properties(self) -> None:
        graph = KnowledgeGraph()
        seed_default_categories(graph)
        graph.apply_observation(
            Observation(
                frame_id="scene_001",
                source="depth_processor",
                objects=[DetectedObject("a", "brick", 0.95, center_xyz=(0.0, 0.0, 0.0)), DetectedObject("b", "glass", 0.90, center_xyz=(0.1, 0.0, 0.0))],
                relations=[DetectedRelation("a", "near", "b", confidence=0.2)],
            )
        )
        edge = graph.edges[("brick_01", "NEAR", "glass_01")]
        self.assertEqual(set(edge.to_dict()), {"source_id", "relation", "target_id"})

    def test_unsupported_legacy_relation_is_rejected(self) -> None:
        graph = KnowledgeGraph()
        with self.assertRaises(ValueError):
            graph.add_relation(RelationEdge("a", "on_top_of", "b"))


if __name__ == "__main__":
    unittest.main()
