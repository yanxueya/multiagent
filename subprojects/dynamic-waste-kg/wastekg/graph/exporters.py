"""把三层知识图谱导出为 JSON、Mermaid、JSONL 和 Neo4j Cypher。"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

from wastekg.core.models import GraphEvent
from wastekg.graph.store import KnowledgeGraph


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", value)


def _neo4j_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, dict, tuple)):
        value = json.dumps(value, ensure_ascii=True, sort_keys=True)
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'"


def _neo4j_map(properties: Dict[str, Any]) -> str:
    return "{" + ", ".join(f"{key}: {_neo4j_literal(value)}" for key, value in properties.items()) + "}"


def graph_to_json_snapshot(graph: KnowledgeGraph) -> Dict[str, Any]:
    return graph.to_dict()


def graph_events_to_jsonl(graph: KnowledgeGraph) -> str:
    return "\n".join(_json(event.to_dict()) for event in graph.events)


def graph_to_mermaid(graph: KnowledgeGraph, *, title: str = "Dynamic Waste Knowledge Graph") -> str:
    lines = ["flowchart TD", f"  %% {title}", "  subgraph LT[长期知识层]"]
    for name, spec in graph.categories.items():
        node_id = f"CAT_{_safe(name)}"
        lines.append(f'    {node_id}["{name}\\nR:{spec.risk_level} F:{spec.fragility} G:{spec.graspability_prior}"]')
        lines.append(f"    class {node_id} category")
    lines.append("  end")

    lines.append("  subgraph ST[短期记忆层]")
    for scene_id in graph.scenes:
        lines.append(f'    SC_{_safe(scene_id)}["Scene\\n{scene_id}"]')
        lines.append(f"    class SC_{_safe(scene_id)} scene")
    for instance_id, instance in graph.instances.items():
        lines.append(f'    IN_{_safe(instance_id)}["{instance_id}\\n{instance.recognition_status}\\n{instance.current_handling_policy}"]')
        lines.append(f"    class IN_{_safe(instance_id)} instance")
    for sample_id in graph.unknown_samples:
        lines.append(f'    US_{_safe(sample_id)}["UnknownSample\\n{sample_id}"]')
        lines.append(f"    class US_{_safe(sample_id)} unknown")
    for cluster_id in graph.unknown_clusters:
        lines.append(f'    UC_{_safe(cluster_id)}["UnknownCluster\\n{cluster_id}"]')
        lines.append(f"    class UC_{_safe(cluster_id)} unknown")
    lines.append("  end")

    lines.append("  subgraph EV[事件日志层]")
    for event in graph.events:
        lines.append(f'    EV_{_safe(event.event_id)}["{event.event_type}\\n{event.event_source}"]')
        lines.append(f"    class EV_{_safe(event.event_id)} event")
    lines.append("  end")

    node_ids = _mermaid_node_ids(graph)
    for edge in graph.edges.values():
        source = node_ids.get(edge.source_id)
        target = node_ids.get(edge.target_id)
        if source and target:
            lines.append(f"  {source} -->|{edge.relation}| {target}")
    lines.extend(
        [
            "  classDef category fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20;",
            "  classDef scene fill:#ede7f6,stroke:#5e35b1,color:#311b92;",
            "  classDef instance fill:#e3f2fd,stroke:#1565c0,color:#0d47a1;",
            "  classDef unknown fill:#fff8e1,stroke:#f9a825,color:#e65100;",
            "  classDef event fill:#fce4ec,stroke:#ad1457,color:#880e4f;",
        ]
    )
    return "\n".join(lines)


def graph_to_neo4j_cypher(graph: KnowledgeGraph) -> List[str]:
    statements: List[str] = []
    node_refs: Dict[str, Tuple[str, str, str]] = {}
    for name, spec in graph.categories.items():
        props = spec.to_dict()
        props["visual_prototype_json"] = json.dumps(props.pop("visual_prototype"), ensure_ascii=True, sort_keys=True)
        statements.append(f"MERGE (n:WasteCategory {{category_name: {_neo4j_literal(name)}}}) SET n += {_neo4j_map(props)}")
        node_refs[name] = ("WasteCategory", "category_name", name)
    for scene_id, scene in graph.scenes.items():
        statements.append(f"MERGE (n:Scene {{scene_id: {_neo4j_literal(scene_id)}}}) SET n += {_neo4j_map(scene.to_dict())}")
        node_refs[scene_id] = ("Scene", "scene_id", scene_id)
    for instance_id, instance in graph.instances.items():
        statements.append(f"MERGE (n:ObjectInstance {{instance_id: {_neo4j_literal(instance_id)}}}) SET n += {_neo4j_map(instance.to_dict())}")
        node_refs[instance_id] = ("ObjectInstance", "instance_id", instance_id)
    for sample_id, sample in graph.unknown_samples.items():
        props = sample.to_dict()
        props["yolo_topk_json"] = json.dumps(props.pop("yolo_topk"), ensure_ascii=True, sort_keys=True)
        props["vlm_attributes_json"] = json.dumps(props.pop("vlm_attributes"), ensure_ascii=True, sort_keys=True)
        statements.append(f"MERGE (n:UnknownSample {{sample_id: {_neo4j_literal(sample_id)}}}) SET n += {_neo4j_map(props)}")
        node_refs[sample_id] = ("UnknownSample", "sample_id", sample_id)
    for cluster_id, cluster in graph.unknown_clusters.items():
        props = cluster.to_dict()
        props["prototype_attributes_json"] = json.dumps(props.pop("prototype_attributes"), ensure_ascii=True, sort_keys=True)
        statements.append(f"MERGE (n:UnknownCluster {{cluster_id: {_neo4j_literal(cluster_id)}}}) SET n += {_neo4j_map(props)}")
        node_refs[cluster_id] = ("UnknownCluster", "cluster_id", cluster_id)
    for event in graph.events:
        props = _event_props(event)
        label = event.event_type
        statements.append(f"MERGE (n:Event:{label} {{event_id: {_neo4j_literal(event.event_id)}}}) SET n += {_neo4j_map(props)}")
        node_refs[event.event_id] = (label, "event_id", event.event_id)
    for edge in graph.edges.values():
        source = node_refs.get(edge.source_id)
        target = node_refs.get(edge.target_id)
        if source is None or target is None:
            continue
        statements.append(_relation_statement(source, edge.relation, target))
    return statements


def _event_props(event: GraphEvent) -> Dict[str, Any]:
    props = event.to_dict()
    for key, value in list(props.items()):
        if isinstance(value, (dict, list, tuple)):
            props[f"{key}_json"] = json.dumps(value, ensure_ascii=True, sort_keys=True)
            del props[key]
    return props


def _relation_statement(source: Tuple[str, str, str], relation: str, target: Tuple[str, str, str]) -> str:
    source_label, source_key, source_value = source
    target_label, target_key, target_value = target
    return (
        f"MATCH (s:{source_label} {{{source_key}: {_neo4j_literal(source_value)}}}), "
        f"(t:{target_label} {{{target_key}: {_neo4j_literal(target_value)}}}) "
        f"MERGE (s)-[:{relation}]->(t)"
    )


def _mermaid_node_ids(graph: KnowledgeGraph) -> Dict[str, str]:
    result = {name: f"CAT_{_safe(name)}" for name in graph.categories}
    result.update({scene_id: f"SC_{_safe(scene_id)}" for scene_id in graph.scenes})
    result.update({instance_id: f"IN_{_safe(instance_id)}" for instance_id in graph.instances})
    result.update({sample_id: f"US_{_safe(sample_id)}" for sample_id in graph.unknown_samples})
    result.update({cluster_id: f"UC_{_safe(cluster_id)}" for cluster_id in graph.unknown_clusters})
    result.update({event.event_id: f"EV_{_safe(event.event_id)}" for event in graph.events})
    return result
