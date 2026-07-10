"""初始化当前 Python 包中的四个真正智能体描述。"""

from .action_planning_agent import describe_action_planning_agent
from .execution_agent import describe_execution_agent
from .perception_agent import describe_perception_agent
from .supervisor_agent import describe_supervisor_agent

__all__ = [
    "describe_action_planning_agent",
    "describe_execution_agent",
    "describe_perception_agent",
    "describe_supervisor_agent",
]