"""运行 run e3 policy routing 小论文实验入口。"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.core.knowledge_base import DEFAULT_CATEGORY_SPECS
from wastekg.paper.policy import PolicyCase, evaluate_policy_cases


def main() -> int:
    output_dir = PROJECT_ROOT / "artifacts" / "paper" / "e3_policy_routing"
    output_dir.mkdir(parents=True, exist_ok=True)
    categories = {spec.name: spec for spec in DEFAULT_CATEGORY_SPECS}
    evaluation = evaluate_policy_cases(_default_cases(), categories)

    cases_path = output_dir / "policy_cases.csv"
    with cases_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(evaluation.cases[0].to_dict().keys()))
        writer.writeheader()
        for case in evaluation.cases:
            writer.writerow(case.to_dict())

    metrics_path = output_dir / "policy_metrics.json"
    metrics_path.write_text(json.dumps(evaluation.metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    report_path = output_dir / "policy_report.md"
    report_path.write_text(_report(evaluation.metrics), encoding="utf-8")
    print(f"E3 policy routing results written to {output_dir}")
    return 0


def _default_cases() -> list[PolicyCase]:
    classes = [
        ("brick", "brick", 0.95, "confirmed"),
        ("wood", "wood", 0.91, "confirmed"),
        ("tile", "tile", 0.90, "confirmed"),
        ("concrete", "concrete", 0.88, "confirmed"),
        ("metal", "metal", 0.86, "confirmed"),
        ("hard_plastic", "hard_plastic", 0.93, "confirmed"),
        ("soft_plastic", "soft_plastic", 0.77, "confirmed"),
        ("paperboard", "paperboard", 0.74, "confirmed"),
        ("foam", "foam", 0.79, "uncertain"),
        ("gypsum_board", "gypsum_board", 0.89, "confirmed"),
        ("glass", "glass", 0.72, "uncertain"),
        ("unknown", "unknown", 0.90, "human_review_required"),
        ("unknown", "gypsum_board", 0.86, "human_review_required"),
        ("glass", "paperboard", 0.91, "confirmed"),
        ("metal", "hard_plastic", 0.84, "review_error"),
    ]
    return [
        PolicyCase(
            case_id=f"policy_{index:03d}",
            true_class=true_class,
            predicted_class=predicted_class,
            final_confidence=confidence,
            review_status=review_status,
        )
        for index, (true_class, predicted_class, confidence, review_status) in enumerate(classes, start=1)
    ]


def _report(metrics: dict[str, float]) -> str:
    lines = [
        "# E3 Policy Routing Report",
        "",
        "This controlled evaluation checks whether layered category priors and short-term review states can be projected into conservative task routes.",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in metrics.items():
        lines.append(f"| {key} | {value:.4f} |")
    lines.extend(
        [
            "",
            "Interpretation: `unsafe_automation_rate` is the key risk metric. Any non-zero value indicates cases where a truly human-review class was routed as automatic because the predicted class was wrong.",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
