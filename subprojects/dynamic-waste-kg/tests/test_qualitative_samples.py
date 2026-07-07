"""验证 test qualitative samples 相关功能。"""

import tempfile
import unittest
from pathlib import Path
import subprocess
import sys

from PIL import Image

from wastekg.paper.qualitative_samples import render_ground_truth_overlay, select_sparse_examples


class QualitativeSampleTests(unittest.TestCase):
    def test_qualitative_export_command_exposes_data_and_weight_arguments(self) -> None:
        project_root = Path(__file__).resolve().parents[1]

        completed = subprocess.run(
            [sys.executable, "scripts/paper/export_qualitative_samples.py", "--help"],
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--data", completed.stdout)
        self.assertIn("--weights", completed.stdout)
        self.assertIn("--classes", completed.stdout)

    def test_selects_the_least_cluttered_example_for_each_target_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_dir = root / "images"
            label_dir = root / "labels"
            image_dir.mkdir()
            label_dir.mkdir()
            for name in ("crowded", "sparse"):
                Image.new("RGB", (20, 20), color="white").save(image_dir / f"{name}.jpg")
            polygon = "0.1 0.1 0.8 0.1 0.8 0.8 0.1 0.8"
            (label_dir / "crowded.txt").write_text(f"1 {polygon}\n0 {polygon}\n", encoding="utf-8")
            (label_dir / "sparse.txt").write_text(f"1 {polygon}\n", encoding="utf-8")

            samples = select_sparse_examples(
                image_dir=image_dir,
                label_dir=label_dir,
                class_names=["concrete", "metal"],
                target_classes=["metal"],
            )

            self.assertEqual(len(samples), 1)
            self.assertEqual(samples[0]["image_path"].name, "sparse.jpg")
            self.assertEqual(samples[0]["target_instances"], 1)
            self.assertEqual(samples[0]["total_instances"], 1)

    def test_renders_a_ground_truth_mask_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "sample.jpg"
            label_path = root / "sample.txt"
            output_path = root / "gt_overlay.jpg"
            Image.new("RGB", (20, 20), color="white").save(image_path)
            label_path.write_text("0 0.1 0.1 0.8 0.1 0.8 0.8 0.1 0.8\n", encoding="utf-8")

            render_ground_truth_overlay(
                image_path=image_path,
                label_path=label_path,
                class_names=["concrete"],
                output_path=output_path,
            )

            self.assertTrue(output_path.is_file())
            with Image.open(output_path) as rendered:
                self.assertNotEqual(rendered.convert("RGB").getpixel((10, 10)), (255, 255, 255))


if __name__ == "__main__":
    unittest.main()
