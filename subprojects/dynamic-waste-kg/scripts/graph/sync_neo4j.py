"""启动连接检查，并把三层示例知识图谱同步到 Neo4j。"""

from __future__ import annotations

import argparse
from getpass import getpass
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.graph.cli import build_demo_graph
from wastekg.graph.neo4j_store import Neo4jConnectionSettings, Neo4jGraphMirror


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify Neo4j and sync the controlled three-layer demo graph.")
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--user", default="neo4j")
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--check-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    password = os.environ.get("WASTEKG_NEO4J_PASSWORD", "") or getpass("Neo4j password: ")
    if not password:
        raise ValueError("Neo4j password cannot be empty")
    mirror = Neo4jGraphMirror(Neo4jConnectionSettings(args.uri, args.user, password, args.database))
    try:
        mirror.verify_connectivity()
        print(f"Neo4j connectivity OK: {args.uri}/{args.database}")
        if not args.check_only:
            counts = mirror.sync_graph(build_demo_graph())
            print("Neo4j sync complete: " + " ".join(f"{key}={value}" for key, value in counts.items()))
            live_counts = mirror.read_summary()
            print("Neo4j live summary: " + " ".join(f"{key}={value}" for key, value in live_counts.items()))
    finally:
        mirror.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
