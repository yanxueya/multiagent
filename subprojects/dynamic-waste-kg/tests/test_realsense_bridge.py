import json
import tempfile
import unittest
from pathlib import Path

from wastekg.realsense_bridge import RealSenseCaptureConfig, write_capture_metadata


class RealSenseBridgeTests(unittest.TestCase):
    def test_module_imports_without_realsense_sdk(self) -> None:
        config = RealSenseCaptureConfig(width=640, height=480, fps=30, warmup_frames=3)

        self.assertEqual(config.width, 640)
        self.assertEqual(config.height, 480)
        self.assertEqual(config.fps, 30)

    def test_write_capture_metadata_creates_beginner_readable_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            write_capture_metadata(
                output_dir,
                intrinsics={
                    "width": 640,
                    "height": 480,
                    "fx": 610.0,
                    "fy": 611.0,
                    "ppx": 320.0,
                    "ppy": 240.0,
                    "depth_scale": 0.001,
                },
                metadata={"device_name": "test_camera"},
            )

            intrinsics = json.loads((output_dir / "camera_intrinsics.json").read_text(encoding="utf-8"))
            capture_meta = json.loads((output_dir / "capture_meta.json").read_text(encoding="utf-8"))

        self.assertEqual(intrinsics["fx"], 610.0)
        self.assertEqual(capture_meta["device_name"], "test_camera")


if __name__ == "__main__":
    unittest.main()
