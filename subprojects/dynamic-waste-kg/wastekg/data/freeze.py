"""冻结论文使用的视觉数据集版本。"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Sequence

from wastekg.data.audit import SPLITS, audit_dataset
from wastekg.data.grouping import _link_or_copy


def freeze_visual_dataset(source_root: Path, output_root: Path, *, class_names: Sequence[str]) -> Dict[str, Any]:
    """从已审计的源数据集创建类别数更少、split 不变的独立视觉训练视图。"""

    source_root = source_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise ValueError(f"目标目录必须为空，避免覆盖已冻结的视觉数据集：{output_root}")
    if not class_names:
        raise ValueError("至少需要一个视觉类别")

    audit = audit_dataset(source_root)
    _validate_visual_classes(audit, class_names)
    for split in SPLITS:
        (output_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_root / "labels" / split).mkdir(parents=True, exist_ok=True)

    materialization = Counter()
    split_image_counts = Counter()
    for record in audit["manifest"]:
        split = record["split"]
        source_image = source_root / record["image"]
        source_label = source_root / record["label"]
        destination_image = output_root / "images" / split / source_image.name
        destination_label = output_root / "labels" / split / source_label.name
        if destination_image.exists() or destination_label.exists():
            raise ValueError(f"冻结视图出现文件名冲突：{source_image.name}")
        materialization[_link_or_copy(source_image, destination_image)] += 1
        materialization[_link_or_copy(source_label, destination_label)] += 1
        split_image_counts[split] += 1

    _write_data_yaml(output_root, class_names)
    result = {
        "source_root": str(source_root),
        "output_root": str(output_root),
        "class_names": list(class_names),
        "source_data_yaml_sha256": audit["data_yaml_sha256"],
        "split_image_counts": {split: split_image_counts[split] for split in SPLITS},
        "materialization": dict(materialization),
    }
    (output_root / "visual_dataset_manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _validate_visual_classes(audit: Dict[str, Any], class_names: Sequence[str]) -> None:
    source_classes = audit["class_names"]
    if source_classes[: len(class_names)] != list(class_names):
        raise ValueError("视觉类别必须与源数据集类别顺序的前缀一致，避免改变 YOLO 类别 ID")
    removed_classes = source_classes[len(class_names) :]
    retained_instances = {
        class_name: sum(audit["splits"][split]["by_class"][class_name] for split in SPLITS)
        for class_name in removed_classes
    }
    nonempty_removed = {name: count for name, count in retained_instances.items() if count > 0}
    if nonempty_removed:
        raise ValueError(f"不能静默移除仍有标注实例的类别：{nonempty_removed}")


def _write_data_yaml(output_root: Path, class_names: Sequence[str]) -> None:
    names = "\n".join(f"  {index}: {name}" for index, name in enumerate(class_names))
    output_root.joinpath("data.yaml").write_text(
        f"path: {output_root.as_posix()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n{names}\n",
        encoding="utf-8",
    )
