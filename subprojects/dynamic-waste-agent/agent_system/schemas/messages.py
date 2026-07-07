"""定义 messages 多智能体占位逻辑。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentMessage:
    sender: str
    receiver: str
    content: dict[str, object]
