"""导出论文定性样本图像和预测结果。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.data.audit import _read_data_yaml, _resolve_split_dir, _sha256
from wastekg.paper.qualitative_samples import render_ground_truth_overlay, select_sparse_examples
from wastekg.yolo.ultralytics_runtime import prepare_ultralytics_runtime


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="导出 YOLO 分割 test 样例的真值和预测对照图。")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("artifacts/e1_qualitative_samples"))
    parser.add_argument("--classes", default="metal,soft_plastic,glass,foam", help="逗号分隔的目标类别，按指定顺序各导出一个稀疏样例。")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.25, help="仅用于预测图显示的置信度阈值，不用于 AP 计算。")
    parser.add_argument("--device", default="0")
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
    target_classes = [name.strip() for name in args.classes.split(",") if name.strip()]
    if not target_classes:
        raise SystemExit("--classes 至少需要一个类别。")

    config = _read_data_yaml(data_path)
    image_dir = _resolve_split_dir(data_path.parent, config["split_paths"]["test"])
    label_dir = data_path.parent / "labels" / "test"
    samples = select_sparse_examples(
        image_dir=image_dir,
        label_dir=label_dir,
        class_names=config["class_names"],
        target_classes=target_classes,
    )

    prepare_ultralytics_runtime(PROJECT_ROOT)
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("请先在项目虚拟环境安装 ultralytics。") from exc

    model = YOLO(str(weights_path))
    records = []
    for sample in samples:
        stem = f"{sample['target_class']}__{sample['image_path'].stem}"
        gt_path = output_dir / f"{stem}__ground_truth.jpg"
        prediction_path = output_dir / f"{stem}__prediction.jpg"
        render_ground_truth_overlay(
            image_path=sample["image_path"],
            label_path=sample["label_path"],
            class_names=config["class_names"],
            output_path=gt_path,
        )
        result = model.predict(
            source=str(sample["image_path"]),
            imgsz=args.imgsz,
            conf=args.conf,
            device=args.device,
            verbose=False,
        )[0]
        # Ultralytics 的 plot 返回 BGR 数组，Pillow 保存前转换为 RGB。
        Image.fromarray(result.plot()[..., ::-1]).save(prediction_path, quality=95)
        records.append(
            {
                "target_class": sample["target_class"],
                "source_image": str(sample["image_path"]),
                "source_label": str(sample["label_path"]),
                "target_instances": sample["target_instances"],
                "total_instances": sample["total_instances"],
                "ground_truth_overlay": str(gt_path),
                "prediction_overlay": str(prediction_path),
            }
        )

    manifest = {
        "data_yaml": str(data_path),
        "data_yaml_sha256": _sha256(data_path),
        "weights": str(weights_path),
        "weights_sha256": _sha256(weights_path),
        "split": "test",
        "selection_rule": "每个目标类别选择总实例数最少的可用 test 图像；同分时按目标实例数和文件名排序。",
        "prediction_visualization": {"imgsz": args.imgsz, "conf": args.conf, "device": args.device},
        "samples": records,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "qualitative_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "samples": records}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
