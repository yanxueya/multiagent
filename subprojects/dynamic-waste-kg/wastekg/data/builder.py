"""从原始数据构建 YOLO 格式数据集。"""

from __future__ import annotations

import argparse
import json
import shutil
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from wastekg.core.taxonomy import CLASS_TO_ID, KNOWN_VISUAL_CLASSES, canonicalize_category_name


def build_dataset(
    *,
    codd_root: Path,
    instance_seg_root: Path,
    output_root: Path,
    copy_images: bool = True,
) -> Dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    summary: Dict[str, Any] = {
        "classes": KNOWN_VISUAL_CLASSES,
        "splits": defaultdict(lambda: {"images": 0, "objects": 0, "by_class": Counter(), "skipped_objects": Counter()}),
        "sources": {"codd": str(codd_root), "instance_segmentation": str(instance_seg_root)},
    }

    for split in ("train", "val", "test"):
        (output_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_root / "labels" / split).mkdir(parents=True, exist_ok=True)

    _convert_codd(codd_root, output_root, summary, copy_images=copy_images)
    _convert_coco_instance_seg(instance_seg_root, output_root, summary, copy_images=copy_images)
    _write_data_yaml(output_root)
    serializable = _summary_to_plain_dict(summary)
    (output_root / "dataset_summary.json").write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")
    return serializable


def _convert_codd(root: Path, output_root: Path, summary: Dict[str, Any], *, copy_images: bool) -> None:
    split_map = {"training": "train", "validation": "val", "testing": "test"}
    for source_split, target_split in split_map.items():
        split_dir = root / source_split
        if not split_dir.exists():
            continue
        for xml_path in sorted(split_dir.glob("*.xml")):
            image_path = split_dir / f"{xml_path.stem}.jpg"
            if not image_path.exists():
                continue
            record = _parse_codd_xml(xml_path)
            if not record["labels"]:
                continue
            target_stem = f"codd_{xml_path.stem}"
            _write_yolo_label(output_root / "labels" / target_split / f"{target_stem}.txt", record["labels"])
            if copy_images:
                shutil.copy2(image_path, output_root / "images" / target_split / f"{target_stem}.jpg")
            _update_summary(summary, target_split, record["labels"], record["skipped"])


def _parse_codd_xml(xml_path: Path) -> Dict[str, Any]:
    root = ET.parse(xml_path).getroot()
    width = float(root.findtext("size/width", default="1"))
    height = float(root.findtext("size/height", default="1"))
    labels: List[List[float]] = []
    skipped: Counter[str] = Counter()

    for obj in root.findall("object"):
        raw_name = obj.findtext("name", default="").strip()
        class_name = canonicalize_category_name(raw_name)
        class_id = CLASS_TO_ID.get(class_name)
        if class_id is None:
            skipped[raw_name or "unknown"] += 1
            continue
        polygon = _read_codd_polygon(obj)
        if not polygon:
            polygon = _bbox_to_polygon(obj.find("bndbox"))
        normalized = _normalize_polygon(polygon, width, height)
        if len(normalized) < 6:
            skipped[raw_name or "unknown"] += 1
            continue
        labels.append([float(class_id), *normalized])
    return {"labels": labels, "skipped": skipped}


def _read_codd_polygon(obj: ET.Element) -> List[Tuple[float, float]]:
    polygon = obj.find("polygon")
    if polygon is None:
        return []
    points: List[Tuple[float, float]] = []
    index = 1
    while True:
        x = polygon.findtext(f"x{index}")
        y = polygon.findtext(f"y{index}")
        if x is None or y is None:
            break
        points.append((float(x), float(y)))
        index += 1
    return points


def _bbox_to_polygon(bndbox: Optional[ET.Element]) -> List[Tuple[float, float]]:
    if bndbox is None:
        return []
    xmin = float(bndbox.findtext("xmin", default="0"))
    ymin = float(bndbox.findtext("ymin", default="0"))
    xmax = float(bndbox.findtext("xmax", default="0"))
    ymax = float(bndbox.findtext("ymax", default="0"))
    return [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]


