import unittest

from wastekg.models import CategorySpec, DetectedObject, Observation
from wastekg.store import KnowledgeGraph


class LearningAttributeTests(unittest.TestCase):
    def test_category_attributes_feed_instance_attributes(self) -> None:
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
                        confidence=0.95,
                        center_xyz=(0.1, 0.1, 0.1),
                        risk_level="unknown",
                    )
                ],
            )
        )

        instance = graph.instances["paint_can_01"]
        self.assertEqual(instance.risk_level, "high")
        self.assertFalse(instance.processable)
        self.assertEqual(graph.categories["paint_can"].material, "metal")

    def test_mark_processed_updates_task_status_and_events(self) -> None:
        graph = KnowledgeGraph()
        graph.apply_observation(
            Observation(
                frame_id="frame_001",
                source="realsense",
                objects=[
                    DetectedObject(
                        temp_id="t1",
                        class_name="brick",
                        confidence=0.9,
                        center_xyz=(0.0, 0.0, 0.0),
                    )
                ],
            )
        )

        before_events = len(graph.events)
        graph.mark_processed("brick_01", action="removed")
        instance = graph.instances["brick_01"]

        self.assertTrue(instance.processed_flag)
        self.assertEqual(instance.task_status, "completed")
        self.assertEqual(instance.last_action, "removed")
        self.assertGreater(len(graph.events), before_events)


if __name__ == "__main__":
    unittest.main()
