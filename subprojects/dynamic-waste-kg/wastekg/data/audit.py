"""审计 YOLO 数据集结构、标注和泄漏风险。"""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import platform
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import numpy as np
from PIL import Image


SPLITS = ("train", "val", "test")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def audit_dataset(dataset_root: Path) -> Dict[str, Any]:
    """审计一个 YOLO 分割数据集，但绝不修改图像、标签或数据划分。"""

    dataset_root = dataset_root.resolve()
    config = _read_data_yaml(dataset_root / "data.yaml")
    class_names = config["class_names"]
    split_summaries: Dict[str, Dict[str, Any]] = {}
    manifest: List[Dict[str, Any]] = []
    issues: Dict[str, Any] = {
        "missing_label_images": [],
        "orphan_label_files": [],
        "empty_label_files": [],
        "malformed_label_lines": 0,
        "invalid_class_ids": 0,
        "out_of_range_coordinates": 0,
        "degenerate_polygons": 0,
        "duplicate_annotation_lines": 0,
        "ultralytics_duplicate_box_labels": 0,
        "unreadable_images": [],
    }

    for split in SPLITS:
        image_dir = _resolve_split_dir(dataset_root, config["split_paths"].get(split, f"images/{split}"))
        label_dir = dataset_root / "labels" / split
        image_paths = _image_paths(image_dir)
        label_paths = {path.stem: path for path in label_dir.glob("*.txt")} if label_dir.exists() else {}
        by_class: Counter[str] = Counter()
        instances = 0
        raw_valid_instances = 0
        matched_labels = 0

        for image_path in image_paths:
            # 审计流程只读数据集：逐张图像匹配同名标签，并记录可复现的 manifest。
            relative_image = image_path.relative_to(dataset_root).as_posix()
            label_path = label_paths.pop(image_path.stem, None)
            if label_path is None:
                issues["missing_label_images"].append(f"{split}/{image_path.name}")
            else:
                matched_labels += 1
                label_result = _audit_label_file(label_path, len(class_names))
                if label_result["empty"]:
                    issues["empty_label_files"].append(f"{split}/{label_path.name}")
                for issue_name, count in label_result["issues"].items():
                    issues[issue_name] += count
                for class_id in label_result["class_ids"]:
                    by_class[class_names[class_id]] += 1
                raw_valid_instances += label_result["raw_valid_instances"]
                instances += len(label_result["class_ids"])

            image_hash = _sha256(image_path)
            perceptual_hash, readable = _perceptual_hash(image_path)
            if not readable:
                issues["unreadable_images"].append(relative_image)
            manifest.append(
                {
                    "split": split,
                    "image": relative_image,
                    "label": label_path.relative_to(dataset_root).as_posix() if label_path else "",
                    "sha256": image_hash,
                    "perceptual_hash": perceptual_hash,
                }
            )

        issues["orphan_label_files"].extend(f"{split}/{path.name}" for path in label_paths.values())
        split_summaries[split] = {
            "images": len(image_paths),
            "labels": matched_labels,
            "raw_valid_instances": raw_valid_instances,
            "instances": instances,
            "by_class": {name: by_class[name] for name in class_names},
        }

    return {
        "dataset_root": str(dataset_root),
        "data_yaml_sha256": _sha256(dataset_root / "data.yaml"),
        "class_names": class_names,
        "splits": split_summaries,
        "annotation_issues": issues,
        "duplicates": {
            "exact_cross_split": _cross_split_duplicate_groups(manifest, "sha256"),
            "perceptual_hash_cross_split": _cross_split_duplicate_groups(manifest, "perceptual_hash"),
        },
        "manifest": manifest,
    }


def _read_data_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"找不到数据集配置文件：{path}")

    split_paths: Dict[str, str] = {}
    class_mapping: Dict[int, str] = {}
    in_names = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        split_match = re.match(r"^(train|val|test):\s*(.+?)\s*$", stripped)
        if split_match:
            split_paths[split_match.group(1)] = split_match.group(2).strip("'\"")
            in_names = False
            continue
        if stripped == "names:":
            in_names = True
            continue
        if in_names:
            name_match = re.match(r"^(\d+):\s*(.+?)\s*$", stripped)
            if name_match:
                class_mapping[int(name_match.group(1))] = name_match.group(2).strip("'\"")
                continue
            in_names = False

    if not class_mapping:
        raise ValueError(f"data.yaml 缺少可解析的 names 映射：{path}")
    max_index = max(class_mapping)
    class_names = []
    for index in range(max_index + 1):
        if index not in class_mapping:
            raise ValueError(f"data.yaml 的类别编号不连续，缺少 {index}")
        class_names.append(class_mapping[index])
    return {"split_paths": split_paths, "class_names": class_names}


