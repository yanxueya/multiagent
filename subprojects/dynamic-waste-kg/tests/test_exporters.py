"""验证新三层图谱的 JSON、Mermaid、JSONL 和 Neo4j 导出。"""

import unittest

from wastekg import graph_events_to_jsonl, graph_to_mermaid, graph_to_neo4j_cypher, seed_default_categories, stabilize_event_ids
from wastekg.core.models import DetectedObject, Observation
from wastekg.graph.store import KnowledgeGraph


class ExporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = KnowledgeGraph()
        seed_default_categories(self.graph)
        self.graph.apply_observation(
            Observation(
                frame_id="scene_001",
                source="camera",
                objects=[
                    DetectedObject("a", "glass", 0.93, yolo_confidence=0.93, depth_valid_ratio=0.5),
                    DetectedObject("b", "brick", 0.90, yolo_confidence=0.90, center_xyz=(0.1, 0.0, 0.0), depth_valid_ratio=0.8),
                ],
            )
        )

    def test_mermaid_contains_three_layers_and_document_nodes(self) -> None:
        mermaid = graph_to_mermaid(self.graph)
        self.assertIn("长期知识层", mermaid)
        self.assertIn("短期记忆层", mermaid)
        self.assertIn("事件日志层", mermaid)
        self.assertIn("Scene", mermaid)
        self.assertIn("DetectionEvent", mermaid)

    def test_neo4j_uses_authoritative_labels_relations_and_fields(self) -> None:
        joined = "\n".join(graph_to_neo4j_cypher(self.graph))
        self.assertIn("WasteCategory", joined)
        self.assertIn("ObjectInstance", joined)
        self.assertIn("DetectionEvent", joined)
        self.assertIn("CANDIDATE_OF", joined)
        self.assertIn("CONFIRMED_AS", joined)
        self.assertIn("default_handling_policy", joined)
        self.assertNotIn("task_value", joined)
        self.assertNotIn("safe_grasp_score", joined)
        self.assertNotIn("OF_CATEGORY", joined)

    def test_neo4j_cypher_is_ascii_safe(self) -> None:
        for statement in graph_to_neo4j_cypher(self.graph):
            statement.encode("ascii")

    def test_jsonl_contains_only_supported_event_types(self) -> None:
        lines = [line for line in graph_events_to_jsonl(self.graph).splitlines() if line]
        self.assertTrue(lines)
        self.assertTrue(all("Event" in line for line in lines))

    def test_offline_event_ids_can_be_stabilized_without_breaking_edges(self) -> None:
        stabilize_event_ids(self.graph, namespace="same-input")
        first_ids = [event.event_id for event in self.graph.events]
        first_edges = list(self.graph.edges)
        stabilize_event_ids(self.graph, namespace="same-input")
        self.assertEqual([event.event_id for event in self.graph.events], first_ids)
        self.assertEqual(list(self.graph.edges), first_edges)


if __name__ == "__main__":
    unittest.main()
