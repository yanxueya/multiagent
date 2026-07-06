import tempfile
import unittest
from pathlib import Path

from PIL import Image

from wastekg.visual_review_evidence import attach_visual_evidence_to_records, create_visual_review_evidence


class VisualReviewEvidenceTests(unittest.TestCase):
    def test_attaches_serializable_visual_evidence_without_mutating_input_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "scene.jpg"
            Image.new("RGB", (100, 80), color="white").save(image_path)
            records = [
                {
                    "temp_id": "det_001",
                    "bbox_xyxy": [20, 20, 60, 50],
                    "mask_polygon": [(20, 20), (60, 20), (60, 50), (20, 50)],
                    "metadata": {"source": "yolo"},
                }
            ]

            enriched = attach_visual_evidence_to_records(
                records,
                image_path=image_path,
                output_dir=root / "evidence",
            )

            self.assertNotIn("visual_evidence", records[0])
            self.assertTrue(Path(enriched[0]["visual_evidence"]["crop_image"]).is_file())
            self.assertEqual(enriched[0]["metadata"]["visual_evidence"]["instance_id"], "det_001")

    def test_creates_original_crop_and_mask_overlay_with_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "scene.jpg"
            Image.new("RGB", (100, 80), color="white").save(image_path)

            evidence = create_visual_review_evidence(
                image_path=image_path,
                bbox_xyxy=[20, 20, 60, 50],
                mask_polygon=[(20, 20), (60, 20), (60, 50), (20, 50)],
                output_dir=root / "evidence",
                instance_id="det_001",
                padding_ratio=0.2,
            )

            self.assertTrue(evidence.original_image.is_file())
            self.assertTrue(evidence.crop_image.is_file())
            self.assertTrue(evidence.mask_overlay_image.is_file())
            self.assertEqual(set(evidence.sha256), {"original_image", "crop_image", "mask_overlay_image"})
            self.assertTrue(all(len(value) == 64 for value in evidence.sha256.values()))
            with Image.open(evidence.crop_image) as crop:
                self.assertEqual(crop.size, (56, 42))
            self.assertEqual(evidence.to_dict()["instance_id"], "det_001")


if __name__ == "__main__":
    unittest.main()
