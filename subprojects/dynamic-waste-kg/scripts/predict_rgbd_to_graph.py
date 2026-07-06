from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg import KnowledgeGraph, OpenAICompatibleReviewer, apply_perception_records_to_graph, seed_default_categories
from wastekg.exporters import graph_events_to_jsonl, graph_to_json_snapshot, graph_to_mermaid, graph_to_neo4j_cypher
from wastekg.rgbd_geometry import enrich_records_with_rgbd
from wastekg.rgbd_io import load_depth_image, load_intrinsics
from wastekg.yolo_image_pipeline import records_from_yolo_result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Predict one aligned RGB-D frame and export a 3D knowledge graph snapshot.")
    parser.add_argument("--image", required=True, type=Path, help="Path to color.png.")
    parser.add_argument("--depth", required=True, type=Path, help="Path to aligned_depth.png.")
    parser.add_argument("--intrinsics", required=True, type=Path, help="Path to camera_intrinsics.json.")
    parser.add_argument("--weights", required=True, type=Path, help="Path to YOLO segmentation weights.")
    parser.add_argument("--out", type=Path, default=Path("artifacts/rgbd_graph_demo"), help="Output directory.")
    parser.add_argument("--conf", type=float, default=0.25, help="YOLO confidence threshold.")
    parser.add_argument("--imgsz", type=int, default=640, help="YOLO input image size.")
    parser.add_argument("--device", default="0", help="CUDA device id, or cpu.")
    parser.add_argument("--max-det", type=int, default=None, help="Keep only the top-N detections by confidence.")
    parser.add_argument("--min-depth", type=float, default=0.10, help="Minimum valid depth in meters.")
    parser.add_argument("--max-depth", type=float, default=3.00, help="Maximum valid depth in meters.")
    parser.add_argument("--llm-review", action="store_true", help="Use the configured OpenAI-compatible LLM reviewer.")
    parser.add_argument("--deepseek", action="store_true", help="Backward-compatible alias of --llm-review.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("Please install ultralytics in this project's Python environment before running RGB-D prediction.") from exc

    intrinsics = load_intrinsics(args.intrinsics)
    depth_image = load_depth_image(args.depth)
    model = YOLO(str(args.weights))
    results = model.predict(
        source=str(args.image),
        conf=args.conf,
        imgsz=args.imgsz,
        device=args.device,
        save=True,
        project=str(out_dir),
        name="prediction",
        exist_ok=True,
        verbose=False,
    )
    if not results:
        raise SystemExit("YOLO did not return prediction results.")

    yolo_records = records_from_yolo_result(results[0], max_detections=args.max_det)
    rgbd_records = enrich_records_with_rgbd(
        yolo_records,
        depth_image,
        intrinsics,
        min_depth_m=args.min_depth,
        max_depth_m=args.max_depth,
    )

    graph = KnowledgeGraph()
    seed_default_categories(graph)
    use_llm_review = args.llm_review or args.deepseek
    reviewer = OpenAICompatibleReviewer() if use_llm_review else None
    packet, summary = apply_perception_records_to_graph(
        graph,
        frame_id=args.image.stem,
        source="realsense_rgbd_yolo_llm" if use_llm_review else "realsense_rgbd_yolo",
        yolo_records=rgbd_records,
        reviewer=reviewer,
        camera_pose={"frame_id": intrinsics.frame_id},
    )

    (out_dir / "yolo_records.json").write_text(json.dumps(yolo_records, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "rgbd_records.json").write_text(json.dumps(rgbd_records, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "camera_intrinsics.json").write_text(json.dumps(intrinsics.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "vision_packet.json").write_text(
        json.dumps(
            {
                "frame_id": packet.frame_id,
                "source": packet.source,
                "camera_pose": packet.camera_pose,
                "detections": [
                    {
                        "temp_id": item.temp_id,
                        "resolved_class_name": item.resolved_class_name(),
                        "resolved_confidence": item.resolved_confidence(),
                        "center_xyz": item.center_xyz,
                        "bbox_3d": item.bbox_3d,
                        "visible_area_ratio": item.visible_area_ratio,
                        "safe_grasp_score": item.safe_grasp_score,
                        "review_status": item.review_status(),
                    }
                    for item in packet.detections
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "graph_snapshot.json").write_text(json.dumps(graph_to_json_snapshot(graph), ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "events.jsonl").write_text(graph_events_to_jsonl(graph), encoding="utf-8")
    (out_dir / "graph.mmd").write_text(graph_to_mermaid(graph), encoding="utf-8")
    (out_dir / "neo4j_import.cypher").write_text("\n".join(graph_to_neo4j_cypher(graph)) + "\n", encoding="utf-8")

    yolo_save_dir = Path(getattr(results[0], "save_dir", out_dir / "prediction")).resolve()
    print(f"Image: {args.image.resolve()}")
    print(f"Depth: {args.depth.resolve()}")
    print(f"Intrinsics: {args.intrinsics.resolve()}")
    print(f"Weights: {args.weights.resolve()}")
    print(f"Detections: {len(rgbd_records)}")
    print(f"Graph instances: {len(graph.instances)}")
    print(f"Exported to: {out_dir}")
    print(f"YOLO annotated image folder: {yolo_save_dir}")
    print(f"Summary: {json.dumps(summary, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
