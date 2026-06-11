import unittest

from wastekg import (
    ExecutionFeedback,
    KnowledgeGraph,
    PlannerRequest,
    VisionDetection,
    VisionPacket,
    build_langgraph_state,
    build_ros2_action_command,
    seed_default_categories,
    vision_packet_to_observation,
    apply_execution_feedback,
)


class InterfaceTests(unittest.TestCase):
    def test_vision_packet_prefers_llm_when_more_confident(self) -> None:
        packet = VisionPacket(
            frame_id="frame_001",
            source="camera",
            detections=[
                VisionDetection(
                    temp_id="d1",
                    yolo_class_name="brick",
                    yolo_confidence=0.71,
                    llm_class_name="glass",
                    llm_confidence=0.86,
                    center_xyz=(0.1, 0.1, 0.0),
                    risk_hint="medium",
                )
            ],
        )

        obs = vision_packet_to_observation(packet)
        self.assertEqual(obs.objects[0].class_name, "glass")
        self.assertEqual(obs.objects[0].confidence, 0.86)

    def test_langgraph_state_contains_long_term_and_planning_context(self) -> None:
        graph = KnowledgeGraph()
        seed_default_categories(graph)
        graph.apply_observation(
            vision_packet_to_observation(
                VisionPacket(
                    frame_id="frame_002",
                    source="camera",
                    detections=[
                        VisionDetection(
                            temp_id="d1",
                            yolo_class_name="glass",
                            yolo_confidence=0.92,
                            center_xyz=(0.0, 0.0, 0.0),
                            risk_hint="medium",
                        )
                    ],
                )
            )
        )

        state = build_langgraph_state(
            graph,
            PlannerRequest(task_id="task_001", objective="sort_glass", target_categories=["glass"]),
        )
        self.assertIn("planning_context", state)
        self.assertIn("long_term_knowledge", state)
        self.assertIn("glass", state["long_term_knowledge"])
        self.assertTrue(state["planning_context"]["candidates"])

    def test_ros2_feedback_marks_instance_processed_or_blocked(self) -> None:
        graph = KnowledgeGraph()
        seed_default_categories(graph)
        graph.apply_observation(
            vision_packet_to_observation(
                VisionPacket(
                    frame_id="frame_003",
                    source="camera",
                    detections=[
                        VisionDetection(
                            temp_id="d1",
                            yolo_class_name="brick",
                            yolo_confidence=0.95,
                            center_xyz=(0.0, 0.0, 0.0),
                            risk_hint="low",
                        )
                    ],
                )
            )
        )

        action = build_ros2_action_command("pick", "brick_01", {"gripper": "close"}, requires_confirmation=False)
        result = apply_execution_feedback(
            graph,
            ExecutionFeedback(
                action_id=action.action_id,
                target_instance_id="brick_01",
                status="success",
                message="removed",
            ),
        )
        self.assertEqual(result["status"], "success")
        self.assertTrue(graph.instances["brick_01"].processed_flag)

        blocked_action = build_ros2_action_command("pick", "glass_01")
        blocked_result = apply_execution_feedback(
            graph,
            ExecutionFeedback(
                action_id=blocked_action.action_id,
                target_instance_id="glass_01",
                status="failed",
                message="grasp_failed",
            ),
        )
        self.assertEqual(blocked_result["status"], "failed")
        self.assertGreaterEqual(len(graph.events), 1)


if __name__ == "__main__":
    unittest.main()
