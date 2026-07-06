"""从现有 YOLO 数据集生成场景候选分组后的独立数据版本。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

# 支持从项目根目录以 `python scripts/...` 方式直接执行。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.dataset_grouping import build_grouped_dataset


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a non-destructive grouped YOLO dataset split.")
    parser.add_argument("--source", type=Path, default=Path("datasets/waste12_yolo"))
    parser.add_argument("--out", type=Path, default=Path("datasets/waste12_grouped_candidate_v1"))
    parser.add_argument("--seed", type=int, default=0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = build_grouped_dataset(args.source, args.out, seed=args.seed)
    print("Grouped dataset created")
    print(f"Output: {Path(result['output_root'])}")
    print(f"Groups: {result['group_count']}")
    print(f"Split image counts: {result['split_image_counts']}")
    print(f"Materialization: {result['materialization']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
