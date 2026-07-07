"""验证 test paper event replay 相关功能。"""

from __future__ import annotations

import unittest

from wastekg.paper.event_replay import (
    REQUIRED_SCENARIOS,
    evaluate_event_replay_cases,
    generate_default_replay_cases,
)


class PaperEventReplayTest(unittest.TestCase):
    def test_event_replay_generates_at_least_30_cases_and_required_scenarios(self) -> None:
        cases = generate_default_replay_cases()

        self.assertGreaterEqual(len(cases), 30)
        scenario_names = {case.scenario for case in cases}
        self.assertTrue(set(REQUIRED_SCENARIOS).issubset(scenario_names))

    def test_event_replay_records_versions_and_events(self) -> None:
        case = generate_default_replay_cases()[0]

        versions = [event.state_version for event in case.events]
        event_types = [event.event_type for event in case.events]

        self.assertEqual(versions, [1, 2, 3, 4])
        self.assertEqual(event_types, ["OBSERVED", "REVIEWED", "POLICY_PROJECTED", "ROUTED"])

    def test_event_replay_metrics_are_complete_for_default_cases(self) -> None:
        evaluation = evaluate_event_replay_cases(generate_default_replay_cases())

        self.assertGreaterEqual(evaluation.metrics["case_count"], 30)
        self.assertEqual(evaluation.metrics["event_chain_completeness"], 1.0)
        self.assertEqual(evaluation.metrics["state_version_consistency"], 1.0)
        self.assertEqual(evaluation.metrics["temporal_policy_consistency"], 1.0)
        self.assertEqual(evaluation.metrics["instance_update_success_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
