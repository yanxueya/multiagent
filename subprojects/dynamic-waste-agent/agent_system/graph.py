"""LangGraph 风格的建筑废弃物多智能体编排。"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Callable, Literal, TypedDict

from agent_system.planner import build_ordered_plan

START_NODE = "__start__"
END_NODE = "__end__"

AGENT_ORDER = (
    "supervisor_agent",
    "perception_agent",
    "action_planning_agent",
    "execution_agent",
)

COMPONENT_ORDER = (
    "world_model_adapter",
    "risk_gate",
    "human_control_gate",
    "ros2_bridge",
    "feedback_update",
)


class WasteAgentState(TypedDict, total=False):
    """LangGraph 共享状态。"""

    task_id: str
    objective: str
    user_intent: str
    target_categories: list[str]
    perception_events: list[dict[str, Any]]
    rejected_candidates: list[dict[str, Any]]
    knowledge_context: dict[str, Any]
    graph_state: list[dict[str, Any]]
    risk_assessments: list[dict[str, Any]]
    planning_decision: dict[str, Any]
    execution_request: dict[str, Any]
    execution_feedback: list[dict[str, Any]]
    human_review_requests: list[dict[str, Any]]
    audit_trail: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    next_node: str


NodeName = Literal[
    "supervisor_agent",
    "perception_agent",
    "world_model_adapter",
    "risk_gate",
    "action_planning_agent",
    "human_control_gate",
    "execution_agent",
    "feedback_update",
    "no_executable_action",
]


def describe_graph() -> dict[str, object]:
    """返回当前编排图结构，同时区分真正 agent 与被调用组件。"""

    return {
        "status": "langgraph_runtime_ready",
        "agents": list(AGENT_ORDER),
        "components": list(COMPONENT_ORDER),
        "flow": [
            "START -> supervisor_agent",
            "supervisor_agent -> perception_agent",
            "perception_agent -> world_model_adapter",
            "world_model_adapter -> risk_gate",
            "risk_gate -> action_planning_agent",
            "action_planning_agent -> route_after_planning",
            "route_after_planning -> human_control_gate | execution_agent | no_executable_action",
            "human_control_gate -> feedback_update",
            "execution_agent -> feedback_update",
            "no_executable_action -> feedback_update",
            "feedback_update -> END",
        ],
        "decision_rule": "The KG provides category priors and current graph_state only; action_planning_agent performs feasibility filtering and computes priority_tier plus dynamic_priority_score at planning time.",
        "hard_boundaries": {
            "world_model_adapter": "KG state is not an agent; it projects category priors and current feasibility predicates but stores no planning score or action order.",
            "risk_gate": "Risk and safety gating is a policy component, not an autonomous agent.",
            "human_control_gate": "Human confirmation is an explicit control gate, not an LLM agent.",
            "action_planning_agent": "Plans ordered actions but does not send ROS2 commands.",
            "execution_agent": "Wraps approved plans as structured ROS2 bridge requests and never forwards free-form LLM text to the robot.",
        },
    }


def supervisor_node(state: WasteAgentState) -> WasteAgentState:
    """记录总体目标，并把任务交给固定的信息流。"""

    return {
        "audit_trail": _append_audit(
            state,
            "supervisor_agent",
            {
                "objective": state.get("objective", ""),
                "target_category_count": len(state.get("target_categories", [])),
            },
        )
    }


def perception_node(state: WasteAgentState) -> WasteAgentState:
    """标准化外部感知输入；当前阶段不在 agent 层运行 YOLO/VLM。"""

    events = [dict(item) for item in state.get("perception_events", [])]
    rejected = [dict(item) for item in state.get("rejected_candidates", [])]
    return {
        "perception_events": events,
        "rejected_candidates": rejected,
        "audit_trail": _append_audit(state, "perception_agent", {"event_count": len(events), "rejected_count": len(rejected)}),
    }


def world_model_adapter_node(state: WasteAgentState) -> WasteAgentState:
    """读取 KG 上下文并投影当前可行性状态，不计算规划优先级。"""

    context = dict(state.get("knowledge_context", {}))
    graph_state = [dict(item) for item in context.get("graph_state", state.get("graph_state", []))]
    candidates = context.get("candidates") or state.get("perception_events", [])
    if candidates and not context.get("candidates"):
        context["candidates"] = [dict(item) for item in candidates]
    return {
        "knowledge_context": context,
        "graph_state": graph_state,
        "audit_trail": _append_audit(state, "world_model_adapter", {"graph_state_count": len(graph_state), "priority_source": "action_planning_agent"}),
    }


def risk_gate_node(state: WasteAgentState) -> WasteAgentState:
    """基于 graph_state 做保守风险门控。"""

    assessments: list[dict[str, Any]] = []
    for item in state.get("graph_state", []):
        graph_item = dict(item)
        requires_review = bool(graph_item.get("requires_review", False))
        blocked = bool(graph_item.get("blocked", False))
        risk_level = str(graph_item.get("risk_level", "unknown"))
        attempt_count = int(graph_item.get("attempt_count", 0) or 0)
        recognition_status = str(graph_item.get("recognition_status", "review_required"))
        handling_policy = str(graph_item.get("current_handling_policy", "human_confirmation_required"))
        auto_allowed = bool(graph_item.get("can_attempt_now", False))
        auto_allowed = (
            auto_allowed
            and recognition_status == "accepted"
            and handling_policy == "auto_allowed"
            and not requires_review
            and not blocked
            and attempt_count < 2
            and risk_level not in {"high", "critical", "hazardous"}
        )
        reasons: list[str] = []
        if requires_review:
            reasons.append("requires_review")
        if recognition_status != "accepted":
            reasons.append(f"recognition_status={recognition_status}")
        if handling_policy != "auto_allowed":
            reasons.append(f"current_handling_policy={handling_policy}")
        if blocked:
            reasons.append("blocked")
        if attempt_count >= 2:
            reasons.append("attempt_count_exceeded")
        if risk_level in {"high", "critical", "hazardous"}:
            reasons.append("high_risk")
        assessments.append(
            {
                "instance_id": str(graph_item.get("instance_id", "unknown")),
                "risk_level": risk_level,
                "auto_grasp_allowed": auto_allowed,
                "requires_human_review": requires_review,
                "risk_reasons": reasons,
            }
        )
    return {
        "risk_assessments": assessments,
        "audit_trail": _append_audit(state, "risk_gate", {"assessment_count": len(assessments)}),
    }


def action_planning_node(state: WasteAgentState) -> WasteAgentState:
    """基于 graph_state 和风险门控动态计算优先级并生成操作序列。"""

    blocked_by_risk = {
        item["instance_id"]
        for item in state.get("risk_assessments", [])
        if not item.get("auto_grasp_allowed", False)
    }
    graph_state = []
    for item in state.get("graph_state", []):
        state_item = dict(item)
        if state_item.get("instance_id") in blocked_by_risk:
            state_item["can_attempt_now"] = False
            reasons = list(state_item.get("feasibility_reasons", []))
            if "risk_gate_blocked" not in reasons:
                reasons.append("risk_gate_blocked")
            state_item["feasibility_reasons"] = reasons
        graph_state.append(state_item)
    decision = build_ordered_plan(
        graph_state,
        objective=str(state.get("objective", "")),
    )
    return {
        "graph_state": graph_state,
        "planning_decision": _to_plain_dict(decision),
        "audit_trail": _append_audit(state, "action_planning_agent", {"step_count": len(decision.steps), "deferred_count": len(decision.deferred)}),
    }


def route_after_planning(state: WasteAgentState) -> NodeName:
    """LangGraph 条件边：先处理人工确认，再执行可自动动作。"""

    if any(item.get("requires_human_review") for item in state.get("risk_assessments", [])):
        return "human_control_gate"
    if state.get("planning_decision", {}).get("steps"):
        return "execution_agent"
    return "no_executable_action"


def human_control_gate_node(state: WasteAgentState) -> WasteAgentState:
    """形成人工复核请求，等待 UI 或人工确认回写。"""

    requests = []
    for item in state.get("risk_assessments", []):
        if item.get("requires_human_review"):
            requests.append(
                {
                    "instance_id": item.get("instance_id"),
                    "reason": item.get("risk_reasons", ["requires_human_review"]),
                    "status": "pending_human_review",
                }
            )
    return {
        "next_node": "human_control_gate",
        "human_review_requests": requests,
        "audit_trail": _append_audit(state, "human_control_gate", {"request_count": len(requests)}),
    }


def execution_node(state: WasteAgentState) -> WasteAgentState:
    """把已批准计划封装为 ROS2 bridge 请求；当前不启动 ROS2。"""

    steps = state.get("planning_decision", {}).get("steps", [])
    if not steps:
        return {
            "next_node": "execution_agent",
            "execution_request": {"status": "skipped", "bridge": "ros2_bridge", "reason": "no_plan_step"},
            "audit_trail": _append_audit(state, "execution_agent", {"status": "skipped"}),
        }
    first_step = dict(steps[0])
    return {
        "next_node": "execution_agent",
        "execution_request": {
            "status": "pending_ros2_bridge",
            "bridge": "ros2_bridge",
            "action_type": first_step.get("action_type"),
            "target_instance_id": first_step.get("target_instance_id"),
            "parameters": {
                "preconditions": first_step.get("preconditions", []),
                "failure_recovery": first_step.get("failure_recovery"),
            },
            "requires_confirmation": False,
        },
        "audit_trail": _append_audit(state, "execution_agent", {"target": first_step.get("target_instance_id"), "bridge": "ros2_bridge"}),
    }


def no_executable_action_node(state: WasteAgentState) -> WasteAgentState:
    """没有可执行动作时保留可追踪状态，而不是生成空白计划。"""

    return {
        "next_node": "no_executable_action",
        "execution_request": {"status": "skipped", "bridge": "ros2_bridge", "reason": "no_executable_action"},
        "audit_trail": _append_audit(state, "no_executable_action", {}),
    }


def feedback_update_node(state: WasteAgentState) -> WasteAgentState:
    """将执行或人工复核状态整理为未来 KG 回写入口。"""

    feedback = [dict(item) for item in state.get("execution_feedback", [])]
    if state.get("execution_request"):
        feedback.append({"source": "agent_graph", "execution_request": dict(state["execution_request"])})
    if state.get("human_review_requests"):
        feedback.append({"source": "human_control_gate", "requests": list(state["human_review_requests"])})
    return {
        "execution_feedback": feedback,
        "audit_trail": _append_audit(state, "feedback_update", {"feedback_count": len(feedback)}),
    }


def build_langgraph_app() -> Any:
    """构建真实 LangGraph app；未安装 langgraph 时给出明确错误。"""

    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise RuntimeError("langgraph is not installed. Install it with: python -m pip install langgraph") from exc

    graph = StateGraph(WasteAgentState)
    graph.add_node("supervisor_agent", supervisor_node)
    graph.add_node("perception_agent", perception_node)
    graph.add_node("world_model_adapter", world_model_adapter_node)
    graph.add_node("risk_gate", risk_gate_node)
    graph.add_node("action_planning_agent", action_planning_node)
    graph.add_node("human_control_gate", human_control_gate_node)
    graph.add_node("execution_agent", execution_node)
    graph.add_node("no_executable_action", no_executable_action_node)
    graph.add_node("feedback_update", feedback_update_node)

    graph.add_edge(START, "supervisor_agent")
    graph.add_edge("supervisor_agent", "perception_agent")
    graph.add_edge("perception_agent", "world_model_adapter")
    graph.add_edge("world_model_adapter", "risk_gate")
    graph.add_edge("risk_gate", "action_planning_agent")
    graph.add_conditional_edges(
        "action_planning_agent",
        route_after_planning,
        {
            "human_control_gate": "human_control_gate",
            "execution_agent": "execution_agent",
            "no_executable_action": "no_executable_action",
        },
    )
    graph.add_edge("human_control_gate", "feedback_update")
    graph.add_edge("execution_agent", "feedback_update")
    graph.add_edge("no_executable_action", "feedback_update")
    graph.add_edge("feedback_update", END)
    return graph.compile()


def run_dry_graph(initial_state: WasteAgentState) -> WasteAgentState:
    """不依赖 LangGraph 的顺序执行版本，用于单元测试和无依赖环境。"""

    state: WasteAgentState = dict(initial_state)
    for node in (supervisor_node, perception_node, world_model_adapter_node, risk_gate_node, action_planning_node):
        state.update(node(state))
    next_node = route_after_planning(state)
    state["next_node"] = next_node
    branch: dict[NodeName, Callable[[WasteAgentState], WasteAgentState]] = {
        "human_control_gate": human_control_gate_node,
        "execution_agent": execution_node,
        "no_executable_action": no_executable_action_node,
    }
    state.update(branch[next_node](state))
    state.update(feedback_update_node(state))
    return state


# 旧名称保留为兼容别名；新代码应使用 world_model_adapter/risk_gate/action_planning/human_control。
knowledge_node = world_model_adapter_node
risk_node = risk_gate_node
planning_node = action_planning_node
human_review_node = human_control_gate_node


def _append_audit(state: WasteAgentState, node: str, summary: dict[str, Any]) -> list[dict[str, Any]]:
    trail = [dict(item) for item in state.get("audit_trail", [])]
    trail.append({"node": node, "summary": dict(summary)})
    return trail


def _to_plain_dict(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return dict(value)
    raise TypeError(f"Cannot convert {type(value)!r} to dict")


if __name__ == "__main__":
    print(describe_graph())
