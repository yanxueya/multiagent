import unittest

from wastekg.paper_e4_image_sequence import (
    SequenceDetection,
    bbox_iou,
    match_image_sequence_detections,
    summarize_image_sequence,
)


class PaperE4ImageSequenceTests(unittest.TestCase):
    def test_bbox_iou_returns_one_for_identical_boxes(self) -> None:
        self.assertAlmostEqual(bbox_iou((10, 10, 30, 30), (10, 10, 30, 30)), 1.0)

    def test_match_image_sequence_marks_persisted_removed_and_appeared(self) -> None:
        before = [
            SequenceDetection("before", "b1", "wood", 0.91, (10, 10, 40, 40)),
            SequenceDetection("before", "b2", "brick", 0.88, (100, 100, 150, 150)),
        ]
        after = [
            SequenceDetection("after", "a1", "wood", 0.90, (12, 12, 42, 42)),
            SequenceDetection("after", "a2", "glass", 0.76, (200, 200, 260, 260)),
        ]

        result = match_image_sequence_detections(before, after, iou_threshold=0.30)

        self.assertEqual([(m.before_id, m.after_id, m.class_name) for m in result.matches], [("b1", "a1", "wood")])
        self.assertEqual([item.temp_id for item in result.removed_candidates], ["b2"])
        self.assertEqual([item.temp_id for item in result.appeared_candidates], ["a2"])

    def test_summarize_image_sequence_counts_events(self) -> None:
        before = [SequenceDetection("before", "b1", "wood", 0.91, (10, 10, 40, 40))]
        after: list[SequenceDetection] = []
        result = match_image_sequence_detections(before, after, iou_threshold=0.30)

        summary = summarize_image_sequence(before, after, result)

        self.assertEqual(summary["before_detection_count"], 1)
        self.assertEqual(summary["after_detection_count"], 0)
        self.assertEqual(summary["removed_candidate_count"], 1)
        self.assertEqual(summary["event_count"], 3)


if __name__ == "__main__":
    unittest.main()
