"""验证 test vision bridge 相关功能。"""

import unittest

from wastekg import build_vision_packet_from_records, seed_default_categories, vision_packet_to_observation
from wastekg.graph.store import KnowledgeGraph


class VisionBridgeTests(unittest.TestCase):
    def test_records_are_normalized_into_vision_packet(self) -> None:
        packet = build_vision_packet_from_records(
            frame_id="frame_100",
            source="yolo_pipeline",
            detections=[
                {
                    "temp_id": "d1",
                    "yolo_class_name": "glass",
                    "yolo_confidence": 0.73,
                    "llm_class_name": "glass",
                    "llm_confidence": 0.91,
                    "center_xyz": [0.1, 0.2, 0.3],
                    "bbox": [0.1, 0.2, 0.3, 0.05, 0.05, 0.05],
                    "risk_hint": "medium",
                    "mask_polygon": [[10, 10], [30, 10], [30, 35], [10, 35]],
                    "boundary_points": [[10, 10], [30, 10], [30, 35], [10, 35]],
                    "visible_area_ratio": 0.82,
                    "occlusion_state": "partial",
                    "grasp_candidates": [{"center": [20, 22], "angle": 0.1, "score": 0.66}],
                    "safe_grasp_score": 0.44,
                    "metadata": {"source": "unit_test"},
                }
            ],
            relation_hints=[
                {
                    "source_temp_id": "d1",
                    "relation": "near",
                    "target_temp_id": "d1",
                    "confidence": 0.5,
                }
            ],
        )

        observation = vision_packet_to_observation(packet)
        self.assertEqual(observation.objects[0].class_name, "glass")
        self.assertEqual(observation.objects[0].confidence, 0.91)
        self.assertEqual(observation.relations[0].relation, "near")
        self.assertEqual(observation.objects[0].metadata["source"], "unit_test")
        self.assertEqual(len(observation.objects[0].mask_polygon), 4)
        self.assertEqual(observation.objects[0].visible_area_ratio, 0.82)
        self.assertEqual(observation.objects[0].safe_grasp_score, 0.44)

    def test_observation_can_write_into_graph(self) -> None:
        graph = KnowledgeGraph()
        seed_default_categories(graph)
        packet = build_vision_packet_from_records(
            frame_id="frame_101",
            source="yolo_pipeline",
            detections=[
                {
                    "temp_id": "d1",
                    "yolo_class_name": "brick",
                    "yolo_confidence": 0.91,
                    "center_xyz": [0.0, 0.0, 0.0],
                }
            ],
        )
        graph.apply_observation(vision_packet_to_observation(packet))
        self.assertIn("brick_01", graph.instances)
        self.assertEqual(graph.instances["brick_01"].handling_mode, "robot_grasp")

    def test_segmentation_and_grasp_fields_enter_short_term_memory(self) -> None:
        graph = KnowledgeGraph()
        seed_default_categories(graph)
        packet = build_vision_packet_from_records(
            frame_id="frame_103",
            source="yolo_seg_pipeline",
            detections=[
                {
                    "temp_id": "g1",
                    "yolo_class_name": "glass",
                    "yolo_confidence": 0.88,
                    "mask_polygon": [[0.1, 0.1], [0.3, 0.1], [0.3, 0.4], [0.1, 0.4]],
                    "boundary_points": [[0.1, 0.1], [0.3, 0.1], [0.3, 0.4], [0.1, 0.4]],
                    "visible_area_ratio": 0.62,
                    "occlusion_state": "partial",
                    "grasp_candidates": [{"center": [0.2, 0.25], "angle": 0.0, "score": 0.52}],
                    "safe_grasp_score": 0.31,
                }
            ],
        )

        graph.apply_observation(vision_packet_to_observation(packet))
        instance = graph.instances["glass_01"]
        self.assertEqual(instance.mask_polygon[0], (0.1, 0.1))
        self.assertEqual(instance.occlusion_state, "partial")
        self.assertEqual(instance.safe_grasp_score, 0.31)
        self.assertEqual(instance.handling_mode, "robot_with_supervision")

    def test_dataset_aliases_are_canonicalized(self) -> None:
        graph = KnowledgeGraph()
        seed_default_categories(graph)
        packet = build_vision_packet_from_records(
            frame_id="frame_102",
            source="dataset_adapter",
            detections=[
                {"temp_id": "d1", "yolo_class_name": "stone", "yolo_confidence": 0.91},
                {"temp_id": "d2", "yolo_class_name": "pipes", "yolo_confidence": 0.90},
                {"temp_id": "d3", "yolo_class_name": "cardboard", "yolo_confidence": 0.89},
            ],
        )
        graph.apply_observation(vision_packet_to_observation(packet))

        self.assertIn("concrete_01", graph.instances)
        self.assertIn("hard_plastic_01", graph.instances)
        self.assertIn("paperboard_01", graph.instances)


if __name__ == "__main__":
    unittest.main()
