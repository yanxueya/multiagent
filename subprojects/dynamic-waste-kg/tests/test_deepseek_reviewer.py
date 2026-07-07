"""验证 test deepseek reviewer 相关功能。"""

import json
import os
import unittest
from unittest.mock import patch

from wastekg.llm.deepseek_reviewer import DeepSeekReviewer


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class DeepSeekReviewerTests(unittest.TestCase):
    def test_requires_api_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            reviewer = DeepSeekReviewer(api_key=None)
            with self.assertRaises(RuntimeError):
                reviewer.review(
                    "crop_001.jpg",
                    yolo_class_name="gypsum_board",
                    yolo_confidence=0.72,
                    allowed_classes=["gypsum_board", "unknown"],
                )

    def test_calls_deepseek_chat_completion_and_parses_json_review(self) -> None:
        response_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "class_name": "unknown",
                                "confidence": 0.76,
                                "risk_hint": "high",
                                "need_human_review": True,
                                "reason": "板材外观与石膏板相似，当前证据不足，需要人工复核。",
                            }
                        )
                    }
                }
            ]
        }

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeHTTPResponse(response_payload)

        with patch.dict(os.environ, {"LLM_ENV_FILE": "missing-test-env-file"}, clear=True):
            reviewer = DeepSeekReviewer(api_key="test-key", timeout=12)

        with patch("urllib.request.urlopen", fake_urlopen):
            result = reviewer.review(
                "crop_001.jpg",
                yolo_class_name="gypsum_board",
                yolo_confidence=0.72,
                allowed_classes=["gypsum_board", "unknown"],
            )

        self.assertEqual(captured["url"], "https://api.deepseek.com/chat/completions")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(captured["payload"]["model"], "deepseek-ai/DeepSeek-V4-Pro")
        self.assertEqual(captured["payload"]["response_format"], {"type": "json_object"})
        self.assertEqual(captured["payload"]["thinking"], {"type": "disabled"})
        self.assertEqual(result.class_name, "unknown")
        self.assertEqual(result.confidence, 0.76)
        self.assertEqual(result.risk_hint, "high")
        self.assertTrue(result.need_human_review)


if __name__ == "__main__":
    unittest.main()
