import os
import tempfile
import unittest
from pathlib import Path

from wastekg.ultralytics_runtime import prepare_ultralytics_runtime


class UltralyticsRuntimeTests(unittest.TestCase):
    def test_prepare_runtime_uses_project_config_directory_and_local_font(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_font = root / "source.ttf"
            source_font.write_bytes(b"fake-font")

            result = prepare_ultralytics_runtime(root / "project", font_candidates=[source_font])

            self.assertEqual(os.environ["YOLO_CONFIG_DIR"], str((root / "project" / ".ultralytics_runtime").resolve()))
            self.assertTrue(result["font_path"].exists())
            self.assertEqual(result["font_path"].read_bytes(), b"fake-font")
            self.assertEqual(result["config_dir"], (root / "project" / ".ultralytics_runtime" / "Ultralytics").resolve())


if __name__ == "__main__":
    unittest.main()
