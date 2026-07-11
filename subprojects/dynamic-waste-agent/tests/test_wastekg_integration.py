"""验证真实内存 KG 与 LangGraph 的单动作闭环。"""

import unittest

from agent_system.graph import GraphRuntime, build_langgraph_app
from agent_system.integrations import WasteKgRuntimeAdapter
from agent_system.state import build_thread_config
from wastekg import seed_default_categories
from wastekg.core.models import DetectedObject, Observation
from wastekg.graph.store import KnowledgeGraph


class WasteKgIntegrationTests(unittest.TestCase):
    def test_perception_plan_execution_and_new_scene_are_committed_to_kg(self) -> None:
        graph = KnowledgeGraph()
        seed_default_categories(graph)
        runtime = GraphRuntime()
        adapter = WasteKgRuntimeAdapter(graph, runtime.transient_objects)
        scene_counter = iter(["scene_001", "scene_002"])

        def execute(operation, plan, state):
            if operation == "acquire_scene":
                return {"execution_status": "scene_acquired", "scene_id": next(scene_counter), "physical_attempt_started": False}
            return {"execution_status": "success", "physical_attempt_started": True}

        def perceive(scene_id, state):
            objects = []
            if scene_id == "scene_001":
                objects = [
                    DetectedObject(
                        "track_brick_01",
                        "brick",
                        0.95,
                        yolo_confidence=0.95,
                        depth_valid_ratio=0.90,
                        occlusion_state="none",
                    )
                ]
            return {
                "status": "complete",
                "scene_id": scene_id,
                "observation": Observation(frame_id=scene_id, source="camera", objects=objects),
                "perception_completed": True,
            }

        runtime.candidate_loader = adapter.candidate_loader
        runtime.review_payload_loader = adapter.review_payload_loader
        runtime.knowledge_query_runner = adapter.knowledge_query_runner
        runtime.action_already_executed = adapter.action_already_executed
        runtime.kg_writer_backend = adapter.write_backend
        runtime.execution_runner = execute
        runtime.perception_runner = perceive

        app = build_langgraph_app(runtime=runtime)
        result = app.invoke(
            {
                "task_id": "kg_closed_loop",
                "operation_mode": "supervised_execution",
                "user_goal": {"goal_type": "sort", "target_categories": ["brick"]},
            },
            config=build_thread_config("kg-closed-loop-thread"),
        )

        self.assertTrue(result.get("task_completed", False), result)
        self.assertEqual(list(graph.scenes), ["scene_001", "scene_002"])
        self.assertEqual(graph.instances["brick_01"].task_status, "completed")
        self.assertEqual(graph.instances["brick_01"].attempt_count, 1)
        self.assertEqual(sum(event.event_type == "PlanningEvent" for event in graph.events), 1)
        self.assertEqual(sum(event.event_type == "ExecutionEvent" for event in graph.events), 1)
        self.assertTrue(adapter.action_already_executed(result["last_execution_result"]["action_id"]))
        self.assertEqual(runtime.transient_objects, {})


if __name__ == "__main__":
    unittest.main()
