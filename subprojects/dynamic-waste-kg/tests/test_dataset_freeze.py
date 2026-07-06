import tempfile
import unittest
import subprocess
import sys
from pathlib import Path

from PIL import Image

from wastekg.dataset_audit import audit_dataset
from wastekg.dataset_freeze import freeze_visual_dataset


class DatasetFreezeTests(unittest.TestCase):
    def test_freeze_visual_dataset_preserves_split_and_uses_selected_visual_classes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            target = Path(tmp) / "waste11"
            self._write_source_dataset(source)

            result = freeze_visual_dataset(source, target, class_names=["concrete", "gypsum_board"])

            frozen_audit = audit_dataset(target)
            self.assertEqual(frozen_audit["class_names"], ["concrete", "gypsum_board"])
            self.assertEqual(result["split_image_counts"], {"train": 1, "val": 1, "test": 1})
            self.assertTrue((target / "visual_dataset_manifest.json").exists())
            self.assertTrue((target / "images" / "train" / "train_sample.jpg").exists())
            self.assertTrue((target / "labels" / "test" / "test_sample.txt").exists())

    def test_freeze_command_creates_visual_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            target = Path(tmp) / "waste11"
            self._write_source_dataset(source)
            project_root = Path(__file__).resolve().parents[1]

            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/freeze_visual_dataset.py",
                    "--source",
                    str(source),
                    "--out",
                    str(target),
                    "--class-name",
                    "concrete",
                    "--class-name",
                    "gypsum_board",
                ],
                cwd=project_root,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("Visual dataset frozen", completed.stdout)
            self.assertTrue((target / "data.yaml").exists())

    @staticmethod
    def _write_source_dataset(root: Path) -> None:
        (root / "data.yaml").parent.mkdir(parents=True, exist_ok=True)
        (root / "data.yaml").write_text(
            f"path: {root.as_posix()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: concrete\n  1: gypsum_board\n  2: asbestos_suspect\n",
            encoding="utf-8",
        )
        for index, split in enumerate(("train", "val", "test")):
            (root / "images" / split).mkdir(parents=True)
            (root / "labels" / split).mkdir(parents=True)
            Image.new("RGB", (20, 20), color=(index * 50, 20, 40)).save(root / "images" / split / f"{split}_sample.jpg")
            class_id = 0 if split != "val" else 1
            (root / "labels" / split / f"{split}_sample.txt").write_text(
                f"{class_id} 0.1 0.1 0.8 0.1 0.8 0.8 0.1 0.8\n",
                encoding="utf-8",
            )


if __name__ == "__main__":
    unittest.main()
