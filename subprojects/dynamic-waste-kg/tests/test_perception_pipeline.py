"""验证 test perception pipeline 相关功能。"""

import unittest

from wastekg import KnowledgeGraph, ReviewResult, apply_perception_records_to_graph, seed_default_categories
from wastekg.perception.pipeline import build_records_with_optional_review


class FakeReviewer:
    def review(self, crop_or_image_ref, *, yolo_class_name, yolo_confidence, allowed_classes):
        return ReviewResult(
            class_name="glass",
            confidence=0.91,
            risk_hint="medium",
            reason="transparent brittle fragment",
            need_human_review=True,
        )


class UnknownReviewer:
    def review(self, crop_or_image_ref, *, yolo_class_name, yolo_confidence, allowed_classes):
        return ReviewResult(
            class_name="unknown",
            confidence=0.75,
            risk_hint="high",
            reason="surface texture and board-like shape require human review",
            need_human_review=True,
        )


class CapturingReviewer:
    def __init__(self) -> None:
        self.received = None
        self.allowed_classes = None

    def review(self, crop_or_image_ref, *, yolo_class_name, yolo_confidence, allowed_classes):
        self.received = crop_or_image_ref
        self.allowed_classes = allowed_classes
        return ReviewResult(class_name=yolo_class_name, confidence=yolo_confidence)


class FailingReviewer:
    def review(self, crop_or_image_ref, *, yolo_class_name, yolo_confidence, allowed_classes):
        raise RuntimeError("provider rejected visual input")


class PerceptionPipelineTests(unittest.TestCase):
    def test_visual_evidence_is_preferred_over_plain_image_reference(self) -> None:
        reviewer = CapturingReviewer()
        evidence = {
            "original_image": "evidence/original.jpg",
            "crop_image": "evidence/crop.jpg",
            "mask_overlay_image": "evidence/overlay.jpg",
        }

        records = build_records_with_optional_review(
            [
                {
                    "temp_id": "d1",
                    "yolo_class_name": "glass",
                    "yolo_confidence": 0.60,
                    "image_ref": "scene.jpg",
                    "visual_evidence": evidence,
                }
            ],
            reviewer=reviewer,
        )

        self.assertEqual(reviewer.received, {"visual_evidence": evidence})
        self.assertEqual(records[0]["yolo_class_name"], "glass")

    def test_low_confidence_record_can_be_reviewed_and_written_to_graph(self) -> None:
        graph = KnowledgeGraph()
        seed_default_categories(graph)

        packet, result = apply_perception_records_to_graph(
            graph,
            frame_id="frame_200",
            source="unit_perception",
            yolo_records=[
                {
                    "temp_id": "d1",
                    "yolo_class_name": "brick",
                    "yolo_confidence": 0.60,
                    "center_xyz": [0.1, 0.2, 0.3],
                }
            ],
            reviewer=FakeReviewer(),
        )

        self.assertEqual(packet.detections[0].resolved_class_name(), "glass")
        self.assertEqual(result["created_instances"], ["glass_01"])
        self.assertIn("glass_01", graph.instances)
        self.assertFalse(graph.instances["glass_01"].processable)

    def test_apply_pipeline_forwards_paper_visual_class_whitelist(self) -> None:
        graph = KnowledgeGraph()
        seed_default_categories(graph)
        reviewer = CapturingReviewer()
        visual_classes = ["concrete", "brick", "glass"]

        apply_perception_records_to_graph(
            graph,
            frame_id="frame_visual_scope",
            source="unit_perception",
            yolo_records=[{"temp_id": "d1", "yolo_class_name": "glass", "yolo_confidence": 0.60}],
            reviewer=reviewer,
            allowed_classes=visual_classes,
        )

        self.assertEqual(reviewer.allowed_classes, visual_classes)

    def test_review_failure_retains_yolo_and_requires_human_review(self) -> None:
        records = build_records_with_optional_review(
            [{"temp_id": "d1", "yolo_class_name": "glass", "yolo_confidence": 0.60}],
            reviewer=FailingReviewer(),
        )

        self.assertEqual(records[0]["llm_class_name"], "glass")
        self.assertEqual(records[0]["llm_confidence"], 0.0)
        self.assertTrue(records[0]["metadata"]["need_human_review"])
        self.assertEqual(records[0]["metadata"]["review_decision"], "review_error")
        self.assertEqual(records[0]["metadata"]["review_error_type"], "RuntimeError")
        self.assertIn("provider rejected", records[0]["metadata"]["review_error_message"])

    def test_unknown_review_metadata_is_preserved_in_graph_instance(self) -> None:
        graph = KnowledgeGraph()
        seed_default_categories(graph)

        packet, result = apply_perception_records_to_graph(
            graph,
            frame_id="frame_hazard",
            source="unit_perception",
            yolo_records=[
                {
                    "temp_id": "d1",
                    "yolo_class_name": "gypsum_board",
                    "yolo_confidence": 0.90,
                    "center_xyz": [0.1, 0.2, 0.3],
                }
            ],
            reviewer=UnknownReviewer(),
            allowed_classes=["concrete", "brick", "gypsum_board", "unknown"],
        )

        self.assertEqual(packet.detections[0].resolved_class_name(), "unknown")
        self.assertEqual(result["created_instances"], ["unknown_01"])
        instance = graph.instances["unknown_01"]
        self.assertEqual(instance.class_name, "unknown")
        self.assertEqual(instance.yolo_confidence, 0.90)
        self.assertEqual(instance.llm_confidence, 0.75)
        self.assertEqual(instance.review_status, "human_review_required")
        self.assertEqual(instance.handling_mode, "human_review")

    def test_very_low_confidence_detection_becomes_unknown_without_llm_review(self) -> None:
        records = build_records_with_optional_review(
            [{"temp_id": "d1", "yolo_class_name": "brick", "yolo_confidence": 0.20}],
            reviewer=FakeReviewer(),
        )

        self.assertEqual(records[0]["yolo_class_name"], "unknown")
        self.assertTrue(records[0]["metadata"]["need_human_review"])
        self.assertEqual(records[0]["metadata"]["review_decision"], "unknown")
        self.assertEqual(records[0]["metadata"]["original_yolo_class_name"], "brick")


if __name__ == "__main__":
    unittest.main()
