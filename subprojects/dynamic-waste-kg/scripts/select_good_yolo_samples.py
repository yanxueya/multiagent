"""筛选 YOLO 分割模型识别较好的代表样本。

用途：
1. 按数据来源和类别统计数据集；
2. 用训练好的 YOLO 模型在指定 split 上预测；
3. 根据“类别一致 + bbox IoU + 置信度”筛选代表样本；
4. 导出 CSV、JSON 和 contact sheet，方便人工检查数据集是否过杂。

注意：这里用 bbox IoU 做快速筛选，不等同于严格 mask IoU。
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO
import yaml


@dataclass
class GroundTruthObject:
    image_path: str
    label_path: str
    source: str
    split: str
    class_id: int
    class_name: str
    bbox_xyxy: tuple[float, float, float, float]


@dataclass
class MatchRecord:
    image_path: str
    source: str
    split: str
    class_id: int
    class_name: str
    gt_bbox_xyxy: tuple[float, float, float, float]
    pred_bbox_xyxy: tuple[float, float, float, float]
    confidence: float
    bbox_iou: float
    score: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="datasets/waste11_grouped_v1/data.yaml")
    parser.add_argument("--weights", default="runs/paper_e1/yolo11s_seg_waste11_grouped_e50_v1/weights/best.pt")
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--out", default="artifacts/good_samples_yolo11s_test")
    parser.add_argument("--conf", type=float, default=0.10)
    parser.add_argument("--iou-threshold", type=float, default=0.50)
    parser.add_argument("--conf-threshold", type=float, default=0.50)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="0")
    parser.add_argument("--batch-size", type=int, default=8, help="小批量预测，避免 8GB 显存溢出")
    parser.add_argument("--max-images", type=int, default=0, help="0 表示处理整个 split")
    return parser.parse_args()


def load_data_yaml(path: Path) -> tuple[Path, dict[int, str], str]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    root = Path(data["path"])
    names = {int(k): v for k, v in data["names"].items()}
    return root, names, data


def source_from_name(path: Path) -> str:
    return path.stem.split("_")[0].lower()


def yolo_seg_line_to_bbox(line: str, image_size: tuple[int, int]) -> tuple[int, tuple[float, float, float, float]] | None:
    parts = line.strip().split()
    if len(parts) < 5:
        return None
    class_id = int(float(parts[0]))
    values = [float(v) for v in parts[1:]]
    if len(values) < 4:
        return None
    width, height = image_size
    xs = values[0::2]
    ys = values[1::2]
    if not xs or not ys:
        return None
    x1 = max(0.0, min(xs) * width)
    y1 = max(0.0, min(ys) * height)
    x2 = min(float(width), max(xs) * width)
    y2 = min(float(height), max(ys) * height)
    if x2 <= x1 or y2 <= y1:
        return None
    return class_id, (x1, y1, x2, y2)


def iter_ground_truth(root: Path, names: dict[int, str], split: str, max_images: int = 0) -> Iterable[GroundTruthObject]:
    image_dir = root / "images" / split
    label_dir = root / "labels" / split
    image_paths = sorted([p for p in image_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}])
    if max_images > 0:
        image_paths = image_paths[:max_images]
    for image_path in image_paths:
        label_path = label_dir / f"{image_path.stem}.txt"
        if not label_path.exists():
            continue
        with Image.open(image_path) as im:
            size = im.size
        for line in label_path.read_text(encoding="utf-8").splitlines():
            parsed = yolo_seg_line_to_bbox(line, size)
            if parsed is None:
                continue
            class_id, bbox = parsed
            yield GroundTruthObject(
                image_path=str(image_path.resolve()),
                label_path=str(label_path.resolve()),
                source=source_from_name(image_path),
                split=split,
                class_id=class_id,
                class_name=names[class_id],
                bbox_xyxy=bbox,
            )


def bbox_iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


def predict_by_image(
    model: YOLO,
    image_paths: list[str],
    conf: float,
    imgsz: int,
    device: str,
    batch_size: int,
) -> dict[str, list[dict]]:
    predictions: dict[str, list[dict]] = {}
    for start in range(0, len(image_paths), batch_size):
        batch = image_paths[start : start + batch_size]
        results = model.predict(batch, conf=conf, imgsz=imgsz, device=device, verbose=False)
        for source_path, result in zip(batch, results):
            items: list[dict] = []
            if result.boxes is not None:
                for box in result.boxes:
                    cls = int(box.cls.item())
                    xyxy = tuple(float(v) for v in box.xyxy[0].tolist())
                    items.append(
                        {
                            "class_id": cls,
                            "confidence": float(box.conf.item()),
                            "bbox_xyxy": xyxy,
                        }
                    )
            # Ultralytics may report paths like image0.jpg when a Python list is used.
            # Use the original batch path so predictions can be matched to labels.
            predictions[str(Path(source_path).resolve())] = items
    return predictions


def make_contact_sheet(records: list[MatchRecord], out_path: Path, title: str) -> None:
    if not records:
        return
    cell_w, cell_h = 320, 260
    cols = 3
    rows = (len(records) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h + 40), "white")
    draw = ImageDraw.Draw(sheet)
    draw.text((8, 8), title, fill=(0, 0, 0))
    for idx, record in enumerate(records):
        row, col = divmod(idx, cols)
        x0 = col * cell_w
        y0 = row * cell_h + 40
        with Image.open(record.image_path) as im:
            im = im.convert("RGB")
            im.thumbnail((cell_w, cell_h - 55))
            canvas = Image.new("RGB", (cell_w, cell_h), "white")
            canvas.paste(im, ((cell_w - im.width) // 2, 0))
            scale_x = im.width / Image.open(record.image_path).size[0]
            scale_y = im.height / Image.open(record.image_path).size[1]
            offset_x = (cell_w - im.width) // 2
            gt = record.gt_bbox_xyxy
            pred = record.pred_bbox_xyxy
            d = ImageDraw.Draw(canvas)
            gt_box = [gt[0] * scale_x + offset_x, gt[1] * scale_y, gt[2] * scale_x + offset_x, gt[3] * scale_y]
            pred_box = [pred[0] * scale_x + offset_x, pred[1] * scale_y, pred[2] * scale_x + offset_x, pred[3] * scale_y]
            d.rectangle(gt_box, outline=(0, 180, 0), width=3)
            d.rectangle(pred_box, outline=(220, 0, 0), width=2)
            label = f"{record.source}/{record.class_name} conf={record.confidence:.2f} iou={record.bbox_iou:.2f}"
            d.text((5, cell_h - 45), label, fill=(0, 0, 0))
            d.text((5, cell_h - 25), Path(record.image_path).name[:42], fill=(0, 0, 0))
            sheet.paste(canvas, (x0, y0))
    sheet.save(out_path)


def write_csv(path: Path, records: list[MatchRecord]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = list(asdict(records[0]).keys()) if records else [
            "image_path",
            "source",
            "split",
            "class_id",
            "class_name",
            "gt_bbox_xyxy",
            "pred_bbox_xyxy",
            "confidence",
            "bbox_iou",
            "score",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))


def main() -> int:
    args = parse_args()
    data_yaml = Path(args.data)
    root, names, raw_data = load_data_yaml(data_yaml)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    gt_objects = list(iter_ground_truth(root, names, args.split, args.max_images))
    image_paths = sorted({obj.image_path for obj in gt_objects})
    model = YOLO(args.weights)
    predictions = predict_by_image(model, image_paths, args.conf, args.imgsz, args.device, args.batch_size)

    dataset_counts: dict[str, dict[str, int]] = {}
    for obj in gt_objects:
        dataset_counts.setdefault(obj.source, {}).setdefault(obj.class_name, 0)
        dataset_counts[obj.source][obj.class_name] += 1

    matches: list[MatchRecord] = []
    for obj in gt_objects:
        best_pred = None
        best_iou = 0.0
        for pred in predictions.get(obj.image_path, []):
            if pred["class_id"] != obj.class_id:
                continue
            iou = bbox_iou(obj.bbox_xyxy, pred["bbox_xyxy"])
            if iou > best_iou:
                best_iou = iou
                best_pred = pred
        if best_pred is None:
            continue
        conf = best_pred["confidence"]
        if best_iou < args.iou_threshold or conf < args.conf_threshold:
            continue
        matches.append(
            MatchRecord(
                image_path=obj.image_path,
                source=obj.source,
                split=args.split,
                class_id=obj.class_id,
                class_name=obj.class_name,
                gt_bbox_xyxy=obj.bbox_xyxy,
                pred_bbox_xyxy=best_pred["bbox_xyxy"],
                confidence=conf,
                bbox_iou=best_iou,
                score=conf * best_iou,
            )
        )

    matches.sort(key=lambda r: (r.source, r.class_id, -r.score))
    selected: list[MatchRecord] = []
    groups: dict[tuple[str, str], list[MatchRecord]] = {}
    for record in matches:
        groups.setdefault((record.source, record.class_name), []).append(record)
    for key in sorted(groups):
        selected.extend(groups[key][: args.top_k])

    write_csv(out / "all_good_matches.csv", matches)
    write_csv(out / "selected_good_samples.csv", selected)
    (out / "dataset_counts_by_source_class.json").write_text(
        json.dumps(dataset_counts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "selected_good_samples.json").write_text(
        json.dumps([asdict(r) for r in selected], ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for source in sorted({record.source for record in selected}):
        source_records = [record for record in selected if record.source == source]
        make_contact_sheet(source_records[: min(len(source_records), 33)], out / f"contact_sheet_{source}.jpg", source)
    make_contact_sheet(selected[: min(len(selected), 33)], out / "contact_sheet_all_sources.jpg", "selected good samples")

    summary = {
        "data": raw_data,
        "weights": str(Path(args.weights).resolve()),
        "split": args.split,
        "image_count": len(image_paths),
        "gt_object_count": len(gt_objects),
        "match_count": len(matches),
        "selected_count": len(selected),
        "criteria": {
            "prediction_conf_min": args.conf,
            "selected_conf_threshold": args.conf_threshold,
            "selected_bbox_iou_threshold": args.iou_threshold,
            "top_k_per_source_class": args.top_k,
        },
        "outputs": {
            "all_good_matches": str((out / "all_good_matches.csv").resolve()),
            "selected_good_samples": str((out / "selected_good_samples.csv").resolve()),
            "dataset_counts": str((out / "dataset_counts_by_source_class.json").resolve()),
        },
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
