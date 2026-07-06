from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.llm_reviewer import LLMReviewerConfig, OpenAICompatibleReviewer


def mask_secret(value: str | None) -> str:
    if not value:
        return "<empty>"
    if len(value) < 8:
        return "<too-short>"
    return f"{value[:4]}...{value[-4:]}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check LLM reviewer configuration without running YOLO.")
    parser.add_argument("--live", action="store_true", help="Actually call the configured LLM API. This consumes token.")
    parser.add_argument("--yolo-class", default="gypsum_board", help="Class name used in live review test.")
    parser.add_argument("--confidence", type=float, default=0.62, help="YOLO confidence used in live review test.")
    parser.add_argument(
        "--allowed-classes",
        nargs="+",
        default=["gypsum_board", "asbestos_suspect", "glass", "brick"],
        help="Allowed classes used in live review test.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    config = LLMReviewerConfig.from_environment()
    print("LLM configuration")
    print(f"  base_url: {config.base_url}")
    print(f"  model: {config.model}")
    print(f"  api_key: {mask_secret(config.api_key)}")
    print(f"  timeout: {config.timeout}")
    print(f"  temperature: {config.temperature}")
    print(f"  max_tokens: {config.max_tokens}")

    if not args.live:
        print("\nDry run only. Add --live to test the API connection.")
        return 0

    reviewer = OpenAICompatibleReviewer(config)
    try:
        result = reviewer.review(
            "config_check_no_image",
            yolo_class_name=args.yolo_class,
            yolo_confidence=args.confidence,
            allowed_classes=list(args.allowed_classes),
        )
    except RuntimeError as exc:
        print("\nLive API check failed.")
        print(str(exc))
        print(
            "\nMost common causes: wrong API key, relay token used with official base_url, "
            "official key used with relay base_url, or model name not supported by the provider."
        )
        return 1

    print("\nLive API check succeeded.")
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
