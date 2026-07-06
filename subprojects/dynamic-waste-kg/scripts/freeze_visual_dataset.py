"""冻结论文使用的 11 类视觉数据集，不改变知识图谱的 12 类长期知识。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.dataset_freeze import freeze_visual_dataset
from wastekg.taxonomy import WASTE12_CLASSES


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Freeze the paper's visual-class dataset without rewriting source data.")
    parser.add_argument("--source", type=Path, default=Path("datasets/waste12_grouped_candidate_v2"))
    parser.add_argument("--out", type=Path, default=Path("datasets/waste11_grouped_v1"))
    parser.add_argument("--class-name", action="append", default=None, help="Repeat in class-ID order. Defaults to the first 11 project classes.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    class_names = args.class_name or WASTE12_CLASSES[:-1]
    result = freeze_visual_dataset(args.source, args.out, class_names=class_names)
    print("Visual dataset frozen")
    print(f"Output: {Path(result['output_root'])}")
    print(f"Classes: {result['class_names']}")
    print(f"Split image counts: {result['split_image_counts']}")
    print(f"Materialization: {result['materialization']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
