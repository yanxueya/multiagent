"""定义 actions 多智能体占位逻辑。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RobotAction:
    action_type: str
    target_id: str
    parameters: dict[str, object]
