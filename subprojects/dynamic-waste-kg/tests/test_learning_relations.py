import unittest

from wastekg.models import DetectedObject, Observation
from wastekg.query import build_planning_context
from wastekg.store import KnowledgeGraph


class LearningRelationTests(unittest.TestCase):
    def test_on_top_of_creates_blocking_relation(self) -> None:
        graph = KnowledgeGraph()
        graph.apply_observation(
            Observation(
                frame_id="frame_001",
                source="realsense",
                objects=[
                    DetectedObject(temp_id="a", class_name="brick", confidence=0.95, center_xyz=(0.0, 0.0, 0.0)),
                    DetectedObject(temp_id="b", class_name="paint_can", confidence=0.92, center_xyz=(0.0, 0.0, 0.12), risk_level="high"),
                ],
            )
        )

        paint_can = graph.instances["paint_can_01"]
        brick = graph.instances["brick_01"]

        self.assertIn("brick_01", paint_can.blocked_by)
        self.assertEqual(paint_can.support_state, "on_top_of")
        self.assertEqual(brick.support_state, "supporting")
        self.assertFalse(paint_can.processable)

    def test_planning_context_uses_relations_and_priority(self) -> None:
        graph = KnowledgeGraph()
        graph.apply_observation(
            Observation(
                frame_id="frame_001",
                source="realsense",
                objects=[
                    DetectedObject(temp_id="a", class_name="brick", confidence=0.95, center_xyz=(0.0, 0.0, 0.0)),
                    DetectedObject(temp_id="b", class_name="paint_can", confidence=0.92, center_xyz=(0.0, 0.0, 0.12), risk_level="high"),
                    DetectedObject(temp_id="c", class_name="metal", confidence=0.85, center_xyz=(0.3, 0.2, 0.0), risk_level="medium"),
                ],
            )
        )

        context = build_planning_context(graph)
        self.assertIn("candidates", context)
        self.assertIn("blocked", context)
        self.assertIn("risky", context)
        self.assertEqual(context["candidates"][0]["class_name"], "paint_can")
        self.assertTrue(any(item["class_name"] == "paint_can" for item in context["blocked"]))
        self.assertTrue(any(item["class_name"] == "paint_can" for item in context["risky"]))


if __name__ == "__main__":
    unittest.main()
