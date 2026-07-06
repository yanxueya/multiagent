import unittest

from scripts.check_llm_config import mask_secret


class CheckLlmConfigTests(unittest.TestCase):
    def test_masks_secret_without_exposing_full_key(self) -> None:
        self.assertEqual(mask_secret("sk-1234567890abcd"), "sk-1...abcd")

    def test_masks_empty_secret(self) -> None:
        self.assertEqual(mask_secret(""), "<empty>")


if __name__ == "__main__":
    unittest.main()
