from __future__ import annotations

from typing import Any, Dict, List, Optional


def _to_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)


def _mask_to_points(mask: Any) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for point in _to_list(mask):
        if len(point) >= 2:
            points.append((float(point[0]), float(point[1])))
    return points


def records_from_yolo_result(result: Any, *, max_detections: Optional[int] = None) -> List[Dict[str, Any]]:
    """把 Ultralytics 单张图片预测结果转换为本项目图谱可接收的 yolo_records。"""

    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return []

    class_ids = _to_list(getattr(boxes, "cls", []))
    confidences = _to_list(getattr(boxes, "conf", []))
    xyxy_values = _to_list(getattr(boxes, "xyxy", []))
    mask_values = _to_list(getattr(getattr(result, "masks", None), "xy", []))
    names = getattr(result, "names", {})

    records: List[Dict[str, Any]] = []
    ordered_indices = list(range(len(class_ids)))
    ordered_indices.sort(key=lambda item: float(confidences[item]), reverse=True)
    if max_detections is not None:
        ordered_indices = ordered_indices[:max(0, int(max_detections))]

    for output_index, index in enumerate(ordered_indices):
        class_id = class_ids[index]
        bbox = [float(value) for value in xyxy_values[index]]
        x1, y1, x2, y2 = bbox[:4]
        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0
        class_name = names.get(int(class_id), str(int(class_id))) if isinstance(names, dict) else str(int(class_id))
        mask_polygon = _mask_to_points(mask_values[index]) if index < len(mask_values) else []
        records.append(
            {
                "temp_id": f"det_{output_index + 1:03d}",
                "yolo_class_name": class_name,
                "yolo_confidence": float(confidences[index]),
                "center_xyz": [center_x, center_y, 0.0],
                "bbox_xyxy": bbox,
                "mask_polygon": mask_polygon,
                "boundary_points": mask_polygon,
                "visible_area_ratio": 1.0,
                "occlusion_state": "unknown",
                "metadata": {
                    "bbox_xyxy": bbox,
                    "pixel_center_xy": [center_x, center_y],
                    "note": "single RGB image demo; z=0 because no RealSense depth is available",
                },
            }
        )
    return records
