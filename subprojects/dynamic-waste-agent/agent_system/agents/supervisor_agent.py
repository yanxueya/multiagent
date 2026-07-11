"""定义 supervisor agent 的总体调度职责。"""


def describe_supervisor_agent() -> dict[str, object]:
    return {
        "name": "supervisor_agent",
        "role": "route exploration, supervised execution, and human collaboration through one conditional LangGraph",
        "inputs": ["operation_mode", "user_goal", "thread_control_state", "kg_summary_ref"],
        "outputs": ["next_step", "target_instance_ids", "reason", "replan_required"],
        "status": "implemented_with_deterministic_route_validation",
    }
