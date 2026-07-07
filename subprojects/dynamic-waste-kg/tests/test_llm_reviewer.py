"""验证 test llm reviewer 相关功能。"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wastekg.llm.reviewer import LLMReviewerConfig, OpenAICompatibleReviewer


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class OpenAICompatibleReviewerTests(unittest.TestCase):
    def test_visual_evidence_payload_embeds_three_image_data_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            evidence_paths = {}
            for name in ("original_image", "crop_image", "mask_overlay_image"):
                path = root / f"{name}.jpg"
                path.write_bytes(b"jpeg-bytes")
                evidence_paths[name] = str(path)
            reviewer = OpenAICompatibleReviewer(
                LLMReviewerConfig(
                    api_key="test-key",
                    base_url="https://provider.example/api",
                    model="vision-review-model",
                )
            )

            payload = reviewer._build_payload(
                {"visual_evidence": evidence_paths},
                yolo_class_name="glass",
                yolo_confidence=0.61,
                allowed_classes=["glass", "brick"],
            )

        content = payload["messages"][1]["content"]
        self.assertIsInstance(content, list)
        image_blocks = [block for block in content if block["type"] == "image_url"]
        self.assertEqual(len(image_blocks), 3)
        self.assertTrue(all(block["image_url"]["url"].startswith("data:image/jpeg;base64,") for block in image_blocks))
        self.assertIn("decision", content[0]["text"])

    def test_visual_evidence_can_skip_original_image_for_batch_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            evidence_paths = {"send_original_image": False}
            for name in ("original_image", "crop_image", "mask_overlay_image"):
                path = root / f"{name}.jpg"
                path.write_bytes(b"jpeg-bytes")
                evidence_paths[name] = str(path)
            reviewer = OpenAICompatibleReviewer(
                LLMReviewerConfig(
                    api_key="test-key",
                    base_url="https://provider.example/api",
                    model="vision-review-model",
                )
            )

            payload = reviewer._build_payload(
                {"visual_evidence": evidence_paths},
                yolo_class_name="glass",
                yolo_confidence=0.61,
                allowed_classes=["glass", "brick"],
            )

        content = payload["messages"][1]["content"]
        image_blocks = [block for block in content if block["type"] == "image_url"]
        self.assertEqual(len(image_blocks), 2)

    def test_uses_generic_llm_environment_variables(self) -> None:
        with patch.dict(
            os.environ,
            {
                "LLM_API_KEY": "generic-key",
                "LLM_BASE_URL": "https://example.test/v1",
                "LLM_MODEL": "my-vision-reviewer",
            },
            clear=True,
        ):
            reviewer = OpenAICompatibleReviewer()

        self.assertEqual(reviewer.config.api_key, "generic-key")
        self.assertEqual(reviewer.config.base_url, "https://example.test/v1")
        self.assertEqual(reviewer.config.model, "my-vision-reviewer")

    def test_loads_generic_llm_values_from_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        'LLM_API_KEY="env-file-key"',
                        "LLM_BASE_URL=https://relay.example/v1",
                        "LLM_MODEL=relay-model",
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"LLM_ENV_FILE": str(env_path)}, clear=True):
                reviewer = OpenAICompatibleReviewer()

        self.assertEqual(reviewer.config.api_key, "env-file-key")
        self.assertEqual(reviewer.config.base_url, "https://relay.example/v1")
        self.assertEqual(reviewer.config.model, "relay-model")

    def test_can_disable_json_mode_from_env_file_for_vision_models(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "LLM_API_KEY=env-file-key",
                        "LLM_BASE_URL=https://api.siliconflow.cn/v1",
                        "LLM_MODEL=zai-org/GLM-4.5V",
                        "LLM_RESPONSE_FORMAT_JSON=false",
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"LLM_ENV_FILE": str(env_path)}, clear=True):
                reviewer = OpenAICompatibleReviewer()

        payload = reviewer._build_payload(
            "crop_001.jpg",
            yolo_class_name="brick",
            yolo_confidence=0.8,
            allowed_classes=["brick", "glass"],
        )

        self.assertFalse(reviewer.config.response_format_json)
        self.assertNotIn("response_format", payload)

    def test_calls_openai_compatible_chat_completion(self) -> None:
        response_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "class_name": "glass",
                                "confidence": 0.82,
                                "risk_hint": "medium",
                                "need_human_review": True,
                                "reason": "边缘反光且易碎，建议复核。",
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

        reviewer = OpenAICompatibleReviewer(
            LLMReviewerConfig(
                provider_name="custom",
                api_key="test-key",
                base_url="https://provider.example/api",
                model="review-model",
                timeout=7,
            )
        )

        with patch("urllib.request.urlopen", fake_urlopen):
            result = reviewer.review(
                {"image_ref": "crop_001.jpg"},
                yolo_class_name="glass",
                yolo_confidence=0.61,
                allowed_classes=["glass", "brick"],
            )

        self.assertEqual(captured["url"], "https://provider.example/api/chat/completions")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(captured["payload"]["model"], "review-model")
        self.assertEqual(captured["payload"]["response_format"], {"type": "json_object"})
        self.assertEqual(captured["timeout"], 7)
        self.assertEqual(result.class_name, "glass")
        self.assertEqual(result.confidence, 0.82)
        self.assertTrue(result.need_human_review)

    def test_invalid_returned_class_falls_back_to_yolo_and_requires_review(self) -> None:
        reviewer = OpenAICompatibleReviewer(
            LLMReviewerConfig(
                api_key="test-key",
                base_url="https://provider.example/api",
                model="review-model",
            )
        )
        response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "class_name": "unknown_new_class",
                                "confidence": 0.99,
                                "risk_hint": "high",
                                "need_human_review": False,
                                "reason": "bad class",
                            }
                        )
                    }
                }
            ]
        }

        result = reviewer._review_result_from_response(
            response,
            yolo_class_name="gypsum_board",
            allowed_classes=["gypsum_board", "glass"],
        )

        self.assertEqual(result.class_name, "gypsum_board")
        self.assertEqual(result.confidence, 0.0)
        self.assertTrue(result.need_human_review)

    def test_visual_uncertain_result_preserves_yolo_and_routes_to_human_review(self) -> None:
        reviewer = OpenAICompatibleReviewer(
            LLMReviewerConfig(
                api_key="test-key",
                base_url="https://provider.example/api",
                model="vision-review-model",
            )
        )
        response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "decision": "uncertain",
                                "proposed_class": "glass",
                                "confidence": 0.97,
                                "requires_human_review": False,
                                "reason": "The mask boundary is ambiguous.",
                            }
                        )
                    }
                }
            ]
        }

        result = reviewer._review_result_from_response(
            response,
            yolo_class_name="glass",
            allowed_classes=["glass", "brick"],
        )

        self.assertEqual(result.decision, "uncertain")
        self.assertEqual(result.class_name, "glass")
        self.assertEqual(result.confidence, 0.0)
        self.assertTrue(result.need_human_review)
        self.assertIn("ambiguous", result.reason)

    def test_glm_box_wrapped_json_is_parsed_as_visual_review(self) -> None:
        reviewer = OpenAICompatibleReviewer(
            LLMReviewerConfig(
                api_key="test-key",
                base_url="https://api.siliconflow.cn/v1",
                model="zai-org/GLM-4.5V",
            )
        )
        response = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '<|begin_of_box|>{"decision":"uncertain","proposed_class":"hard_plastic",'
                            '"confidence":0.0,"requires_human_review":true,'
                            '"reason":"visual evidence is insufficient"}<|end_of_box|>'
                        )
                    }
                }
            ]
        }

        result = reviewer._review_result_from_response(
            response,
            yolo_class_name="hard_plastic",
            allowed_classes=["hard_plastic", "glass"],
        )

        self.assertEqual(result.class_name, "hard_plastic")
        self.assertEqual(result.decision, "uncertain")
        self.assertTrue(result.need_human_review)

    def test_siliconflow_payload_uses_enable_thinking_flag(self) -> None:
        reviewer = OpenAICompatibleReviewer(
            LLMReviewerConfig(
                api_key="test-key",
                base_url="https://api.siliconflow.cn/v1",
                model="Qwen/Qwen2.5-7B-Instruct",
            )
        )

        payload = reviewer._build_payload(
            "crop_001.jpg",
            yolo_class_name="brick",
            yolo_confidence=0.8,
            allowed_classes=["brick", "glass"],
        )

        self.assertEqual(payload["enable_thinking"], False)
        self.assertNotIn("thinking", payload)


if __name__ == "__main__":
    unittest.main()
