"""提供 import neo4j cypher 命令行入口。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neo4j import GraphDatabase


def main() -> int:
    parser = argparse.ArgumentParser(description="Import generated Cypher statements into Neo4j.")
    parser.add_argument("--cypher", type=Path, default=Path("artifacts/demo_graph/neo4j_import.cypher"))
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--user", default="neo4j")
    parser.add_argument("--password", default="wastekg123456")
    args = parser.parse_args()

    statements = [line.strip() for line in args.cypher.read_text(encoding="utf-8").splitlines() if line.strip()]
    with GraphDatabase.driver(args.uri, auth=(args.user, args.password)) as driver:
        driver.verify_connectivity()
        with driver.session(database="neo4j") as session:
            for statement in statements:
                session.run(statement).consume()
    print(f"Imported {len(statements)} Cypher statements into {args.uri}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
