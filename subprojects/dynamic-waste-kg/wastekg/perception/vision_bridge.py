"""将感知记录转换为 VisionPacket 接口对象。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from wastekg.interfaces.contracts import VisionDetection, VisionPacket, VisionRelationHint
from wastekg.core.taxonomy import canonicalize_category_name


Vector3 = Tuple[float, float, float]
Quaternion = Tuple[float, float, float, float]
BBox3D = Tuple[float, float, float, float, float, float]
BBox2D = Tuple[float, float, float, float]


def _as_vector3(value: Any, fallback: Vector3 = (0.0, 0.0, 0.0)) -> Vector3:
    if value is None:
        return fallback
    if isinstance(value, Sequence) and len(value) >= 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    return fallback


def _as_quaternion(value: Any, fallback: Quaternion = (0.0, 0.0, 0.0, 1.0)) -> Quaternion:
    if value is None:
        return fallback
    if isinstance(value, Sequence) and len(value) >= 4:
        return (float(value[0]), float(value[1]), float(value[2]), float(value[3]))
    return fallback


def _as_bbox3d(value: Any) -> Optional[BBox3D]:
    if value is None:
        return None
    if isinstance(value, Sequence) and len(value) >= 6:
        return (float(value[0]), float(value[1]), float(value[2]), float(value[3]), float(value[4]), float(value[5]))
    return None


def _as_bbox2d(value: Any) -> Optional[BBox2D]:
    if isinstance(value, Sequence) and len(value) >= 4:
        return (float(value[0]), float(value[1]), float(value[2]), float(value[3]))
    return None


def _as_point_list(value: Any) -> list[tuple[float, float]]:
    if value is None:
        return []
    points: list[tuple[float, float]] = []
    if isinstance(value, Sequence):
        for point in value:
            if isinstance(point, Sequence) and len(point) >= 2:
                points.append((float(point[0]), float(point[1])))
    return points


def _pick_first(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def vision_detection_from_record(record: Mapping[str, Any]) -> VisionDetection:
    # 这个适配器让你可以把 YOLO 原始输出、LLM 复核结果或中间 JSON 记录统一成同一种结构。
    return VisionDetection(
        temp_id=str(_pick_first(record, "temp_id", "id", default="unknown")),
        yolo_class_name=canonicalize_category_name(str(_pick_first(record, "yolo_class_name", "class_name", "label", default="unknown"))),
        yolo_confidence=float(_pick_first(record, "yolo_confidence", "confidence", default=0.0)),
        llm_class_name=canonicalize_category_name(str(_pick_first(record, "llm_class_name", default=""))),
        llm_confidence=float(_pick_first(record, "llm_confidence", default=0.0)),
        bbox_2d=_as_bbox2d(_pick_first(record, "bbox_2d", "bbox", default=None)),
        mask_ref=str(_pick_first(record, "mask_ref", default="")),
        crop_ref=str(_pick_first(record, "crop_ref", default="")),
        center_xyz=_as_vector3(_pick_first(record, "center_xyz", "center", default=None)),
        depth_valid_ratio=float(_pick_first(record, "depth_valid_ratio", default=0.0)),
        observed_extent_3d=_as_vector3(_pick_first(record, "observed_extent_3d", "estimated_size_3d", default=None)),
        orientation=_as_quaternion(_pick_first(record, "orientation", default=None)),
        bbox_3d=_as_bbox3d(_pick_first(record, "bbox_3d", default=None)),
        risk_hint=str(_pick_first(record, "risk_hint", "risk_level", default="unknown")),
        mask_polygon=_as_point_list(_pick_first(record, "mask_polygon", "segmentation", default=None)),
        boundary_points=_as_point_list(_pick_first(record, "boundary_points", "boundary", default=None)),
        visible_area_ratio=float(_pick_first(record, "visible_area_ratio", default=1.0)),
        occlusion_state=str(_pick_first(record, "occlusion_state", default="unknown")),
        grasp_candidates=list(_pick_first(record, "grasp_candidates", default=[])),
        safe_grasp_score=float(_pick_first(record, "safe_grasp_score", default=0.0)),
        metadata=dict(record.get("metadata", {})),
    )


def relation_hint_from_record(record: Mapping[str, Any]) -> VisionRelationHint:
    return VisionRelationHint(
        source_temp_id=str(_pick_first(record, "source_temp_id", "source_id", default="unknown")),
        relation=str(_pick_first(record, "relation", default="near")),
        target_temp_id=str(_pick_first(record, "target_temp_id", "target_id", default="unknown")),
        confidence=float(_pick_first(record, "confidence", default=1.0)),
        metadata=dict(record.get("metadata", {})),
    )


def build_vision_packet_from_records(
    *,
    frame_id: str,
    source: str,
    detections: Iterable[Mapping[str, Any]],
    relation_hints: Optional[Iterable[Mapping[str, Any]]] = None,
    camera_pose: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> VisionPacket:
    return VisionPacket(
        frame_id=frame_id,
        source=source,
        detections=[vision_detection_from_record(record) for record in detections],
        relation_hints=[relation_hint_from_record(record) for record in (relation_hints or [])],
        camera_pose=camera_pose,
        metadata=dict(metadata or {}),
    )
