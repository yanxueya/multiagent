"""定义 LangGraph 线程级控制状态，不复制完整知识图谱。"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

OperationMode = Literal["exploration", "supervised_execution", "human_collaboration"]
NextStep = Literal["acquire_scene", "perceive", "human_review", "plan", "execute", "complete", "abort"]


class WasteAgentState(TypedDict, total=False):
    """一次分拣任务的线程状态；领域事实仍由 KG 持久化。"""

    messages: list[dict[str, Any]]
    task_id: str
    operation_mode: OperationMode
    user_goal: dict[str, Any]
    current_scene_id: str
    scene_is_fresh: bool
    perception_completed: bool
    review_instance_ids: list[str]
    eligible_instance_ids: list[str]
    current_plan: dict[str, Any]
    plan_validated: bool
    last_execution_result: dict[str, Any]
    replan_required: bool
    task_completed: bool
    next_step: NextStep
    error_message: str
    external_status: str
    kg_summary_ref: str
    knowledge_query_result_ref: str
    pending_kg_write: dict[str, Any]
    kg_write_result: dict[str, Any]
    execution_request: dict[str, Any]
    perception_request: dict[str, Any]
    audit_trail: list[dict[str, Any]]


def build_thread_config(thread_id: str) -> dict[str, dict[str, str]]:
    """创建 LangGraph checkpointer 所需的稳定线程配置。"""

    normalized = thread_id.strip()
    if not normalized:
        raise ValueError("thread_id must not be empty")
    return {"configurable": {"thread_id": normalized}}
