"""为受约束视觉复核构造可追溯的图像证据。"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from PIL import Image, ImageDraw


@dataclass(frozen=True, slots=True)
class VisualReviewEvidence:
    instance_id: str
    original_image: Path
    crop_image: Path
    mask_overlay_image: Path
    sha256: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "instance_id": self.instance_id,
            "original_image": str(self.original_image),
            "crop_image": str(self.crop_image),
            "mask_overlay_image": str(self.mask_overlay_image),
            "sha256": dict(self.sha256),
        }


def attach_visual_evidence_to_records(
    records: Sequence[Mapping[str, Any]], *, image_path: Path, output_dir: Path
) -> list[dict[str, Any]]:
    """为每条 YOLO 记录创建独立证据，并返回不修改输入对象的新记录列表。"""

    enriched_records: list[dict[str, Any]] = []
    for index, raw_record in enumerate(records, start=1):
        record = dict(raw_record)
        instance_id = str(record.get("temp_id") or f"det_{index:03d}")
        bbox = record.get("bbox_xyxy")
        if not isinstance(bbox, Sequence) or len(bbox) < 4:
            raise ValueError(f"检测 {instance_id} 缺少 bbox_xyxy，无法生成视觉复核证据。")
        evidence = create_visual_review_evidence(
            image_path=image_path,
            bbox_xyxy=bbox,
            mask_polygon=record.get("mask_polygon") or [],
            output_dir=output_dir,
            instance_id=instance_id,
        )
        evidence_dict = evidence.to_dict()
        metadata = dict(record.get("metadata", {}))
        metadata["visual_evidence"] = evidence_dict
        record["metadata"] = metadata
        record["visual_evidence"] = evidence_dict
        enriched_records.append(record)
    return enriched_records


def create_visual_review_evidence(
    *,
    image_path: Path,
    bbox_xyxy: Sequence[float],
    mask_polygon: Sequence[Sequence[float]],
    output_dir: Path,
    instance_id: str,
    padding_ratio: float = 0.15,
) -> VisualReviewEvidence:
    """保存原图、扩边裁剪图和 mask-overlay 图，并返回路径与哈希。"""

    if len(bbox_xyxy) < 4:
        raise ValueError("bbox_xyxy 至少需要四个值。")
    if not 0.0 <= padding_ratio <= 1.0:
        raise ValueError("padding_ratio 必须位于 0 到 1 之间。")

    image_path = image_path.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = image_path.suffix.lower() if image_path.suffix.lower() in {".jpg", ".jpeg", ".png"} else ".jpg"
    original_path = output_dir / f"{instance_id}__original{suffix}"
    crop_path = output_dir / f"{instance_id}__crop.jpg"
    overlay_path = output_dir / f"{instance_id}__mask_overlay.jpg"
    shutil.copy2(image_path, original_path)

    with Image.open(image_path) as source:
        image = source.convert("RGB")
    crop_box = _padded_crop_box(bbox_xyxy, image.size, padding_ratio)
    crop = image.crop(crop_box)
    crop.save(crop_path, quality=95)

    overlay = Image.new("RGBA", crop.size, (0, 0, 0, 0))
    points = [(float(point[0]) - crop_box[0], float(point[1]) - crop_box[1]) for point in mask_polygon if len(point) >= 2]
    if len(points) >= 3:
        draw = ImageDraw.Draw(overlay)
        draw.polygon(points, fill=(239, 95, 41, 105), outline=(239, 95, 41, 255), width=3)
    Image.alpha_composite(crop.convert("RGBA"), overlay).convert("RGB").save(overlay_path, quality=95)

    hashes = {
        "original_image": _sha256(original_path),
        "crop_image": _sha256(crop_path),
        "mask_overlay_image": _sha256(overlay_path),
    }
    return VisualReviewEvidence(
        instance_id=instance_id,
        original_image=original_path,
        crop_image=crop_path,
        mask_overlay_image=overlay_path,
        sha256=hashes,
    )


def _padded_crop_box(bbox_xyxy: Sequence[float], image_size: tuple[int, int], padding_ratio: float) -> tuple[int, int, int, int]:
    width, height = image_size
    x1, y1, x2, y2 = (float(value) for value in bbox_xyxy[:4])
    left, right = sorted((x1, x2))
    top, bottom = sorted((y1, y2))
    padding_x = (right - left) * padding_ratio
    padding_y = (bottom - top) * padding_ratio
    return (
        max(0, int(left - padding_x)),
        max(0, int(top - padding_y)),
        min(width, int(right + padding_x)),
        min(height, int(bottom + padding_y)),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
