"""将 CDW COCO 分割数据合并到当前 YOLO 数据集。"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any


CLASS_NAMES = [
    "concrete",
    "brick",
    "tile",
    "wood",
    "gypsum_board",
    "foam",
    "metal",
    "soft_plastic",
    "hard_plastic",
    "paperboard",
    "glass",
]

# COCO category codes in this dataset:
# BIN=skip bin, CB=concrete, FD=fill dirt, WT=timber, HP=hard plastic,
# SP=soft plastic, ST=steel, FB=fabric, CP=cardboard, PB=plasterboard.
COCO_CATEGORY_TO_TARGET = {
    2: 0,  # CB -> concrete
    4: 3,  # WT/timber -> wood
    5: 8,  # HP -> hard_plastic
    6: 7,  # SP -> soft_plastic
    7: 6,  # ST/steel -> metal
    9: 9,  # CP/cardboard -> paperboard
    10: 4,  # PB/plasterboard -> gypsum_board
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge the 2026.6.15 COCO semantic-segmentation CDW dataset into the current 11-class YOLO dataset.")
    parser.add_argument("--coco-zip", type=Path, required=True)
    parser.add_argument("--target-root", type=Path, default=Path("datasets/waste12_yolo"))
    parser.add_argument("--prefix", default="cdw2026")
    parser.add_argument("--train-ratio", type=float, default=0.80)
    parser.add_argument("--val-ratio", type=float, default=0.10)
    parser.add_argument("--max-points", type=int, default=120)
    return parser


def _split_for_index(index: int, total: int, train_ratio: float, val_ratio: float) -> str:
    train_cutoff = int(total * train_ratio)
    val_cutoff = train_cutoff + int(total * val_ratio)
    if index < train_cutoff:
        return "train"
    if index < val_cutoff:
        return "val"
    return "test"


def _simplify_polygon(coords: list[float], max_points: int) -> list[float]:
    points = [(coords[i], coords[i + 1]) for i in range(0, len(coords) - 1, 2)]
    if len(points) <= max_points:
        return coords
    step = max(1, len(points) // max_points)
    simplified = points[::step][:max_points]
    if len(simplified) < 3:
        simplified = points[:3]
    flattened: list[float] = []
    for x, y in simplified:
        flattened.extend([x, y])
    return flattened


def _yolo_polygon_line(category_id: int, polygon: list[float], width: int, height: int, max_points: int) -> str | None:
    target_id = COCO_CATEGORY_TO_TARGET.get(category_id)
    if target_id is None or len(polygon) < 6:
        return None
    polygon = _simplify_polygon(polygon, max_points=max_points)
    normalized: list[str] = []
    for i in range(0, len(polygon) - 1, 2):
        x = min(max(float(polygon[i]) / width, 0.0), 1.0)
        y = min(max(float(polygon[i + 1]) / height, 0.0), 1.0)
        normalized.extend([f"{x:.8f}", f"{y:.8f}"])
    if len(normalized) < 6:
        return None
    return " ".join([str(target_id), *normalized])


class _DirectoryArchive:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _resolve(self, name: str) -> Path:
        normalized = name.replace("\\", "/")
        candidates = [
            self.root / Path(*normalized.split("/")),
            self.root / self.root.name / Path(*normalized.split("/")),
        ]
        parts = normalized.split("/")
        if parts and parts[0] == self.root.name:
            candidates.append(self.root / Path(*parts[1:]))
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Cannot find {name!r} under {self.root}")

    def open(self, name: str):
        return self._resolve(name).open("rb")

    def namelist(self) -> list[str]:
        return [str(path.relative_to(self.root)).replace("\\", "/") for path in self.root.rglob("*") if path.is_file()]

    def read(self, name: str) -> bytes:
        return self._resolve(name).read_bytes()

    def close(self) -> None:
        return None


def _load_coco_archive(coco_path: Path) -> tuple[Any, dict[str, Any], str]:
    archive: Any
    if coco_path.is_dir():
        archive = _DirectoryArchive(coco_path)
    else:
        archive = zipfile.ZipFile(coco_path)
    annotation_name = next(name for name in archive.namelist() if name.endswith("annotations.json"))
    data = json.loads(archive.read(annotation_name))
    return archive, data, annotation_name


def _count_current_dataset(target_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"classes": CLASS_NAMES, "splits": {}}
    for split in ("train", "val", "test"):
        images = list((target_root / "images" / split).glob("*"))
        labels = list((target_root / "labels" / split).glob("*.txt"))
        class_counts: dict[str, int] = {}
        objects = 0
        for label_path in labels:
            for line in label_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                class_id = line.split()[0]
                class_counts[class_id] = class_counts.get(class_id, 0) + 1
                objects += 1
        result["splits"][split] = {
            "images": len(images),
            "labels": len(labels),
            "objects": objects,
            "by_class_id": dict(sorted(class_counts.items(), key=lambda item: int(item[0]))),
            "by_class": {
                CLASS_NAMES[int(class_id)]: count
                for class_id, count in sorted(class_counts.items(), key=lambda item: int(item[0]))
                if int(class_id) < len(CLASS_NAMES)
            },
        }
    return result


def _write_data_yaml(target_root: Path) -> None:
    lines = [
        f"path: {target_root.resolve().as_posix()}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "names:",
    ]
    for idx, name in enumerate(CLASS_NAMES):
        lines.append(f"  {idx}: {name}")
    (target_root / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = _build_parser().parse_args()
    coco_zip = args.coco_zip.resolve()
    target_root = args.target_root.resolve()
    if not coco_zip.exists():
        raise SystemExit(f"COCO 数据不存在：{coco_zip}")
    if not target_root.exists():
        raise SystemExit(f"目标数据集不存在：{target_root}")

    archive, data, annotation_name = _load_coco_archive(coco_zip)
    images = sorted(data["images"], key=lambda item: item["id"])
    image_by_id = {image["id"]: image for image in images}
    annotations_by_image: dict[int, list[dict[str, Any]]] = {}
    for annotation in data["annotations"]:
        annotations_by_image.setdefault(annotation["image_id"], []).append(annotation)

    summary: dict[str, Any] = {
        "source_zip": str(coco_zip),
        "annotation_file": annotation_name,
        "target_root": str(target_root),
        "prefix": args.prefix,
        "category_mapping": {
            "CB": "concrete",
            "WT": "wood",
            "HP": "hard_plastic",
            "SP": "soft_plastic",
            "ST": "metal",
            "CP": "paperboard",
            "PB": "gypsum_board",
        },
        "ignored_categories": ["BIN", "FD", "FB", "_background_"],
        "splits": {
            "train": {"copied_images": 0, "copied_label_files": 0, "copied_objects": 0, "by_class": {}},
            "val": {"copied_images": 0, "copied_label_files": 0, "copied_objects": 0, "by_class": {}},
            "test": {"copied_images": 0, "copied_label_files": 0, "copied_objects": 0, "by_class": {}},
        },
        "skipped_images_without_mapped_objects": 0,
    }

    for idx, image in enumerate(images):
        width = int(image["width"])
        height = int(image["height"])
        lines: list[str] = []
        class_counts: dict[str, int] = {}
        for annotation in annotations_by_image.get(image["id"], []):
            category_id = int(annotation["category_id"])
            segmentation = annotation.get("segmentation") or []
            if not isinstance(segmentation, list):
                continue
            for polygon in segmentation:
                if not isinstance(polygon, list):
                    continue
                line = _yolo_polygon_line(category_id, polygon, width, height, max_points=args.max_points)
                if line is None:
                    continue
                target_name = CLASS_NAMES[int(line.split()[0])]
                class_counts[target_name] = class_counts.get(target_name, 0) + 1
                lines.append(line)

        if not lines:
            summary["skipped_images_without_mapped_objects"] += 1
            continue

        split = _split_for_index(idx, len(images), args.train_ratio, args.val_ratio)
        target_images = target_root / "images" / split
        target_labels = target_root / "labels" / split
        target_images.mkdir(parents=True, exist_ok=True)
        target_labels.mkdir(parents=True, exist_ok=True)

        source_image_name = str(image["file_name"]).replace("\\", "/")
        output_stem = f"{args.prefix}_{Path(source_image_name).stem}"
        output_image = target_images / f"{output_stem}.jpg"
        output_label = target_labels / f"{output_stem}.txt"

        with archive.open(source_image_name) as src, tempfile.NamedTemporaryFile(delete=False) as tmp:
            shutil.copyfileobj(src, tmp)
            tmp_path = Path(tmp.name)
        shutil.move(str(tmp_path), output_image)
        output_label.write_text("\n".join(lines) + "\n", encoding="utf-8")

        split_summary = summary["splits"][split]
        split_summary["copied_images"] += 1
        split_summary["copied_label_files"] += 1
        split_summary["copied_objects"] += len(lines)
        for class_name, count in class_counts.items():
            split_summary["by_class"][class_name] = split_summary["by_class"].get(class_name, 0) + count

    _write_data_yaml(target_root)
    summary["dataset_after_merge"] = _count_current_dataset(target_root)
    (target_root / "cdw2026_coco_merge_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (target_root / "dataset_summary_augmented.json").write_text(
        json.dumps(summary["dataset_after_merge"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    archive.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
