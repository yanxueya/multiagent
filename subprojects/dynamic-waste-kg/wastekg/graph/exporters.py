"""导出知识图谱快照、事件和 Neo4j Cypher。"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List

from wastekg.core.models import GraphEvent, ObjectInstance, RelationEdge
from wastekg.graph.store import KnowledgeGraph


def _sanitize_neo4j_type(value: str, fallback: str = "RELATED_TO") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", value.upper()).strip("_")
    if not cleaned:
        return fallback
    if cleaned[0].isdigit():
        cleaned = f"R_{cleaned}"
    return cleaned


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _neo4j_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return repr(value)
    if isinstance(value, str):
        # PowerShell 管道传给 docker exec 时容易破坏非 ASCII 字符；
        # 用 JSON/Cypher 兼容的 unicode 转义保证导入语句稳定。
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_neo4j_literal(item) for item in value) + "]"
    if isinstance(value, dict):
        inner = ", ".join(f"{_neo4j_key(str(key))}: {_neo4j_literal(item)}" for key, item in value.items())
        return "{ " + inner + " }"
    return json.dumps(str(value), ensure_ascii=False)


def _neo4j_key(value: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        return value
    return "`" + value.replace("`", "``") + "`"


def _neo4j_map(properties: Dict[str, Any]) -> str:
    return "{ " + ", ".join(f"{_neo4j_key(key)}: {_neo4j_literal(value)}" for key, value in properties.items()) + " }"


def _is_neo4j_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, bool, int, float))


def _normalize_neo4j_properties(properties: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key, value in properties.items():
        if _is_neo4j_scalar(value):
            normalized[key] = value
        elif isinstance(value, (list, tuple)) and all(_is_neo4j_scalar(item) for item in value):
            normalized[key] = list(value)
        else:
            # Neo4j 节点属性不能直接保存二维列表或字典，复杂几何/候选抓取信息用 JSON 保真存储。
            normalized[f"{key}_json"] = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return normalized


def _flatten_category_props(spec) -> Dict[str, Any]:
    return _normalize_neo4j_properties({
        "name": spec.name,
        "category": spec.category,
        "material": spec.material,
        "risk_level": spec.risk_level,
        "fragility": spec.fragility,
        "graspability": spec.graspability,
        "pollution_level": spec.pollution_level,
        "recognition_difficulty": spec.recognition_difficulty,
        "handling_mode": spec.handling_mode,
        "grasp_difficulty": spec.grasp_difficulty,
        "needs_llm_review": spec.needs_llm_review,
        "auto_processable": spec.auto_processable,
        "recyclability": spec.recyclability,
        "semantic_tags": list(spec.semantic_tags),
        "confidence_prior": spec.confidence_prior,
        "description": spec.description,
        "source_refs": list(spec.source_refs),
        "notes": spec.notes,
    })


def _flatten_instance_props(instance: ObjectInstance) -> Dict[str, Any]:
    props = instance.to_dict()
    metadata = dict(props.pop("metadata", {}))
    props["metadata_json"] = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    return _normalize_neo4j_properties(props)


def _flatten_relation_props(edge: RelationEdge) -> Dict[str, Any]:
    props = edge.to_dict()
    metadata = dict(props.pop("metadata", {}))
    props["metadata_json"] = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    return _normalize_neo4j_properties(props)


def _flatten_event_props(event: GraphEvent) -> Dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "subject_id": event.subject_id,
        "relation": event.relation,
        "before_state_json": json.dumps(event.before_state, ensure_ascii=False, sort_keys=True),
        "after_state_json": json.dumps(event.after_state, ensure_ascii=False, sort_keys=True),
        "source": event.source,
        "timestamp": event.timestamp.isoformat(),
        "confidence_delta": event.confidence_delta,
        "metadata_json": json.dumps(dict(event.metadata), ensure_ascii=False, sort_keys=True),
    }


def graph_to_json_snapshot(graph: KnowledgeGraph) -> Dict[str, Any]:
    # 直接导出一个稳定的 JSON 快照，适合保存到文件、传给前端或调试。
    return graph.to_dict()


def graph_events_to_jsonl(graph: KnowledgeGraph) -> str:
    # 事件日志采用 JSONL 形式最方便：一行一条事件，便于后续增量追加和流式消费。
    return "\n".join(_json(event.to_dict()) for event in graph.events)


def graph_to_mermaid(graph: KnowledgeGraph, *, title: str = "Dynamic Waste Knowledge Graph") -> str:
    lines: List[str] = [
        "flowchart TD",
        f'  %% {title}',
        "  subgraph LT[长期知识层]",
    ]
    for name, spec in graph.categories.items():
        label = f"{name}\\n{spec.category}\\nR:{spec.risk_level}\\nF:{spec.fragility}\\nG:{spec.graspability}"
        lines.append(f'    LT_{_sanitize_neo4j_type(name)}["{label}"]')
        lines.append(f"    class LT_{_sanitize_neo4j_type(name)} category")
    lines.append("  end")

    lines.append("  subgraph ST[短期记忆层]")
    for instance_id, instance in graph.instances.items():
        label = f"{instance_id}\\n{instance.class_name}\\nP:{instance.priority}\\n{instance.task_status}"
        lines.append(f'    ST_{_sanitize_neo4j_type(instance_id)}["{label}"]')
        if instance.risk_level in {"high", "critical", "hazardous"}:
            lines.append(f"    class ST_{_sanitize_neo4j_type(instance_id)} hazard")
        else:
            lines.append(f"    class ST_{_sanitize_neo4j_type(instance_id)} instance")
        if instance.class_name in graph.categories:
            lines.append(
                f"    LT_{_sanitize_neo4j_type(instance.class_name)} -->|belongs_to| ST_{_sanitize_neo4j_type(instance_id)}"
            )
    lines.append("  end")

    lines.append("  subgraph EV[事件日志层]")
    for event in graph.events[-25:]:
        event_node = f"EV_{_sanitize_neo4j_type(event.event_id)}"
        label = f"{event.event_type}\\n{event.timestamp.isoformat()}"
        lines.append(f'    {event_node}["{label}"]')
        lines.append(f"    class {event_node} event")
        if event.subject_id in graph.instances:
            lines.append(f"    {event_node} --> ST_{_sanitize_neo4j_type(event.subject_id)}")
        elif event.subject_id in graph.categories:
            lines.append(f"    {event_node} --> LT_{_sanitize_neo4j_type(event.subject_id)}")
    lines.append("  end")

    for edge in graph.edges.values():
        lines.append(
            f"  ST_{_sanitize_neo4j_type(edge.source_id)} -->|{edge.relation}| ST_{_sanitize_neo4j_type(edge.target_id)}"
        )

    lines.extend(
        [
            "  classDef category fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20,stroke-width:1px;",
            "  classDef instance fill:#e3f2fd,stroke:#1565c0,color:#0d47a1,stroke-width:1px;",
            "  classDef hazard fill:#ffebee,stroke:#c62828,color:#b71c1c,stroke-width:2px;",
            "  classDef event fill:#fff3e0,stroke:#ef6c00,color:#e65100,stroke-width:1px;",
        ]
    )
    return "\n".join(lines)


def graph_to_neo4j_cypher(graph: KnowledgeGraph) -> List[str]:
    statements: List[str] = []
    for spec in graph.categories.values():
        statements.append(_category_merge_statement(spec))

    for instance in graph.instances.values():
        statements.extend(_instance_merge_statements(instance))

    for edge in graph.edges.values():
        statements.append(_relation_merge_statement(edge))

    for event in graph.events:
        statements.extend(_event_merge_statement(event, graph))

    return statements


def _instance_merge_statements(instance: ObjectInstance) -> List[str]:
    props = _flatten_instance_props(instance)
    statements = [f"MERGE (i:Instance {_neo4j_map({'instance_id': instance.instance_id})}) SET i += {_neo4j_map(props)}"]
    if instance.class_name:
        statements.append(
            f"MATCH (i:Instance {{instance_id: {_neo4j_literal(instance.instance_id)}}}), "
            f"(c:Category {{name: {_neo4j_literal(instance.class_name)}}}) MERGE (i)-[:OF_CATEGORY]->(c)"
        )
    return statements


def _relation_merge_statement(edge: RelationEdge) -> str:
    relation_type = _sanitize_neo4j_type(edge.relation, fallback="RELATED_TO")
    props = _flatten_relation_props(edge)
    props["source_id"] = edge.source_id
    props["relation"] = edge.relation
    props["target_id"] = edge.target_id
    return (
        f"MATCH (s:Instance {{instance_id: {_neo4j_literal(edge.source_id)}}}), "
        f"(t:Instance {{instance_id: {_neo4j_literal(edge.target_id)}}}) "
        f"MERGE (s)-[r:{relation_type}]->(t) "
        f"SET r += {_neo4j_map(props)}"
    )


def _category_merge_statement(spec) -> str:
    props = _flatten_category_props(spec)
    return f"MERGE (c:Category {{name: {_neo4j_literal(spec.name)}}}) SET c += {_neo4j_map(props)}"

def _event_merge_statement(event: GraphEvent, graph: KnowledgeGraph) -> List[str]:
    event_props = _flatten_event_props(event)
    lines = [f"MERGE (e:Event {{event_id: {_neo4j_literal(event.event_id)}}}) SET e += {_neo4j_map(event_props)}"]
    if event.subject_id in graph.instances:
        lines.append(
            f"MATCH (e:Event {{event_id: {_neo4j_literal(event.event_id)}}}), "
            f"(i:Instance {{instance_id: {_neo4j_literal(event.subject_id)}}}) MERGE (e)-[:ABOUT_INSTANCE]->(i)"
        )
    elif event.subject_id in graph.categories:
        lines.append(
            f"MATCH (e:Event {{event_id: {_neo4j_literal(event.event_id)}}}), "
            f"(c:Category {{name: {_neo4j_literal(event.subject_id)}}}) MERGE (e)-[:ABOUT_CATEGORY]->(c)"
        )
    after_state = event.after_state if isinstance(event.after_state, dict) else {}
    source_id = after_state.get("source_id")
    target_id = after_state.get("target_id")
    if source_id in graph.instances:
        lines.append(
            f"MATCH (e:Event {{event_id: {_neo4j_literal(event.event_id)}}}), "
            f"(i:Instance {{instance_id: {_neo4j_literal(source_id)}}}) MERGE (e)-[:SOURCE_INSTANCE]->(i)"
        )
    if target_id in graph.instances:
        lines.append(
            f"MATCH (e:Event {{event_id: {_neo4j_literal(event.event_id)}}}), "
            f"(i:Instance {{instance_id: {_neo4j_literal(target_id)}}}) MERGE (e)-[:TARGET_INSTANCE]->(i)"
        )
    return lines
