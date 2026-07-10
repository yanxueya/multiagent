"""定义 KG 状态适配组件，不把知识图谱包装成 agent。"""


def describe_world_model_adapter() -> dict[str, object]:
    return {
        "name": "world_model_adapter",
        "role": "read dynamic-waste-kg and expose category priors plus current graph_state predicates",
        "inputs": ["perception_events", "kg_snapshot", "task_context"],
        "outputs": ["graph_state", "long_term_knowledge", "event_refs"],
        "status": "component_not_agent",
    }
