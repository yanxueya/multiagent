import json
import tempfile
import unittest
from pathlib import Path

from wastekg.dataset_builder import build_dataset


class DatasetBuilderTests(unittest.TestCase):
    def test_build_dataset_maps_source_labels_to_research_classes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codd_root = root / "codd"
            inst_root = root / "instance"
            out_root = root / "out"
            (codd_root / "training").mkdir(parents=True)
            (codd_root / "training" / "sample.jpg").write_bytes(b"fake-jpg")
            (codd_root / "training" / "sample.xml").write_text(
                """<?xml version="1.0" encoding="utf-8"?>
<annotation>
  <filename>sample.jpg</filename>
  <size><width>100</width><height>100</height><depth>3</depth></size>
  <object>
    <name>stone</name>
    <bndbox><xmin>10</xmin><ymin>20</ymin><xmax>50</xmax><ymax>80</ymax></bndbox>
  </object>
</annotation>
""",
                encoding="utf-8",
            )
            (inst_root / "train").mkdir(parents=True)
            (inst_root / "train" / "img.jpg").write_bytes(b"fake-jpg")
            (inst_root / "train" / "_annotations.coco.json").write_text(
                json.dumps(
                    {
                        "images": [{"id": 1, "file_name": "img.jpg", "width": 100, "height": 100}],
                        "categories": [{"id": 1, "name": "cardboard"}],
                        "annotations": [
                            {
                                "id": 1,
                                "image_id": 1,
                                "category_id": 1,
                                "segmentation": [[10, 10, 40, 10, 40, 40, 10, 40]],
                                "bbox": [10, 10, 30, 30],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            summary = build_dataset(codd_root=codd_root, instance_seg_root=inst_root, output_root=out_root)

            self.assertTrue((out_root / "data.yaml").exists())
            self.assertTrue((out_root / "labels" / "train" / "codd_sample.txt").exists())
            self.assertTrue((out_root / "labels" / "train" / "instseg_img.txt").exists())
            self.assertEqual(summary["splits"]["train"]["by_class"]["concrete"], 1)
            self.assertEqual(summary["splits"]["train"]["by_class"]["paperboard"], 1)


if __name__ == "__main__":
    unittest.main()
