"""提供 audit waste12 dataset 命令行入口。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

# 支持从项目根目录以 `python scripts/...` 方式直接执行。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.data.audit import audit_dataset, write_audit_artifacts


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit a YOLO segmentation dataset without changing its contents.")
    parser.add_argument("--dataset", type=Path, default=Path("datasets/waste12_yolo"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/e0_dataset_audit"))
    parser.add_argument("--weights", type=Path, action="append", default=[], help="Repeat for each frozen model weight file.")
    parser.add_argument("--training-command", default=None, help="Exact command used to produce the evaluated weights.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    audit = audit_dataset(args.dataset)
    written = write_audit_artifacts(
        audit,
        args.out,
        weight_paths=args.weights,
        training_command=args.training_command,
    )
    print("E0 dataset audit completed")
    for key, path in written.items():
        print(f"{key}: {path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
