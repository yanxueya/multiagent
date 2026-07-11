"""验证三模式 Supervisor、六节点编排和 interrupt/checkpointer。"""

import unittest

from langgraph.types import Command

from agent_system.graph import GraphRuntime, build_langgraph_app, choose_supervisor_decision, describe_graph
from agent_system.state import build_thread_config


class LangGraphArchitectureTests(unittest.TestCase):
    def test_graph_has_four_agents_and_two_deterministic_nodes(self) -> None:
        description = describe_graph()

        self.assertEqual(description["operation_modes"], ["exploration", "supervised_execution", "human_collaboration"])
        self.assertEqual(description["agents"], ["supervisor_agent", "perception_agent", "action_planning_agent", "execution_agent"])
        self.assertEqual(description["deterministic_nodes"], ["kg_writer", "human_review_interrupt"])
        self.assertNotIn("risk_gate", description["deterministic_nodes"])
        self.assertIn("One physical action", description["planning_rule"])

    def test_supervisor_routes_each_control_stage(self) -> None:
        self.assertEqual(choose_supervisor_decision({"operation_mode": "exploration"}).next_step, "acquire_scene")
        self.assertEqual(
            choose_supervisor_decision(
                {"operation_mode": "exploration", "current_scene_id": "s1", "scene_is_fresh": True, "perception_completed": True}
            ).next_step,
            "complete",
        )
        self.assertEqual(
            choose_supervisor_decision(
                {"operation_mode": "supervised_execution", "current_scene_id": "s1", "scene_is_fresh": True, "perception_completed": True, "eligible_instance_ids": ["b1"]}
            ).next_step,
            "plan",
        )
        self.assertEqual(
            choose_supervisor_decision(
                {"operation_mode": "human_collaboration", "current_scene_id": "s1", "scene_is_fresh": True, "perception_completed": True, "review_instance_ids": ["g1"]}
            ).next_step,
            "human_review",
        )

    def test_real_graph_uses_checkpointer_and_resumes_human_interrupt(self) -> None:
        app = build_langgraph_app()
        config = build_thread_config("human-review-thread")
        interrupted = app.invoke(
            {
                "task_id": "task_review",
                "operation_mode": "human_collaboration",
                "user_goal": {"goal_type": "sort"},
                "current_scene_id": "scene_001",
                "scene_is_fresh": True,
                "perception_completed": True,
                "review_instance_ids": ["glass_01"],
                "eligible_instance_ids": [],
            },
            config=config,
        )
        self.assertIn("__interrupt__", interrupted)
        self.assertEqual(interrupted["__interrupt__"][0].value["review_instance_ids"], ["glass_01"])

        resumed = app.invoke(
            Command(resume={"instance_id": "glass_01", "review_action": "mark_unknown", "reason": "human decision"}),
            config=config,
        )
        self.assertEqual(resumed["next_step"], "complete")
        self.assertEqual(resumed["review_instance_ids"], [])
        self.assertEqual(resumed["kg_write_result"]["write_type"], "human_review")

    def test_supervised_execution_runs_one_action_then_requests_new_scene(self) -> None:
        def load_candidates(scene_id, instance_ids, goal):
            return [
                {
                    "instance_id": "brick_01",
                    "scene_id": scene_id,
                    "candidate_class": "brick",
                    "recognition_status": "accepted",
                    "current_handling_policy": "auto_allowed",
                    "task_status": "pending",
                    "attempt_count": 0,
                    "depth_valid_ratio": 0.92,
                    "occlusion_state": "none",
                    "graspability_prior": "medium",
                    "near_neighbor_count": 0,
                }
            ]

        def execute(operation, plan, state):
            if operation == "execute_action":
                return {"execution_status": "success", "physical_attempt_started": True}
            return {"execution_status": "pending_external_execution", "operation": "acquire_scene", "physical_attempt_started": False}

        app = build_langgraph_app(runtime=GraphRuntime(candidate_loader=load_candidates, execution_runner=execute))
        result = app.invoke(
            {
                "task_id": "task_bricks",
                "operation_mode": "supervised_execution",
                "user_goal": {"goal_type": "sort", "target_categories": ["brick"]},
                "current_scene_id": "scene_001",
                "scene_is_fresh": True,
                "perception_completed": True,
                "eligible_instance_ids": ["brick_01"],
                "review_instance_ids": [],
            },
            config=build_thread_config("supervised-thread"),
        )

        self.assertEqual(result["last_execution_result"]["execution_status"], "success")
        self.assertTrue(result["last_execution_result"]["new_scene_required"])
        self.assertFalse(result["scene_is_fresh"])
        self.assertEqual(result["external_status"], "pending_external_execution")
        nodes = [item["node"] for item in result["audit_trail"]]
        self.assertIn("action_planning_agent", nodes)
        self.assertIn("execution_agent", nodes)
        self.assertGreaterEqual(nodes.count("kg_writer"), 2)

    def test_exploration_history_query_is_managed_by_supervisor(self) -> None:
        runtime = GraphRuntime(knowledge_query_runner=lambda goal: {"status": "complete", "result_ref": "kg://history/query-001"})
        app = build_langgraph_app(runtime=runtime)
        result = app.invoke(
            {"task_id": "query_001", "operation_mode": "exploration", "user_goal": {"goal_type": "history_query", "query": "recent glass"}},
            config=build_thread_config("query-thread"),
        )
        self.assertEqual(result["knowledge_query_result_ref"], "kg://history/query-001")
        self.assertEqual(result["next_step"], "complete")

    def test_current_environment_exploration_acquires_perceives_and_commits(self) -> None:
        def execute(operation, plan, state):
            self.assertEqual(operation, "acquire_scene")
            return {"execution_status": "scene_acquired", "scene_id": "scene_explore_001", "physical_attempt_started": False}

        def perceive(scene_id, state):
            return {
                "status": "complete",
                "scene_id": scene_id,
                "updated_instance_ids": ["brick_01"],
                "accepted_instance_ids": ["brick_01"],
                "review_instance_ids": [],
                "unknown_instance_ids": [],
                "eligible_instance_ids": ["brick_01"],
                "events": {"detection_events": [], "vlm_review_events": [], "depth_update_events": []},
                "perception_completed": True,
            }

        app = build_langgraph_app(runtime=GraphRuntime(execution_runner=execute, perception_runner=perceive))
        result = app.invoke(
            {"task_id": "explore_001", "operation_mode": "exploration", "user_goal": {"goal_type": "inspect_environment"}},
            config=build_thread_config("exploration-thread"),
        )
        self.assertEqual(result["current_scene_id"], "scene_explore_001")
        self.assertTrue(result["perception_completed"])
        self.assertEqual(result["kg_write_result"]["write_type"], "perception")
        self.assertEqual(result["next_step"], "complete")


if __name__ == "__main__":
    unittest.main()
