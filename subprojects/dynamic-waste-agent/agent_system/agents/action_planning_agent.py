"""定义 action planning agent 的操作序列规划职责。"""


def describe_action_planning_agent() -> dict[str, object]:
    return {
        "name": "action_planning_agent",
        "role": "apply hard eligibility constraints and lexicographically select exactly one next action",
        "inputs": ["user_goal", "current_scene_id", "eligible_instance_ids", "kg_candidate_loader"],
        "outputs": ["single_action_plan"],
        "status": "implemented_phase_one_lexicographic_ranking",
    }
