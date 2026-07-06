import unittest

from wastekg import graph_events_to_jsonl, graph_to_mermaid, graph_to_neo4j_cypher, seed_default_categories
from wastekg.models import DetectedObject, Observation
from wastekg.store import KnowledgeGraph


class ExporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = KnowledgeGraph()
        seed_default_categories(self.graph)
        self.graph.apply_observation(
            Observation(
                frame_id="frame_001",
                source="camera",
                objects=[
                    DetectedObject(
                        temp_id="a",
                        class_name="glass",
                        confidence=0.93,
                        center_xyz=(0.0, 0.0, 0.0),
                        mask_polygon=[(1.0, 2.0), (3.0, 4.0)],
                    ),
                    DetectedObject(temp_id="b", class_name="brick", confidence=0.90, center_xyz=(0.0, 0.0, 0.10)),
                ],
            )
        )

    def test_mermaid_contains_layers(self) -> None:
        mermaid = graph_to_mermaid(self.graph)
        self.assertIn("长期知识层", mermaid)
        self.assertIn("短期记忆层", mermaid)
        self.assertIn("事件日志层", mermaid)
        self.assertIn("classDef hazard", mermaid)

    def test_neo4j_cypher_contains_event_and_instance_merges(self) -> None:
        statements = graph_to_neo4j_cypher(self.graph)
        joined = "\n".join(statements)
        self.assertIn("MERGE (c:Category", joined)
        self.assertIn("MERGE (i:Instance", joined)
        self.assertIn("MERGE (e:Event", joined)
        self.assertIn("OF_CATEGORY", joined)
        self.assertFalse(any(";" in stmt for stmt in statements))
        self.assertTrue(any("ABOUT_INSTANCE" in stmt or "ABOUT_CATEGORY" in stmt for stmt in statements))

    def test_neo4j_category_export_contains_planning_attributes(self) -> None:
        statements = graph_to_neo4j_cypher(self.graph)
        category_statements = "\n".join(statement for statement in statements if statement.startswith("MERGE (c:Category"))

        self.assertIn("handling_mode", category_statements)
        self.assertIn("grasp_difficulty", category_statements)

    def test_neo4j_cypher_is_ascii_safe_for_powershell_pipe(self) -> None:
        statements = graph_to_neo4j_cypher(self.graph)

        for statement in statements:
            statement.encode("ascii")

    def test_neo4j_complex_instance_fields_are_stored_as_json(self) -> None:
        statements = graph_to_neo4j_cypher(self.graph)
        instance_statements = "\n".join(statement for statement in statements if statement.startswith("MERGE (i:Instance"))

        self.assertIn("mask_polygon_json", instance_statements)
        self.assertNotIn("mask_polygon: [[", instance_statements)

    def test_jsonl_contains_one_event_per_line(self) -> None:
        jsonl = graph_events_to_jsonl(self.graph)
        lines = [line for line in jsonl.splitlines() if line.strip()]
        self.assertGreaterEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("{"))


if __name__ == "__main__":
    unittest.main()
