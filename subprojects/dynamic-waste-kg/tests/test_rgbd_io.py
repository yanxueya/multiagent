"""验证 test rgbd io 相关功能。"""

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from wastekg.rgbd.io import load_depth_image, load_intrinsics


class RgbdIoTests(unittest.TestCase):
    def test_load_intrinsics_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "camera_intrinsics.json"
            path.write_text(
                json.dumps(
                    {
                        "width": 4,
                        "height": 3,
                        "fx": 100.0,
                        "fy": 101.0,
                        "ppx": 2.0,
                        "ppy": 1.5,
                        "depth_scale": 0.001,
                    }
                ),
                encoding="utf-8",
            )

            intrinsics = load_intrinsics(path)

        self.assertEqual(intrinsics.width, 4)
        self.assertEqual(intrinsics.height, 3)
        self.assertEqual(intrinsics.depth_scale, 0.001)

    def test_load_depth_png_as_nested_raw_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "aligned_depth.png"
            Image.new("I;16", (3, 2)).save(path)

            depth = load_depth_image(path)

        self.assertEqual(len(depth), 2)
        self.assertEqual(len(depth[0]), 3)


if __name__ == "__main__":
    unittest.main()