def _convert_coco_instance_seg(root: Path, output_root: Path, summary: Dict[str, Any], *, copy_images: bool) -> None:
    split_map = {"train": "train", "valid": "val", "test": "test"}
    for source_split, target_split in split_map.items():
        split_dir = root / source_split
        ann_path = split_dir / "_annotations.coco.json"
        if not ann_path.exists():
            continue
        data = json.loads(ann_path.read_text(encoding="utf-8"))
        categories = {item["id"]: canonicalize_category_name(item["name"]) for item in data.get("categories", [])}
        images = {item["id"]: item for item in data.get("images", [])}
        annotations_by_image: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for annotation in data.get("annotations", []):
            annotations_by_image[int(annotation["image_id"])].append(annotation)

        for image_id, image_info in images.items():
            image_path = split_dir / image_info["file_name"]
            if not image_path.exists():
                continue
            labels, skipped = _labels_from_coco_annotations(
                annotations_by_image.get(int(image_id), []),
                categories,
                float(image_info["width"]),
                float(image_info["height"]),
            )
            if not labels:
                continue
            target_stem = f"instseg_{Path(image_info['file_name']).stem}"
            _write_yolo_label(output_root / "labels" / target_split / f"{target_stem}.txt", labels)
            if copy_images:
                shutil.copy2(image_path, output_root / "images" / target_split / f"{target_stem}.jpg")
            _update_summary(summary, target_split, labels, skipped)


def _labels_from_coco_annotations(
    annotations: Iterable[Dict[str, Any]],
    categories: Dict[int, str],
    width: float,
    height: float,
) -> Tuple[List[List[float]], Counter[str]]:
    labels: List[List[float]] = []
    skipped: Counter[str] = Counter()
    for annotation in annotations:
        class_name = categories.get(int(annotation["category_id"]), "")
        class_id = CLASS_TO_ID.get(class_name)
        if class_id is None:
            skipped[class_name or str(annotation["category_id"])] += 1
            continue
        polygon = _first_valid_coco_polygon(annotation.get("segmentation"))
        if not polygon:
            polygon = _coco_bbox_to_polygon(annotation.get("bbox"))
        normalized = _normalize_polygon(polygon, width, height)
        if len(normalized) < 6:
            skipped[class_name] += 1
            continue
        labels.append([float(class_id), *normalized])
    return labels, skipped


def _first_valid_coco_polygon(segmentation: Any) -> List[Tuple[float, float]]:
    if not isinstance(segmentation, list):
        return []
    for segment in segmentation:
        if not isinstance(segment, list) or len(segment) < 6:
            continue
        return [(float(segment[index]), float(segment[index + 1])) for index in range(0, len(segment) - 1, 2)]
    return []


def _coco_bbox_to_polygon(bbox: Any) -> List[Tuple[float, float]]:
    if not isinstance(bbox, Sequence) or len(bbox) < 4:
        return []
    x, y, width, height = [float(value) for value in bbox[:4]]
    return [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]


def _normalize_polygon(points: List[Tuple[float, float]], width: float, height: float) -> List[float]:
    normalized: List[float] = []
    for x, y in points:
        normalized.append(_clamp(x / width))
        normalized.append(_clamp(y / height))
    return normalized


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def _write_yolo_label(path: Path, labels: List[List[float]]) -> None:
    lines = []
    for label in labels:
        class_id = int(label[0])
        coords = " ".join(f"{value:.6f}" for value in label[1:])
        lines.append(f"{class_id} {coords}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_summary(summary: Dict[str, Any], split: str, labels: List[List[float]], skipped: Counter[str]) -> None:
    split_summary = summary["splits"][split]
    split_summary["images"] += 1
    split_summary["objects"] += len(labels)
    for label in labels:
        split_summary["by_class"][KNOWN_VISUAL_CLASSES[int(label[0])]] += 1
    split_summary["skipped_objects"].update(skipped)


def _write_data_yaml(output_root: Path) -> None:
    names = "\n".join(f"  {index}: {name}" for index, name in enumerate(KNOWN_VISUAL_CLASSES))
    text = f"""path: {output_root.resolve().as_posix()}
train: images/train
val: images/val
test: images/test
names:
{names}
"""
    (output_root / "data.yaml").write_text(text, encoding="utf-8")


def _summary_to_plain_dict(summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "classes": list(summary["classes"]),
        "sources": dict(summary["sources"]),
        "splits": {
            split: {
                "images": value["images"],
                "objects": value["objects"],
                "by_class": dict(value["by_class"]),
                "skipped_objects": dict(value["skipped_objects"]),
            }
            for split, value in summary["splits"].items()
        },
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the research YOLO segmentation dataset for 11 known visual classes.")
    parser.add_argument("--codd-root", type=Path, required=True)
    parser.add_argument("--instance-seg-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--no-copy-images", action="store_true", help="Only generate labels and metadata.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    summary = build_dataset(
        codd_root=args.codd_root,
        instance_seg_root=args.instance_seg_root,
        output_root=args.output_root,
        copy_images=not args.no_copy_images,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
