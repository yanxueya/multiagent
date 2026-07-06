import unittest

from wastekg.taxonomy import KNOWN_VISUAL_CLASSES, PAPER_VISUAL_CLASSES, UNKNOWN_CATEGORY, WASTE12_CLASSES


class PaperVisualScopeTests(unittest.TestCase):
    def test_visual_scope_is_the_eleven_trained_classes_only(self) -> None:
        self.assertEqual(PAPER_VISUAL_CLASSES, KNOWN_VISUAL_CLASSES)
        self.assertEqual(WASTE12_CLASSES, KNOWN_VISUAL_CLASSES)
        self.assertNotIn("asbestos_suspect", PAPER_VISUAL_CLASSES)
        self.assertNotIn(UNKNOWN_CATEGORY, PAPER_VISUAL_CLASSES)


if __name__ == "__main__":
    unittest.main()
