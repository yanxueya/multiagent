"""提供 export demo neo4j 命令行入口。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.graph.cli import build_demo_graph
from wastekg.graph.exporters import graph_events_to_jsonl, graph_to_json_snapshot, graph_to_mermaid, graph_to_neo4j_cypher
import json


def main() -> int:
    parser = argparse.ArgumentParser(description="Export demo graph artifacts for Neo4j and documentation.")
    parser.add_argument("--out", type=Path, default=Path("artifacts/demo_graph"))
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    graph = build_demo_graph()
    (args.out / "graph_snapshot.json").write_text(json.dumps(graph_to_json_snapshot(graph), ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out / "events.jsonl").write_text(graph_events_to_jsonl(graph), encoding="utf-8")
    (args.out / "graph.mmd").write_text(graph_to_mermaid(graph), encoding="utf-8")
    (args.out / "neo4j_import.cypher").write_text("\n".join(graph_to_neo4j_cypher(graph)) + "\n", encoding="utf-8")
    print(f"Exported demo graph artifacts to {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
