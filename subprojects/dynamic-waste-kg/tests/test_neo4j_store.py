"""验证 Neo4j 镜像只执行受控约束和图谱导出语句。"""

import unittest

from wastekg import seed_default_categories
from wastekg.core.models import DetectedObject, Observation
from wastekg.graph.neo4j_store import Neo4jConnectionSettings, Neo4jGraphMirror, SCHEMA_STATEMENTS
from wastekg.graph.store import KnowledgeGraph


class _Result:
    def consume(self):
        return None

    def single(self):
        return {"count": 3}


class _Transaction:
    def __init__(self):
        self.statements = []

    def run(self, statement):
        self.statements.append(statement)
        return _Result()


class _Session:
    def __init__(self, driver):
        self.driver = driver

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute_write(self, callback, statements):
        callback(self.driver.tx, statements)

    def run(self, statement):
        self.driver.tx.statements.append(statement)
        return _Result()


class _Driver:
    def __init__(self):
        self.tx = _Transaction()
        self.database = ""
        self.verified = False
        self.closed = False

    def session(self, *, database):
        self.database = database
        return _Session(self)

    def verify_connectivity(self):
        self.verified = True

    def close(self):
        self.closed = True


class Neo4jStoreTests(unittest.TestCase):
    def test_sync_creates_schema_and_all_three_layers(self):
        graph = KnowledgeGraph()
        seed_default_categories(graph)
        graph.apply_observation(Observation("scene_001", "camera", objects=[DetectedObject("a", "brick", 0.9, yolo_confidence=0.9)]))
        driver = _Driver()
        mirror = Neo4jGraphMirror(
            Neo4jConnectionSettings("bolt://test", "neo4j", "secret", "wastekg"),
            driver_factory=lambda *_args, **_kwargs: driver,
        )

        counts = mirror.sync_graph(graph)

        self.assertEqual(driver.database, "wastekg")
        self.assertEqual(driver.tx.statements[: len(SCHEMA_STATEMENTS)], list(SCHEMA_STATEMENTS))
        joined = "\n".join(driver.tx.statements)
        self.assertIn("WasteCategory", joined)
        self.assertIn("ObjectInstance", joined)
        self.assertIn("DetectionEvent", joined)
        self.assertEqual(counts["categories"], 11)
        self.assertEqual(counts["events"], len(graph.events))
        self.assertNotIn("task_value", joined)

    def test_connectivity_and_close_delegate_to_driver(self):
        driver = _Driver()
        mirror = Neo4jGraphMirror(
            Neo4jConnectionSettings("bolt://test", "neo4j", "secret"),
            driver_factory=lambda *_args, **_kwargs: driver,
        )
        mirror.verify_connectivity()
        mirror.close()
        self.assertTrue(driver.verified)
        self.assertTrue(driver.closed)

    def test_replace_deletes_business_nodes_inside_write_transaction(self):
        graph = KnowledgeGraph()
        seed_default_categories(graph)
        driver = _Driver()
        mirror = Neo4jGraphMirror(
            Neo4jConnectionSettings("bolt://test", "neo4j", "secret"),
            driver_factory=lambda *_args, **_kwargs: driver,
        )

        mirror.replace_graph(graph)

        self.assertEqual(driver.tx.statements[len(SCHEMA_STATEMENTS)], "MATCH (n) DETACH DELETE n")
        self.assertTrue(any("WasteCategory" in statement for statement in driver.tx.statements))

    def test_live_summary_reads_all_three_layers_and_relations(self):
        driver = _Driver()
        mirror = Neo4jGraphMirror(
            Neo4jConnectionSettings("bolt://test", "neo4j", "secret"),
            driver_factory=lambda *_args, **_kwargs: driver,
        )
        self.assertEqual(mirror.read_summary(), {"categories": 3, "short_term": 3, "events": 3, "relations": 3})


if __name__ == "__main__":
    unittest.main()
