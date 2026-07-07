"""运行 run e4 image sequence 小论文实验入口。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Iterable

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.paper.e4_image_sequence import (  # noqa: E402
    SequenceDetection,
    build_image_sequence_events,
    detections_from_yolo_records,
    match_image_sequence_detections,
    summarize_image_sequence,
)
from wastekg.yolo.ultralytics_runtime import prepare_ultralytics_runtime  # noqa: E402
from wastekg.yolo.image_pipeline import records_from_yolo_result  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run E4 image-sequence evidence with before/after images.")
    parser.add_argument("--before", required=True, type=Path, help="移除前图片。")
    parser.add_argument("--after", required=True, type=Path, help="移除后图片。")
    parser.add_argument("--weights", required=True, type=Path, help="YOLO segmentation weights, for example best.pt.")
    parser.add_argument("--out", type=Path, default=Path("artifacts/paper/e4_image_sequence"), help="输出目录。")
    parser.add_argument("--conf", type=float, default=0.35, help="YOLO confidence threshold.")
    parser.add_argument("--imgsz", type=int, default=640, help="YOLO input image size.")
    parser.add_argument("--device", default="0", help="CUDA device id, or cpu.")
    parser.add_argument("--max-det", type=int, default=20, help="每张图最多保留多少个检测结果。")
    parser.add_argument("--iou-threshold", type=float, default=0.30, help="前后帧同类包围盒匹配 IoU 阈值。")
    parser.add_argument("--note", default="", help="人工记录，例如：removed wood board manually.")
    return parser


def _predict_one(model: object, image_path: Path, out_dir: Path, name: str, args: argparse.Namespace) -> tuple[list[dict], Path]:
    results = model.predict(
        source=str(image_path),
        conf=args.conf,
        imgsz=args.imgsz,
        device=args.device,
        save=True,
        project=str(out_dir),
        name=name,
        exist_ok=True,
        verbose=False,
    )
    if not results:
        raise RuntimeError(f"YOLO did not return prediction for {image_path}")
    records = records_from_yolo_result(results[0], max_detections=args.max_det)
    save_dir = Path(getattr(results[0], "save_dir", out_dir / name))
    annotated = save_dir / image_path.name
    if not annotated.exists():
        matches = list(save_dir.glob(f"{image_path.stem}.*"))
        annotated = matches[0] if matches else image_path
    return records, annotated.resolve()


def _write_detections(path: Path, detections: Iterable[SequenceDetection]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["frame", "temp_id", "class_name", "confidence", "x1", "y1", "x2", "y2"],
        )
        writer.writeheader()
        for item in detections:
            x1, y1, x2, y2 = item.bbox_xyxy
            writer.writerow(
                {
                    "frame": item.frame,
                    "temp_id": item.temp_id,
                    "class_name": item.class_name,
                    "confidence": f"{item.confidence:.4f}",
                    "x1": f"{x1:.2f}",
                    "y1": f"{y1:.2f}",
                    "x2": f"{x2:.2f}",
                    "y2": f"{y2:.2f}",
                }
            )


def _make_comparison_image(before_path: Path, after_path: Path, out_path: Path) -> None:
    before = Image.open(before_path).convert("RGB")
    after = Image.open(after_path).convert("RGB")
    target_h = 520

    def resize_to_height(image: Image.Image) -> Image.Image:
        ratio = target_h / image.height
        return image.resize((max(1, int(image.width * ratio)), target_h))

    before = resize_to_height(before)
    after = resize_to_height(after)
    label_h = 44
    pad = 18
    width = before.width + after.width + pad * 3
    height = target_h + label_h + pad * 2
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    canvas.paste(before, (pad, pad + label_h))
    canvas.paste(after, (pad * 2 + before.width, pad + label_h))
    draw.text((pad, pad), "Before: manual removal candidate source", fill=(0, 0, 0))
    draw.text((pad * 2 + before.width, pad), "After: same-scene re-observation", fill=(0, 0, 0))
    canvas.save(out_path, quality=92)


def _write_report(
    path: Path,
    *,
    before_image: Path,
    after_image: Path,
    comparison_image: Path,
    summary: dict,
    note: str,
) -> None:
    comparison_ref = comparison_image.name if comparison_image.parent == path.parent else str(comparison_image)
    report = f"""# E4 图片序列状态更新实验报告

## 实验目的

本实验用于证明：在受控环境中，系统可以对同一场景的“移除前图片”和“移除后图片”分别执行 YOLO 实例分割，并将前后帧差异转化为可追溯事件。该实验暂不假设机械臂真实执行，只验证人工移除后的再感知与状态更新链路。

## 输入图片

- 移除前图片：`{before_image}`
- 移除后图片：`{after_image}`
- 人工记录：{note or "未提供；当前结果只能解释为视觉变化候选。"}

## 关键结果

- 移除前检测数：{summary["before_detection_count"]}
- 移除后检测数：{summary["after_detection_count"]}
- 持续存在实例数：{summary["persisted_count"]}
- 移除候选实例数：{summary["removed_candidate_count"]}
- 新增候选实例数：{summary["appeared_candidate_count"]}
- 事件数：{summary["event_count"]}

## 证据图

![E4 before-after comparison]({comparison_ref})

## 论文写作口径

如果输入图片由固定相机位姿采集，并且人工记录明确说明移除了某一物体，则“移除候选”可以作为人工移除后图谱状态变化的视觉证据。若没有人工记录，则应表述为“同一场景前后观测中的消失候选”，不能直接写成真实执行成功。
"""
    path.write_text(report, encoding="utf-8")


def main() -> int:
    args = _build_parser().parse_args()
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    prepare_ultralytics_runtime(PROJECT_ROOT)
    from ultralytics import YOLO

    model = YOLO(str(args.weights))
    before_records, before_annotated = _predict_one(model, args.before.resolve(), out_dir, "before_prediction", args)
    after_records, after_annotated = _predict_one(model, args.after.resolve(), out_dir, "after_prediction", args)

    before_detections = detections_from_yolo_records("before", before_records)
    after_detections = detections_from_yolo_records("after", after_records)
    match_result = match_image_sequence_detections(
        before_detections,
        after_detections,
        iou_threshold=args.iou_threshold,
    )
    events = build_image_sequence_events(before_detections, after_detections, match_result)
    summary = summarize_image_sequence(before_detections, after_detections, match_result)

    (out_dir / "before_yolo_records.json").write_text(json.dumps(before_records, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "after_yolo_records.json").write_text(json.dumps(after_records, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_detections(out_dir / "before_detections.csv", before_detections)
    _write_detections(out_dir / "after_detections.csv", after_detections)
    (out_dir / "events.jsonl").write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in events) + "\n", encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    comparison_image = (out_dir / "before_after_prediction_comparison.jpg").resolve()
    _make_comparison_image(before_annotated, after_annotated, comparison_image)
    _write_report(
        out_dir / "report.md",
        before_image=args.before.resolve(),
        after_image=args.after.resolve(),
        comparison_image=comparison_image,
        summary=summary,
        note=args.note,
    )

    print(f"Before image: {args.before.resolve()}")
    print(f"After image: {args.after.resolve()}")
    print(f"Before annotated: {before_annotated}")
    print(f"After annotated: {after_annotated}")
    print(f"Comparison image: {comparison_image}")
    print(f"Exported to: {out_dir}")
    print(f"Summary: {json.dumps(summary, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
