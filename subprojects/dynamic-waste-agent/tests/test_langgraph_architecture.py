"""验证 LangGraph 风格编排中的智能体与系统组件边界。"""

import unittest

from agent_system.graph import (
    build_langgraph_app,
    describe_graph,
    route_after_planning,
    run_dry_graph,
)


class LangGraphArchitectureTests(unittest.TestCase):
    def test_describe_graph_separates_agents_from_world_model_and_gates(self) -> None:
        description = describe_graph()

        self.assertEqual(description["status"], "langgraph_runtime_ready")
        self.assertEqual(
            description["agents"],
            [
                "supervisor_agent",
                "perception_agent",
                "action_planning_agent",
                "execution_agent",
            ],
        )
        self.assertEqual(
            description["components"],
            [
                "world_model_adapter",
                "risk_gate",
                "human_control_gate",
                "ros2_bridge",
                "feedback_update",
            ],
        )
        self.assertNotIn("knowledge_agent", description["agents"])
        self.assertNotIn("risk_agent", description["agents"])
        self.assertNotIn("value_function", description["agents"])
        self.assertIn("graph_state", description["decision_rule"])
        self.assertIn("dynamic_priority_score", description["decision_rule"])

    def test_dry_graph_separates_kg_state_value_and_plan(self) -> None:
        result = run_dry_graph(
            {
                "task_id": "task_001",
                "objective": "recover wood",
                "target_categories": ["wood"],
                "perception_events": [
                    {
                        "instance_id": "wood_01",
                        "class_name": "wood",
                        "recyclability": "high",
                        "handling_mode": "robot_grasp",
                        "risk_level": "low",
                    }
                ],
                "knowledge_context": {
                    "graph_state": [
                        {
                            "instance_id": "wood_01",
                            "candidate_class": "wood",
                            "can_attempt_now": True,
                            "requires_review": False,
                            "blocked": False,
                            "yolo_confidence": 0.90,
                            "recognition_status": "accepted",
                            "current_handling_policy": "auto_allowed",
                        }
                    ],
                    "long_term_knowledge": {
                        "wood": {
                            "category_name": "wood",
                            "graspability_prior": "medium",
                            "risk_level": "low",
                        }
                    },
                },
            }
        )

        self.assertEqual(result["next_node"], "execution_agent")
        self.assertTrue(result["planning_decision"]["steps"])
        self.assertNotIn("task_value", result["graph_state"][0])
        self.assertIn("dynamic_priority_score", result["planning_decision"]["steps"][0])
        self.assertEqual(result["execution_request"]["status"], "pending_ros2_bridge")
        self.assertEqual(result["execution_request"]["bridge"], "ros2_bridge")
        self.assertIn("supervisor_agent", [item["node"] for item in result["audit_trail"]])
        self.assertIn("world_model_adapter", [item["node"] for item in result["audit_trail"]])
        self.assertIn("risk_gate", [item["node"] for item in result["audit_trail"]])

    def test_human_review_route_blocks_execution(self) -> None:
        state = {
            "planning_decision": {"steps": []},
            "risk_assessments": [
                {
                    "instance_id": "glass_01",
                    "requires_human_review": True,
                    "auto_grasp_allowed": False,
                }
            ],
        }

        self.assertEqual(route_after_planning(state), "human_control_gate")

    def test_real_langgraph_app_compiles_and_invokes(self) -> None:
        app = build_langgraph_app()
        result = app.invoke(
            {
                "task_id": "task_langgraph_001",
                "objective": "recover wood",
                "knowledge_context": {
                    "graph_state": [
                        {
                            "instance_id": "wood_01",
                            "candidate_class": "wood",
                            "can_attempt_now": True,
                            "requires_review": False,
                            "blocked": False,
                            "risk_level": "low",
                            "yolo_confidence": 0.90,
                            "recognition_status": "accepted",
                            "current_handling_policy": "auto_allowed",
                            "attempt_count": 0,
                        }
                    ]
                },
            }
        )

        self.assertEqual(result["next_node"], "execution_agent")
        self.assertEqual(result["execution_request"]["status"], "pending_ros2_bridge")
        self.assertFalse(result["execution_request"]["requires_confirmation"])


if __name__ == "__main__":
    unittest.main()
