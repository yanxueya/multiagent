"""提供实验室域适配数据规范化和 E4 holdout 隔离入口。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.data.lab_adaptation import prepare_lab_adaptation_dataset


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Remap a Roboflow lab dataset to the canonical 11 classes and isolate E4 sequences.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("datasets/lab_adaptation_v1"))
    parser.add_argument(
        "--holdout-prefix",
        action="append",
        default=None,
        help="Original filename prefix reserved for E4. Repeat as needed.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    prefixes = args.holdout_prefix or ["image_1-", "image_2-", "image_3-"]
    try:
        manifest = prepare_lab_adaptation_dataset(args.source, args.out, holdout_prefixes=prefixes)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps({key: manifest[key] for key in ("output_root", "role_image_counts", "instance_counts")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
