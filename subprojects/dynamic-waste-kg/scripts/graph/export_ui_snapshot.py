"""导出供 dynamic-waste-ui 读取的知识图谱快照。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUBPROJECTS_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.graph.cli import build_demo_graph
from wastekg.graph.exporters import graph_to_json_snapshot
from wastekg.graph.neo4j_store import Neo4jGraphMirror

DEFAULT_OUTPUT = SUBPROJECTS_ROOT / "dynamic-waste-ui" / "public" / "data" / "kg-snapshot.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export a KG JSON snapshot for dynamic-waste-ui.")
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Optional existing KnowledgeGraph.to_dict() JSON snapshot. If omitted, a demo graph is exported.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSON path consumed by dynamic-waste-ui/public/data/kg-snapshot.json.",
    )
    parser.add_argument(
        "--neo4j",
        action="store_true",
        help="Read the current live Neo4j graph instead of the demo graph.",
    )
    return parser


def _load_snapshot(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("KG snapshot must be a JSON object.")
    return data


def _build_demo_ui_snapshot() -> Dict[str, Any]:
    graph = build_demo_graph()
    return graph_to_json_snapshot(graph)


def _normalize_for_ui(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    # UI 可以展示 unknown 实例，但不能把 unknown 误解为长期类别知识。
    categories = snapshot.get("categories")
    if isinstance(categories, dict):
        categories.pop("unknown", None)
    snapshot.setdefault("categories", {})
    snapshot.setdefault("scenes", {})
    snapshot.setdefault("instances", {})
    snapshot.setdefault("unknown_samples", {})
    snapshot.setdefault("unknown_clusters", {})
    snapshot.setdefault("edges", [])
    snapshot.setdefault("events", [])
    snapshot.setdefault("schema", {})
    snapshot.setdefault("provenance", {})
    return snapshot




def _compact_for_ui(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    # 核心模型已经只导出文档定义字段，UI 不再二次创造别名属性。
    return {
        "categories": dict(snapshot.get("categories", {})),
        "scenes": dict(snapshot.get("scenes", {})),
        "instances": dict(snapshot.get("instances", {})),
        "unknown_samples": dict(snapshot.get("unknown_samples", {})),
        "unknown_clusters": dict(snapshot.get("unknown_clusters", {})),
        "edges": list(snapshot.get("edges", [])),
        "events": list(snapshot.get("events", [])),
        "schema": dict(snapshot.get("schema", {})),
        "provenance": dict(snapshot.get("provenance", {})),
    }

def _write_snapshot(snapshot: Dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(snapshot, file, ensure_ascii=False, indent=2)
        file.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.input and args.neo4j:
        parser.error("--input and --neo4j cannot be used together")
    if args.neo4j:
        mirror = Neo4jGraphMirror.from_env()
        try:
            snapshot = mirror.read_snapshot()
        finally:
            mirror.close()
    else:
        snapshot = _load_snapshot(args.input) if args.input else _build_demo_ui_snapshot()
    snapshot = _compact_for_ui(_normalize_for_ui(snapshot))
    _write_snapshot(snapshot, args.output)

    print(f"Exported UI KG snapshot: {args.output.resolve()}")
    print(f"categories={len(snapshot.get('categories', {}))} instances={len(snapshot.get('instances', {}))} events={len(snapshot.get('events', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
