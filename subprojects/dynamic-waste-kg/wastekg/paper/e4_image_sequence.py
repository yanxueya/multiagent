"""构建 E4 图像序列事件回放。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence, Tuple


BBox = Tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class SequenceDetection:
    """E4 图片序列中的单个检测结果。"""

    frame: str
    temp_id: str
    class_name: str
    confidence: float
    bbox_xyxy: BBox


@dataclass(frozen=True, slots=True)
class SequenceMatch:
    """前后两帧中被认为是同一个物体的匹配关系。"""

    before_id: str
    after_id: str
    class_name: str
    iou: float


@dataclass(frozen=True, slots=True)
class SequenceMatchResult:
    matches: List[SequenceMatch]
    removed_candidates: List[SequenceDetection]
    appeared_candidates: List[SequenceDetection]


def bbox_iou(first: BBox, second: BBox) -> float:
    """计算两个二维包围盒的 IoU，用于固定视角前后帧的实例关联。"""

    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    intersection = inter_w * inter_h

    first_area = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    second_area = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = first_area + second_area - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def detections_from_yolo_records(frame: str, records: Iterable[Dict[str, Any]]) -> List[SequenceDetection]:
    detections: List[SequenceDetection] = []
    for index, record in enumerate(records, start=1):
        bbox = record.get("bbox_xyxy") or record.get("metadata", {}).get("bbox_xyxy")
        if not bbox or len(bbox) < 4:
            continue
        class_name = str(record.get("llm_class_name") or record.get("yolo_class_name") or record.get("class_name") or "unknown")
        confidence = float(record.get("llm_confidence", record.get("yolo_confidence", record.get("confidence", 0.0))))
        detections.append(
            SequenceDetection(
                frame=frame,
                temp_id=str(record.get("temp_id") or f"{frame}_{index:03d}"),
                class_name=class_name,
                confidence=confidence,
                bbox_xyxy=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
            )
        )
    return detections


def match_image_sequence_detections(
    before: Sequence[SequenceDetection],
    after: Sequence[SequenceDetection],
    *,
    iou_threshold: float = 0.30,
) -> SequenceMatchResult:
    """用同类 IoU 贪心匹配固定视角前后帧。

    未匹配的前帧实例是“移除候选”，未匹配的后帧实例是“新增候选”。
    这里不直接断言真实移除，因为严格论文证据还需要人工记录或标注确认。
    """

    candidate_pairs: list[tuple[float, int, int]] = []
    for before_index, before_item in enumerate(before):
        for after_index, after_item in enumerate(after):
            if before_item.class_name != after_item.class_name:
                continue
            iou = bbox_iou(before_item.bbox_xyxy, after_item.bbox_xyxy)
            if iou >= iou_threshold:
                candidate_pairs.append((iou, before_index, after_index))

    candidate_pairs.sort(key=lambda item: item[0], reverse=True)
    used_before: set[int] = set()
    used_after: set[int] = set()
    matches: list[SequenceMatch] = []
    for iou, before_index, after_index in candidate_pairs:
        if before_index in used_before or after_index in used_after:
            continue
        before_item = before[before_index]
        after_item = after[after_index]
        matches.append(
            SequenceMatch(
                before_id=before_item.temp_id,
                after_id=after_item.temp_id,
                class_name=before_item.class_name,
                iou=iou,
            )
        )
        used_before.add(before_index)
        used_after.add(after_index)

    removed = [item for index, item in enumerate(before) if index not in used_before]
    appeared = [item for index, item in enumerate(after) if index not in used_after]
    return SequenceMatchResult(matches=matches, removed_candidates=removed, appeared_candidates=appeared)


def build_image_sequence_events(
    before: Sequence[SequenceDetection],
    after: Sequence[SequenceDetection],
    result: SequenceMatchResult,
) -> List[Dict[str, Any]]:
    events: list[dict[str, Any]] = [
        {"event_type": "FRAME_OBSERVED", "frame": "before", "detection_count": len(before)},
        {"event_type": "FRAME_OBSERVED", "frame": "after", "detection_count": len(after)},
    ]
    for item in result.matches:
        events.append(
            {
                "event_type": "INSTANCE_PERSISTED",
                "before_id": item.before_id,
                "after_id": item.after_id,
                "class_name": item.class_name,
                "iou": round(item.iou, 4),
            }
        )
    for item in result.removed_candidates:
        events.append(
            {
                "event_type": "INSTANCE_REMOVED_CANDIDATE",
                "before_id": item.temp_id,
                "class_name": item.class_name,
                "confidence": round(item.confidence, 4),
                "bbox_xyxy": list(item.bbox_xyxy),
            }
        )
    for item in result.appeared_candidates:
        events.append(
            {
                "event_type": "INSTANCE_APPEARED_CANDIDATE",
                "after_id": item.temp_id,
                "class_name": item.class_name,
                "confidence": round(item.confidence, 4),
                "bbox_xyxy": list(item.bbox_xyxy),
            }
        )
    return events


def summarize_image_sequence(
    before: Sequence[SequenceDetection],
    after: Sequence[SequenceDetection],
    result: SequenceMatchResult,
) -> Dict[str, Any]:
    events = build_image_sequence_events(before, after, result)
    return {
        "before_detection_count": len(before),
        "after_detection_count": len(after),
        "persisted_count": len(result.matches),
        "removed_candidate_count": len(result.removed_candidates),
        "appeared_candidate_count": len(result.appeared_candidates),
        "event_count": len(events),
    }
