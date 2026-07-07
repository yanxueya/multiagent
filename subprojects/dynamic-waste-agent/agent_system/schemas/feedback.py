"""定义 feedback 多智能体占位逻辑。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionFeedback:
    task_id: str
    status: str
    message: str
