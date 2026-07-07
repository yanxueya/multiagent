"""验证 test paper policy 相关功能。"""

from __future__ import annotations

import unittest

from wastekg.core.knowledge_base import DEFAULT_CATEGORY_SPECS
from wastekg.core.models import ObjectInstance
from wastekg.paper.policy import (
    AUTO_CANDIDATE,
    HUMAN_REVIEW_REQUIRED,
    SUPERVISED_CANDIDATE,
    PolicyCase,
    evaluate_policy_cases,
    route_instance,
)


class PaperPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.categories = {spec.name: spec for spec in DEFAULT_CATEGORY_SPECS}

    def test_policy_routes_unknown_category_as_review_required(self) -> None:
        instance = ObjectInstance(
            instance_id="unknown_01",
            class_name="unknown",
            confidence=0.95,
            final_confidence=0.95,
            review_status="confirmed",
            processable=True,
        )

        result = route_instance(instance, self.categories)

        self.assertEqual(result.route, HUMAN_REVIEW_REQUIRED)
        self.assertIn("unknown_category", result.reason)

    def test_policy_routes_clean_robot_grasp_instance_as_auto_candidate(self) -> None:
        instance = ObjectInstance(
            instance_id="brick_01",
            class_name="brick",
            confidence=0.91,
            final_confidence=0.91,
            review_status="confirmed",
            processable=True,
        )

        result = route_instance(instance, self.categories)

        self.assertEqual(result.route, AUTO_CANDIDATE)
        self.assertIn("auto_processable", result.reason)

    def test_policy_routes_uncertain_review_as_human_review_required(self) -> None:
        instance = ObjectInstance(
            instance_id="metal_01",
            class_name="metal",
            confidence=0.84,
            final_confidence=0.84,
            review_status="uncertain",
            processable=True,
        )

        result = route_instance(instance, self.categories)

        self.assertEqual(result.route, HUMAN_REVIEW_REQUIRED)
        self.assertIn("review_status", result.reason)

    def test_policy_routes_robot_with_supervision_class_as_supervised_candidate(self) -> None:
        instance = ObjectInstance(
            instance_id="tile_01",
            class_name="tile",
            confidence=0.92,
            final_confidence=0.92,
            review_status="confirmed",
            processable=True,
        )

        result = route_instance(instance, self.categories)

        self.assertEqual(result.route, SUPERVISED_CANDIDATE)
        self.assertIn("robot_with_supervision", result.reason)

    def test_policy_metrics_penalize_unsafe_automation(self) -> None:
        cases = [
            PolicyCase(
                case_id="safe_brick",
                true_class="brick",
                predicted_class="brick",
                final_confidence=0.95,
                review_status="confirmed",
            ),
            PolicyCase(
                case_id="dangerous_override",
                true_class="unknown",
                predicted_class="brick",
                final_confidence=0.96,
                review_status="confirmed",
            ),
            PolicyCase(
                case_id="glass_review",
                true_class="glass",
                predicted_class="glass",
                final_confidence=0.72,
                review_status="uncertain",
            ),
        ]

        evaluation = evaluate_policy_cases(cases, self.categories)

        self.assertEqual(evaluation.metrics["case_count"], 3)
        self.assertEqual(evaluation.metrics["unsafe_automation_count"], 1)
        self.assertAlmostEqual(evaluation.metrics["unsafe_automation_rate"], 0.5)
        self.assertLess(evaluation.metrics["policy_consistency_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
