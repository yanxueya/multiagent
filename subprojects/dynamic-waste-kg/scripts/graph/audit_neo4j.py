"""只读审计在线 Neo4j 是否符合三层知识图谱权威结构。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any

from neo4j import GraphDatabase

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.core.knowledge_base import DEFAULT_CATEGORY_SPECS
from wastekg.core.models import EVENT_ATTRIBUTE_FIELDS, EVENT_SOURCES
from wastekg.core.schema import CATEGORY_ATTRIBUTE_ENUMS, INSTANCE_ATTRIBUTE_ENUMS, knowledge_schema_snapshot
from wastekg.graph.store import ALLOWED_RELATIONS


def _records(session: Any, query: str) -> list[dict[str, Any]]:
    return [dict(record) for record in session.run(query)]


def _decode_json_property(properties: dict[str, Any], key: str) -> Any:
    value = properties.get(f"{key}_json", properties.get(key))
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def main() -> int:
    password = os.environ.get("WASTEKG_NEO4J_PASSWORD", "")
    if not password:
        raise ValueError("WASTEKG_NEO4J_PASSWORD is required")
    uri = os.environ.get("WASTEKG_NEO4J_URI", "bolt://localhost:7687")
    driver = GraphDatabase.driver(uri, auth=(os.environ.get("WASTEKG_NEO4J_USER", "neo4j"), password))
    try:
        with driver.session(database=os.environ.get("WASTEKG_NEO4J_DATABASE", "neo4j")) as session:
            label_counts = _records(session, "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS count ORDER BY label")
            relation_counts = _records(session, "MATCH ()-[r]->() RETURN type(r) AS relation, count(*) AS count ORDER BY relation")
            event_counts = _records(session, "MATCH (e:Event) RETURN e.event_type AS event_type, count(*) AS count ORDER BY event_type")
            categories = _records(session, "MATCH (c:WasteCategory) RETURN properties(c) AS properties ORDER BY c.category_name")
            events = _records(session, "MATCH (e:Event) RETURN properties(e) AS properties ORDER BY e.event_time")
            node_ids = _records(
                session,
                """
                MATCH (n)
                WITH labels(n) AS labels,
                     coalesce(n.category_name, n.scene_id, n.instance_id, n.sample_id,
                              n.cluster_id, n.event_id) AS business_id
                WHERE business_id IS NOT NULL
                RETURN labels, business_id, size(toString(business_id)) AS length
                ORDER BY length DESC, business_id
                """,
            )
            orphan_counts = _records(
                session,
                """
                MATCH (n) WHERE NOT (n)--()
                RETURN labels(n) AS labels,
                       collect(coalesce(n.category_name, n.scene_id, n.instance_id, n.sample_id,
                                        n.cluster_id, n.event_id)) AS business_ids,
                       count(*) AS count
                ORDER BY labels
                """,
            )
            layer_links = _records(
                session,
                """
                RETURN
                  count { (:Scene)-[:CONTAINS]->(:ObjectInstance) } AS scene_instance,
                  count { (:ObjectInstance)-[:CANDIDATE_OF|CONFIRMED_AS]->(:WasteCategory) } AS instance_category,
                  count { (:Event)-[]->() } AS event_targets
                """,
            )[0]
    finally:
        driver.close()

    expected_categories = {item.name: item.to_dict() for item in DEFAULT_CATEGORY_SPECS}
    actual_categories = {item["properties"]["category_name"]: item["properties"] for item in categories}
    category_differences: dict[str, list[str]] = {}
    for name, expected in expected_categories.items():
        actual = actual_categories.get(name)
        if actual is None:
            category_differences[name] = ["missing_node"]
            continue
        differing = []
        for field in ("risk_level", "fragility", "graspability_prior", "vlm_review_policy", "default_handling_policy"):
            if actual.get(field) != expected.get(field):
                differing.append(field)
        if _decode_json_property(actual, "visual_prototype") != expected.get("visual_prototype"):
            differing.append("visual_prototype")
        if differing:
            category_differences[name] = differing

    actual_event_types = {item["event_type"] for item in event_counts}
    category_value_usage = {
        field: sorted({str(properties.get(field)) for properties in actual_categories.values() if properties.get(field) is not None})
        for field in CATEGORY_ATTRIBUTE_ENUMS
    }
    event_violations: list[dict[str, Any]] = []
    common_event_fields = {"event_id", "event_type", "event_time", "event_source"}
    for item in events:
        properties = item["properties"]
        event_type = properties.get("event_type")
        actual_source = properties.get("event_source")
        expected_source = EVENT_SOURCES.get(event_type)
        normalized_fields = {
            key[:-5] if key.endswith("_json") else key
            for key in properties
        }
        unsupported_fields = sorted(
            normalized_fields - common_event_fields - EVENT_ATTRIBUTE_FIELDS.get(event_type, set())
        )
        if expected_source != actual_source or unsupported_fields:
            event_violations.append(
                {
                    "event_id": properties.get("event_id"),
                    "event_type": event_type,
                    "source_mismatch": expected_source != actual_source,
                    "unsupported_fields": unsupported_fields,
                }
            )

    actual_relations = {item["relation"] for item in relation_counts}
    long_ids = [item for item in node_ids if int(item["length"]) > 24]
    report = {
        "label_counts": label_counts,
        "relation_counts": relation_counts,
        "layer_links": layer_links,
        "category_schema": {
            "expected": len(expected_categories),
            "actual": len(actual_categories),
            "missing": sorted(set(expected_categories) - set(actual_categories)),
            "unexpected": sorted(set(actual_categories) - set(expected_categories)),
            "attribute_differences": category_differences,
            "allowed_values": {field: list(values) for field, values in CATEGORY_ATTRIBUTE_ENUMS.items()},
            "instantiated_values": category_value_usage,
        },
        "instance_schema": {
            "allowed_values": {field: list(values) for field, values in INSTANCE_ATTRIBUTE_ENUMS.items()},
            "node_fields": knowledge_schema_snapshot()["node_fields"],
        },
        "event_schema": {
            "defined_types": sorted(EVENT_SOURCES),
            "instantiated_types": sorted(actual_event_types),
            "not_yet_instantiated": sorted(set(EVENT_SOURCES) - actual_event_types),
            "counts": event_counts,
            "violations": event_violations,
        },
        "relation_schema": {
            "allowed": sorted(ALLOWED_RELATIONS),
            "instantiated": sorted(actual_relations),
            "unexpected": sorted(actual_relations - ALLOWED_RELATIONS),
        },
        "id_audit": {
            "node_count": len(node_ids),
            "max_length": max((int(item["length"]) for item in node_ids), default=0),
            "over_24_characters": long_ids,
        },
        "orphan_nodes": orphan_counts,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
