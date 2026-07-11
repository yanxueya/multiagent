"""验证 test paper visual scope 相关功能。"""

import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from scripts.data import freeze_visual_dataset as freeze_script
from wastekg.core.taxonomy import KNOWN_VISUAL_CLASSES, PAPER_VISUAL_CLASSES, UNKNOWN_CATEGORY, WASTE12_CLASSES


class PaperVisualScopeTests(unittest.TestCase):
    def test_visual_scope_is_the_eleven_trained_classes_only(self) -> None:
        self.assertEqual(PAPER_VISUAL_CLASSES, KNOWN_VISUAL_CLASSES)
        self.assertEqual(WASTE12_CLASSES, KNOWN_VISUAL_CLASSES)
        self.assertNotIn("asbestos_suspect", PAPER_VISUAL_CLASSES)
        self.assertNotIn(UNKNOWN_CATEGORY, PAPER_VISUAL_CLASSES)

    def test_freeze_script_keeps_all_eleven_classes_including_glass(self) -> None:
        fake_result = {
            "output_root": "out",
            "class_names": KNOWN_VISUAL_CLASSES,
            "split_image_counts": {},
            "materialization": "test",
        }
        with patch.object(freeze_script, "freeze_visual_dataset", return_value=fake_result) as mocked:
            with redirect_stdout(StringIO()):
                freeze_script.main([])

        self.assertEqual(mocked.call_args.kwargs["class_names"], KNOWN_VISUAL_CLASSES)
        self.assertEqual(mocked.call_args.kwargs["class_names"][-1], "glass")


if __name__ == "__main__":
    unittest.main()
