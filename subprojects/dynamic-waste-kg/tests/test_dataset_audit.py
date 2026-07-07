"""验证 test dataset audit 相关功能。"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from wastekg.data.audit import audit_dataset, write_audit_artifacts


CLASS_NAMES = [
    "concrete",
    "brick",
    "tile",
    "wood",
    "gypsum_board",
    "foam",
    "metal",
    "soft_plastic",
    "hard_plastic",
    "paperboard",
    "glass",
]


class DatasetAuditTests(unittest.TestCase):
    def test_audit_counts_instances_and_reports_cross_split_duplicates_and_invalid_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "waste12"
            self._write_data_yaml(root)
            for split in ("train", "val", "test"):
                (root / "images" / split).mkdir(parents=True)
                (root / "labels" / split).mkdir(parents=True)

            train_image = root / "images" / "train" / "same.jpg"
            Image.new("RGB", (20, 20), color="red").save(train_image)
            shutil.copy2(train_image, root / "images" / "val" / "same_copy.jpg")
            Image.new("RGB", (20, 20), color="blue").save(root / "images" / "test" / "bad.jpg")
            Image.new("RGB", (20, 20), color="green").save(root / "images" / "test" / "missing.jpg")

            valid_polygon = "0 0.1 0.1 0.8 0.1 0.8 0.8 0.1 0.8\n"
            (root / "labels" / "train" / "same.txt").write_text(valid_polygon, encoding="utf-8")
            (root / "labels" / "val" / "same_copy.txt").write_text(valid_polygon, encoding="utf-8")
            (root / "labels" / "test" / "bad.txt").write_text("1 0.1 0.1 0.8\n", encoding="utf-8")

            result = audit_dataset(root)

            self.assertEqual(result["splits"]["train"]["images"], 1)
            self.assertEqual(result["splits"]["train"]["instances"], 1)
            self.assertEqual(result["splits"]["val"]["instances"], 1)
            self.assertEqual(result["splits"]["test"]["images"], 2)
            self.assertEqual(result["splits"]["test"]["instances"], 0)
            self.assertEqual(len(result["duplicates"]["exact_cross_split"]), 1)
            self.assertEqual(result["annotation_issues"]["missing_label_images"], ["test/missing.jpg"])
            self.assertEqual(result["annotation_issues"]["malformed_label_lines"], 1)

    def test_write_audit_artifacts_creates_the_five_required_e0_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "waste12"
            self._write_data_yaml(root)
            (root / "images" / "train").mkdir(parents=True)
            (root / "labels" / "train").mkdir(parents=True)
            Image.new("RGB", (20, 20), color="red").save(root / "images" / "train" / "sample.jpg")
            (root / "labels" / "train" / "sample.txt").write_text(
                "0 0.1 0.1 0.8 0.1 0.8 0.8 0.1 0.8\n",
                encoding="utf-8",
            )

            written = write_audit_artifacts(audit_dataset(root), Path(tmp) / "artifacts")

            expected = {
                "class_distribution.csv",
                "split_manifest.csv",
                "split_leakage_report.md",
                "annotation_validation_report.md",
                "model_environment.json",
            }
            self.assertEqual({path.name for path in written.values()}, expected)
            self.assertIn("class_name", written["class_distribution"].read_text(encoding="utf-8"))
            self.assertIn("missing_label_images", written["annotation_report"].read_text(encoding="utf-8"))
            self.assertIn("raw_valid_instances", written["annotation_report"].read_text(encoding="utf-8"))

    def test_audit_reports_and_excludes_duplicate_polygon_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "waste12"
            self._write_data_yaml(root)
            (root / "images" / "train").mkdir(parents=True)
            (root / "labels" / "train").mkdir(parents=True)
            Image.new("RGB", (20, 20), color="red").save(root / "images" / "train" / "sample.jpg")
            polygon = "0 0.1 0.1 0.8 0.1 0.8 0.8 0.1 0.8\n"
            (root / "labels" / "train" / "sample.txt").write_text(polygon + polygon, encoding="utf-8")

            result = audit_dataset(root)

            self.assertEqual(result["annotation_issues"]["duplicate_annotation_lines"], 1)
            self.assertEqual(result["splits"]["train"]["instances"], 1)

    def test_audit_matches_ultralytics_box_level_deduplication_for_segmentation_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "waste12"
            self._write_data_yaml(root)
            (root / "images" / "train").mkdir(parents=True)
            (root / "labels" / "train").mkdir(parents=True)
            Image.new("RGB", (20, 20), color="red").save(root / "images" / "train" / "sample.jpg")
            # 两个 polygon 的顶点数不同，但同属一个类别且有相同的最小外接框。
            first = "0 0.1 0.1 0.8 0.1 0.8 0.8 0.1 0.8\n"
            second = "0 0.1 0.1 0.8 0.1 0.8 0.8 0.1 0.8 0.1 0.5\n"
            (root / "labels" / "train" / "sample.txt").write_text(first + second, encoding="utf-8")

            result = audit_dataset(root)

            self.assertEqual(result["annotation_issues"]["duplicate_annotation_lines"], 0)
            self.assertEqual(result["annotation_issues"]["ultralytics_duplicate_box_labels"], 1)
            self.assertEqual(result["splits"]["train"]["raw_valid_instances"], 2)
            self.assertEqual(result["splits"]["train"]["instances"], 1)

    def test_empty_label_contributes_zero_to_raw_and_effective_instance_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "waste12"
            self._write_data_yaml(root)
            (root / "images" / "train").mkdir(parents=True)
            (root / "labels" / "train").mkdir(parents=True)
            Image.new("RGB", (20, 20), color="red").save(root / "images" / "train" / "empty.jpg")
            (root / "labels" / "train" / "empty.txt").write_text("", encoding="utf-8")

            result = audit_dataset(root)

            self.assertEqual(result["splits"]["train"]["raw_valid_instances"], 0)
            self.assertEqual(result["splits"]["train"]["instances"], 0)

    def test_environment_record_includes_weight_hash_and_training_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "waste12"
            self._write_data_yaml(root)
            weights = Path(tmp) / "best.pt"
            weights.write_bytes(b"demo-weights")

            written = write_audit_artifacts(
                audit_dataset(root),
                Path(tmp) / "artifacts",
                weight_paths=[weights],
                training_command="python scripts/train_yolo_seg.py --epochs 50",
            )

            environment = json.loads(written["environment_report"].read_text(encoding="utf-8"))
            self.assertEqual(environment["training_command"], "python scripts/train_yolo_seg.py --epochs 50")
            self.assertEqual(environment["weights"][0]["path"], str(weights.resolve()))
            self.assertEqual(len(environment["weights"][0]["sha256"]), 64)

    def test_audit_command_generates_e0_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "waste12"
            self._write_data_yaml(root)
            output_dir = Path(tmp) / "artifacts"
            project_root = Path(__file__).resolve().parents[1]

            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/data/audit_waste12_dataset.py",
                    "--dataset",
                    str(root),
                    "--out",
                    str(output_dir),
                ],
                cwd=project_root,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((output_dir / "class_distribution.csv").exists())
            self.assertIn("E0 dataset audit completed", completed.stdout)

    @staticmethod
    def _write_data_yaml(root: Path) -> None:
        names = "\n".join(f"  {index}: {name}" for index, name in enumerate(CLASS_NAMES))
        (root / "data.yaml").parent.mkdir(parents=True, exist_ok=True)
        (root / "data.yaml").write_text(
            f"path: {root.as_posix()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n{names}\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
