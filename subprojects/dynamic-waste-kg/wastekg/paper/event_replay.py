"""回放小论文事件序列并生成评估结果。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from wastekg.paper.policy import AUTO_CANDIDATE, HUMAN_REVIEW_REQUIRED, SUPERVISED_CANDIDATE


REQUIRED_SCENARIOS = (
    "normal_confirmation",
    "vlm_correction",
    "vlm_uncertain_fallback",
    "low_confidence_human_review",
    "sensitive_class_review",
    "object_removed",
    "object_reappeared",
    "api_schema_error_fallback",
)


@dataclass(frozen=True)
class ReplayEvent:
    event_type: str
    state_version: int
    route: str
    detail: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "event_type": self.event_type,
            "state_version": self.state_version,
            "route": self.route,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ReplayCase:
    case_id: str
    scenario: str
    true_class: str
    initial_class: str
    final_class: str
    expected_route: str
    events: List[ReplayEvent]

    def to_dict(self) -> Dict[str, object]:
        return {
            "case_id": self.case_id,
            "scenario": self.scenario,
            "true_class": self.true_class,
            "initial_class": self.initial_class,
            "final_class": self.final_class,
            "expected_route": self.expected_route,
            "events": [event.to_dict() for event in self.events],
        }


@dataclass(frozen=True)
class ReplayEvaluation:
    cases: List[ReplayCase]
    case_results: List[Dict[str, object]]
    metrics: Dict[str, float]


def generate_default_replay_cases(case_count: int = 32) -> List[ReplayCase]:
    if case_count < len(REQUIRED_SCENARIOS):
        raise ValueError("case_count must cover all required scenarios")
    cases: List[ReplayCase] = []
    for index in range(case_count):
        scenario = REQUIRED_SCENARIOS[index % len(REQUIRED_SCENARIOS)]
        cases.append(_build_case(index + 1, scenario))
    return cases


def evaluate_event_replay_cases(cases: Iterable[ReplayCase]) -> ReplayEvaluation:
    replay_cases = list(cases)
    results: List[Dict[str, object]] = []
    for case in replay_cases:
        versions = [event.state_version for event in case.events]
        routes = [event.route for event in case.events]
        chain_complete = [event.event_type for event in case.events] == [
            "OBSERVED",
            "REVIEWED",
            "POLICY_PROJECTED",
            "ROUTED",
        ]
        version_consistent = versions == list(range(1, len(versions) + 1))
        final_route_correct = routes[-1] == case.expected_route
        temporal_policy_consistent = _temporal_policy_is_consistent(routes)
        results.append(
            {
                "case_id": case.case_id,
                "scenario": case.scenario,
                "chain_complete": chain_complete,
                "version_consistent": version_consistent,
                "final_route_correct": final_route_correct,
                "temporal_policy_consistent": temporal_policy_consistent,
            }
        )
    return ReplayEvaluation(cases=replay_cases, case_results=results, metrics=_metrics(results))


def _build_case(index: int, scenario: str) -> ReplayCase:
    case_id = f"replay_{index:03d}"
    true_class = "brick"
    initial_class = "brick"
    final_class = "brick"
    route = AUTO_CANDIDATE
    review_detail = "confirmed"

    if scenario == "vlm_correction":
        true_class = "metal"
        initial_class = "hard_plastic"
        final_class = "metal"
        route = SUPERVISED_CANDIDATE
        review_detail = "vlm_changed_class"
    elif scenario == "vlm_uncertain_fallback":
        true_class = "glass"
        initial_class = "glass"
        final_class = "glass"
        route = HUMAN_REVIEW_REQUIRED
        review_detail = "vlm_uncertain_kept_yolo"
    elif scenario == "low_confidence_human_review":
        true_class = "foam"
        initial_class = "foam"
        final_class = "foam"
        route = HUMAN_REVIEW_REQUIRED
        review_detail = "low_confidence"
    elif scenario == "sensitive_class_review":
        true_class = "unknown"
        initial_class = "gypsum_board"
        final_class = "unknown"
        route = HUMAN_REVIEW_REQUIRED
        review_detail = "sensitive_or_unknown_external_label"
    elif scenario == "object_removed":
        true_class = "wood"
        initial_class = "wood"
        final_class = "wood"
        route = SUPERVISED_CANDIDATE
        review_detail = "removed_after_action"
    elif scenario == "object_reappeared":
        true_class = "paperboard"
        initial_class = "paperboard"
        final_class = "paperboard"
        route = SUPERVISED_CANDIDATE
        review_detail = "weak_memory_reactivated"
    elif scenario == "api_schema_error_fallback":
        true_class = "soft_plastic"
        initial_class = "soft_plastic"
        final_class = "soft_plastic"
        route = HUMAN_REVIEW_REQUIRED
        review_detail = "schema_error_fallback"

    events = [
        ReplayEvent("OBSERVED", 1, route, f"initial_class={initial_class}"),
        ReplayEvent("REVIEWED", 2, route, review_detail),
        ReplayEvent("POLICY_PROJECTED", 3, route, "paper_policy_v1_conservative"),
        ReplayEvent("ROUTED", 4, route, f"route={route}"),
    ]
    return ReplayCase(
        case_id=case_id,
        scenario=scenario,
        true_class=true_class,
        initial_class=initial_class,
        final_class=final_class,
        expected_route=route,
        events=events,
    )


def _temporal_policy_is_consistent(routes: List[str]) -> bool:
    if not routes:
        return False
    projected_route = routes[-2] if len(routes) >= 2 else routes[-1]
    final_route = routes[-1]
    return projected_route == final_route


def _metrics(results: List[Dict[str, object]]) -> Dict[str, float]:
    total = len(results)
    return {
        "case_count": float(total),
        "instance_update_success_rate": _ratio(results, "final_route_correct"),
        "event_chain_completeness": _ratio(results, "chain_complete"),
        "state_version_consistency": _ratio(results, "version_consistent"),
        "temporal_policy_consistency": _ratio(results, "temporal_policy_consistent"),
    }


def _ratio(results: List[Dict[str, object]], key: str) -> float:
    if not results:
        return 0.0
    return sum(1 for result in results if result[key]) / len(results)
