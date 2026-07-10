"""定义 supervisor agent 的总体调度职责。"""


def describe_supervisor_agent() -> dict[str, object]:
    return {
        "name": "supervisor_agent",
        "role": "coordinate the task-level workflow and decide which system component or agent should run next",
        "inputs": ["objective", "user_intent", "task_status", "feedback"],
        "outputs": ["workflow_decision", "next_step", "audit_trail"],
        "status": "placeholder_with_orchestration_contract",
    }