import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from wastekg.dataset_grouping import build_grouped_dataset


class DatasetGroupingTests(unittest.TestCase):
    def test_grouped_split_keeps_identical_visual_candidates_in_one_split(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            target = Path(tmp) / "grouped"
            self._write_data_yaml(source)
            for split in ("train", "val", "test"):
                (source / "images" / split).mkdir(parents=True)
                (source / "labels" / split).mkdir(parents=True)

            shared = source / "images" / "train" / "shared.jpg"
            self._make_image(shared, "red", 2)
            shutil.copy2(shared, source / "images" / "test" / "shared_copy.jpg")
            self._make_image(source / "images" / "train" / "blue.jpg", "blue", 5)
            self._make_image(source / "images" / "val" / "green.jpg", "green", 9)
            self._make_image(source / "images" / "test" / "yellow.jpg", "yellow", 13)

            for split in ("train", "val", "test"):
                for image_path in (source / "images" / split).glob("*.jpg"):
                    (source / "labels" / split / f"{image_path.stem}.txt").write_text(
                        "0 0.1 0.1 0.8 0.1 0.8 0.8 0.1 0.8\n",
                        encoding="utf-8",
                    )

            result = build_grouped_dataset(source, target, seed=7)

            shared_assignments = [item for item in result["assignments"] if item["group_id"].startswith("visual_")]
            self.assertEqual(len(shared_assignments), 2)
            self.assertEqual({item["assigned_split"] for item in shared_assignments}, {shared_assignments[0]["assigned_split"]})
            self.assertTrue((target / "data.yaml").exists())
            self.assertEqual(sum(result["split_image_counts"].values()), 5)
            self.assertEqual(sum(result["materialization"].values()), 10)
            for assignment in result["assignments"]:
                copied_image = target / "images" / assignment["assigned_split"] / Path(assignment["source_image"]).name
                copied_label = target / "labels" / assignment["assigned_split"] / f"{copied_image.stem}.txt"
                self.assertTrue(copied_image.exists())
                self.assertTrue(copied_label.exists())

    def test_grouped_dataset_command_creates_a_new_dataset_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            target = Path(tmp) / "grouped"
            self._write_data_yaml(source)
            (source / "images" / "train").mkdir(parents=True)
            (source / "labels" / "train").mkdir(parents=True)
            self._make_image(source / "images" / "train" / "sample.jpg", "red", 2)
            (source / "labels" / "train" / "sample.txt").write_text(
                "0 0.1 0.1 0.8 0.1 0.8 0.8 0.1 0.8\n",
                encoding="utf-8",
            )
            project_root = Path(__file__).resolve().parents[1]

            completed = subprocess.run(
                [sys.executable, "scripts/build_grouped_dataset.py", "--source", str(source), "--out", str(target)],
                cwd=project_root,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((target / "grouped_split_manifest.json").exists())
            self.assertIn("Grouped dataset created", completed.stdout)

    def test_grouped_split_namespaces_same_filename_from_different_source_splits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            target = Path(tmp) / "grouped"
            self._write_data_yaml(source)
            for split in ("train", "val", "test"):
                (source / "images" / split).mkdir(parents=True)
                (source / "labels" / split).mkdir(parents=True)

            self._make_image(source / "images" / "train" / "same.jpg", "red", 2)
            self._make_image(source / "images" / "test" / "same.jpg", "blue", 9)
            for split in ("train", "test"):
                (source / "labels" / split / "same.txt").write_text(
                    "0 0.1 0.1 0.8 0.1 0.8 0.8 0.1 0.8\n",
                    encoding="utf-8",
                )

            result = build_grouped_dataset(source, target, seed=0)

            same_records = [item for item in result["assignments"] if item["source_image"].endswith("same.jpg")]
            self.assertEqual(len(same_records), 2)
            target_names = {item["target_image"] for item in same_records}
            self.assertEqual(target_names, {"same__src_train.jpg", "same__src_test.jpg"})
            for item in same_records:
                self.assertTrue((target / "images" / item["assigned_split"] / item["target_image"]).exists())

    @staticmethod
    def _write_data_yaml(root: Path) -> None:
        (root / "data.yaml").parent.mkdir(parents=True, exist_ok=True)
        (root / "data.yaml").write_text(
            f"path: {root.as_posix()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: concrete\n  1: brick\n",
            encoding="utf-8",
        )

    @staticmethod
    def _make_image(path: Path, color: str, marker: int) -> None:
        image = Image.new("RGB", (20, 20), color=color)
        ImageDraw.Draw(image).rectangle((marker, marker, marker + 3, marker + 3), fill="black")
        image.save(path)


if __name__ == "__main__":
    unittest.main()
