"""验证图谱业务 ID 保持稳定、紧凑并带有类型前缀。"""

import unittest

from wastekg.core.identifiers import stable_compact_id
from wastekg.graph.store import KnowledgeGraph


class StableCompactIdTests(unittest.TestCase):
    def test_same_source_produces_same_short_id(self) -> None:
        first = stable_compact_id("scn", "C:/data/image_001.jpg")
        second = stable_compact_id("scn", "C:/data/image_001.jpg")

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("scn_"))
        self.assertLessEqual(len(first), 20)

    def test_different_sources_produce_different_ids(self) -> None:
        self.assertNotEqual(
            stable_compact_id("scn", "image_001.jpg"),
            stable_compact_id("scn", "image_002.jpg"),
        )

    def test_namespaced_instance_ids_do_not_restart_at_class_name(self) -> None:
        graph = KnowledgeGraph(id_namespace="scn_abcdefghijklm")

        self.assertEqual(graph.generate_instance_id("brick"), "ins_abcdefghijklm_01")
        self.assertEqual(graph.generate_instance_id("wood"), "ins_abcdefghijklm_02")


if __name__ == "__main__":
    unittest.main()
