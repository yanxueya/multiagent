"""验证 Word 规范中的节点、关系和事件模型。"""

import unittest

from wastekg.core.models import CategorySpec, GraphEvent, ObjectInstance, RelationEdge, Scene, UnknownCluster, UnknownSample


class ModelTests(unittest.TestCase):
    def test_persisted_node_fields_match_authoritative_document(self) -> None:
        category = CategorySpec(name="brick", risk_level="medium", graspability_prior="medium")
        instance = ObjectInstance(instance_id="brick_01", class_name="brick", recognition_status="accepted")
        scene = Scene(scene_id="scene_001")
        sample = UnknownSample(sample_id="sample_001")
        cluster = UnknownCluster(cluster_id="cluster_001")

        self.assertEqual(set(category.to_dict()), {"category_name", "risk_level", "fragility", "graspability_prior", "vlm_review_policy", "default_handling_policy", "visual_prototype"})
        self.assertNotIn("class_name", instance.to_dict())
        self.assertNotIn("task_value", category.to_dict())
        self.assertEqual(scene.to_dict()["scene_id"], "scene_001")
        self.assertEqual(sample.to_dict()["review_status"], "pending")
        self.assertEqual(cluster.to_dict()["member_count"], 0)

    def test_relations_have_no_independent_properties(self) -> None:
        edge = RelationEdge("brick_01", "NEAR", "glass_01")
        self.assertEqual(edge.to_dict(), {"source_id": "brick_01", "relation": "NEAR", "target_id": "glass_01"})

    def test_event_type_enforces_source_and_fixed_attributes(self) -> None:
        event = GraphEvent("ExecutionEvent", attributes={"execution_result": "failure", "failure_reason": "grasp_failed"})
        self.assertEqual(event.event_source, "robot_controller")
        with self.assertRaises(ValueError):
            GraphEvent("ExecutionEvent", attributes={"priority": 1})


if __name__ == "__main__":
    unittest.main()
