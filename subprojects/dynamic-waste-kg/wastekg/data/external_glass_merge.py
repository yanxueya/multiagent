"""将外部玻璃分割数据合并到当前 YOLO 数据集。"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


DEFAULT_CLASS_NAMES = [
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Merge an external Roboflow YOLO segmentation glass dataset into the 11-class dataset stored in historical directory waste12_yolo."
    )
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--target-root", type=Path, default=Path("datasets/waste12_yolo"))
    parser.add_argument("--source-glass-class", type=int, default=0)
    parser.add_argument("--target-glass-class", type=int, default=10)
    parser.add_argument("--prefix", default="glassdebris_v5")
    parser.add_argument("--keep-background", action="store_true")
    return parser


def _iter_label_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _map_glass_lines(lines: list[str], source_class: int, target_class: int) -> list[str]:
    mapped: list[str] = []
    for line in lines:
        parts = line.split()
        if not parts:
            continue
        try:
            class_id = int(float(parts[0]))
        except ValueError:
            continue
        if class_id != source_class:
            continue
        if len(parts) <= 5:
            # This project trains segmentation. Skip bbox-only records to avoid mixing tasks.
            continue
        mapped.append(" ".join([str(target_class), *parts[1:]]))
    return mapped


def _copy_split(
    source_root: Path,
    target_root: Path,
    source_split: str,
    target_split: str,
    source_class: int,
    target_class: int,
    prefix: str,
    keep_background: bool,
) -> dict[str, int]:
    source_images = source_root / source_split / "images"
    source_labels = source_root / source_split / "labels"
    target_images = target_root / "images" / target_split
    target_labels = target_root / "labels" / target_split
    target_images.mkdir(parents=True, exist_ok=True)
    target_labels.mkdir(parents=True, exist_ok=True)

    copied_images = 0
    copied_labels = 0
    copied_objects = 0
    skipped_no_glass = 0
    skipped_missing_label = 0

    if not source_images.exists():
        return {
            "copied_images": 0,
            "copied_label_files": 0,
            "copied_glass_objects": 0,
            "skipped_no_glass": 0,
            "skipped_missing_label": 0,
        }

    for image_path in sorted(source_images.glob("*")):
        if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
            continue
        label_path = source_labels / f"{image_path.stem}.txt"
        if not label_path.exists():
            skipped_missing_label += 1
            continue
        mapped_lines = _map_glass_lines(_iter_label_lines(label_path), source_class, target_class)
        if not mapped_lines and not keep_background:
            skipped_no_glass += 1
            continue

        output_stem = f"{prefix}_{source_split}_{image_path.stem}"
        output_image = target_images / f"{output_stem}{image_path.suffix.lower()}"
        output_label = target_labels / f"{output_stem}.txt"
        shutil.copy2(image_path, output_image)
        output_label.write_text("\n".join(mapped_lines) + ("\n" if mapped_lines else ""), encoding="utf-8")

        copied_images += 1
        copied_labels += 1
        copied_objects += len(mapped_lines)

    return {
        "copied_images": copied_images,
        "copied_label_files": copied_labels,
        "copied_glass_objects": copied_objects,
        "skipped_no_glass": skipped_no_glass,
        "skipped_missing_label": skipped_missing_label,
    }


def _count_current_dataset(target_root: Path) -> dict[str, object]:
    result: dict[str, object] = {"classes": DEFAULT_CLASS_NAMES, "splits": {}}
    for split in ("train", "val", "test"):
        images = list((target_root / "images" / split).glob("*"))
        labels = list((target_root / "labels" / split).glob("*.txt"))
        class_counts: dict[str, int] = {}
        objects = 0
        for label in labels:
            for line in _iter_label_lines(label):
                parts = line.split()
                if not parts:
                    continue
                class_id = parts[0]
                class_counts[class_id] = class_counts.get(class_id, 0) + 1
                objects += 1
        by_class_name = {
            DEFAULT_CLASS_NAMES[int(class_id)]: count
            for class_id, count in sorted(class_counts.items(), key=lambda item: int(item[0]))
            if int(class_id) < len(DEFAULT_CLASS_NAMES)
        }
        result["splits"][split] = {
            "images": len(images),
            "labels": len(labels),
            "objects": objects,
            "by_class_id": dict(sorted(class_counts.items(), key=lambda item: int(item[0]))),
            "by_class": by_class_name,
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
    for idx, name in enumerate(DEFAULT_CLASS_NAMES):
        lines.append(f"  {idx}: {name}")
    (target_root / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = _build_parser().parse_args()
    source_root = args.source_root.resolve()
    target_root = args.target_root.resolve()
    if not source_root.exists():
        raise SystemExit(f"外部数据集不存在：{source_root}")
    if not target_root.exists():
        raise SystemExit(f"目标数据集不存在：{target_root}")

    split_map = {"train": "train", "valid": "val", "test": "test"}
    merge_summary: dict[str, object] = {
        "source_root": str(source_root),
        "target_root": str(target_root),
        "source_glass_class": args.source_glass_class,
        "target_glass_class": args.target_glass_class,
        "prefix": args.prefix,
        "keep_background": args.keep_background,
        "splits": {},
    }
    for source_split, target_split in split_map.items():
        merge_summary["splits"][target_split] = _copy_split(
            source_root=source_root,
            target_root=target_root,
            source_split=source_split,
            target_split=target_split,
            source_class=args.source_glass_class,
            target_class=args.target_glass_class,
            prefix=args.prefix,
            keep_background=args.keep_background,
        )

    _write_data_yaml(target_root)
    merge_summary["dataset_after_merge"] = _count_current_dataset(target_root)
    output_path = target_root / "glass_merge_summary.json"
    output_path.write_text(json.dumps(merge_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    augmented_summary_path = target_root / "dataset_summary_augmented.json"
    augmented_summary_path.write_text(
        json.dumps(merge_summary["dataset_after_merge"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(merge_summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
