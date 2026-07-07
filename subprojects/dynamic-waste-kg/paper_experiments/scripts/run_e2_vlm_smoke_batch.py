"""运行 run e2 vlm smoke batch 小论文实验入口。"""

from __future__ import annotations

import argparse
import json
import time
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg import (
    PAPER_VISUAL_CLASSES,
    KnowledgeGraph,
    OpenAICompatibleReviewer,
    PerceptionPolicy,
    apply_perception_records_to_graph,
    seed_default_categories,
)
from wastekg.graph.exporters import graph_events_to_jsonl, graph_to_json_snapshot
from wastekg.paper.e2_batch import select_image_paths, summarize_review_rows, write_batch_outputs
from wastekg.yolo.ultralytics_runtime import prepare_ultralytics_runtime
from wastekg.yolo.visual_review_evidence import attach_visual_evidence_to_records
from wastekg.yolo.image_pipeline import records_from_yolo_result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a small-batch E2 visual VLM smoke validation.")
    parser.add_argument("--image-dir", type=Path, default=PROJECT_ROOT / "datasets" / "waste12_yolo" / "images" / "val")
    parser.add_argument("--weights", type=Path, default=PROJECT_ROOT / "runs" / "segment" / "runs" / "waste12_seg" / "yolo11n_seg_cdw_glass_e50" / "weights" / "best.pt")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "artifacts" / "paper" / "e2_vlm_glm45v_batch20")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--max-det", type=int, default=1)
    parser.add_argument("--conf", type=float, default=0.5)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="0")
    parser.add_argument("--sleep-seconds", type=float, default=2.0, help="Delay before each VLM review request to reduce provider rate-limit errors.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    output_dir = args.out.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    images = select_image_paths(args.image_dir, limit=args.limit)
    if not images:
        raise SystemExit(f"No images found in {args.image_dir}")

    prepare_ultralytics_runtime(PROJECT_ROOT)
    from ultralytics import YOLO

    model = YOLO(str(args.weights))
    reviewer = OpenAICompatibleReviewer()
    policy = PerceptionPolicy()
    graph = KnowledgeGraph()
    seed_default_categories(graph)
    rows = []

    for index, image_path in enumerate(images, start=1):
        image_output_dir = output_dir / "images" / f"{index:03d}_{image_path.stem}"
        image_output_dir.mkdir(parents=True, exist_ok=True)
        start = time.perf_counter()
        results = model.predict(
            source=str(image_path),
            conf=args.conf,
            imgsz=args.imgsz,
            device=args.device,
            save=True,
            project=str(image_output_dir),
            name="prediction",
            exist_ok=True,
            verbose=False,
        )
        if not results:
            continue
        yolo_records = records_from_yolo_result(results[0], max_detections=args.max_det)
        review_candidates = [
            record
            for record in yolo_records
            if policy.needs_review(str(record.get("yolo_class_name", "unknown")), float(record.get("yolo_confidence", 0.0)))
        ]
        enriched_candidates = attach_visual_evidence_to_records(
            review_candidates,
            image_path=image_path,
            output_dir=image_output_dir / "visual_evidence",
        )
        for record in enriched_candidates:
            record["visual_evidence"]["send_original_image"] = False
            record["metadata"]["visual_evidence"]["send_original_image"] = False
        evidence_by_id = {str(record["temp_id"]): record for record in enriched_candidates}
        yolo_records = [evidence_by_id.get(str(record.get("temp_id")), record) for record in yolo_records]
        if review_candidates and args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)
        packet, _summary = apply_perception_records_to_graph(
            graph,
            frame_id=image_path.stem,
            source="e2_batch_yolo_visual_vlm",
            yolo_records=yolo_records,
            reviewer=reviewer,
            allowed_classes=PAPER_VISUAL_CLASSES,
        )
        packet_by_temp_id = {item.temp_id: item for item in packet.detections}
        latency = time.perf_counter() - start
        for record in yolo_records:
            temp_id = str(record.get("temp_id", ""))
            metadata = dict(record.get("metadata", {}))
            detection = packet_by_temp_id.get(temp_id)
            rows.append(
                {
                    "image": str(image_path),
                    "temp_id": temp_id,
                    "yolo_class_name": record.get("yolo_class_name", ""),
                    "yolo_confidence": record.get("yolo_confidence", 0.0),
                    "resolved_class_name": detection.resolved_class_name() if detection else "",
                    "resolved_confidence": detection.resolved_confidence() if detection else 0.0,
                    "review_status": detection.review_status() if detection else "not_reviewed",
                    "review_decision": metadata.get("review_decision", "not_reviewed"),
                    "need_human_review": metadata.get("need_human_review", False),
                    "review_error_type": metadata.get("review_error_type", ""),
                    "review_error_message": metadata.get("review_error_message", ""),
                    "latency_seconds": latency,
                }
            )

    summary = summarize_review_rows(rows)
    summary["image_count"] = len(images)
    if rows:
        summary["mean_latency_seconds"] = sum(float(row["latency_seconds"]) for row in rows) / len(rows)
    else:
        summary["mean_latency_seconds"] = 0.0
    write_batch_outputs(output_dir, rows, summary)
    (output_dir / "graph_snapshot.json").write_text(
        json.dumps(graph_to_json_snapshot(graph), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "events.jsonl").write_text(graph_events_to_jsonl(graph), encoding="utf-8")
    print(f"E2 small-batch VLM smoke results written to {output_dir}")
    print(f"Images: {summary['image_count']}; detections: {summary['detection_count']}; decisions: {summary['decision_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
