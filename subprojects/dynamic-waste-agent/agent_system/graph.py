"""定义 graph 多智能体占位逻辑。"""

AGENT_ORDER = (
    "perception_agent",
    "knowledge_agent",
    "risk_agent",
    "planning_agent",
    "execution_agent",
)


def describe_graph() -> dict[str, object]:
    """Return the intended graph shape without importing LangGraph yet."""

    return {
        "status": "placeholder",
        "agents": list(AGENT_ORDER),
        "flow": "perception -> knowledge -> risk -> planning -> execution -> feedback",
    }


if __name__ == "__main__":
    print(describe_graph())
