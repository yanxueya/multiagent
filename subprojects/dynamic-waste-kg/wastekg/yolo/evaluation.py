"""整理 YOLO 分割评估结果并导出论文可复核指标。"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_CSV_FIELDS = (
    "class_id",
    "class_name",
    "instances",
    "box_precision",
    "box_recall",
    "box_map50",
    "box_map50_95",
    "mask_precision",
    "mask_recall",
    "mask_map50",
    "mask_map50_95",
)


def build_segmentation_evaluation_summary(
    *,
    class_names: Sequence[str],
    box_metric: Any,
    mask_metric: Any,
    class_instance_counts: Sequence[int],
    speed_ms: Mapping[str, float],
    split: str,
    image_count: int,
) -> dict[str, Any]:
    """将 box 和 mask 指标分开保存，避免以检测指标替代实例分割指标。"""

    classes = list(class_names)
    if not classes:
        raise ValueError("class_names 不能为空。")
    if not split:
        raise ValueError("split 不能为空。")
    if image_count < 0:
        raise ValueError("image_count 不能为负数。")
    if len(class_instance_counts) != len(classes):
        raise ValueError("class_instance_counts 必须与 class_names 一一对应。")

    box_by_id = _metric_by_class_id(box_metric, classes, metric_name="box")
    mask_by_id = _metric_by_class_id(mask_metric, classes, metric_name="mask")
    rows = []
    for class_id, class_name in enumerate(classes):
        box = box_by_id[class_id]
        mask = mask_by_id[class_id]
        rows.append(
            {
                "class_id": class_id,
                "class_name": class_name,
                "instances": int(class_instance_counts[class_id]),
                "box_precision": box["precision"],
                "box_recall": box["recall"],
                "box_map50": box["map50"],
                "box_map50_95": box["map50_95"],
                "mask_precision": mask["precision"],
                "mask_recall": mask["recall"],
                "mask_map50": mask["map50"],
                "mask_map50_95": mask["map50_95"],
            }
        )

    return {
        "split": split,
        "image_count": image_count,
        "class_names": classes,
        "overall": {"box": _overall_metric(box_metric), "mask": _overall_metric(mask_metric)},
        "speed_ms": {str(name): float(value) for name, value in speed_ms.items()},
        "per_class": rows,
    }


def write_evaluation_artifacts(
    summary: Mapping[str, Any], output_dir: Path, *, metadata: Mapping[str, Any]
) -> dict[str, Path]:
    """写入总体指标、逐类指标和输入溯源信息。"""

    output_dir.mkdir(parents=True, exist_ok=True)
    overall_path = output_dir / "overall_metrics.json"
    per_class_path = output_dir / "per_class_metrics.csv"
    manifest_path = output_dir / "evaluation_manifest.json"

    overall = {
        key: value
        for key, value in summary.items()
        if key in {"split", "image_count", "class_names", "overall", "speed_ms"}
    }
    overall["metadata"] = dict(metadata)
    overall_path.write_text(json.dumps(overall, ensure_ascii=False, indent=2), encoding="utf-8")

    with per_class_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(summary["per_class"])

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifact_version": 1,
        "split": summary["split"],
        "class_count": len(summary["class_names"]),
        "per_class_row_count": len(summary["per_class"]),
        "metadata": dict(metadata),
        "files": {
            "overall_metrics": overall_path.name,
            "per_class_metrics": per_class_path.name,
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "overall_metrics": overall_path,
        "per_class_metrics": per_class_path,
        "evaluation_manifest": manifest_path,
    }


def _overall_metric(metric: Any) -> dict[str, float]:
    precision, recall, map50, map50_95 = metric.mean_results()
    return {
        "precision": float(precision),
        "recall": float(recall),
        "map50": float(map50),
        "map50_95": float(map50_95),
    }


def _metric_by_class_id(metric: Any, class_names: Sequence[str], *, metric_name: str) -> dict[int, dict[str, float | int]]:
    class_ids = [int(value) for value in _as_list(metric.ap_class_index)]
    precision = _as_float_list(metric.p)
    recall = _as_float_list(metric.r)
    map50 = _as_float_list(metric.ap50)
    map50_95 = _as_float_list(metric.ap)
    lengths = {len(class_ids), len(precision), len(recall), len(map50), len(map50_95)}
    if len(lengths) != 1:
        raise ValueError(f"{metric_name} 指标长度不一致，无法可靠导出逐类结果。")
    expected_ids = set(range(len(class_names)))
    actual_ids = set(class_ids)
    if actual_ids != expected_ids:
        missing = sorted(expected_ids - actual_ids)
        extra = sorted(actual_ids - expected_ids)
        raise ValueError(f"{metric_name} 指标类别不完整：missing={missing}, extra={extra}。")
    if len(actual_ids) != len(class_ids):
        raise ValueError(f"{metric_name} 指标存在重复 class_id，无法可靠导出。")

    return {
        class_id: {
            "precision": precision[position],
            "recall": recall[position],
            "map50": map50[position],
            "map50_95": map50_95[position],
        }
        for position, class_id in enumerate(class_ids)
    }


def _as_list(value: Any) -> list[Any]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    return list(value)


def _as_float_list(value: Any) -> list[float]:
    return [float(item) for item in _as_list(value)]
