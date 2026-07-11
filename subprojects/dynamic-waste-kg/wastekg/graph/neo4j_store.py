"""将受控的内存知识图谱事务镜像到 Neo4j。"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Callable, Dict, Iterable, Optional

from wastekg.graph.exporters import graph_to_neo4j_cypher
from wastekg.graph.store import KnowledgeGraph
from wastekg.core.schema import knowledge_schema_snapshot


SCHEMA_STATEMENTS = (
    "CREATE CONSTRAINT waste_category_name IF NOT EXISTS FOR (n:WasteCategory) REQUIRE n.category_name IS UNIQUE",
    "CREATE CONSTRAINT scene_id IF NOT EXISTS FOR (n:Scene) REQUIRE n.scene_id IS UNIQUE",
    "CREATE CONSTRAINT object_instance_id IF NOT EXISTS FOR (n:ObjectInstance) REQUIRE n.instance_id IS UNIQUE",
    "CREATE CONSTRAINT unknown_sample_id IF NOT EXISTS FOR (n:UnknownSample) REQUIRE n.sample_id IS UNIQUE",
    "CREATE CONSTRAINT unknown_cluster_id IF NOT EXISTS FOR (n:UnknownCluster) REQUIRE n.cluster_id IS UNIQUE",
    "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (n:Event) REQUIRE n.event_id IS UNIQUE",
)


@dataclass(frozen=True, slots=True)
class Neo4jConnectionSettings:
    """保存 Neo4j 连接参数；密码只从调用方或环境变量取得。"""

    uri: str
    user: str
    password: str
    database: str = "neo4j"

    @classmethod
    def from_env(cls) -> "Neo4jConnectionSettings":
        password = os.environ.get("WASTEKG_NEO4J_PASSWORD", "")
        if not password:
            raise ValueError("WASTEKG_NEO4J_PASSWORD is required")
        return cls(
            uri=os.environ.get("WASTEKG_NEO4J_URI", "bolt://localhost:7687"),
            user=os.environ.get("WASTEKG_NEO4J_USER", "neo4j"),
            password=password,
            database=os.environ.get("WASTEKG_NEO4J_DATABASE", "neo4j"),
        )


class Neo4jGraphMirror:
    """先确保 Schema，再以单个数据事务幂等同步当前三层图谱。"""

    def __init__(
        self,
        settings: Neo4jConnectionSettings,
        *,
        driver_factory: Optional[Callable[..., Any]] = None,
    ) -> None:
        if driver_factory is None:
            try:
                from neo4j import GraphDatabase
            except ImportError as exc:
                raise RuntimeError("Install the neo4j Python package before enabling the Neo4j mirror") from exc
            driver_factory = GraphDatabase.driver
        self.settings = settings
        self._driver = driver_factory(settings.uri, auth=(settings.user, settings.password))

    @classmethod
    def from_env(cls, *, driver_factory: Optional[Callable[..., Any]] = None) -> "Neo4jGraphMirror":
        return cls(Neo4jConnectionSettings.from_env(), driver_factory=driver_factory)

    def close(self) -> None:
        self._driver.close()

    def verify_connectivity(self) -> None:
        self._driver.verify_connectivity()

    def sync_graph(self, graph: KnowledgeGraph) -> Dict[str, int]:
        """创建约束并同步节点、关系；只执行仓库内部生成的 Cypher。"""

        statements = graph_to_neo4j_cypher(graph)
        with self._driver.session(database=self.settings.database) as session:
            for statement in SCHEMA_STATEMENTS:
                session.run(statement).consume()
            session.execute_write(self._write_transaction, statements)
        return {
            "categories": len(graph.categories),
            "scenes": len(graph.scenes),
            "instances": len(graph.instances),
            "unknown_samples": len(graph.unknown_samples),
            "unknown_clusters": len(graph.unknown_clusters),
            "events": len(graph.events),
            "relations": len(graph.edges),
        }

    def replace_graph(self, graph: KnowledgeGraph) -> Dict[str, int]:
        """在单个事务中替换业务图；约束保留，写入失败时整体回滚。"""

        statements = graph_to_neo4j_cypher(graph)
        with self._driver.session(database=self.settings.database) as session:
            for statement in SCHEMA_STATEMENTS:
                session.run(statement).consume()
            session.execute_write(self._replace_transaction, statements)
        return {
            "categories": len(graph.categories),
            "scenes": len(graph.scenes),
            "instances": len(graph.instances),
            "unknown_samples": len(graph.unknown_samples),
            "unknown_clusters": len(graph.unknown_clusters),
            "events": len(graph.events),
            "relations": len(graph.edges),
        }

    def read_summary(self) -> Dict[str, int]:
        """从在线数据库读取三层节点和关系计数，供启动验收使用。"""

        queries = {
            "categories": "MATCH (n:WasteCategory) RETURN count(n) AS count",
            "short_term": "MATCH (n) WHERE n:Scene OR n:ObjectInstance OR n:UnknownSample OR n:UnknownCluster RETURN count(n) AS count",
            "events": "MATCH (n:Event) RETURN count(n) AS count",
            "relations": "MATCH ()-[r]->() RETURN count(r) AS count",
        }
        with self._driver.session(database=self.settings.database) as session:
            return {name: int(session.run(query).single()["count"]) for name, query in queries.items()}

    def read_snapshot(self) -> Dict[str, Any]:
        """读取 Neo4j 中的完整三层图，供只读 UI 快照使用。"""

        snapshot: Dict[str, Any] = {
            "categories": {}, "scenes": {}, "instances": {},
            "unknown_samples": {}, "unknown_clusters": {}, "events": [], "edges": [],
            "schema": knowledge_schema_snapshot(),
        }
        with self._driver.session(database=self.settings.database) as session:
            for record in session.run("MATCH (n) RETURN labels(n) AS labels, properties(n) AS props"):
                labels = set(record["labels"])
                props = self._decode_json_properties(dict(record["props"]))
                if "WasteCategory" in labels:
                    snapshot["categories"][props["category_name"]] = props
                elif "Scene" in labels:
                    snapshot["scenes"][props["scene_id"]] = props
                elif "ObjectInstance" in labels:
                    snapshot["instances"][props["instance_id"]] = props
                elif "UnknownSample" in labels:
                    snapshot["unknown_samples"][props["sample_id"]] = props
                elif "UnknownCluster" in labels:
                    snapshot["unknown_clusters"][props["cluster_id"]] = props
                elif "Event" in labels:
                    snapshot["events"].append(props)
            edge_query = """
                MATCH (s)-[r]->(t)
                RETURN coalesce(s.category_name, s.scene_id, s.instance_id, s.sample_id, s.cluster_id, s.event_id) AS source_id,
                       type(r) AS relation,
                       coalesce(t.category_name, t.scene_id, t.instance_id, t.sample_id, t.cluster_id, t.event_id) AS target_id
            """
            snapshot["edges"] = [dict(record) for record in session.run(edge_query)]
        snapshot["events"].sort(key=lambda item: str(item.get("event_time", "")))
        return snapshot

    @staticmethod
    def _decode_json_properties(properties: Dict[str, Any]) -> Dict[str, Any]:
        decoded = dict(properties)
        for key in list(properties):
            if not key.endswith("_json"):
                continue
            try:
                decoded[key[:-5]] = json.loads(str(properties[key]))
                del decoded[key]
            except json.JSONDecodeError:
                continue
        return decoded

    @staticmethod
    def _write_transaction(tx: Any, statements: Iterable[str]) -> None:
        for statement in statements:
            tx.run(statement).consume()

    @staticmethod
    def _replace_transaction(tx: Any, statements: Iterable[str]) -> None:
        tx.run("MATCH (n) DETACH DELETE n").consume()
        for statement in statements:
            tx.run(statement).consume()
