"""按场景候选组重新划分数据集。"""

from __future__ import annotations

import json
import os
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from wastekg.data.audit import SPLITS, audit_dataset


def build_grouped_dataset(
    source_root: Path,
    output_root: Path,
    *,
    seed: int = 0,
    split_ratios: Mapping[str, float] | None = None,
) -> Dict[str, Any]:
    """复制到新目录并保证相同感知哈希的图像不会被分到不同 split。"""

    source_root = source_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise ValueError(f"目标目录必须为空，避免覆盖已冻结的数据集：{output_root}")

    ratios = dict(split_ratios or {"train": 0.70, "val": 0.15, "test": 0.15})
    _validate_ratios(ratios)
    audit = audit_dataset(source_root)
    groups = _visual_groups(audit["manifest"])
    assignments = _assign_groups(groups, ratios=ratios, seed=seed)
    duplicate_filenames = _duplicate_filenames(audit["manifest"])
    for assignment in assignments:
        assignment["target_image"] = _target_image_name(assignment["source_image"], duplicate_filenames)

    for split in SPLITS:
        (output_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_root / "labels" / split).mkdir(parents=True, exist_ok=True)

    materialization = Counter()
    for assignment in assignments:
        source_image = source_root / assignment["source_image"]
        source_label = source_root / assignment["source_label"]
        destination_image = output_root / "images" / assignment["assigned_split"] / assignment["target_image"]
        destination_label = output_root / "labels" / assignment["assigned_split"] / f"{destination_image.stem}{source_label.suffix}"
        if destination_image.exists() or destination_label.exists():
            raise ValueError(f"重划分后出现文件名冲突：{destination_image.name}")
        materialization[_link_or_copy(source_image, destination_image)] += 1
        materialization[_link_or_copy(source_label, destination_label)] += 1

    _write_data_yaml(output_root, audit["class_names"])
    split_image_counts = Counter(item["assigned_split"] for item in assignments)
    result = {
        "source_root": str(source_root),
        "output_root": str(output_root),
        "seed": seed,
        "split_ratios": ratios,
        "group_count": len(groups),
        "split_image_counts": {split: split_image_counts[split] for split in SPLITS},
        "materialization": dict(materialization),
        "assignments": assignments,
    }
    (output_root / "grouped_split_manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _visual_groups(manifest: Sequence[Mapping[str, str]]) -> List[Dict[str, Any]]:
    by_hash: Dict[str, List[Mapping[str, str]]] = defaultdict(list)
    for record in manifest:
        by_hash[record["perceptual_hash"]].append(record)

    groups: List[Dict[str, Any]] = []
    for perceptual_hash, records in sorted(by_hash.items()):
        if perceptual_hash and len(records) > 1:
            groups.append({"group_id": f"visual_{perceptual_hash}", "records": list(records)})
        else:
            for record in records:
                groups.append({"group_id": f"singleton_{record['sha256']}", "records": [record]})
    return groups


def _assign_groups(
    groups: Sequence[Mapping[str, Any]],
    *,
    ratios: Mapping[str, float],
    seed: int,
) -> List[Dict[str, str]]:
    del seed  # 分配由稳定 group_id 排序决定，避免随机运行导致冻结划分变化。
    total_images = sum(len(group["records"]) for group in groups)
    target_images = {split: total_images * ratios[split] for split in SPLITS}
    assigned_images = Counter()
    assignments: List[Dict[str, str]] = []

    for group in sorted(groups, key=lambda item: (-len(item["records"]), item["group_id"])):
        group_size = len(group["records"])
        selected_split = min(
            SPLITS,
            key=lambda split: (
                (assigned_images[split] + group_size) / target_images[split] if target_images[split] else float("inf"),
                assigned_images[split],
                split,
            ),
        )
        assigned_images[selected_split] += group_size
        for record in group["records"]:
            assignments.append(
                {
                    "group_id": group["group_id"],
                    "source_image": record["image"],
                    "source_label": record["label"],
                    "assigned_split": selected_split,
                }
            )
    return sorted(assignments, key=lambda item: item["source_image"])


def _duplicate_filenames(manifest: Sequence[Mapping[str, str]]) -> set[str]:
    counts = Counter(Path(record["image"]).name for record in manifest)
    return {name for name, count in counts.items() if count > 1}


def _target_image_name(source_image: str, duplicate_filenames: set[str]) -> str:
    path = Path(source_image)
    if path.name not in duplicate_filenames:
        return path.name
    source_split = path.parts[1]
    return f"{path.stem}__src_{source_split}{path.suffix}"


def _validate_ratios(ratios: Mapping[str, float]) -> None:
    if set(ratios) != set(SPLITS):
        raise ValueError("split_ratios 必须恰好包含 train、val、test")
    if any(value <= 0 for value in ratios.values()):
        raise ValueError("所有 split 比例必须大于 0")
    if abs(sum(ratios.values()) - 1.0) > 1e-9:
        raise ValueError("split_ratios 之和必须为 1")


def _write_data_yaml(output_root: Path, class_names: Sequence[str]) -> None:
    names = "\n".join(f"  {index}: {name}" for index, name in enumerate(class_names))
    output_root.joinpath("data.yaml").write_text(
        f"path: {output_root.as_posix()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n{names}\n",
        encoding="utf-8",
    )


def _link_or_copy(source: Path, destination: Path) -> str:
    """同一 NTFS 卷优先硬链接，跨卷或权限受限时保守回退为复制。"""

    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"
