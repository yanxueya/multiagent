"""基于 RGB-D 几何信息补全目标三维位置。"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor
from statistics import median
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

Vector3 = Tuple[float, float, float]
PixelPoint = Tuple[float, float]


@dataclass(frozen=True, slots=True)
class CameraIntrinsics:
    """RealSense color/aligned-depth camera intrinsics."""

    width: int
    height: int
    fx: float
    fy: float
    ppx: float
    ppy: float
    depth_scale: float = 0.001
    frame_id: str = "camera_color_optical_frame"

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CameraIntrinsics":
        return cls(
            width=int(value["width"]),
            height=int(value["height"]),
            fx=float(value["fx"]),
            fy=float(value["fy"]),
            ppx=float(value["ppx"]),
            ppy=float(value["ppy"]),
            depth_scale=float(value.get("depth_scale", 0.001)),
            frame_id=str(value.get("frame_id", "camera_color_optical_frame")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "fx": self.fx,
            "fy": self.fy,
            "ppx": self.ppx,
            "ppy": self.ppy,
            "depth_scale": self.depth_scale,
            "frame_id": self.frame_id,
        }


def deproject_pixel_to_point(pixel_x: float, pixel_y: float, depth_m: float, intrinsics: CameraIntrinsics) -> Vector3:
    """Convert one RGB/depth-aligned pixel into camera-frame XYZ meters."""

    x = (pixel_x - intrinsics.ppx) / intrinsics.fx * depth_m
    y = (pixel_y - intrinsics.ppy) / intrinsics.fy * depth_m
    return (x, y, depth_m)


def enrich_records_with_rgbd(
    records: Iterable[Mapping[str, Any]],
    depth_image: Sequence[Sequence[Any]],
    intrinsics: CameraIntrinsics,
    *,
    min_depth_m: float = 0.10,
    max_depth_m: float = 3.00,
) -> List[Dict[str, Any]]:
    return [
        enrich_record_with_rgbd(record, depth_image, intrinsics, min_depth_m=min_depth_m, max_depth_m=max_depth_m)
        for record in records
    ]


def enrich_record_with_rgbd(
    record: Mapping[str, Any],
    depth_image: Sequence[Sequence[Any]],
    intrinsics: CameraIntrinsics,
    *,
    min_depth_m: float = 0.10,
    max_depth_m: float = 3.00,
) -> Dict[str, Any]:
    """Add camera-frame 3D fields to one YOLO detection record."""

    enriched = dict(record)
    metadata = dict(enriched.get("metadata", {}))
    pixels, source = _candidate_pixels(record, intrinsics.width, intrinsics.height)
    valid_points: List[Vector3] = []

    for pixel_x, pixel_y in pixels:
        depth_m = _depth_at(depth_image, int(pixel_x), int(pixel_y), intrinsics.depth_scale)
        if min_depth_m <= depth_m <= max_depth_m:
            valid_points.append(deproject_pixel_to_point(float(pixel_x), float(pixel_y), depth_m, intrinsics))

    total_pixels = max(1, len(pixels))
    visible_area_ratio = len(valid_points) / total_pixels
    confidence = float(enriched.get("yolo_confidence", enriched.get("confidence", 0.0)))

    if valid_points:
        center_xyz = _median_point(valid_points)
        bbox_3d = _bbox3d(valid_points)
        safe_grasp_score = round(max(0.0, min(1.0, confidence * visible_area_ratio)), 4)
        grasp_candidates = [
            {
                "type": "top_down_center",
                "frame": intrinsics.frame_id,
                "position_xyz": list(center_xyz),
                "approach_vector": [0.0, 0.0, -1.0],
                "score": safe_grasp_score,
                "source": "rgbd_geometry_v1",
            }
        ]
    else:
        center_xyz = tuple(enriched.get("center_xyz", (0.0, 0.0, 0.0)))
        bbox_3d = enriched.get("bbox_3d")
        safe_grasp_score = 0.0
        grasp_candidates = []

    enriched["center_xyz"] = list(center_xyz)
    enriched["bbox_3d"] = list(bbox_3d) if bbox_3d is not None else None
    enriched["visible_area_ratio"] = round(visible_area_ratio, 4)
    enriched["occlusion_state"] = _occlusion_state(visible_area_ratio)
    enriched["grasp_candidates"] = grasp_candidates
    enriched["safe_grasp_score"] = safe_grasp_score
    metadata.update(
        {
            "rgbd_source": source,
            "camera_frame_id": intrinsics.frame_id,
            "candidate_pixel_count": len(pixels),
            "valid_depth_pixel_count": len(valid_points),
            "depth_scale": intrinsics.depth_scale,
        }
    )
    enriched["metadata"] = metadata
    return enriched


def _depth_at(depth_image: Sequence[Sequence[Any]], pixel_x: int, pixel_y: int, depth_scale: float) -> float:
    if pixel_y < 0 or pixel_x < 0:
        return 0.0
    try:
        raw_value = depth_image[pixel_y][pixel_x]
    except (IndexError, TypeError):
        return 0.0
    if hasattr(raw_value, "item"):
        raw_value = raw_value.item()
    depth_raw = float(raw_value)
    if depth_raw <= 0:
        return 0.0
    return depth_raw * depth_scale


def _candidate_pixels(record: Mapping[str, Any], width: int, height: int) -> Tuple[List[Tuple[int, int]], str]:
    polygon = _point_list(record.get("mask_polygon"))
    if polygon:
        return _pixels_from_polygon(polygon, width, height), "aligned_depth_mask"
    bbox = _bbox_xyxy(record.get("bbox_xyxy") or record.get("bbox"))
    if bbox is not None:
        return _pixels_from_bbox(bbox, width, height), "aligned_depth_bbox"
    center = record.get("center_xyz") or record.get("pixel_center_xy") or [width / 2.0, height / 2.0]
    pixel_x = int(round(float(center[0])))
    pixel_y = int(round(float(center[1])))
    return [(max(0, min(width - 1, pixel_x)), max(0, min(height - 1, pixel_y)))], "aligned_depth_center"


def _point_list(value: Any) -> List[PixelPoint]:
    if not isinstance(value, Sequence):
        return []
    points: List[PixelPoint] = []
    for point in value:
        if isinstance(point, Sequence) and len(point) >= 2:
            points.append((float(point[0]), float(point[1])))
    return points


def _bbox_xyxy(value: Any) -> Tuple[float, float, float, float] | None:
    if isinstance(value, Sequence) and len(value) >= 4:
        return (float(value[0]), float(value[1]), float(value[2]), float(value[3]))
    return None


def _pixels_from_bbox(bbox: Tuple[float, float, float, float], width: int, height: int) -> List[Tuple[int, int]]:
    x1, y1, x2, y2 = bbox
    min_x = max(0, int(floor(min(x1, x2))))
    max_x = min(width, int(ceil(max(x1, x2))))
    min_y = max(0, int(floor(min(y1, y2))))
    max_y = min(height, int(ceil(max(y1, y2))))
    return [(x, y) for y in range(min_y, max_y) for x in range(min_x, max_x)]


def _pixels_from_polygon(polygon: Sequence[PixelPoint], width: int, height: int) -> List[Tuple[int, int]]:
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    bbox_pixels = _pixels_from_bbox((min(xs), min(ys), max(xs), max(ys)), width, height)
    return [(x, y) for x, y in bbox_pixels if _point_in_polygon(x + 0.5, y + 0.5, polygon)]


def _point_in_polygon(pixel_x: float, pixel_y: float, polygon: Sequence[PixelPoint]) -> bool:
    inside = False
    j = len(polygon) - 1
    for i, point_i in enumerate(polygon):
        xi, yi = point_i
        xj, yj = polygon[j]
        intersects = ((yi > pixel_y) != (yj > pixel_y)) and (
            pixel_x < (xj - xi) * (pixel_y - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _median_point(points: Sequence[Vector3]) -> Vector3:
    return (
        float(median(point[0] for point in points)),
        float(median(point[1] for point in points)),
        float(median(point[2] for point in points)),
    )


def _bbox3d(points: Sequence[Vector3]) -> Tuple[float, float, float, float, float, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    zs = [point[2] for point in points]
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def _occlusion_state(visible_area_ratio: float) -> str:
    if visible_area_ratio >= 0.70:
        return "visible"
    if visible_area_ratio >= 0.30:
        return "partial"
    if visible_area_ratio > 0:
        return "poor_depth"
    return "no_valid_depth"
