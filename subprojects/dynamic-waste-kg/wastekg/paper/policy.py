"""定义小论文实验使用的策略路由规则。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional

from wastekg.core.models import CategorySpec, ObjectInstance


AUTO_CANDIDATE = "AUTO_CANDIDATE"
SUPERVISED_CANDIDATE = "SUPERVISED_CANDIDATE"
HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"

POLICY_VERSION = "paper_policy_v1_conservative"

_HUMAN_REVIEW_STATUSES = {
    "review_required",
    "unknown",
    "needs_review",
    "human_review",
    "human_review_required",
    "uncertain",
    "review_error",
    "failed",
    "schema_error",
    "api_error",
}


@dataclass(frozen=True)
class PolicyRouteResult:
    instance_id: str
    predicted_class: str
    route: str
    reason: str
    policy_version: str = POLICY_VERSION

    def to_dict(self) -> Dict[str, object]:
        return {
            "instance_id": self.instance_id,
            "predicted_class": self.predicted_class,
            "route": self.route,
            "reason": self.reason,
            "policy_version": self.policy_version,
        }


@dataclass(frozen=True)
class PolicyCase:
    case_id: str
    true_class: str
    predicted_class: str
    final_confidence: float
    review_status: str = "confirmed"
    processable: bool = True


@dataclass(frozen=True)
class EvaluatedPolicyCase:
    case_id: str
    true_class: str
    predicted_class: str
    expected_route: str
    predicted_route: str
    final_confidence: float
    review_status: str
    correct: bool
    reason: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "case_id": self.case_id,
            "true_class": self.true_class,
            "predicted_class": self.predicted_class,
            "expected_route": self.expected_route,
            "predicted_route": self.predicted_route,
            "final_confidence": self.final_confidence,
            "review_status": self.review_status,
            "correct": self.correct,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class PolicyEvaluation:
    cases: List[EvaluatedPolicyCase]
    metrics: Dict[str, float]


def route_instance(
    instance: ObjectInstance,
    categories: Mapping[str, CategorySpec],
    *,
    min_auto_confidence: float = 0.80,
) -> PolicyRouteResult:
    spec = categories.get(instance.class_name)
    if spec is None:
        return PolicyRouteResult(
            instance_id=instance.instance_id,
            predicted_class=instance.class_name,
            route=HUMAN_REVIEW_REQUIRED,
            reason="unknown_category",
        )

    confidence = instance.yolo_confidence
    review_status = (instance.recognition_status or "").lower()
    task_status = (instance.task_status or "").lower()

    if review_status in _HUMAN_REVIEW_STATUSES or task_status in _HUMAN_REVIEW_STATUSES:
        return _result(instance, HUMAN_REVIEW_REQUIRED, f"recognition_status={instance.recognition_status or instance.task_status}")

    if instance.current_handling_policy in {"human_review_required", "robot_forbidden"}:
        return _result(instance, HUMAN_REVIEW_REQUIRED, f"current_handling_policy={instance.current_handling_policy}")

    if spec.risk_level in {"high", "critical", "hazardous"}:
        return _result(instance, HUMAN_REVIEW_REQUIRED, f"risk_level={spec.risk_level}")

    if confidence < min_auto_confidence:
        return _result(instance, HUMAN_REVIEW_REQUIRED, f"final_confidence<{min_auto_confidence:.2f}")

    if spec.default_handling_policy == "auto_allowed" and instance.current_handling_policy == "auto_allowed":
        return _result(instance, AUTO_CANDIDATE, "auto_allowed")

    return _result(instance, SUPERVISED_CANDIDATE, "conservative_default")


def evaluate_policy_cases(
    cases: Iterable[PolicyCase],
    categories: Mapping[str, CategorySpec],
    *,
    min_auto_confidence: float = 0.80,
) -> PolicyEvaluation:
    evaluated: List[EvaluatedPolicyCase] = []
    for case in cases:
        predicted_instance = _instance_from_case(case, class_name=case.predicted_class)
        expected_instance = _instance_from_case(case, class_name=case.true_class)
        predicted = route_instance(predicted_instance, categories, min_auto_confidence=min_auto_confidence)
        expected = route_instance(expected_instance, categories, min_auto_confidence=min_auto_confidence)
        evaluated.append(
            EvaluatedPolicyCase(
                case_id=case.case_id,
                true_class=case.true_class,
                predicted_class=case.predicted_class,
                expected_route=expected.route,
                predicted_route=predicted.route,
                final_confidence=case.final_confidence,
                review_status=case.review_status,
                correct=predicted.route == expected.route,
                reason=predicted.reason,
            )
        )
    return PolicyEvaluation(cases=evaluated, metrics=_metrics(evaluated))


def _result(instance: ObjectInstance, route: str, reason: str) -> PolicyRouteResult:
    return PolicyRouteResult(
        instance_id=instance.instance_id,
        predicted_class=instance.class_name,
        route=route,
        reason=reason,
    )


def _instance_from_case(case: PolicyCase, *, class_name: str) -> ObjectInstance:
    return ObjectInstance(
        instance_id=case.case_id,
        class_name=class_name,
        yolo_confidence=case.final_confidence,
        recognition_status="accepted" if case.review_status == "confirmed" else "review_required",
        current_handling_policy="auto_allowed" if case.processable else "human_review_required",
    )


def _metrics(cases: List[EvaluatedPolicyCase]) -> Dict[str, float]:
    total = len(cases)
    correct = sum(1 for case in cases if case.correct)
    expected_human = [case for case in cases if case.expected_route == HUMAN_REVIEW_REQUIRED]
    expected_auto = [case for case in cases if case.expected_route == AUTO_CANDIDATE]
    predicted_human = [case for case in cases if case.predicted_route == HUMAN_REVIEW_REQUIRED]
    unsafe_auto = [
        case
        for case in expected_human
        if case.predicted_route == AUTO_CANDIDATE
    ]
    restriction_hits = [
        case
        for case in expected_human
        if case.predicted_route == HUMAN_REVIEW_REQUIRED
    ]
    over_conservative = [
        case
        for case in expected_auto
        if case.predicted_route == HUMAN_REVIEW_REQUIRED
    ]
    return {
        "case_count": float(total),
        "correct_count": float(correct),
        "policy_consistency_rate": _safe_div(correct, total),
        "expected_human_review_count": float(len(expected_human)),
        "human_escalation_count": float(len(predicted_human)),
        "human_escalation_rate": _safe_div(len(predicted_human), total),
        "restriction_recall": _safe_div(len(restriction_hits), len(expected_human)),
        "unsafe_automation_count": float(len(unsafe_auto)),
        "unsafe_automation_rate": _safe_div(len(unsafe_auto), len(expected_human)),
        "over_conservative_count": float(len(over_conservative)),
        "over_conservative_rate": _safe_div(len(over_conservative), len(expected_auto)),
    }


def _safe_div(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
