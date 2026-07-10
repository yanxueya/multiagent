"""验证 test update 相关功能。"""

import unittest

from wastekg.core.models import DetectedObject, DetectedRelation, Observation
from wastekg.graph.store import KnowledgeGraph


class UpdateTests(unittest.TestCase):
    def test_apply_observation_creates_instance(self) -> None:
        graph = KnowledgeGraph()
        obs = Observation(
            frame_id="f1",
            source="realsense",
            objects=[
                DetectedObject(
                    temp_id="t1",
                    class_name="brick",
                    confidence=0.92,
                    center_xyz=(0.1, 0.2, 0.3),
                )
            ],
        )
        summary = graph.apply_observation(obs)

        self.assertEqual(summary["created_instances"], ["brick_01"])
        self.assertIn("brick_01", graph.instances)
        self.assertEqual(graph.resolve_instance_category("brick_01"), "brick")

    def test_apply_observation_updates_relations(self) -> None:
        graph = KnowledgeGraph()
        obs = Observation(
            frame_id="f2",
            source="realsense",
            objects=[
                DetectedObject(temp_id="a", class_name="brick", confidence=0.95, center_xyz=(0.0, 0.0, 0.0)),
                DetectedObject(temp_id="b", class_name="paint_can", confidence=0.93, center_xyz=(0.0, 0.0, 0.10), risk_level="high"),
            ],
            relations=[
                DetectedRelation(source_temp_id="b", relation="near", target_temp_id="a", confidence=0.9)
            ],
        )
        graph.apply_observation(obs)

        self.assertTrue(any(edge.relation == "NEAR" for edge in graph.edges.values()))
        self.assertEqual(set(next(edge for edge in graph.edges.values() if edge.relation == "NEAR").to_dict()), {"source_id", "relation", "target_id"})


if __name__ == "__main__":
    unittest.main()
