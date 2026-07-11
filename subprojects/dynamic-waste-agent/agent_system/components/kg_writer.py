"""验证 Agent 结构化载荷，并通过唯一入口提交知识图谱更新。"""

from __future__ import annotations

from typing import Any, Callable

KGWriterBackend = Callable[[dict[str, Any]], dict[str, Any]]

_ALLOWED_PAYLOAD_FIELDS = {
    "perception": {"scene_id", "updated_instance_ids", "accepted_instance_ids", "review_instance_ids", "unknown_instance_ids", "eligible_instance_ids", "events", "perception_completed"},
    "planning": {"action_plan", "planned_action", "reason"},
    "human_review": {"review_results", "events"},
    "execution": {"execution_result"},
}


def validate_kg_write(request: dict[str, Any]) -> dict[str, Any]:
    """拒绝未知写入类型、未知载荷字段和自由 Cypher。"""

    write_type = str(request.get("write_type", ""))
    if write_type not in _ALLOWED_PAYLOAD_FIELDS:
        raise ValueError(f"Unsupported KG write_type: {write_type}")
    if set(request) - {"write_type", "payload"}:
        raise ValueError("KG write envelope contains undefined fields")
    payload = request.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("KG write payload must be an object")
    unsupported = set(payload) - _ALLOWED_PAYLOAD_FIELDS[write_type]
    if unsupported:
        raise ValueError(f"Undefined {write_type} payload fields: {sorted(unsupported)}")
    if any(key.lower() in {"cypher", "query", "neo4j_query"} for key in payload):
        raise ValueError("Agents must not submit arbitrary Cypher")
    return {"write_type": write_type, "payload": dict(payload)}


def commit_kg_write(request: dict[str, Any], *, backend: KGWriterBackend | None = None) -> dict[str, Any]:
    """校验后调用确定性后端；未接后端时只返回可审计预览。"""

    validated = validate_kg_write(request)
    if backend is None:
        return {"status": "validated_only", "write_type": validated["write_type"]}
    result = backend(validated)
    if not isinstance(result, dict):
        raise TypeError("KG writer backend must return a dictionary")
    return dict(result)
