import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from wastekg.yolo_evaluation import build_segmentation_evaluation_summary, write_evaluation_artifacts


class _FakeMetric:
    def __init__(self, *, p, r, ap50, ap, ap_class_index) -> None:
        self.p = p
        self.r = r
        self.ap50 = ap50
        self.ap = ap
        self.ap_class_index = ap_class_index

    def mean_results(self):
        return [
            sum(self.p) / len(self.p),
            sum(self.r) / len(self.r),
            sum(self.ap50) / len(self.ap50),
            sum(self.ap) / len(self.ap),
        ]


class YoloEvaluationTests(unittest.TestCase):
    def test_evaluation_command_exposes_required_test_set_arguments(self) -> None:
        project_root = Path(__file__).resolve().parents[1]

        completed = subprocess.run(
            [sys.executable, "scripts/evaluate_yolo_seg.py", "--help"],
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--data", completed.stdout)
        self.assertIn("--weights", completed.stdout)
        self.assertIn("--split", completed.stdout)

    def test_summary_keeps_box_and_mask_metrics_separate_for_each_class(self) -> None:
        box = _FakeMetric(
            p=[0.8, 0.6],
            r=[0.7, 0.5],
            ap50=[0.9, 0.7],
            ap=[0.6, 0.4],
            ap_class_index=[0, 1],
        )
        mask = _FakeMetric(
            p=[0.75, 0.55],
            r=[0.65, 0.45],
            ap50=[0.85, 0.65],
            ap=[0.55, 0.35],
            ap_class_index=[0, 1],
        )

        summary = build_segmentation_evaluation_summary(
            class_names=["brick", "glass"],
            box_metric=box,
            mask_metric=mask,
            class_instance_counts=[12, 8],
            speed_ms={"preprocess": 1.2, "inference": 4.5, "postprocess": 0.6},
            split="test",
            image_count=5,
        )

        self.assertEqual(summary["split"], "test")
        self.assertEqual(summary["image_count"], 5)
        self.assertAlmostEqual(summary["overall"]["box"]["map50_95"], 0.5)
        self.assertAlmostEqual(summary["overall"]["mask"]["map50_95"], 0.45)
        self.assertEqual(summary["per_class"][1]["class_name"], "glass")
        self.assertEqual(summary["per_class"][1]["instances"], 8)
        self.assertAlmostEqual(summary["per_class"][1]["box_map50"], 0.7)
        self.assertAlmostEqual(summary["per_class"][1]["mask_map50_95"], 0.35)

    def test_writer_emits_paper_ready_json_csv_and_manifest(self) -> None:
        metric = _FakeMetric(
            p=[0.8],
            r=[0.7],
            ap50=[0.9],
            ap=[0.6],
            ap_class_index=[0],
        )
        summary = build_segmentation_evaluation_summary(
            class_names=["brick"],
            box_metric=metric,
            mask_metric=metric,
            class_instance_counts=[12],
            speed_ms={"inference": 4.5},
            split="test",
            image_count=5,
        )

        with tempfile.TemporaryDirectory() as tmp:
            output = write_evaluation_artifacts(
                summary,
                Path(tmp),
                metadata={"weights_sha256": "abc123", "dataset": "waste11_grouped_v1"},
            )

            self.assertEqual(
                {path.name for path in output.values()},
                {"overall_metrics.json", "per_class_metrics.csv", "evaluation_manifest.json"},
            )
            overall = json.loads(output["overall_metrics"].read_text(encoding="utf-8"))
            self.assertEqual(overall["split"], "test")
            self.assertEqual(overall["metadata"]["dataset"], "waste11_grouped_v1")
            with output["per_class_metrics"].open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["class_name"], "brick")
            self.assertEqual(rows[0]["mask_map50_95"], "0.6")


if __name__ == "__main__":
    unittest.main()
