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
        graph.record_execution_event("scene_001", "brick_01", execution_result="failure", failure_reason="grasp_failed")

        instance = graph.instances["brick_01"]
        self.assertEqual(instance.attempt_count, before + 1)
        self.assertEqual(instance.task_status, "failed")
        self.assertEqual(graph.events[-1].event_type, "ExecutionEvent")


if __name__ == "__main__":
    unittest.main()
