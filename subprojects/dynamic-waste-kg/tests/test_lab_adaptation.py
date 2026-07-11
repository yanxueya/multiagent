"""验证实验室数据类别重映射与 E4 序列隔离。"""

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from wastekg.data.lab_adaptation import prepare_lab_adaptation_dataset


class LabAdaptationTests(unittest.TestCase):
    def test_remaps_by_class_name_and_isolates_sequence_holdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            output = Path(tmp) / "output"
            for split in ("train", "valid"):
                (source / split / "images").mkdir(parents=True)
                (source / split / "labels").mkdir(parents=True)
            source.joinpath("data.yaml").write_text(
                "train: ../train/images\nval: ../valid/images\nnames: ['brick', 'wood']\n",
                encoding="utf-8",
            )
            Image.new("RGB", (20, 20), color="red").save(source / "train" / "images" / "lab_scene_jpg.rf.a.jpg")
            source.joinpath("train/labels/lab_scene_jpg.rf.a.txt").write_text(
                "0 0.1 0.1 0.8 0.1 0.8 0.8 0.1 0.8\n",
                encoding="utf-8",
            )
            Image.new("RGB", (20, 20), color="blue").save(source / "valid" / "images" / "image_1-before_jpg.rf.b.jpg")
            source.joinpath("valid/labels/image_1-before_jpg.rf.b.txt").write_text(
                "1 0.1 0.1 0.8 0.1 0.8 0.8 0.1 0.8\n",
                encoding="utf-8",
            )

            result = prepare_lab_adaptation_dataset(source, output, holdout_prefixes=["image_1-"])

            self.assertEqual(result["role_image_counts"], {"train_pool": 1, "e4_holdout": 1})
            self.assertTrue((output / "train_pool/images/lab_scene_jpg.rf.a.jpg").exists())
            self.assertTrue((output / "e4_holdout/images/image_1-before_jpg.rf.b.jpg").exists())
            self.assertTrue((output / "train_pool/labels/lab_scene_jpg.rf.a.txt").read_text(encoding="utf-8").startswith("1 "))
            self.assertTrue((output / "e4_holdout/labels/image_1-before_jpg.rf.b.txt").read_text(encoding="utf-8").startswith("3 "))

    def test_rejects_conflicting_class_masks_before_copying(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            output = Path(tmp) / "output"
            (source / "train" / "images").mkdir(parents=True)
            (source / "train" / "labels").mkdir(parents=True)
            source.joinpath("data.yaml").write_text(
                "train: ../train/images\nnames: ['brick', 'wood']\n",
                encoding="utf-8",
            )
            Image.new("RGB", (20, 20), color="red").save(source / "train/images/sample.jpg")
            polygon = "0.1 0.1 0.8 0.1 0.8 0.8 0.1 0.8"
            source.joinpath("train/labels/sample.txt").write_text(f"0 {polygon}\n1 {polygon}\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "类别冲突"):
                prepare_lab_adaptation_dataset(source, output, holdout_prefixes=[])

            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
