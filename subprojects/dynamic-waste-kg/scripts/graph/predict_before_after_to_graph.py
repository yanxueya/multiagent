"""Predict before/after scene images and update an auditable KG snapshot."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


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
from wastekg.core.identifiers import stable_compact_id
from wastekg.graph.exporters import (
    graph_events_to_jsonl,
    graph_to_json_snapshot,
    graph_to_mermaid,
    graph_to_neo4j_cypher,
    stabilize_event_ids,
)
from wastekg.paper.e4_image_sequence import (
    build_image_sequence_events,
    detections_from_yolo_records,
    match_image_sequence_detections,
    summarize_image_sequence,
)
from wastekg.yolo.image_pipeline import records_from_yolo_result
from wastekg.yolo.ultralytics_runtime import prepare_ultralytics_runtime
from wastekg.yolo.visual_review_evidence import attach_visual_evidence_to_records


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Predict before/after scene images with YOLO, write KG observations, and export change events."
    )
    parser.add_argument("--before", required=True, type=Path, help="Image captured before the action.")
    parser.add_argument("--after", required=True, type=Path, help="Image captured after the action.")
    parser.add_argument("--weights", required=True, type=Path, help="YOLO segmentation weights, for example best.pt.")
    parser.add_argument("--out", type=Path, default=Path("artifacts/before_after_graph"), help="Output directory.")
    parser.add_argument("--scene-id", default="", help="Stable scene id. If omitted, a deterministic id is generated.")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="0")
    parser.add_argument("--max-det", type=int, default=None)
    parser.add_argument("--iou-threshold", type=float, default=0.30, help="Same-class IoU threshold for fixed-view matching.")
    parser.add_argument("--llm-review", action="store_true", help="Use configured OpenAI-compatible LLM review.")
    parser.add_argument("--deepseek", action="store_true", help="Backward-compatible alias of --llm-review.")
    parser.add_argument("--sync-neo4j", action="store_true", help="Sync the final graph to Neo4j.")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-database", default="neo4j")
    parser.add_argument("--ui-snapshot", type=Path, default=None, help="Optional UI kg-snapshot.json output path.")
    return parser


def _predict_records(
    model: Any,
    image_path: Path,
    *,
    out_dir: Path,
    name: str,
    conf: float,
    imgsz: int,
    device: str,
    max_det: int | None,
) -> list[dict[str, Any]]:
    results = model.predict(
        source=str(image_path),
        conf=conf,
        imgsz=imgsz,
        device=device,
        save=True,
        project=str(out_dir),
        name=name,
        exist_ok=True,
        verbose=False,
    )
    if not results:
        raise RuntimeError(f"YOLO returned no result for {image_path}")
    return records_from_yolo_result(results[0], max_detections=max_det)


def _maybe_attach_llm_evidence(
    records: list[dict[str, Any]],
    *,
    image_path: Path,
    output_dir: Path,
    use_llm_review: bool,
) -> list[dict[str, Any]]:
    if not use_llm_review:
        return records
    policy = PerceptionPolicy()
    review_candidates = [
        record
        for record in records
        if policy.needs_review(str(record.get("yolo_class_name", "unknown")), float(record.get("yolo_confidence", 0.0)))
    ]
    enriched_candidates = attach_visual_evidence_to_records(
        review_candidates,
        image_path=image_path,
        output_dir=output_dir,
    )
    evidence_by_id = {str(record["temp_id"]): record for record in enriched_candidates}
    return [evidence_by_id.get(str(record.get("temp_id")), record) for record in records]


def _apply_frame(
    graph: KnowledgeGraph,
    *,
    frame_id: str,
    source: str,
    records: list[dict[str, Any]],
    reviewer: OpenAICompatibleReviewer | None,
    image_path: Path,
) -> dict[str, Any]:
    packet, summary = apply_perception_records_to_graph(
        graph,
        frame_id=frame_id,
        source=source,
        yolo_records=records,
        reviewer=reviewer,
        metadata={"rgb_ref": str(image_path.resolve())},
        allowed_classes=PAPER_VISUAL_CLASSES,
    )
    return {
        "frame_id": packet.frame_id,
        "source": packet.source,
        "summary": summary,
        "detections": [
            {
                "temp_id": item.temp_id,
                "resolved_class_name": item.resolved_class_name(),
                "resolved_confidence": item.resolved_confidence(),
                "review_status": item.review_status(),
            }
            for item in packet.detections
        ],
    }


def main() -> int:
    args = _build_parser().parse_args()
    before = args.before.resolve()
    after = args.after.resolve()
    if not before.is_file():
        raise SystemExit(f"Before image does not exist: {before}")
    if not after.is_file():
        raise SystemExit(f"After image does not exist: {after}")

    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    use_llm_review = args.llm_review or args.deepseek

    try:
        prepare_ultralytics_runtime(PROJECT_ROOT)
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("Please install ultralytics in this project's Python environment first.") from exc

    model = YOLO(str(args.weights))
    before_records = _predict_records(
        model,
        before,
        out_dir=out_dir,
        name="before_prediction",
        conf=args.conf,
        imgsz=args.imgsz,
        device=args.device,
        max_det=args.max_det,
    )
    after_records = _predict_records(
        model,
        after,
        out_dir=out_dir,
        name="after_prediction",
        conf=args.conf,
        imgsz=args.imgsz,
        device=args.device,
        max_det=args.max_det,
    )

    before_records = _maybe_attach_llm_evidence(
        before_records,
        image_path=before,
        output_dir=out_dir / "visual_evidence" / "before",
        use_llm_review=use_llm_review,
    )
    after_records = _maybe_attach_llm_evidence(
        after_records,
        image_path=after,
        output_dir=out_dir / "visual_evidence" / "after",
        use_llm_review=use_llm_review,
    )

    scene_id = args.scene_id or stable_compact_id("scn", f"{before}|{after}")
    graph = KnowledgeGraph(id_namespace=scene_id)
    seed_default_categories(graph)
    reviewer = OpenAICompatibleReviewer() if use_llm_review else None
    before_frame = f"{scene_id}_before"
    after_frame = f"{scene_id}_after"

    before_packet = _apply_frame(
        graph,
        frame_id=before_frame,
        source="before_after_yolo_visual_vlm" if use_llm_review else "before_after_yolo",
        records=before_records,
        reviewer=reviewer,
        image_path=before,
    )
    after_packet = _apply_frame(
        graph,
        frame_id=after_frame,
        source="before_after_yolo_visual_vlm" if use_llm_review else "before_after_yolo",
        records=after_records,
        reviewer=reviewer,
        image_path=after,
    )

    before_detections = detections_from_yolo_records("before", before_records)
    after_detections = detections_from_yolo_records("after", after_records)
    match_result = match_image_sequence_detections(
        before_detections,
        after_detections,
        iou_threshold=args.iou_threshold,
    )
    change_events = build_image_sequence_events(before_detections, after_detections, match_result)
    change_summary = summarize_image_sequence(before_detections, after_detections, match_result)

    stabilize_event_ids(graph, namespace=f"before_after:{before}|{after}")
    (out_dir / "before_yolo_records.json").write_text(json.dumps(before_records, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "after_yolo_records.json").write_text(json.dumps(after_records, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "vision_packets.json").write_text(
        json.dumps({"before": before_packet, "after": after_packet}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "change_events.json").write_text(json.dumps(change_events, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "change_summary.json").write_text(json.dumps(change_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "graph_snapshot.json").write_text(json.dumps(graph_to_json_snapshot(graph), ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "events.jsonl").write_text(graph_events_to_jsonl(graph), encoding="utf-8")
    (out_dir / "graph.mmd").write_text(graph_to_mermaid(graph), encoding="utf-8")
    (out_dir / "neo4j_import.cypher").write_text("\n".join(graph_to_neo4j_cypher(graph)) + "\n", encoding="utf-8")

    online_snapshot = None
    if args.sync_neo4j:
        from wastekg.graph.neo4j_store import Neo4jConnectionSettings, Neo4jGraphMirror

        password = os.environ.get("WASTEKG_NEO4J_PASSWORD", "")
        if not password:
            raise SystemExit("Set WASTEKG_NEO4J_PASSWORD before using --sync-neo4j.")
        mirror = Neo4jGraphMirror(
            Neo4jConnectionSettings(args.neo4j_uri, args.neo4j_user, password, args.neo4j_database)
        )
        try:
            mirror.verify_connectivity()
            neo4j_counts = mirror.sync_graph(graph)
            print(f"Neo4j sync: {json.dumps(neo4j_counts, ensure_ascii=False)}")
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

    print(f"Before: {before}")
    print(f"After: {after}")
    print(f"Weights: {args.weights.resolve()}")
    print(f"Scene id: {scene_id}")
    print(f"Before detections: {len(before_records)}")
    print(f"After detections: {len(after_records)}")
    print(f"Graph instances: {len(graph.instances)}")
    print(f"Change summary: {json.dumps(change_summary, ensure_ascii=False)}")
    print(f"Exported to: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
