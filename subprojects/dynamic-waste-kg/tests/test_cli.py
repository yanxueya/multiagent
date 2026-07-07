"""验证 test cli 相关功能。"""

import unittest

from wastekg.graph.cli import build_demo_graph
from wastekg.graph.query import build_planning_context


class CLITests(unittest.TestCase):
    def test_demo_graph_builds(self) -> None:
        graph = build_demo_graph()
        self.assertGreaterEqual(len(graph.categories), 5)
        self.assertGreaterEqual(len(graph.instances), 3)

    def test_demo_graph_planning_context(self) -> None:
        graph = build_demo_graph()
        context = build_planning_context(graph)
        self.assertIn("candidates", context)


if __name__ == "__main__":
    unittest.main()
