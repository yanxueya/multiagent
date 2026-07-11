"""将单张图像预测结果写入知识图谱。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import os
import sys

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
from wastekg.graph.exporters import graph_events_to_jsonl, graph_to_json_snapshot, graph_to_mermaid, graph_to_neo4j_cypher, stabilize_event_ids
from wastekg.core.identifiers import stable_compact_id
from wastekg.yolo.ultralytics_runtime import prepare_ultralytics_runtime
from wastekg.yolo.visual_review_evidence import attach_visual_evidence_to_records
from wastekg.yolo.image_pipeline import records_from_yolo_result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Predict one image with YOLO and export a knowledge graph snapshot.")
    parser.add_argument("--image", required=True, type=Path, help="Path to one input image.")
    parser.add_argument("--weights", required=True, type=Path, help="Path to YOLO segmentation weights, for example best.pt.")
    parser.add_argument("--out", type=Path, default=Path("artifacts/single_image_graph"), help="Output directory.")
    parser.add_argument("--conf", type=float, default=0.25, help="YOLO confidence threshold.")
    parser.add_argument("--imgsz", type=int, default=640, help="YOLO input image size.")
    parser.add_argument("--device", default="0", help="CUDA device id, or cpu.")
    parser.add_argument("--max-det", type=int, default=None, help="Keep only the top-N detections by confidence.")
    parser.add_argument("--llm-review", action="store_true", help="Use the configured OpenAI-compatible LLM reviewer.")
    parser.add_argument("--deepseek", action="store_true", help="Backward-compatible alias of --llm-review.")
    parser.add_argument("--sync-neo4j", action="store_true", help="Sync the generated graph through the controlled Neo4j mirror.")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-database", default="neo4j")
    parser.add_argument("--ui-snapshot", type=Path, default=None, help="Optional UI kg-snapshot.json output path.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        prepare_ultralytics_runtime(PROJECT_ROOT)
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("请先安装 ultralytics，或确认已经激活本项目 .venv。") from exc

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
        raise SystemExit("YOLO 没有返回预测结果。")

    yolo_records = records_from_yolo_result(results[0], max_detections=args.max_det)
    image_ref = str(args.image.resolve())
    scene_id = stable_compact_id("scn", image_ref)
    graph = KnowledgeGraph(id_namespace=scene_id)
    seed_default_categories(graph)
    use_llm_review = args.llm_review or args.deepseek
    policy = PerceptionPolicy()
    if use_llm_review:
        review_candidates = [
            record
            for record in yolo_records
            if policy.needs_review(str(record.get("yolo_class_name", "unknown")), float(record.get("yolo_confidence", 0.0)))
        ]
        enriched_candidates = attach_visual_evidence_to_records(
            review_candidates,
            image_path=args.image,
            output_dir=out_dir / "visual_evidence",
        )
        evidence_by_id = {str(record["temp_id"]): record for record in enriched_candidates}
        yolo_records = [evidence_by_id.get(str(record.get("temp_id")), record) for record in yolo_records]
    reviewer = OpenAICompatibleReviewer() if use_llm_review else None
    packet, summary = apply_perception_records_to_graph(
        graph,
        frame_id=scene_id,
        source="single_image_yolo_visual_vlm" if use_llm_review else "single_image_yolo",
        yolo_records=yolo_records,
        reviewer=reviewer,
        metadata={"rgb_ref": image_ref},
        allowed_classes=PAPER_VISUAL_CLASSES,
    )
    stabilize_event_ids(graph, namespace=f"single_image:{args.image.resolve()}")

    (out_dir / "yolo_records.json").write_text(json.dumps(yolo_records, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "vision_packet.json").write_text(
        json.dumps(
            {
                "frame_id": packet.frame_id,
                "source": packet.source,
                "detections": [
                    {
                        "temp_id": item.temp_id,
                        "resolved_class_name": item.resolved_class_name(),
                        "resolved_confidence": item.resolved_confidence(),
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

    online_snapshot = None
    if args.sync_neo4j:
        from wastekg.graph.neo4j_store import Neo4jConnectionSettings, Neo4jGraphMirror

        password = os.environ.get("WASTEKG_NEO4J_PASSWORD", "")
        if not password:
            raise SystemExit("设置 WASTEKG_NEO4J_PASSWORD 后才能启用 --sync-neo4j。")
        mirror = Neo4jGraphMirror(
            Neo4jConnectionSettings(args.neo4j_uri, args.neo4j_user, password, args.neo4j_database)
        )
        try:
            mirror.verify_connectivity()
            neo4j_counts = mirror.sync_graph(graph)
            print(f"Neo4j sync: {json.dumps(neo4j_counts, ensure_ascii=False)}")
            print(f"Neo4j live: {json.dumps(mirror.read_summary(), ensure_ascii=False)}")
            online_snapshot = mirror.read_snapshot()
        finally:
            mirror.close()

    if args.ui_snapshot is not None:
        ui_output = args.ui_snapshot.resolve()
        ui_output.parent.mkdir(parents=True, exist_ok=True)
        temporary = ui_output.with_suffix(ui_output.suffix + ".tmp")
        temporary.write_text(json.dumps(online_snapshot or graph_to_json_snapshot(graph), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(ui_output)
        print(f"UI snapshot: {ui_output}")

    yolo_save_dir = Path(getattr(results[0], "save_dir", out_dir / "prediction")).resolve()
    print(f"Image: {args.image.resolve()}")
    print(f"Weights: {args.weights.resolve()}")
    print(f"Detections: {len(yolo_records)}")
    print(f"Graph instances: {len(graph.instances)}")
    print(f"Exported to: {out_dir}")
    print(f"YOLO annotated image folder: {yolo_save_dir}")
    print(f"Summary: {json.dumps(summary, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
