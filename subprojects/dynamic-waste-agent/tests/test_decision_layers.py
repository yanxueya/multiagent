"""验证 KG 状态与规划期动态优先级的职责边界。"""

import unittest

from agent_system.graph import world_model_adapter_node
from agent_system.planner import build_ordered_plan
from agent_system.schemas.decision import GraphFeasibilityState
from agent_system.state import WasteTaskState


class DecisionLayerTests(unittest.TestCase):
    def test_kg_adapter_does_not_add_planning_score(self) -> None:
        result = world_model_adapter_node({"knowledge_context": {"graph_state": [{"instance_id": "wood_01", "candidate_class": "wood", "can_attempt_now": True, "requires_review": False, "blocked": False}]}})

        self.assertNotIn("task_value", result["graph_state"][0])
        self.assertNotIn("dynamic_priority_score", result["graph_state"][0])
        self.assertEqual(result["audit_trail"][-1]["summary"]["priority_source"], "action_planning_agent")

    def test_planner_filters_infeasible_object_before_dynamic_ranking(self) -> None:
        states = [
            GraphFeasibilityState("glass_01", "glass", False, True, False, yolo_confidence=0.99, recognition_status="accepted", current_handling_policy="human_review_required"),
            GraphFeasibilityState("brick_01", "brick", True, False, False, yolo_confidence=0.80, recognition_status="accepted", current_handling_policy="auto_allowed"),
        ]
        decision = build_ordered_plan(states, objective="recover glass")

        self.assertEqual(decision.steps[0].target_instance_id, "brick_01")
        self.assertEqual(decision.steps[0].action_type, "robot_grasp")
        self.assertGreater(decision.deferred[0]["dynamic_priority_score"], decision.steps[0].dynamic_priority_score)
        self.assertNotIn("task_value", decision.deferred[0])

    def test_target_match_changes_priority_only_inside_plan(self) -> None:
        states = [
            GraphFeasibilityState("wood_01", "wood", True, False, False, yolo_confidence=0.70, recognition_status="accepted", current_handling_policy="auto_allowed"),
            GraphFeasibilityState("brick_01", "brick", True, False, False, yolo_confidence=0.95, recognition_status="accepted", current_handling_policy="auto_allowed"),
        ]
        decision = build_ordered_plan(states, objective="recover wood")

        self.assertEqual(decision.steps[0].target_instance_id, "wood_01")
        self.assertEqual(decision.steps[0].priority_tier, "high")

    def test_shared_state_keeps_graph_and_plan_separate(self) -> None:
        state = WasteTaskState(task_id="task_001", goal="clear sortable debris")
        self.assertEqual(state.graph_state, [])
        self.assertEqual(state.planning_decision, {})
        self.assertFalse(hasattr(state, "value_assessments"))


if __name__ == "__main__":
    unittest.main()
