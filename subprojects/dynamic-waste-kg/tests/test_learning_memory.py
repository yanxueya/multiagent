"""验证 Scene 与 ObjectInstance 构成的短期记忆。"""

import unittest

from wastekg import seed_default_categories
from wastekg.core.models import DetectedObject, Observation
from wastekg.graph.store import KnowledgeGraph


class LearningMemoryTests(unittest.TestCase):
    def test_each_observation_creates_scene_and_preserves_long_term_categories(self) -> None:
        graph = KnowledgeGraph()
        seed_default_categories(graph)
        first = graph.apply_observation(Observation(frame_id="scene_001", source="camera", objects=[DetectedObject("d1", "brick", 0.90, center_xyz=(0.0, 0.0, 0.0))]))
        second = graph.apply_observation(Observation(frame_id="scene_002", source="camera", objects=[DetectedObject("d1", "brick", 0.95, center_xyz=(0.2, 0.0, 0.0))]))

        self.assertEqual(first["created_instances"], ["brick_01"])
        self.assertEqual(second["updated_instances"], ["brick_01"])
        self.assertEqual(len(graph.scenes), 2)
        self.assertIn(("scene_001", "CONTAINS", "brick_01"), graph.edges)
        self.assertIn(("scene_002", "CONTAINS", "brick_01"), graph.edges)
        self.assertAlmostEqual(graph.instances["brick_01"].center_xyz_camera[0], 0.1)
        self.assertEqual(len(graph.categories), 11)


if __name__ == "__main__":
    unittest.main()
