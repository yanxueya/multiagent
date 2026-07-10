"""兼容旧名称；新代码应使用 action_planning_agent。"""

from .action_planning_agent import describe_action_planning_agent


def describe_planning_agent() -> dict[str, object]:
    return describe_action_planning_agent()