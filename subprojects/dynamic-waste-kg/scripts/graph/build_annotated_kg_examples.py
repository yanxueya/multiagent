"""用三张人工标注图片构建可复现 KG 示例，不运行 YOLO 训练或推理。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.core.knowledge_base import seed_default_categories
from wastekg.data.yolo_annotations import annotations_to_detection_records, read_yolo_class_names, read_yolo_segments
from wastekg.graph.exporters import graph_events_to_jsonl, graph_to_json_snapshot, graph_to_neo4j_cypher, stabilize_event_ids
from wastekg.graph.neo4j_store import Neo4jGraphMirror
from wastekg.graph.store import KnowledgeGraph
from wastekg.interfaces.contracts import vision_packet_to_observation
from wastekg.perception.pipeline import apply_perception_records_to_graph
from wastekg.perception.vision_bridge import build_vision_packet_from_records


BEFORE_STEM = "image_3-after_jpg.rf.7dUJB3BVukxkUS2Qgye8"
AFTER_STEM = "image_2-after1_jpg.rf.ytuqfrBe5Um00sPjnTJd"
REVIEW_STEM = "259650ef49ebae050d60dd52614b5c02_jpg.rf.uPUYawnIXxEblhooyu00"

BEFORE_TRACKS = {
    1: "glass_removed_unattributed",
    2: "paperboard_main",
    3: "glass_remaining",
    4: "soft_plastic_remaining",
    5: "paperboard_not_observed_after",
    6: "hard_plastic_action_target",
    7: "paperboard_secondary",
    8: "wood_remaining",
}
AFTER_TRACKS = {
    1: "soft_plastic_remaining",
    2: "paperboard_main",
    3: "paperboard_secondary",
    4: "glass_remaining",
    5: "wood_remaining",
}
REVIEW_TRACKS = {1: "paperboard_low_confidence", 2: "foam_high_confidence"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build annotation-driven KG examples without model inference.")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sync-neo4j", action="store_true")
    parser.add_argument("--replace-neo4j", action="store_true", help="Atomically replace existing Neo4j business nodes with this fixture.")
    return parser


def _paths(dataset_root: Path, stem: str) -> tuple[Path, Path]:
    return dataset_root / "train" / "images" / f"{stem}.jpg", dataset_root / "train" / "labels" / f"{stem}.txt"


def _records(dataset_root: Path, stem: str, class_names: list[str], tracks: dict[int, str], **kwargs: object) -> list[dict[str, object]]:
    image_path, label_path = _paths(dataset_root, stem)
    annotations = read_yolo_segments(image_path, label_path, class_names)
    return annotations_to_detection_records(
        annotations,
        image_path=image_path,
        label_path=label_path,
        track_ids=tracks,
        **kwargs,
    )


def build_examples(dataset_root: Path) -> tuple[KnowledgeGraph, dict[str, object]]:
    class_names = read_yolo_class_names(dataset_root / "data.yaml")
    graph = KnowledgeGraph(id_namespace="labexample")
    seed_default_categories(graph)

    before_records = _records(
        dataset_root, BEFORE_STEM, class_names, BEFORE_TRACKS,
        default_confidence=0.90, accepted_annotations=True,
    )
    before_packet = build_vision_packet_from_records(
        frame_id="scn_action_before",
        source="human_annotation_fixture",
        detections=before_records,
        metadata={"rgb_ref": str(_paths(dataset_root, BEFORE_STEM)[0])},
    )
    before_summary = graph.apply_observation(vision_packet_to_observation(before_packet))

    action_target_id = before_summary["resolved_ids"]["hard_plastic_action_target"]
    graph.record_planning_event(
        "scn_action_before",
        action_target_id,
        planned_action="robot_grasp",
        reason="Illustrative transition: hard_plastic selected from the author-confirmed before/after pair.",
        action_id="plan_demo_hard_plastic",
    )
    graph.record_execution_event(
        "scn_action_before",
        action_target_id,
        action_id="demo_robot_hard_plastic_01",
        physical_attempt_started=True,
        execution_result="success",
    )

    after_records = _records(
        dataset_root, AFTER_STEM, class_names, AFTER_TRACKS,
        default_confidence=0.90, accepted_annotations=True,
    )
    after_packet = build_vision_packet_from_records(
        frame_id="scn_action_after",
        source="human_annotation_fixture",
        detections=after_records,
        metadata={"rgb_ref": str(_paths(dataset_root, AFTER_STEM)[0])},
    )
    after_summary = graph.apply_observation(vision_packet_to_observation(after_packet))

    review_records = _records(
        dataset_root, REVIEW_STEM, class_names, REVIEW_TRACKS,
        confidences={1: 0.50, 2: 0.90}, default_confidence=0.90,
    )
    _, review_summary = apply_perception_records_to_graph(
        graph,
        frame_id="scn_low_conf_review",
        source="human_annotation_confidence_fixture",
        yolo_records=review_records,
        metadata={"rgb_ref": str(_paths(dataset_root, REVIEW_STEM)[0])},
        allowed_classes=class_names,
    )
    paperboard_id = review_summary["resolved_ids"]["paperboard_low_confidence"]
    graph.apply_human_review(
        paperboard_id,
        review_action="confirm_existing",
        confirmed_category="paperboard",
        reason="Author-controlled example: the 0.50 paperboard candidate is confirmed from the annotation.",
    )

    stabilize_event_ids(graph, namespace="annotated_kg_examples_v1")
    manifest: dict[str, object] = {
        "evidence_level": "illustrative_scenario_not_robot_validation",
        "model_inference_used": False,
        "training_used": False,
        "confidence_assumptions": {"accepted_annotations": 0.90, "low_confidence_paperboard": 0.50},
        "action_pair": {
            "before_scene": "scn_action_before",
            "after_scene": "scn_action_after",
            "attributed_execution_target": action_target_id,
            "execution_interpretation": "Illustrative only; no real robot telemetry is present.",
            "unattributed_disappearances": [
                before_summary["resolved_ids"]["glass_removed_unattributed"],
                before_summary["resolved_ids"]["paperboard_not_observed_after"],
            ],
            "reason": "A single-step planner cannot attribute two or more disappearances to one physical action without an intermediate Scene.",
        },
        "low_confidence_review": {
            "scene": "scn_low_conf_review",
            "paperboard_instance_id": paperboard_id,
            "route": ["DetectionEvent", "review_required", "HumanReviewEvent(confirm_existing)", "accepted"],
        },
        "summaries": {"before": before_summary, "after": after_summary, "review": review_summary},
    }
    return graph, manifest


def main() -> int:
    args = _parser().parse_args()
    dataset_root = args.dataset_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    graph, manifest = build_examples(dataset_root)
    snapshot = graph_to_json_snapshot(graph)
    snapshot["provenance"] = {
        "evidence_level": manifest["evidence_level"],
        "model_inference_used": manifest["model_inference_used"],
        "training_used": manifest["training_used"],
    }
    (output_dir / "kg_snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "events.jsonl").write_text(graph_events_to_jsonl(graph) + "\n", encoding="utf-8")
    (output_dir / "neo4j_import.cypher").write_text("\n".join(graph_to_neo4j_cypher(graph)) + "\n", encoding="utf-8")
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.sync_neo4j or args.replace_neo4j:
        mirror = Neo4jGraphMirror.from_env()
        try:
            mirror.verify_connectivity()
            counts = mirror.replace_graph(graph) if args.replace_neo4j else mirror.sync_graph(graph)
        finally:
            mirror.close()
        print("Neo4j sync: " + json.dumps(counts, ensure_ascii=False))
    print(f"Output: {output_dir}")
    print(f"categories={len(graph.categories)} scenes={len(graph.scenes)} instances={len(graph.instances)} events={len(graph.events)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
