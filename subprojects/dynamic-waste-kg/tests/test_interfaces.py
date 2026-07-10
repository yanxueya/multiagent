"""验证 test interfaces 相关功能。"""

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
    def test_vision_packet_routes_vlm_conflict_to_unknown_without_override(self) -> None:
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
        self.assertEqual(obs.objects[0].class_name, "brick")
        self.assertEqual(obs.objects[0].confidence, 0.71)
        self.assertEqual(obs.objects[0].metadata["review_status"], "review_conflict")
        self.assertEqual(obs.objects[0].metadata["recognition_status"], "unknown")

    def test_unknown_llm_review_is_not_ignored_when_less_confident(self) -> None:
        packet = VisionPacket(
            frame_id="frame_hazard",
            source="camera",
            detections=[
                VisionDetection(
                    temp_id="d1",
                    yolo_class_name="gypsum_board",
                    yolo_confidence=0.90,
                    llm_class_name="unknown",
                    llm_confidence=0.75,
                    center_xyz=(0.1, 0.1, 0.0),
                    risk_hint="high",
                )
            ],
        )

        obs = vision_packet_to_observation(packet)

        self.assertEqual(obs.objects[0].class_name, "gypsum_board")
        self.assertEqual(obs.objects[0].confidence, 0.90)
        self.assertEqual(obs.objects[0].metadata["review_status"], "human_review_required")
        self.assertEqual(obs.objects[0].metadata["recognition_status"], "unknown")
        self.assertEqual(obs.objects[0].metadata["yolo_confidence"], 0.90)
        self.assertEqual(obs.objects[0].metadata["llm_confidence"], 0.75)

    def test_uncertain_visual_review_requires_human_review_even_if_category_matches(self) -> None:
        detection = VisionDetection(
            temp_id="d1",
            yolo_class_name="glass",
            yolo_confidence=0.80,
            llm_class_name="glass",
            llm_confidence=0.0,
            metadata={"need_human_review": True, "review_decision": "uncertain"},
        )

        self.assertEqual(detection.review_status(), "human_review_required")
        self.assertEqual(detection.resolved_confidence(), 0.80)

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
        self.assertEqual(graph.instances["brick_01"].task_status, "completed")
        self.assertEqual(graph.instances["brick_01"].attempt_count, 1)

        blocked_action = build_ros2_action_command("pick", "brick_01")
        blocked_result = apply_execution_feedback(
            graph,
            ExecutionFeedback(
                action_id=blocked_action.action_id,
                target_instance_id="brick_01",
                status="failed",
                message="grasp_failed",
            ),
        )
        self.assertEqual(blocked_result["status"], "failed")
        self.assertEqual(graph.instances["brick_01"].task_status, "failed")
        self.assertEqual(graph.instances["brick_01"].attempt_count, 2)
        self.assertEqual(graph.events[-1].event_type, "ExecutionEvent")


if __name__ == "__main__":
    unittest.main()
