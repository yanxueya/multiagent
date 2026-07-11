"""验证 YOLO 分割标注可在不运行模型的情况下转为实例记录。"""

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from wastekg.data.yolo_annotations import annotations_to_detection_records, read_yolo_class_names, read_yolo_segments


class YoloAnnotationTests(unittest.TestCase):
    def test_reads_class_names_and_pixel_bbox(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data.yaml").write_text("nc: 2\nnames: ['glass', 'paperboard']\n", encoding="utf-8")
            image_path = root / "sample.jpg"
            Image.new("RGB", (200, 100)).save(image_path)
            label_path = root / "sample.txt"
            label_path.write_text("1 0.1 0.2 0.5 0.2 0.5 0.8 0.1 0.8\n", encoding="utf-8")

            names = read_yolo_class_names(root / "data.yaml")
            annotations = read_yolo_segments(image_path, label_path, names)
            records = annotations_to_detection_records(
                annotations,
                image_path=image_path,
                label_path=label_path,
                confidences={1: 0.5},
                track_ids={1: "paperboard_review"},
            )

            self.assertEqual(annotations[0].bbox_xyxy, (20.0, 20.0, 100.0, 80.0))
            self.assertEqual(records[0]["temp_id"], "paperboard_review")
            self.assertEqual(records[0]["yolo_confidence"], 0.5)


if __name__ == "__main__":
    unittest.main()
