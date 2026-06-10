import unittest

from wastekg.models import CategorySpec, DetectedObject, GraphEvent, ObjectInstance, Observation, RelationEdge


class ModelTests(unittest.TestCase):
    def test_models_store_expected_fields(self) -> None:
        category = CategorySpec(name="brick", category="building_waste", material="ceramic", risk_level="low")
        instance = ObjectInstance(instance_id="brick_01", class_name="brick")
        edge = RelationEdge(source_id="brick_01", relation="on_top_of", target_id="brick_02")
        obs = Observation(frame_id="f1", source="realsense")
        event = GraphEvent(event_type="recognition", subject_id="brick_01")

        self.assertEqual(category.name, "brick")
        self.assertEqual(instance.instance_id, "brick_01")
        self.assertEqual(edge.relation, "on_top_of")
        self.assertEqual(obs.frame_id, "f1")
        self.assertEqual(event.event_type, "recognition")

    def test_detected_object_defaults(self) -> None:
        detected = DetectedObject(temp_id="t1", class_name="wood", confidence=0.8)
        self.assertEqual(detected.orientation, (0.0, 0.0, 0.0, 1.0))


if __name__ == "__main__":
    unittest.main()
