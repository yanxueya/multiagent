"""验证 test learning memory 相关功能。"""

import unittest

from wastekg.core.models import CategorySpec, DetectedObject, Observation
from wastekg.graph.store import KnowledgeGraph


class LearningMemoryTests(unittest.TestCase):
    def test_long_term_knowledge_persists_across_observations(self) -> None:
        graph = KnowledgeGraph()
        graph.register_category(
            CategorySpec(
                name="paint_can",
                category="hazardous_waste",
                material="metal",
                risk_level="high",
                graspability="low",
            )
        )

        graph.apply_observation(
            Observation(
                frame_id="frame_001",
                source="realsense",
                objects=[
                    DetectedObject(
                        temp_id="t1",
                        class_name="paint_can",
                        confidence=0.90,
                        center_xyz=(0.1, 0.1, 0.05),
                        risk_level="unknown",
                    )
                ],
            )
        )

        graph.apply_observation(
            Observation(
                frame_id="frame_002",
                source="realsense",
                objects=[
                    DetectedObject(
                        temp_id="t1",
                        class_name="paint_can",
                        confidence=0.97,
                        center_xyz=(0.2, 0.2, 0.06),
                        risk_level="unknown",
                    )
                ],
            )
        )

        instance = graph.instances["paint_can_01"]
        self.assertEqual(instance.risk_level, "high")
        self.assertEqual(graph.categories["paint_can"].material, "metal")
        self.assertEqual(instance.class_name, "paint_can")
        self.assertGreaterEqual(instance.observation_count, 2)

    def test_short_term_memory_updates_position_without_new_instance(self) -> None:
        graph = KnowledgeGraph()

        first = graph.apply_observation(
            Observation(
                frame_id="frame_001",
                source="realsense",
                objects=[
                    DetectedObject(
                        temp_id="t1",
                        class_name="brick",
                        confidence=0.88,
                        center_xyz=(0.0, 0.0, 0.0),
                    )
                ],
            )
        )
        second = graph.apply_observation(
            Observation(
                frame_id="frame_002",
                source="realsense",
                objects=[
                    DetectedObject(
                        temp_id="t1",
                        class_name="brick",
                        confidence=0.91,
                        center_xyz=(0.3, 0.0, 0.0),
                    )
                ],
            )
        )

        instance = graph.instances["brick_01"]
        self.assertEqual(first["created_instances"], ["brick_01"])
        self.assertEqual(second["updated_instances"], ["brick_01"])
        self.assertAlmostEqual(instance.center_xyz[0], 0.15)


if __name__ == "__main__":
    unittest.main()
