"""验证类别关系、处理权限和真实执行计数。"""

import unittest

from wastekg import seed_default_categories
from wastekg.core.models import DetectedObject, Observation
from wastekg.graph.store import KnowledgeGraph


class LearningAttributeTests(unittest.TestCase):
    def test_category_is_relation_not_instance_property(self) -> None:
        graph = KnowledgeGraph()
        seed_default_categories(graph)
        graph.apply_observation(Observation(frame_id="scene_001", source="camera", objects=[DetectedObject("d1", "glass", 0.95)]))

        instance = graph.instances["glass_01"]
        self.assertNotIn("class_name", instance.to_dict())
        self.assertEqual(graph.resolve_instance_category(instance.instance_id), "glass")
        self.assertIn(("glass_01", "CANDIDATE_OF", "glass"), graph.edges)
        self.assertEqual(instance.current_handling_policy, "human_confirmation_required")

    def test_execution_event_increments_attempt_count_for_real_action(self) -> None:
        graph = KnowledgeGraph()
        seed_default_categories(graph)
        graph.apply_observation(Observation(frame_id="scene_001", source="camera", objects=[DetectedObject("d1", "brick", 0.95)]))
        before = graph.instances["brick_01"].attempt_count
        graph.record_execution_event(
            "scene_001",
            "brick_01",
            action_id="action_001",
            physical_attempt_started=True,
            execution_result="failure",
            failure_reason="grasp_failed",
        )

        instance = graph.instances["brick_01"]
        self.assertEqual(instance.attempt_count, before + 1)
        self.assertEqual(instance.task_status, "failed")
        self.assertEqual(graph.events[-1].event_type, "ExecutionEvent")
        self.assertEqual(graph.events[-1].attributes["action_id"], "action_001")
        self.assertTrue(graph.has_execution_action("action_001"))

        with self.assertRaisesRegex(ValueError, "Duplicate physical action_id"):
            graph.record_execution_event(
                "scene_001",
                "brick_01",
                action_id="action_001",
                physical_attempt_started=True,
                execution_result="failure",
            )

        graph.apply_observation(
            Observation(
                frame_id="scene_002",
                source="camera",
                objects=[DetectedObject("d1", "brick", 0.96)],
            )
        )
        self.assertEqual(graph.instances["brick_01"].task_status, "pending")
        self.assertEqual(graph.instances["brick_01"].attempt_count, before + 1)

    def test_planning_event_does_not_mark_physical_processing_started(self) -> None:
        graph = KnowledgeGraph()
        seed_default_categories(graph)
        graph.apply_observation(Observation(frame_id="scene_001", source="camera", objects=[DetectedObject("d1", "brick", 0.95)]))

        graph.record_planning_event(
            "scene_001",
            "brick_01",
            planned_action="robot_grasp",
            reason="selected by lexicographic ranking",
            action_id="action_plan_001",
        )

        self.assertEqual(graph.instances["brick_01"].task_status, "pending")
        self.assertEqual(graph.instances["brick_01"].attempt_count, 0)

    def test_discard_detection_preserves_auditable_target_node(self) -> None:
        graph = KnowledgeGraph()
        seed_default_categories(graph)
        graph.apply_observation(Observation(frame_id="scene_001", source="camera", objects=[DetectedObject("d1", "brick", 0.95)]))

        graph.apply_human_review("brick_01", review_action="discard_detection", reason="false positive")

        instance = graph.instances["brick_01"]
        self.assertEqual(instance.task_status, "completed")
        self.assertEqual(instance.current_handling_policy, "robot_forbidden")
        self.assertIn((graph.events[-1].event_id, "REVIEWS", "brick_01"), graph.edges)


if __name__ == "__main__":
    unittest.main()
