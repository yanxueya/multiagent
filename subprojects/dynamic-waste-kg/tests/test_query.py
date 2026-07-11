"""验证 KG 向规划器投影状态但不保存优先级评分。"""

import unittest

from wastekg import seed_default_categories
from wastekg.core.models import DetectedObject, Observation
from wastekg.graph.query import build_planning_context
from wastekg.graph.store import KnowledgeGraph


class QueryTests(unittest.TestCase):
    def test_scene_filter_excludes_stale_instances_from_current_candidates(self) -> None:
        graph = KnowledgeGraph()
        seed_default_categories(graph)
        graph.apply_observation(
            Observation(frame_id="scene_001", source="realsense", objects=[DetectedObject("a", "brick", 0.95, depth_valid_ratio=0.8, occlusion_state="none")])
        )
        graph.apply_observation(
            Observation(frame_id="scene_002", source="realsense", objects=[DetectedObject("b", "wood", 0.95, depth_valid_ratio=0.8, occlusion_state="none")])
        )

        context = build_planning_context(graph, task={"scene_id": "scene_002"})

        self.assertEqual([item["instance_id"] for item in context["candidates"]], ["wood_01"])

    def test_build_planning_context_uses_category_relations(self) -> None:
        graph = KnowledgeGraph()
        seed_default_categories(graph)
        graph.apply_observation(
            Observation(
                frame_id="scene_001",
                source="realsense",
                objects=[DetectedObject("d1", "brick", 0.95, depth_valid_ratio=0.8, occlusion_state="none")],
            )
        )
        context = build_planning_context(graph, task={"target_categories": ["brick"], "max_candidates": 5})

        self.assertEqual(context["candidate_count"], 1)
        self.assertEqual(context["candidates"][0]["candidate_class"], "brick")
        self.assertTrue(context["graph_state"][0]["can_attempt_now"])
        self.assertNotIn("task_value", context["graph_state"][0])
        self.assertNotIn("dynamic_priority_score", context["graph_state"][0])

    def test_review_policy_and_depth_are_hard_feasibility_gates(self) -> None:
        graph = KnowledgeGraph()
        seed_default_categories(graph)
        graph.apply_observation(
            Observation(
                frame_id="scene_001",
                source="realsense",
                objects=[
                    DetectedObject("a", "brick", 0.95, depth_valid_ratio=0.8, occlusion_state="none"),
                    DetectedObject("b", "glass", 0.92, depth_valid_ratio=0.8, occlusion_state="none"),
                    DetectedObject("c", "wood", 0.93, depth_valid_ratio=0.1, occlusion_state="none"),
                ],
            )
        )
        state = {item["instance_id"]: item for item in build_planning_context(graph)["graph_state"]}

        self.assertTrue(state["brick_01"]["can_attempt_now"])
        self.assertFalse(state["glass_01"]["can_attempt_now"])
        self.assertTrue(state["glass_01"]["requires_review"])
        self.assertIn("current_handling_policy=human_confirmation_required", state["glass_01"]["feasibility_reasons"])
        self.assertFalse(state["wood_01"]["can_attempt_now"])
        self.assertTrue(state["wood_01"]["requires_review"])
        self.assertIn("wood_01", [item["instance_id"] for item in build_planning_context(graph)["review_required"]])


if __name__ == "__main__":
    unittest.main()
