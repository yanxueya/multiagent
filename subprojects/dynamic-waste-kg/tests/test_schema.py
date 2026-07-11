"""验证权威枚举和七类事件定义不会在代码与展示间丢失。"""

import unittest

from wastekg.core.models import CategorySpec, GraphEvent
from wastekg.core.schema import (
    CATEGORY_ATTRIBUTE_ENUMS,
    EVENT_DEFINITIONS,
    INSTANCE_ATTRIBUTE_ENUMS,
    knowledge_schema_snapshot,
)


class KnowledgeSchemaTests(unittest.TestCase):
    def test_graspability_keeps_full_domain_even_when_high_is_unused(self) -> None:
        self.assertEqual(CATEGORY_ATTRIBUTE_ENUMS["graspability_prior"], ("low", "medium", "high"))

    def test_instance_status_domains_match_authoritative_document(self) -> None:
        self.assertEqual(INSTANCE_ATTRIBUTE_ENUMS["vlm_consistency"], ("support", "conflict", "not_checked"))
        self.assertEqual(INSTANCE_ATTRIBUTE_ENUMS["task_status"], ("pending", "processing", "completed", "failed"))

    def test_all_seven_event_definitions_include_transition_information(self) -> None:
        self.assertEqual(len(EVENT_DEFINITIONS), 7)
        for definition in EVENT_DEFINITIONS.values():
            self.assertTrue(definition["trigger"])
            self.assertTrue(definition["preconditions"])
            self.assertTrue(definition["relations"])
            self.assertTrue(definition["effects"])

    def test_event_enum_validation_rejects_undefined_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "VLMReviewEvent.consistency"):
            GraphEvent(
                "VLMReviewEvent",
                attributes={"image_quality": "clear", "visual_attributes": {}, "consistency": "insufficient", "reason": ""},
            )

    def test_category_enum_validation_accepts_high_graspability(self) -> None:
        category = CategorySpec(name="future_category", graspability_prior="high")
        self.assertEqual(category.graspability_prior, "high")

    def test_schema_snapshot_lists_nullable_unknown_fields(self) -> None:
        snapshot = knowledge_schema_snapshot()
        self.assertIn("human_label", snapshot["node_fields"]["UnknownSample"])
        self.assertEqual(
            snapshot["node_fields"]["UnknownCluster"],
            [
                "cluster_id", "member_count", "prototype_attributes", "representative_crop_ref",
                "review_status", "candidate_category_name",
            ],
        )


if __name__ == "__main__":
    unittest.main()
