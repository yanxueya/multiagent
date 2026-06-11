import unittest

from wastekg import DEFAULT_CATEGORY_SPECS, KnowledgeGraph, seed_default_categories


class KnowledgeBaseTests(unittest.TestCase):
    def test_seed_default_categories_registers_detailed_knowledge(self) -> None:
        graph = KnowledgeGraph()
        registered = seed_default_categories(graph)

        self.assertGreaterEqual(len(registered), 11)
        self.assertIn("glass", graph.categories)
        self.assertIn("asbestos", graph.categories)
        self.assertIn("waste_paint_can", graph.categories)

        glass = graph.categories["glass"]
        asbestos = graph.categories["asbestos"]
        paint_can = graph.categories["waste_paint_can"]

        self.assertEqual(glass.risk_level, "medium")
        self.assertEqual(glass.fragility, "high")
        self.assertEqual(glass.pollution_level, "low")
        self.assertEqual(glass.graspability, "low")
        self.assertTrue(glass.source_refs)

        self.assertEqual(asbestos.risk_level, "high")
        self.assertEqual(asbestos.pollution_level, "high")
        self.assertTrue(asbestos.source_refs)

        self.assertEqual(paint_can.risk_level, "high")
        self.assertEqual(paint_can.pollution_level, "medium")
        self.assertIn("工程判定", paint_can.notes)

    def test_default_seed_list_is_stable(self) -> None:
        names = [spec.name for spec in DEFAULT_CATEGORY_SPECS]
        self.assertIn("brick", names)
        self.assertIn("glass", names)
        self.assertIn("asbestos", names)


if __name__ == "__main__":
    unittest.main()
