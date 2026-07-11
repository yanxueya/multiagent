"""使用环境变量安全修改本机 Neo4j 密码，不在命令行暴露密码。"""

from __future__ import annotations

import os

from neo4j import GraphDatabase


def main() -> int:
    current = os.environ.get("WASTEKG_NEO4J_PASSWORD", "")
    new = os.environ.get("WASTEKG_NEO4J_NEW_PASSWORD", "")
    if not current or not new:
        raise ValueError("Both WASTEKG_NEO4J_PASSWORD and WASTEKG_NEO4J_NEW_PASSWORD are required")
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", current))
    try:
        with driver.session(database="neo4j") as session:
            session.run(
                "ALTER CURRENT USER SET PASSWORD FROM $current TO $new",
                current=current,
                new=new,
            ).consume()
    finally:
        driver.close()
    print("Neo4j password updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
