"""定义多智能体共享任务状态。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WasteTaskState:
    """保存感知、图谱状态、规划和执行反馈。"""

    task_id: str
    goal: str
    perception_events: list[dict[str, Any]] = field(default_factory=list)
    knowledge_context: dict[str, Any] = field(default_factory=dict)
    graph_state: list[dict[str, Any]] = field(default_factory=list)
    risk_assessment: dict[str, Any] = field(default_factory=dict)
    planning_decision: dict[str, Any] = field(default_factory=dict)
    plan: list[dict[str, Any]] = field(default_factory=list)
    execution_feedback: list[dict[str, Any]] = field(default_factory=list)
