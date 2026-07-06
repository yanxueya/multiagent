from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.paper_event_replay import evaluate_event_replay_cases, generate_default_replay_cases


def main() -> int:
    output_dir = PROJECT_ROOT / "artifacts" / "paper" / "e4_event_replay"
    output_dir.mkdir(parents=True, exist_ok=True)
    evaluation = evaluate_event_replay_cases(generate_default_replay_cases())

    cases_path = output_dir / "event_replay_cases.csv"
    with cases_path.open("w", newline="", encoding="utf-8") as file:
        fieldnames = [
            "case_id",
            "scenario",
            "true_class",
            "initial_class",
            "final_class",
            "expected_route",
            "events_json",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for case in evaluation.cases:
            row = case.to_dict()
            row["events_json"] = json.dumps(row.pop("events"), ensure_ascii=False)
            writer.writerow(row)

    metrics_path = output_dir / "event_replay_metrics.json"
    metrics_path.write_text(json.dumps(evaluation.metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    report_path = output_dir / "event_replay_report.md"
    report_path.write_text(_report(evaluation.metrics), encoding="utf-8")
    print(f"E4 event replay results written to {output_dir}")
    return 0


def _report(metrics: dict[str, float]) -> str:
    lines = [
        "# E4 Controlled Event Replay Report",
        "",
        "This controlled validation checks whether short-term instance states can be represented as ordered, traceable event chains.",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in metrics.items():
        lines.append(f"| {key} | {value:.4f} |")
    lines.extend(
        [
            "",
            "Interpretation: this is a software-state validation. It should not be reported as physical grasping or ROS2 execution validation.",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
