"""批量整理 E2 视觉复核实验结果。"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Mapping


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DECISION_KEYS = ("agree", "change", "uncertain", "review_error", "not_reviewed", "invalid")


def select_image_paths(image_dir: Path, *, limit: int) -> List[Path]:
    paths = [
        path
        for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]
    paths.sort(key=lambda item: item.name.lower())
    return paths[: max(0, int(limit))]


def summarize_review_rows(rows: Iterable[Mapping[str, object]]) -> Dict[str, object]:
    rows = list(rows)
    decision_counts = {key: 0 for key in DECISION_KEYS}
    human_review_required = 0
    valid_vlm = 0
    reviewed = 0

    for row in rows:
        decision = str(row.get("review_decision") or "not_reviewed")
        if decision not in decision_counts:
            decision = "invalid"
        decision_counts[decision] += 1
        if decision != "not_reviewed":
            reviewed += 1
        if decision in {"agree", "change", "uncertain"}:
            valid_vlm += 1
        review_status = str(row.get("review_status") or "")
        if review_status == "human_review_required" or bool(row.get("need_human_review")):
            human_review_required += 1

    detection_count = len(rows)
    return {
        "detection_count": detection_count,
        "reviewed_count": reviewed,
        "valid_vlm_response_count": valid_vlm,
        "human_review_required_count": human_review_required,
        "review_coverage": _safe_div(reviewed, detection_count),
        "valid_vlm_response_rate": _safe_div(valid_vlm, reviewed),
        "human_review_required_rate": _safe_div(human_review_required, detection_count),
        "decision_counts": decision_counts,
    }


def write_batch_outputs(output_dir: Path, rows: List[Mapping[str, object]], summary: Mapping[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_path = output_dir / "e2_vlm_batch_details.csv"
    fieldnames = [
        "image",
        "temp_id",
        "yolo_class_name",
        "yolo_confidence",
        "resolved_class_name",
        "resolved_confidence",
        "review_status",
        "review_decision",
        "need_human_review",
        "review_error_type",
        "review_error_message",
        "latency_seconds",
    ]
    with detail_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    (output_dir / "e2_vlm_batch_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "e2_vlm_batch_report.md").write_text(_report(summary), encoding="utf-8")


def _report(summary: Mapping[str, object]) -> str:
    lines = [
        "# E2 VLM Small-Batch Smoke Report",
        "",
        "This report summarizes a small-batch visual VLM review run. It is a smoke validation, not the final C1/C2 test-set evaluation.",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key in [
        "image_count",
        "detection_count",
        "reviewed_count",
        "valid_vlm_response_count",
        "human_review_required_count",
        "review_coverage",
        "valid_vlm_response_rate",
        "human_review_required_rate",
        "mean_latency_seconds",
    ]:
        if key in summary:
            value = summary[key]
            if isinstance(value, float):
                lines.append(f"| {key} | {value:.4f} |")
            else:
                lines.append(f"| {key} | {value} |")
    decision_counts = summary.get("decision_counts")
    if isinstance(decision_counts, dict):
        lines.extend(["", "## Decision Counts", "", "| Decision | Count |", "|---|---:|"])
        for key, value in decision_counts.items():
            lines.append(f"| {key} | {value} |")
    return "\n".join(lines)


def _safe_div(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