def _resolve_split_dir(dataset_root: Path, configured_path: str) -> Path:
    candidate = Path(configured_path)
    return candidate if candidate.is_absolute() else dataset_root / candidate


def _image_paths(image_dir: Path) -> List[Path]:
    if not image_dir.exists():
        return []
    return sorted(path for path in image_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)


def _audit_label_file(label_path: Path, class_count: int) -> Dict[str, Any]:
    text = label_path.read_text(encoding="utf-8").strip()
    if not text:
        return {"empty": True, "class_ids": [], "raw_valid_instances": 0, "issues": Counter()}

    valid_annotations: List[tuple[int, List[float]]] = []
    issues: Counter[str] = Counter()
    seen_annotations: set[tuple[int, tuple[float, ...]]] = set()
    for raw_line in text.splitlines():
        tokens = raw_line.split()
        if len(tokens) < 7:
            issues["malformed_label_lines"] += 1
            continue
        try:
            class_id = int(tokens[0])
            coordinates = [float(value) for value in tokens[1:]]
        except ValueError:
            issues["malformed_label_lines"] += 1
            continue
        if class_id < 0 or class_id >= class_count:
            issues["invalid_class_ids"] += 1
            continue
        if len(coordinates) % 2:
            issues["malformed_label_lines"] += 1
            continue
        if any(value < 0.0 or value > 1.0 for value in coordinates):
            issues["out_of_range_coordinates"] += 1
            continue
        if _polygon_area(coordinates) <= 1e-8:
            issues["degenerate_polygons"] += 1
            continue
        annotation_key = (class_id, tuple(coordinates))
        if annotation_key in seen_annotations:
            issues["duplicate_annotation_lines"] += 1
        seen_annotations.add(annotation_key)
        valid_annotations.append((class_id, coordinates))

    kept_indices = _ultralytics_unique_annotation_indices(valid_annotations)
    # 这里保留 raw_valid_instances，便于区分原始有效标注和 Ultralytics 去重后的训练口径。
    issues["ultralytics_duplicate_box_labels"] += len(valid_annotations) - len(kept_indices)
    class_ids = [valid_annotations[index][0] for index in kept_indices]
    return {
        "empty": False,
        "class_ids": class_ids,
        "raw_valid_instances": len(valid_annotations),
        "issues": issues,
    }


def _ultralytics_unique_annotation_indices(annotations: Sequence[tuple[int, Sequence[float]]]) -> List[int]:
    """复现 Ultralytics 对分割标签的 class + xywh 去重，保证实例数口径一致。"""

    if not annotations:
        return []
    classes = np.array([class_id for class_id, _ in annotations], dtype=np.float32)
    segments = [np.array(coordinates, dtype=np.float32).reshape(-1, 2) for _, coordinates in annotations]
    boxes = np.array([[segment[:, 0].min(), segment[:, 1].min(), segment[:, 0].max(), segment[:, 1].max()] for segment in segments])
    xywh = np.empty_like(boxes)
    xywh[:, 0] = (boxes[:, 0] + boxes[:, 2]) / 2
    xywh[:, 1] = (boxes[:, 1] + boxes[:, 3]) / 2
    xywh[:, 2] = boxes[:, 2] - boxes[:, 0]
    xywh[:, 3] = boxes[:, 3] - boxes[:, 1]
    labels = np.concatenate((classes.reshape(-1, 1), xywh), axis=1)
    _, indices = np.unique(labels, axis=0, return_index=True)
    return [int(index) for index in indices]


def _polygon_area(coordinates: Sequence[float]) -> float:
    points = list(zip(coordinates[::2], coordinates[1::2]))
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]))) / 2.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _perceptual_hash(path: Path) -> tuple[str, bool]:
    try:
        with Image.open(path) as image:
            # 以 8x8 灰度缩略图表示视觉内容，作为跨 split 候选重复的轻量筛查。
            pixels = list(image.convert("L").resize((8, 8)).get_flattened_data())
    except (OSError, ValueError):
        return "", False
    average = sum(pixels) / len(pixels)
    return "".join("1" if value >= average else "0" for value in pixels), True


def _cross_split_duplicate_groups(manifest: Iterable[Mapping[str, str]], key: str) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Mapping[str, str]]] = defaultdict(list)
    for record in manifest:
        value = record[key]
        if value:
            groups[value].append(record)

    duplicates = []
    for value, records in groups.items():
        # 只有同一哈希出现在多个 split 时才算泄漏候选，单个 split 内重复不在此处处理。
        splits = {record["split"] for record in records}
        if len(splits) > 1:
            duplicates.append(
                {
                    key: value,
                    "splits": sorted(splits),
                    "images": [record["image"] for record in records],
                }
            )
    return sorted(duplicates, key=lambda item: (item["splits"], item[key]))


