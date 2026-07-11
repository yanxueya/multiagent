"""三模式、单步滚动规划的 LangGraph 多智能体编排。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Literal

from agent_system.components.kg_writer import KGWriterBackend, commit_kg_write
from agent_system.components.validators import validate_action_plan
from agent_system.planner import build_single_action_plan
from agent_system.schemas.decision import CandidateSnapshot, SupervisorDecision
from agent_system.state import WasteAgentState, build_thread_config

AGENT_ORDER = ("supervisor_agent", "perception_agent", "action_planning_agent", "execution_agent")
DETERMINISTIC_NODE_ORDER = ("kg_writer", "human_review_interrupt")
COMPONENT_ORDER = DETERMINISTIC_NODE_ORDER
OPERATION_MODES = ("exploration", "supervised_execution", "human_collaboration")

CandidateLoader = Callable[[str, list[str], dict[str, Any]], Iterable[dict[str, Any] | CandidateSnapshot]]
PerceptionRunner = Callable[[str, WasteAgentState], dict[str, Any]]
ExecutionRunner = Callable[[str, dict[str, Any], WasteAgentState], dict[str, Any]]
ReviewPayloadLoader = Callable[[list[str], WasteAgentState], list[dict[str, Any]]]
KnowledgeQueryRunner = Callable[[dict[str, Any]], dict[str, Any]]
ActionExecutionLookup = Callable[[str], bool]


def _empty_candidates(scene_id: str, instance_ids: list[str], goal: dict[str, Any]) -> Iterable[dict[str, Any]]:
    return []


def _pending_perception(scene_id: str, state: WasteAgentState) -> dict[str, Any]:
    return {"status": "pending_external_perception", "scene_id": scene_id}


def _pending_execution(operation: str, plan: dict[str, Any], state: WasteAgentState) -> dict[str, Any]:
    return {"execution_status": "pending_external_execution", "operation": operation, "physical_attempt_started": False}


def _basic_review_payload(instance_ids: list[str], state: WasteAgentState) -> list[dict[str, Any]]:
    return [{"instance_id": instance_id} for instance_id in instance_ids]


def _missing_query_backend(goal: dict[str, Any]) -> dict[str, Any]:
    return {"status": "unavailable", "error": "knowledge_query_backend_not_connected"}


def _action_not_recorded(action_id: str) -> bool:
    return False


@dataclass(slots=True)
class GraphRuntime:
    """把外部感知、KG、ROS2 工具注入图中；这些服务本身不是 Agent。"""

    candidate_loader: CandidateLoader = _empty_candidates
    perception_runner: PerceptionRunner = _pending_perception
    execution_runner: ExecutionRunner = _pending_execution
    review_payload_loader: ReviewPayloadLoader = _basic_review_payload
    knowledge_query_runner: KnowledgeQueryRunner = _missing_query_backend
    action_already_executed: ActionExecutionLookup = _action_not_recorded
    kg_writer_backend: KGWriterBackend | None = None
    executed_action_ids: set[str] = field(default_factory=set)
    transient_objects: dict[str, Any] = field(default_factory=dict)


NodeName = Literal[
    "supervisor_agent",
    "perception_agent",
    "action_planning_agent",
    "execution_agent",
    "kg_writer",
    "human_review_interrupt",
]


def describe_graph() -> dict[str, object]:
    """返回六个图节点、三种模式和循环边界。"""

    return {
        "status": "langgraph_runtime_ready",
        "operation_modes": list(OPERATION_MODES),
        "agents": list(AGENT_ORDER),
        "deterministic_nodes": list(DETERMINISTIC_NODE_ORDER),
        "components": list(DETERMINISTIC_NODE_ORDER),
        "flow": [
            "START -> supervisor_agent",
            "supervisor_agent -> acquire_scene | perceive | human_review | plan | execute | complete | abort",
            "acquire_scene -> execution_agent -> perception_agent -> kg_writer -> supervisor_agent",
            "human_review -> human_review_interrupt -> kg_writer -> supervisor_agent",
            "plan -> action_planning_agent -> kg_writer -> supervisor_agent",
            "execute -> execution_agent -> kg_writer -> supervisor_agent",
            "complete | abort -> END",
        ],
        "planning_rule": "One physical action per plan; re-observe and replan after every physical attempt.",
        "state_boundary": "LangGraph stores control state and KG references only; KG stores domain facts and events.",
    }


def supervisor_node(state: WasteAgentState, *, runtime: GraphRuntime | None = None) -> WasteAgentState:
    """根据三种模式和当前控制状态选择唯一下一步。"""

    runtime = runtime or GraphRuntime()
    updates: WasteAgentState = {}
    mode = str(state.get("operation_mode", "human_collaboration"))
    if mode not in OPERATION_MODES:
        updates["error_message"] = f"unsupported_operation_mode={mode}"

    goal = dict(state.get("user_goal", {}))
    if mode == "exploration" and goal.get("goal_type") == "history_query" and not state.get("knowledge_query_result_ref"):
        query_result = runtime.knowledge_query_runner(goal)
        if query_result.get("status") == "complete" and query_result.get("result_ref"):
            updates["knowledge_query_result_ref"] = str(query_result["result_ref"])
            updates["task_completed"] = True
        else:
            updates["error_message"] = str(query_result.get("error", "knowledge_query_failed"))

    merged: WasteAgentState = dict(state)
    merged.update(updates)
    decision = choose_supervisor_decision(merged)
    updates.update(
        {
            "next_step": decision.next_step,
            "replan_required": decision.replan_required,
            "audit_trail": _append_audit(merged, "supervisor_agent", decision.to_dict()),
        }
    )
    if decision.next_step == "complete":
        updates["task_completed"] = True
    return updates


def choose_supervisor_decision(state: WasteAgentState) -> SupervisorDecision:
    """确定性路由规则约束 Supervisor，避免 LLM 绕过安全流程。"""

    if state.get("error_message"):
        return SupervisorDecision("abort", [], str(state["error_message"]), False)
    if state.get("task_completed"):
        return SupervisorDecision("complete", [], "The user goal is complete.", False)

    mode = str(state.get("operation_mode", "human_collaboration"))
    goal = dict(state.get("user_goal", {}))
    if mode == "exploration" and goal.get("goal_type") == "history_query":
        if state.get("knowledge_query_result_ref"):
            return SupervisorDecision("complete", [], "Historical KG query completed.", False)
        return SupervisorDecision("abort", [], "Historical KG query has no result.", False)

    if not state.get("current_scene_id") or not state.get("scene_is_fresh", False):
        return SupervisorDecision("acquire_scene", [], "A new RGB-D scene is required.", True)
    if not state.get("perception_completed", False):
        return SupervisorDecision("perceive", [], "The current Scene has not completed perception.", True)
    if mode == "exploration":
        return SupervisorDecision("complete", [], "Current environment exploration has been committed to KG.", False)

    review_ids = [str(item) for item in state.get("review_instance_ids", [])]
    if review_ids:
        return SupervisorDecision("human_review", review_ids, "Review-required objects affect the task.", True)
    plan = dict(state.get("current_plan", {}))
    if plan:
        if state.get("plan_validated", False):
            return SupervisorDecision("execute", [str(plan.get("target_instance_id", ""))], "A validated single-step plan is ready.", False)
        return SupervisorDecision("abort", [], "current_plan has not passed deterministic validation.", False)
    eligible_ids = [str(item) for item in state.get("eligible_instance_ids", [])]
    if eligible_ids:
        return SupervisorDecision("plan", eligible_ids, "Eligible instances require a single-step plan.", True)
    return SupervisorDecision("complete", [], "No eligible or review-required object remains.", False)


def perception_node(state: WasteAgentState, *, runtime: GraphRuntime | None = None) -> WasteAgentState:
    """协调外部 YOLO/VLM/D435i 子图并只生成受控 KG 写入载荷。"""

    runtime = runtime or GraphRuntime()
    scene_id = str(state.get("current_scene_id", ""))
    result = runtime.perception_runner(scene_id, state)
    if not result.get("perception_completed", False):
        return {
            "external_status": str(result.get("status", "pending_external_perception")),
            "perception_request": dict(result),
            "audit_trail": _append_audit(state, "perception_agent", {"status": result.get("status", "pending")}),
        }
    payload_keys = {
        "scene_id",
        "observation_ref",
        "updated_instance_ids",
        "accepted_instance_ids",
        "review_instance_ids",
        "unknown_instance_ids",
        "events",
        "perception_completed",
    }
    payload = {key: result[key] for key in payload_keys if key in result}
    payload.setdefault("scene_id", scene_id)
    if "observation" in result:
        observation_ref = str(result.get("observation_ref") or f"memory://observation/{scene_id}")
        runtime.transient_objects[observation_ref] = result["observation"]
        payload["observation_ref"] = observation_ref
    return {
        "external_status": "",
        "pending_kg_write": {"write_type": "perception", "payload": payload},
        "audit_trail": _append_audit(state, "perception_agent", {"scene_id": scene_id, "status": "completed"}),
    }


def action_planning_node(state: WasteAgentState, *, runtime: GraphRuntime | None = None) -> WasteAgentState:
    """临时读取候选并生成唯一 ActionPlan，不把候选快照写进 State。"""

    runtime = runtime or GraphRuntime()
    scene_id = str(state.get("current_scene_id", ""))
    eligible_ids = [str(item) for item in state.get("eligible_instance_ids", [])]
    candidates = runtime.candidate_loader(scene_id, eligible_ids, dict(state.get("user_goal", {})))
    plan = build_single_action_plan(
        candidates,
        scene_id=scene_id,
        user_goal=dict(state.get("user_goal", {})),
        scene_is_fresh=bool(state.get("scene_is_fresh", False)),
        review_instance_ids=state.get("review_instance_ids", []),
    ).to_dict()
    validation_errors = validate_action_plan(
        plan,
        current_scene_id=scene_id,
        scene_is_fresh=bool(state.get("scene_is_fresh", False)),
        eligible_instance_ids=eligible_ids,
    )
    if validation_errors:
        return {
            "error_message": ";".join(validation_errors),
            "plan_validated": False,
            "audit_trail": _append_audit(state, "action_planning_agent", {"validation_errors": validation_errors}),
        }
    return {
        "current_plan": plan,
        "plan_validated": False,
        "pending_kg_write": {
            "write_type": "planning",
            "payload": {"action_plan": plan, "planned_action": plan["action_type"], "reason": plan["reason"]},
        },
        "audit_trail": _append_audit(state, "action_planning_agent", {"action_id": plan["action_id"], "action_type": plan["action_type"]}),
    }


def execution_node(state: WasteAgentState, *, runtime: GraphRuntime | None = None) -> WasteAgentState:
    """以 acquire_scene 或 execute_action 模式调用受约束外部工具。"""

    runtime = runtime or GraphRuntime()
    if state.get("next_step") == "acquire_scene":
        result = runtime.execution_runner("acquire_scene", {}, state)
        if result.get("execution_status") != "scene_acquired" or not result.get("scene_id"):
            return {
                "external_status": str(result.get("execution_status", "pending_external_execution")),
                "execution_request": dict(result),
                "audit_trail": _append_audit(state, "execution_agent", {"operation": "acquire_scene", "status": result.get("execution_status", "pending")}),
            }
        return {
            "current_scene_id": str(result["scene_id"]),
            "scene_is_fresh": True,
            "perception_completed": False,
            "external_status": "",
            "execution_request": dict(result),
            "audit_trail": _append_audit(state, "execution_agent", {"operation": "acquire_scene", "scene_id": result["scene_id"]}),
        }

    plan = dict(state.get("current_plan", {}))
    validation_errors = validate_action_plan(
        plan,
        current_scene_id=str(state.get("current_scene_id", "")),
        scene_is_fresh=bool(state.get("scene_is_fresh", False)),
        eligible_instance_ids=state.get("eligible_instance_ids", []),
    )
    if validation_errors:
        return {"error_message": ";".join(validation_errors), "audit_trail": _append_audit(state, "execution_agent", {"refused": validation_errors})}

    action_type = str(plan.get("action_type", ""))
    if action_type == "rescan":
        return {"scene_is_fresh": False, "current_plan": {}, "plan_validated": False, "replan_required": True}
    if action_type == "request_human_review":
        return {"review_instance_ids": [str(plan.get("target_instance_id", ""))], "current_plan": {}, "plan_validated": False}
    if action_type == "no_action":
        return {"current_plan": {}, "plan_validated": False, "replan_required": False}

    action_id = str(plan.get("action_id", ""))
    if action_id in runtime.executed_action_ids or runtime.action_already_executed(action_id):
        return {"error_message": f"duplicate_action_id={action_id}"}
    result = runtime.execution_runner("execute_action", plan, state)
    if result.get("execution_status") == "pending_external_execution":
        return {"external_status": "pending_external_execution", "execution_request": dict(result)}

    physical_started = bool(result.get("physical_attempt_started", False))
    if not physical_started:
        remaining = [item for item in state.get("eligible_instance_ids", []) if item != plan.get("target_instance_id")]
        review_ids = [str(item) for item in state.get("review_instance_ids", [])]
        if not remaining and plan.get("target_instance_id"):
            review_ids.append(str(plan["target_instance_id"]))
        return {
            "last_execution_result": dict(result),
            "eligible_instance_ids": remaining,
            "review_instance_ids": list(dict.fromkeys(review_ids)),
            "current_plan": {},
            "plan_validated": False,
            "replan_required": True,
            "audit_trail": _append_audit(state, "execution_agent", {"action_id": action_id, "physical_attempt_started": False}),
        }

    if result.get("execution_status") not in {"success", "failure"}:
        return {"error_message": "physical attempt must finish with success or failure"}
    runtime.executed_action_ids.add(action_id)
    execution_result = {
        "action_id": action_id,
        "scene_id": str(state.get("current_scene_id", "")),
        "target_instance_id": str(plan.get("target_instance_id", "")),
        "execution_status": str(result["execution_status"]),
        "physical_attempt_started": True,
        "failure_reason": str(result.get("failure_reason", "")),
        "new_scene_required": True,
    }
    return {
        "external_status": "",
        "last_execution_result": execution_result,
        "pending_kg_write": {"write_type": "execution", "payload": {"execution_result": execution_result}},
        "audit_trail": _append_audit(state, "execution_agent", {"action_id": action_id, "physical_attempt_started": True}),
    }


def human_review_interrupt_node(state: WasteAgentState, *, runtime: GraphRuntime | None = None) -> WasteAgentState:
    """用 interrupt 暂停线程，并在恢复后生成 HumanReviewEvent 写入载荷。"""

    from langgraph.types import interrupt

    runtime = runtime or GraphRuntime()
    review_ids = [str(item) for item in state.get("review_instance_ids", [])]
    payload = {"review_instance_ids": review_ids, "objects": runtime.review_payload_loader(review_ids, state), "allowed_actions": ["confirm_existing", "mark_unknown", "approve_robot", "forbid_robot", "discard_detection"]}
    resume_value = interrupt(payload)
    review_results = resume_value if isinstance(resume_value, list) else [resume_value]
    if not all(isinstance(item, dict) and item.get("review_action") in payload["allowed_actions"] for item in review_results):
        raise ValueError("Invalid human review resume payload")
    for item in review_results:
        instance_id = str(item.get("instance_id", ""))
        if instance_id not in review_ids:
            raise ValueError(f"Human review target is not pending review: {instance_id}")
        if item.get("review_action") == "confirm_existing" and not item.get("confirmed_category"):
            raise ValueError("confirm_existing requires confirmed_category")
    return {
        "pending_kg_write": {
            "write_type": "human_review",
            "payload": {"scene_id": str(state.get("current_scene_id", "")), "review_results": review_results, "events": []},
        },
        "audit_trail": _append_audit(state, "human_review_interrupt", {"review_count": len(review_results)}),
    }


def kg_writer_node(state: WasteAgentState, *, runtime: GraphRuntime | None = None) -> WasteAgentState:
    """唯一 KG 写入口：严格校验载荷后提交，并更新控制状态。"""

    runtime = runtime or GraphRuntime()
    request = dict(state.get("pending_kg_write", {}))
    result = commit_kg_write(request, backend=runtime.kg_writer_backend)
    write_type = str(request.get("write_type", ""))
    payload = dict(request.get("payload", {}))
    updates: WasteAgentState = {"pending_kg_write": {}, "kg_write_result": result}
    if result.get("kg_summary_ref"):
        updates["kg_summary_ref"] = str(result["kg_summary_ref"])

    if write_type == "perception":
        updates.update(
            {
                "current_scene_id": str(payload.get("scene_id", state.get("current_scene_id", ""))),
                "scene_is_fresh": True,
                "perception_completed": bool(payload.get("perception_completed", True)),
                "review_instance_ids": [str(item) for item in result.get("review_instance_ids", payload.get("review_instance_ids", []))],
                "eligible_instance_ids": [str(item) for item in result.get("eligible_instance_ids", [])],
                "current_plan": {},
                "plan_validated": False,
                "replan_required": False,
            }
        )
    elif write_type == "planning":
        updates["plan_validated"] = True
    elif write_type == "human_review":
        updates.update(
            {
                "review_instance_ids": [str(item) for item in result.get("remaining_review_instance_ids", [])],
                "eligible_instance_ids": [str(item) for item in result.get("eligible_instance_ids", state.get("eligible_instance_ids", []))],
                "current_plan": {},
                "plan_validated": False,
                "replan_required": True,
            }
        )
    elif write_type == "execution":
        updates.update(
            {
                "scene_is_fresh": False,
                "perception_completed": False,
                "eligible_instance_ids": [],
                "current_plan": {},
                "plan_validated": False,
                "replan_required": True,
            }
        )
    updates["audit_trail"] = _append_audit(state, "kg_writer", {"write_type": write_type, "status": result.get("status", "committed")})
    return updates


def route_after_supervisor(state: WasteAgentState) -> str:
    return str(state.get("next_step", "abort"))


def route_after_execution(state: WasteAgentState) -> str:
    if state.get("external_status"):
        return "end"
    if state.get("pending_kg_write"):
        return "kg_writer"
    if state.get("execution_request", {}).get("execution_status") == "scene_acquired":
        return "perception_agent"
    if state.get("scene_is_fresh") and not state.get("perception_completed") and state.get("next_step") == "acquire_scene":
        return "perception_agent"
    return "supervisor_agent"


def route_after_perception(state: WasteAgentState) -> str:
    return "kg_writer" if state.get("pending_kg_write") else "end"


def build_langgraph_app(*, runtime: GraphRuntime | None = None, checkpointer: Any | None = None) -> Any:
    """构建带 checkpointer、条件路由和人工 interrupt 的真实 LangGraph。"""

    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph

    runtime = runtime or GraphRuntime()
    checkpointer = checkpointer or InMemorySaver()
    graph = StateGraph(WasteAgentState)
    graph.add_node("supervisor_agent", lambda state: supervisor_node(state, runtime=runtime))
    graph.add_node("perception_agent", lambda state: perception_node(state, runtime=runtime))
    graph.add_node("action_planning_agent", lambda state: action_planning_node(state, runtime=runtime))
    graph.add_node("execution_agent", lambda state: execution_node(state, runtime=runtime))
    graph.add_node("kg_writer", lambda state: kg_writer_node(state, runtime=runtime))
    graph.add_node("human_review_interrupt", lambda state: human_review_interrupt_node(state, runtime=runtime))

    graph.add_edge(START, "supervisor_agent")
    graph.add_conditional_edges(
        "supervisor_agent",
        route_after_supervisor,
        {
            "acquire_scene": "execution_agent",
            "perceive": "perception_agent",
            "human_review": "human_review_interrupt",
            "plan": "action_planning_agent",
            "execute": "execution_agent",
            "complete": END,
            "abort": END,
        },
    )
    graph.add_conditional_edges("execution_agent", route_after_execution, {"perception_agent": "perception_agent", "kg_writer": "kg_writer", "supervisor_agent": "supervisor_agent", "end": END})
    graph.add_conditional_edges("perception_agent", route_after_perception, {"kg_writer": "kg_writer", "end": END})
    graph.add_edge("action_planning_agent", "kg_writer")
    graph.add_edge("human_review_interrupt", "kg_writer")
    graph.add_edge("kg_writer", "supervisor_agent")
    return graph.compile(checkpointer=checkpointer)


def run_supervisor_step(initial_state: WasteAgentState, *, runtime: GraphRuntime | None = None) -> WasteAgentState:
    """不执行外部副作用，只运行一次 Supervisor 决策，供单元测试使用。"""

    state: WasteAgentState = dict(initial_state)
    state.update(supervisor_node(state, runtime=runtime))
    return state


def _append_audit(state: WasteAgentState, node: str, summary: dict[str, Any]) -> list[dict[str, Any]]:
    trail = [dict(item) for item in state.get("audit_trail", [])]
    trail.append({"node": node, "summary": dict(summary)})
    return trail


if __name__ == "__main__":
    print(describe_graph())
    print(build_thread_config("demo-thread"))
