from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.ultralytics_runtime import prepare_ultralytics_runtime


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a YOLO segmentation model for the waste12 dataset.")
    parser.add_argument("--data", type=Path, default=Path("datasets/waste12_yolo/data.yaml"))
    parser.add_argument("--model", default="yolo11n-seg.pt")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--device", default="0")
    parser.add_argument("--project", default="runs/waste12_seg")
    parser.add_argument("--name", default="yolo11n_seg_baseline")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--patience", type=int, default=100)
    parser.add_argument("--cache", action="store_true")
    parser.add_argument("--exist-ok", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--close-mosaic", type=int, default=10)
    parser.add_argument("--optimizer", default="auto")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    prepare_ultralytics_runtime(PROJECT_ROOT)
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("请先安装 ultralytics：pip install ultralytics") from exc

    model = YOLO(args.model)
    train_kwargs = {
        "data": str(args.data),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "device": args.device,
        "project": args.project,
        "name": args.name,
        "workers": args.workers,
        "patience": args.patience,
        "cache": args.cache,
        "exist_ok": args.exist_ok,
        "resume": args.resume,
        "close_mosaic": args.close_mosaic,
        "optimizer": args.optimizer,
    }
    if args.batch is not None:
        train_kwargs["batch"] = args.batch
    model.train(**train_kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
