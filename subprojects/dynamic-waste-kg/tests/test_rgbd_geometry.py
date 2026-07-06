import unittest

from wastekg.rgbd_geometry import (
    CameraIntrinsics,
    deproject_pixel_to_point,
    enrich_record_with_rgbd,
    enrich_records_with_rgbd,
)


class RgbdGeometryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.intrinsics = CameraIntrinsics(width=10, height=10, fx=100.0, fy=100.0, ppx=5.0, ppy=5.0, depth_scale=0.001)

    def test_deprojects_pixel_depth_to_camera_xyz_meters(self) -> None:
        point = deproject_pixel_to_point(6.0, 4.0, 2.0, self.intrinsics)

        self.assertAlmostEqual(point[0], 0.02)
        self.assertAlmostEqual(point[1], -0.02)
        self.assertAlmostEqual(point[2], 2.0)

    def test_enriches_mask_record_with_3d_center_and_bbox(self) -> None:
        depth = [[0 for _ in range(10)] for _ in range(10)]
        for y in range(4, 7):
            for x in range(4, 7):
                depth[y][x] = 1000
        record = {
            "temp_id": "det_001",
            "yolo_class_name": "brick",
            "yolo_confidence": 0.91,
            "mask_polygon": [(4, 4), (7, 4), (7, 7), (4, 7)],
            "bbox_xyxy": [4, 4, 7, 7],
        }

        enriched = enrich_record_with_rgbd(record, depth, self.intrinsics)

        self.assertEqual(enriched["temp_id"], "det_001")
        self.assertEqual(enriched["yolo_class_name"], "brick")
        self.assertEqual(enriched["yolo_confidence"], 0.91)
        self.assertAlmostEqual(enriched["center_xyz"][2], 1.0)
        self.assertIsNotNone(enriched["bbox_3d"])
        self.assertGreater(enriched["visible_area_ratio"], 0.9)
        self.assertEqual(enriched["occlusion_state"], "visible")
        self.assertGreater(enriched["safe_grasp_score"], 0.7)
        self.assertEqual(enriched["grasp_candidates"][0]["frame"], "camera_color_optical_frame")

    def test_uses_bbox_when_mask_is_missing(self) -> None:
        depth = [[1000 for _ in range(10)] for _ in range(10)]
        record = {
            "temp_id": "det_002",
            "yolo_class_name": "wood",
            "yolo_confidence": 0.88,
            "bbox_xyxy": [2, 2, 5, 5],
        }

        enriched = enrich_record_with_rgbd(record, depth, self.intrinsics)

        self.assertAlmostEqual(enriched["center_xyz"][2], 1.0)
        self.assertGreater(enriched["visible_area_ratio"], 0.9)
        self.assertEqual(enriched["metadata"]["rgbd_source"], "aligned_depth_bbox")

    def test_invalid_depth_reduces_visible_area_and_score(self) -> None:
        depth = [[0 for _ in range(10)] for _ in range(10)]
        depth[5][5] = 1000
        record = {
            "temp_id": "det_003",
            "yolo_class_name": "glass",
            "yolo_confidence": 0.76,
            "mask_polygon": [(4, 4), (7, 4), (7, 7), (4, 7)],
            "bbox_xyxy": [4, 4, 7, 7],
        }

        enriched = enrich_record_with_rgbd(record, depth, self.intrinsics)

        self.assertLess(enriched["visible_area_ratio"], 0.5)
        self.assertEqual(enriched["occlusion_state"], "poor_depth")
        self.assertLess(enriched["safe_grasp_score"], 0.4)

    def test_enriches_multiple_records_without_mutating_originals(self) -> None:
        depth = [[1000 for _ in range(10)] for _ in range(10)]
        records = [
            {"temp_id": "a", "yolo_class_name": "brick", "yolo_confidence": 0.9, "bbox_xyxy": [1, 1, 3, 3]},
            {"temp_id": "b", "yolo_class_name": "metal", "yolo_confidence": 0.8, "bbox_xyxy": [4, 4, 6, 6]},
        ]

        enriched = enrich_records_with_rgbd(records, depth, self.intrinsics)

        self.assertEqual(len(enriched), 2)
        self.assertNotIn("bbox_3d", records[0])
        self.assertIn("bbox_3d", enriched[0])


if __name__ == "__main__":
    unittest.main()
