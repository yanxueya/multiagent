from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wastekg.paper_e2_batch import select_image_paths, summarize_review_rows


class PaperE2BatchTests(unittest.TestCase):
    def test_select_image_paths_returns_sorted_limited_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for name in ["b.jpg", "a.png", "c.txt", "d.jpeg"]:
                (root / name).write_text("x", encoding="utf-8")

            selected = select_image_paths(root, limit=2)

        self.assertEqual([path.name for path in selected], ["a.png", "b.jpg"])

    def test_summarize_review_rows_counts_decisions_and_human_review(self) -> None:
        rows = [
            {"review_decision": "agree", "review_status": "reviewed"},
            {"review_decision": "change", "review_status": "reviewed"},
            {"review_decision": "uncertain", "review_status": "human_review_required"},
            {"review_decision": "review_error", "review_status": "human_review_required"},
            {"review_decision": "", "review_status": "not_reviewed"},
        ]

        summary = summarize_review_rows(rows)

        self.assertEqual(summary["detection_count"], 5)
        self.assertEqual(summary["reviewed_count"], 4)
        self.assertEqual(summary["valid_vlm_response_count"], 3)
        self.assertEqual(summary["human_review_required_count"], 2)
        self.assertEqual(summary["decision_counts"]["agree"], 1)
        self.assertEqual(summary["decision_counts"]["change"], 1)
        self.assertEqual(summary["decision_counts"]["uncertain"], 1)
        self.assertEqual(summary["decision_counts"]["review_error"], 1)
        self.assertEqual(summary["decision_counts"]["not_reviewed"], 1)


if __name__ == "__main__":
    unittest.main()
