"""定义 action planning agent 的操作序列规划职责。"""


def describe_action_planning_agent() -> dict[str, object]:
    return {
        "name": "action_planning_agent",
        "role": "filter by graph feasibility and risk gates, then compute dynamic priority and recoverable action order",
        "inputs": ["objective", "graph_state", "risk_assessments", "robot_capabilities"],
        "outputs": ["ordered_plan", "deferred_targets", "failure_policy"],
        "status": "placeholder_with_decision_contract",
    }
