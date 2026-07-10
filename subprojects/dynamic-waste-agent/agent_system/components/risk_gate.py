"""定义风险与人工复核门控组件，不把安全策略包装成 agent。"""


def describe_risk_gate() -> dict[str, object]:
    return {
        "name": "risk_gate",
        "role": "apply deterministic safety, uncertainty and human-review gates before robot execution",
        "inputs": ["graph_state", "category_policy", "execution_history"],
        "outputs": ["risk_assessments", "human_review_requests", "blocked_reasons"],
        "status": "component_not_agent",
    }