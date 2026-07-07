"""定义 state 多智能体占位逻辑。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WasteTaskState:
    """Minimal state shape for perception, KG, risk, planning, and execution."""

    task_id: str
    goal: str
    perception_events: list[dict[str, Any]] = field(default_factory=list)
    knowledge_context: dict[str, Any] = field(default_factory=dict)
    risk_assessment: dict[str, Any] = field(default_factory=dict)
    plan: list[dict[str, Any]] = field(default_factory=list)
    execution_feedback: list[dict[str, Any]] = field(default_factory=list)
