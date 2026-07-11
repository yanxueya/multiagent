"""把 YOLO 分割标注转换为可审计的实例记录，不调用或训练模型。"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from PIL import Image


@dataclass(frozen=True, slots=True)
class YoloSegmentAnnotation:
    """一行 YOLO 分割标注及其可复现二维几何。"""

    line_number: int
    class_id: int
    class_name: str
    polygon_normalized: tuple[tuple[float, float], ...]
    bbox_xyxy: tuple[float, float, float, float]
    centroid_normalized: tuple[float, float]


def read_yolo_class_names(data_yaml: Path) -> list[str]:
    """读取 Roboflow/Ultralytics 常见的单行 names 列表。"""

    for raw_line in data_yaml.read_text(encoding="utf-8").splitlines():
        key, separator, value = raw_line.partition(":")
        if key.strip() != "names" or not separator:
            continue
        parsed = ast.literal_eval(value.strip())
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise ValueError("data.yaml names must be a list of strings")
        return list(parsed)
    raise ValueError(f"No names list found in {data_yaml}")


def read_yolo_segments(image_path: Path, label_path: Path, class_names: Sequence[str]) -> list[YoloSegmentAnnotation]:
    """读取与图像对应的 YOLO polygon，并把 bbox 转换为像素坐标。"""

    with Image.open(image_path) as image:
        width, height = image.size
    annotations: list[YoloSegmentAnnotation] = []
    for line_number, raw_line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        values = raw_line.split()
        class_id = int(values[0])
        coordinates = [float(value) for value in values[1:]]
        if class_id < 0 or class_id >= len(class_names):
            raise ValueError(f"Invalid class id {class_id} at {label_path}:{line_number}")
        if len(coordinates) < 6 or len(coordinates) % 2:
            raise ValueError(f"Invalid polygon at {label_path}:{line_number}")
        points = tuple(zip(coordinates[0::2], coordinates[1::2]))
        if any(x < 0.0 or x > 1.0 or y < 0.0 or y > 1.0 for x, y in points):
            raise ValueError(f"Out-of-range polygon at {label_path}:{line_number}")
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        annotations.append(
            YoloSegmentAnnotation(
                line_number=line_number,
                class_id=class_id,
                class_name=class_names[class_id],
                polygon_normalized=points,
                bbox_xyxy=(min(xs) * width, min(ys) * height, max(xs) * width, max(ys) * height),
                centroid_normalized=(sum(xs) / len(xs), sum(ys) / len(ys)),
            )
        )
    return annotations


def annotations_to_detection_records(
    annotations: Sequence[YoloSegmentAnnotation],
    *,
    image_path: Path,
    label_path: Path,
    track_ids: Mapping[int, str] | None = None,
    confidences: Mapping[int, float] | None = None,
    default_confidence: float = 0.90,
    accepted_annotations: bool = False,
) -> list[dict[str, object]]:
    """构造感知记录；置信度和人工验收假设必须由调用方显式提供。"""

    records: list[dict[str, object]] = []
    for annotation in annotations:
        confidence = float((confidences or {}).get(annotation.line_number, default_confidence))
        metadata: dict[str, object] = {
            "annotation_source": f"{label_path}#{annotation.line_number}",
            "mask_polygon_normalized": [list(point) for point in annotation.polygon_normalized],
        }
        if accepted_annotations:
            metadata.update({"recognition_status": "accepted", "review_decision": "not_checked"})
        records.append(
            {
                "temp_id": (track_ids or {}).get(annotation.line_number, f"ann_{annotation.line_number:02d}"),
                "yolo_class_name": annotation.class_name,
                "yolo_confidence": confidence,
                "bbox_2d": list(annotation.bbox_xyxy),
                "mask_ref": f"{label_path}#{annotation.line_number}",
                "crop_ref": str(image_path),
                "metadata": metadata,
            }
        )
    return records
