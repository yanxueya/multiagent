import unittest

from wastekg import DEFAULT_CATEGORY_SPECS, KnowledgeGraph, seed_default_categories


class KnowledgeBaseTests(unittest.TestCase):
    def test_seed_default_categories_registers_detailed_knowledge(self) -> None:
        graph = KnowledgeGraph()
        registered = seed_default_categories(graph)

        self.assertEqual(len(registered), 11)
        self.assertIn("glass", graph.categories)
        self.assertNotIn("asbestos_suspect", graph.categories)
        self.assertNotIn("unknown", graph.categories)
        self.assertNotIn("asphalt", graph.categories)
        self.assertNotIn("waste_paint_can", graph.categories)

        glass = graph.categories["glass"]

        self.assertEqual(glass.risk_level, "medium")
        self.assertEqual(glass.fragility, "high")
        self.assertEqual(glass.pollution_level, "low")
        self.assertEqual(glass.graspability, "low")
        self.assertEqual(glass.handling_mode, "robot_with_supervision")
        self.assertEqual(glass.grasp_difficulty, "high")
        self.assertTrue(glass.needs_llm_review)
        self.assertFalse(glass.auto_processable)
        self.assertTrue(glass.source_refs)
        self.assertIn("transparency", glass.visual_prototype)

        gypsum = graph.categories["gypsum_board"]
        self.assertEqual(gypsum.handling_mode, "human_review")
        self.assertTrue(gypsum.needs_llm_review)

    def test_default_seed_list_is_stable(self) -> None:
        names = [spec.name for spec in DEFAULT_CATEGORY_SPECS]
        self.assertEqual(
            names,
            [
                "concrete",
                "brick",
                "tile",
                "wood",
                "gypsum_board",
                "foam",
                "metal",
                "soft_plastic",
                "hard_plastic",
                "paperboard",
                "glass",
            ],
        )


if __name__ == "__main__":
    unittest.main()
