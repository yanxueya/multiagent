"""验证单步规划、字典序和 KG Writer 严格边界。"""

import unittest

from agent_system.components.kg_writer import validate_kg_write
from agent_system.planner import build_single_action_plan, rank_candidates
from agent_system.schemas.decision import CandidateSnapshot


def candidate(instance_id: str, **overrides):
    values = {
        "instance_id": instance_id,
        "scene_id": "scene_001",
        "class_name": "brick",
        "recognition_status": "accepted",
        "current_handling_policy": "auto_allowed",
        "task_status": "pending",
        "attempt_count": 0,
        "depth_valid_ratio": 0.90,
        "occlusion_state": "none",
        "graspability_prior": "medium",
        "near_neighbor_count": 0,
        "motion_distance_estimate": 0.5,
    }
    values.update(overrides)
    return CandidateSnapshot(**values)


class DecisionLayerTests(unittest.TestCase):
    def test_planner_returns_exactly_one_robot_action(self) -> None:
        plan = build_single_action_plan(
            [candidate("brick_01"), candidate("brick_02", depth_valid_ratio=0.80)],
            scene_id="scene_001",
            user_goal={"target_categories": ["brick"]},
        )

        self.assertEqual(plan.action_type, "robot_grasp")
        self.assertEqual(plan.target_instance_id, "brick_01")
        self.assertTrue(plan.replan_after_execution)

    def test_phase_one_ranking_is_lexicographic_without_weights(self) -> None:
        ranked = rank_candidates(
            [
                candidate("brick_far", depth_valid_ratio=0.80, graspability_prior="high"),
                candidate("brick_near", depth_valid_ratio=0.90, graspability_prior="medium"),
                candidate("brick_crowded", depth_valid_ratio=0.90, graspability_prior="medium", near_neighbor_count=3),
            ]
        )

        self.assertEqual([item.instance_id for item in ranked], ["brick_near", "brick_crowded", "brick_far"])
        with self.assertRaisesRegex(RuntimeError, "not enabled"):
            rank_candidates(ranked, use_execution_history=True)

    def test_failed_or_occluded_object_is_not_directly_planned(self) -> None:
        plan = build_single_action_plan(
            [candidate("brick_failed", task_status="failed"), candidate("brick_hidden", occlusion_state="partial")],
            scene_id="scene_001",
        )

        self.assertEqual(plan.action_type, "no_action")

    def test_stale_scene_forces_rescan(self) -> None:
        plan = build_single_action_plan([candidate("brick_01")], scene_id="scene_001", scene_is_fresh=False)
        self.assertEqual(plan.action_type, "rescan")

    def test_kg_writer_rejects_undefined_fields_and_free_cypher(self) -> None:
        valid = validate_kg_write(
            {
                "write_type": "planning",
                "payload": {"action_plan": {}, "planned_action": "no_action", "reason": "none"},
            }
        )
        self.assertEqual(valid["write_type"], "planning")

        with self.assertRaisesRegex(ValueError, "Undefined"):
            validate_kg_write({"write_type": "execution", "payload": {"execution_result": {}, "new_kg_property": 1}})
        with self.assertRaisesRegex(ValueError, "Undefined"):
            validate_kg_write({"write_type": "perception", "payload": {"eligible_instance_ids": ["brick_01"]}})
        with self.assertRaisesRegex(ValueError, "undefined fields"):
            validate_kg_write({"write_type": "planning", "payload": {}, "cypher": "MATCH (n) RETURN n"})


if __name__ == "__main__":
    unittest.main()