def write_audit_artifacts(
    audit: Mapping[str, Any],
    output_dir: Path,
    *,
    weight_paths: Sequence[Path] = (),
    training_command: str | None = None,
) -> Dict[str, Path]:
    """将审计结果输出为论文可引用的 E0 文件集合。"""

    output_dir.mkdir(parents=True, exist_ok=True)
    # 输出拆成 CSV/Markdown/JSON，方便论文引用、人工检查和后续自动化复核。
    class_distribution = output_dir / "class_distribution.csv"
    split_manifest = output_dir / "split_manifest.csv"
    leakage_report = output_dir / "split_leakage_report.md"
    annotation_report = output_dir / "annotation_validation_report.md"
    environment_report = output_dir / "model_environment.json"

    with class_distribution.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["split", "class_name", "instances"])
        writer.writeheader()
        for split in SPLITS:
            summary = audit["splits"][split]
            for class_name in audit["class_names"]:
                writer.writerow({"split": split, "class_name": class_name, "instances": summary["by_class"][class_name]})

    with split_manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["split", "image", "label", "sha256", "perceptual_hash"])
        writer.writeheader()
        writer.writerows(audit["manifest"])

    leakage_report.write_text(_leakage_markdown(audit), encoding="utf-8")
    annotation_report.write_text(_annotation_markdown(audit), encoding="utf-8")
    environment = _runtime_environment(audit, weight_paths=weight_paths, training_command=training_command)
    environment_report.write_text(json.dumps(environment, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "class_distribution": class_distribution,
        "split_manifest": split_manifest,
        "leakage_report": leakage_report,
        "annotation_report": annotation_report,
        "environment_report": environment_report,
    }


def _leakage_markdown(audit: Mapping[str, Any]) -> str:
    duplicates = audit["duplicates"]
    exact = duplicates["exact_cross_split"]
    perceptual = duplicates["perceptual_hash_cross_split"]
    lines = [
        "# Train/Val/Test 数据泄漏审计",
        "",
        f"- 数据集根目录：`{audit['dataset_root']}`",
        f"- data.yaml SHA-256：`{audit['data_yaml_sha256']}`",
        f"- 跨 split 完全重复图像组：{len(exact)}",
        f"- 跨 split 相同感知哈希候选组：{len(perceptual)}",
        "",
        "## 完全重复图像",
        "",
    ]
    lines.extend(_duplicate_lines(exact, "sha256"))
    lines.extend(["", "## 感知哈希候选重复", ""])
    lines.extend(_duplicate_lines(perceptual, "perceptual_hash"))
    lines.extend(["", "感知哈希相同仅表示需要人工核查的候选，不自动等同于数据泄漏。"])
    return "\n".join(lines) + "\n"


def _duplicate_lines(groups: Sequence[Mapping[str, Any]], key: str) -> List[str]:
    if not groups:
        return ["未发现。"]
    lines = []
    for group in groups:
        lines.append(f"- `{key}={group[key]}`；splits={', '.join(group['splits'])}；images={', '.join(group['images'])}")
    return lines


def _annotation_markdown(audit: Mapping[str, Any]) -> str:
    issues = audit["annotation_issues"]
    lines = ["# 标注完整性审计", ""]
    for split in SPLITS:
        summary = audit["splits"][split]
        lines.append(
            f"- `{split}`：images={summary['images']}，matched_labels={summary['labels']}，"
            f"raw_valid_instances={summary['raw_valid_instances']}，"
            f"ultralytics_effective_instances={summary['instances']}"
        )
    lines.extend(["", "## 问题汇总", ""])
    for name, value in issues.items():
        count = len(value) if isinstance(value, list) else value
        lines.append(f"- `{name}`：{count}")
    for name in ("missing_label_images", "orphan_label_files", "empty_label_files", "unreadable_images"):
        values = issues[name]
        if values:
            lines.extend(["", f"## {name}", "", *[f"- `{value}`" for value in values]])
    return "\n".join(lines) + "\n"


def _runtime_environment(
    audit: Mapping[str, Any],
    *,
    weight_paths: Sequence[Path],
    training_command: str | None,
) -> Dict[str, Any]:
    packages = {name: _package_version(name) for name in ("torch", "torchvision", "ultralytics", "pillow")}
    return {
        "dataset_root": audit["dataset_root"],
        "data_yaml_sha256": audit["data_yaml_sha256"],
        "class_names": audit["class_names"],
        "python_version": sys.version,
        "platform": platform.platform(),
        "packages": packages,
        "training_command": training_command,
        "weights": [_weight_record(path) for path in weight_paths],
    }


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _weight_record(path: Path) -> Dict[str, Any]:
    resolved = path.resolve()
    return {
        "path": str(resolved),
        "exists": resolved.exists(),
        "sha256": _sha256(resolved) if resolved.is_file() else None,
    }
