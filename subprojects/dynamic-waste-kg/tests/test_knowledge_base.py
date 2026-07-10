"""验证 Word 文档定义的 11 类长期知识种子。"""

import unittest

from wastekg import DEFAULT_CATEGORY_SPECS, KnowledgeGraph, seed_default_categories


class KnowledgeBaseTests(unittest.TestCase):
    def test_seed_fields_and_values_match_document(self) -> None:
        graph = KnowledgeGraph()
        registered = seed_default_categories(graph)

        self.assertEqual(len(registered), 11)
        self.assertNotIn("unknown", graph.categories)
        glass = graph.categories["glass"]
        self.assertEqual(glass.risk_level, "high")
        self.assertEqual(glass.fragility, "high")
        self.assertEqual(glass.graspability_prior, "low")
        self.assertEqual(glass.vlm_review_policy, "always")
        self.assertEqual(glass.default_handling_policy, "human_confirmation_required")
        self.assertEqual(glass.visual_prototype["dominant_color"], ["clear", "light_green", "light_blue"])
        self.assertNotIn("task_value", glass.to_dict())

    def test_default_seed_list_is_stable(self) -> None:
        self.assertEqual(
            [spec.name for spec in DEFAULT_CATEGORY_SPECS],
            ["concrete", "brick", "tile", "wood", "gypsum_board", "foam", "metal", "soft_plastic", "hard_plastic", "paperboard", "glass"],
        )


if __name__ == "__main__":
    unittest.main()
