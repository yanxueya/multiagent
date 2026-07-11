"""规范化实验室 Roboflow 数据，并隔离 E4 动作前后序列。"""

from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from wastekg.core.taxonomy import CLASS_TO_ID, KNOWN_VISUAL_CLASSES
from wastekg.data.audit import audit_dataset


def prepare_lab_adaptation_dataset(
    source_root: Path,
    output_root: Path,
    *,
    holdout_prefixes: Sequence[str],
) -> dict[str, Any]:
    """按类别名称重映射标签，并把动作序列永久隔离为 E4 holdout。"""

    source_root = source_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise ValueError(f"目标目录必须为空：{output_root}")

    audit = audit_dataset(source_root)
    issues = audit["annotation_issues"]
    if issues["conflicting_annotation_classes"]:
        files = ", ".join(issues["conflicting_class_label_files"])
        raise ValueError(f"存在同一 polygon 的类别冲突，必须先修正：{files}")

    source_classes = list(audit["class_names"])
    unsupported = sorted(set(source_classes) - set(KNOWN_VISUAL_CLASSES))
    if unsupported:
        raise ValueError(f"源数据包含当前 11 类体系外的类别：{unsupported}")
    class_id_map = {source_id: CLASS_TO_ID[class_name] for source_id, class_name in enumerate(source_classes)}
    normalized_prefixes = tuple(prefix.lower() for prefix in holdout_prefixes)

    for role in ("train_pool", "e4_holdout"):
        (output_root / role / "images").mkdir(parents=True, exist_ok=True)
        (output_root / role / "labels").mkdir(parents=True, exist_ok=True)

    role_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    records: list[dict[str, str]] = []
    for record in audit["manifest"]:
        source_image = source_root / record["image"]
        source_label = source_root / record["label"]
        if not source_label.is_file():
            raise ValueError(f"图像缺少可导入标签：{source_image}")
        original_stem = _roboflow_original_stem(source_image.name)
        role = "e4_holdout" if original_stem.lower().startswith(normalized_prefixes) else "train_pool"
        destination_image = output_root / role / "images" / source_image.name
        destination_label = output_root / role / "labels" / source_label.name
        if destination_image.exists() or destination_label.exists():
            raise ValueError(f"导入后文件名冲突：{source_image.name}")
        shutil.copy2(source_image, destination_image)
        remapped_counts = _remap_label(source_label, destination_label, source_classes, class_id_map)
        class_counts.update(remapped_counts)
        role_counts[role] += 1
        records.append(
            {
                "source_image": str(source_image),
                "source_label": str(source_label),
                "role": role,
                "output_image": str(destination_image),
                "output_label": str(destination_label),
            }
        )

    manifest = {
        "source_root": str(source_root),
        "output_root": str(output_root),
        "canonical_class_names": list(KNOWN_VISUAL_CLASSES),
        "source_class_names": source_classes,
        "class_id_map": {str(source_id): target_id for source_id, target_id in class_id_map.items()},
        "holdout_prefixes": list(holdout_prefixes),
        "role_image_counts": dict(role_counts),
        "instance_counts": dict(class_counts),
        "records": records,
    }
    (output_root / "lab_adaptation_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def _roboflow_original_stem(filename: str) -> str:
    stem = filename.split(".rf.", 1)[0]
    for suffix in ("_jpg", "_jpeg", "_png"):
        if stem.lower().endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def _remap_label(
    source: Path,
    destination: Path,
    source_classes: Sequence[str],
    class_id_map: dict[int, int],
) -> Counter[str]:
    lines: list[str] = []
    counts: Counter[str] = Counter()
    for line_number, raw_line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        tokens = raw_line.split()
        if len(tokens) < 7:
            raise ValueError(f"无法导入异常标签行：{source}:{line_number}")
        source_id = int(tokens[0])
        if source_id not in class_id_map:
            raise ValueError(f"无法映射类别 ID：{source}:{line_number} id={source_id}")
        class_name = source_classes[source_id]
        lines.append(" ".join([str(class_id_map[source_id]), *tokens[1:]]))
        counts[class_name] += 1
    destination.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return counts
