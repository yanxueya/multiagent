"""把 YOLO/VLM 感知记录写入知识图谱。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Protocol, Tuple

from wastekg.interfaces.contracts import VisionPacket, vision_packet_to_observation
from wastekg.graph.store import KnowledgeGraph
from wastekg.core.taxonomy import KNOWN_VISUAL_CLASSES, UNKNOWN_CATEGORY, canonicalize_category_name
from wastekg.perception.vision_bridge import build_vision_packet_from_records


@dataclass(slots=True)
class PerceptionPolicy:
    proposal_confidence: float = 0.05
    review_confidence: float = 0.30
    accept_confidence: float = 0.75
    unknown_confidence: float = 0.30
    review_categories: set[str] = field(default_factory=lambda: {"glass", "gypsum_board"})
    accept_thresholds: Dict[str, float] = field(default_factory=dict)

    @property
    def high_confidence(self) -> float:
        return self.accept_confidence

    def needs_review(self, class_name: str, confidence: float) -> bool:
        canonical = canonicalize_category_name(class_name)
        accept_threshold = self.accept_thresholds.get(canonical, self.accept_confidence)
        return canonical in self.review_categories or self.review_confidence <= confidence < accept_threshold

    def should_be_unknown(self, class_name: str, confidence: float) -> bool:
        canonical = canonicalize_category_name(class_name)
        return canonical == UNKNOWN_CATEGORY or self.proposal_confidence <= confidence < self.unknown_confidence


@dataclass(slots=True)
class ReviewResult:
    class_name: str
    confidence: float
    risk_hint: str = "unknown"
    reason: str = ""
    need_human_review: bool = False
    consistency_status: str = "not_checked"
    consistency_score: float = 0.0
    visual_attributes: Dict[str, Any] = field(default_factory=dict)
    # ``legacy`` preserves compatibility with the initial text-only reviewer.
    decision: str = "legacy"


class LightweightReviewer(Protocol):
    def review(self, crop_or_image_ref: Any, *, yolo_class_name: str, yolo_confidence: float, allowed_classes: List[str]) -> ReviewResult:
        ...


def build_records_with_optional_review(
    yolo_records: Iterable[Dict[str, Any]],
    *,
    reviewer: Optional[LightweightReviewer] = None,
    policy: Optional[PerceptionPolicy] = None,
    allowed_classes: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    policy = policy or PerceptionPolicy()
    allowed_classes = allowed_classes or list(KNOWN_VISUAL_CLASSES)

    records: List[Dict[str, Any]] = []
    for raw in yolo_records:
        record = dict(raw)
        yolo_class_name = canonicalize_category_name(str(record.get("yolo_class_name") or record.get("class_name") or record.get("label") or "unknown"))
        yolo_confidence = float(record.get("yolo_confidence", record.get("confidence", 0.0)))
        record["yolo_class_name"] = yolo_class_name
        record["yolo_confidence"] = yolo_confidence

        if yolo_confidence < policy.proposal_confidence:
            continue

        if policy.should_be_unknown(yolo_class_name, yolo_confidence):
            record["llm_class_name"] = ""
            record["llm_confidence"] = 0.0
            record["risk_hint"] = "unknown"
            record.setdefault("metadata", {})
            record["metadata"].update(
                {
                    "need_human_review": True,
                    "review_decision": "unknown",
                    "recognition_status": "unknown",
                    "unknown_reason": f"yolo_confidence<{policy.unknown_confidence:.2f}",
                    "original_yolo_class_name": yolo_class_name,
                }
            )
            records.append(record)
            continue

        if reviewer is not None and policy.needs_review(yolo_class_name, yolo_confidence):
            review_input = (
                {"visual_evidence": record["visual_evidence"]}
                if record.get("visual_evidence")
                else record.get("crop") or record.get("image_ref")
            )
            try:
                review = reviewer.review(
                    review_input,
                    yolo_class_name=yolo_class_name,
                    yolo_confidence=yolo_confidence,
                    allowed_classes=allowed_classes,
                )
            except Exception as exc:
                # The perception result remains usable when a remote reviewer is
                # unavailable. It is deliberately routed to human review instead.
                review = ReviewResult(
                    class_name=yolo_class_name,
                    confidence=0.0,
                    reason="LLM review was unavailable; retained the YOLO result.",
                    need_human_review=True,
                    decision="review_error",
                )
                record.setdefault("metadata", {})["review_error_type"] = type(exc).__name__
                record.setdefault("metadata", {})["review_error_message"] = str(exc)
            llm_class_name = canonicalize_category_name(review.class_name)
            review_decision = review.decision
            if review_decision == "legacy":
                if llm_class_name == yolo_class_name:
                    review_decision = "support"
                elif llm_class_name == UNKNOWN_CATEGORY:
                    review_decision = "unknown"
                else:
                    review_decision = "conflict"
            record["llm_class_name"] = llm_class_name
            record["llm_confidence"] = review.confidence
            record["risk_hint"] = review.risk_hint
            record.setdefault("metadata", {})
            record["metadata"].update(
                {
                    "review_reason": review.reason,
                    "need_human_review": review.need_human_review or review_decision in {"conflict", "insufficient", "unknown"},
                    "review_decision": review_decision,
                    "vlm_consistency_status": review.consistency_status if review.consistency_status != "not_checked" else review_decision,
                    "vlm_consistency_score": review.consistency_score,
                    "visual_attributes": dict(review.visual_attributes),
                    "candidate_class": yolo_class_name,
                    "recognition_status": "accepted" if review_decision == "support" else ("unknown" if review_decision in {"conflict", "unknown"} else "review_required"),
                }
            )
        elif policy.needs_review(yolo_class_name, yolo_confidence):
            record.setdefault("metadata", {}).update(
                {
                    "candidate_class": yolo_class_name,
                    "need_human_review": True,
                    "review_decision": "not_checked",
                    "recognition_status": "review_required",
                }
            )
        else:
            record.setdefault("metadata", {}).update(
                {
                    "candidate_class": yolo_class_name,
                    "recognition_status": "accepted",
                }
            )
        records.append(record)
    return records


def apply_perception_records_to_graph(
    graph: KnowledgeGraph,
    *,
    frame_id: str,
    source: str,
    yolo_records: Iterable[Dict[str, Any]],
    relation_hints: Optional[Iterable[Dict[str, Any]]] = None,
    reviewer: Optional[LightweightReviewer] = None,
    camera_pose: Optional[Dict[str, Any]] = None,
    allowed_classes: Optional[List[str]] = None,
) -> Tuple[VisionPacket, Dict[str, Any]]:
    reviewed_records = build_records_with_optional_review(
        yolo_records,
        reviewer=reviewer,
        allowed_classes=allowed_classes,
    )
    packet = build_vision_packet_from_records(
        frame_id=frame_id,
        source=source,
        detections=reviewed_records,
        relation_hints=relation_hints,
        camera_pose=camera_pose,
    )
    result = graph.apply_observation(vision_packet_to_observation(packet))
    return packet, result
