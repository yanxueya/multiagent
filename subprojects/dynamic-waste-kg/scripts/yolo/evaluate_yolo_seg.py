"""提供 evaluate yolo seg 命令行入口。"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.data.audit import _image_paths, _read_data_yaml, _resolve_split_dir, _sha256
from wastekg.yolo.ultralytics_runtime import prepare_ultralytics_runtime
from wastekg.yolo.evaluation import build_segmentation_evaluation_summary, write_evaluation_artifacts


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="在独立数据切分上导出 YOLO 实例分割论文指标。")
    parser.add_argument("--data", type=Path, required=True, help="冻结数据集的 data.yaml 路径。")
    parser.add_argument("--weights", type=Path, required=True, help="训练完成后冻结的 best.pt 路径。")
    parser.add_argument("--out", type=Path, default=Path("artifacts/e1_test_evaluation"), help="评估产物目录。")
    parser.add_argument("--split", choices=("test", "val", "train"), default="test", help="评估切分，论文正式结果必须使用 test。")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=2)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    data_path = args.data.resolve()
    weights_path = args.weights.resolve()
    output_dir = args.out.resolve()
    if not data_path.is_file():
        raise SystemExit(f"找不到 data.yaml：{data_path}")
    if not weights_path.is_file():
        raise SystemExit(f"找不到模型权重：{weights_path}")

    # 必须在导入 Ultralytics 前设置本地配置目录，避免向受限的 AppData 写入文件。
    prepare_ultralytics_runtime(PROJECT_ROOT)
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("请先在项目虚拟环境安装 ultralytics。") from exc

    dataset_config = _read_data_yaml(data_path)
    dataset_root = data_path.parent
    image_dir = _resolve_split_dir(dataset_root, dataset_config["split_paths"][args.split])
    image_count = len(_image_paths(image_dir))
    raw_output_dir = output_dir / "ultralytics"
    model = YOLO(str(weights_path))
    metrics = model.val(
        data=str(data_path),
        split=args.split,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        plots=True,
        project=str(raw_output_dir),
        name="metrics",
        exist_ok=True,
    )
    summary = build_segmentation_evaluation_summary(
        class_names=dataset_config["class_names"],
        box_metric=metrics.box,
        mask_metric=metrics.seg,
        class_instance_counts=metrics.nt_per_class,
        speed_ms=metrics.speed,
        split=args.split,
        image_count=image_count,
    )
    metadata = {
        "data_yaml": str(data_path),
        "data_yaml_sha256": _sha256(data_path),
        "weights": str(weights_path),
        "weights_sha256": _sha256(weights_path),
        "ultralytics_version": _package_version("ultralytics"),
        "torch_version": _package_version("torch"),
        "raw_ultralytics_output": str(Path(metrics.save_dir).resolve()),
        "imgsz": args.imgsz,
        "batch": args.batch,
        "device": args.device,
        "workers": args.workers,
    }
    artifacts = write_evaluation_artifacts(summary, output_dir, metadata=metadata)
    print(json.dumps({"artifacts": {key: str(path) for key, path in artifacts.items()}, "overall": summary["overall"]}, ensure_ascii=False, indent=2))
    return 0


def _package_version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
