"""防止 Agent Prompt 与 KG schema、三模式编排再次漂移。"""

from pathlib import Path
import unittest


PROMPTS = Path(__file__).resolve().parents[1] / "agent_system" / "prompts"


class PromptContractTests(unittest.TestCase):
    def test_supervisor_prompt_defines_three_modes_and_one_route(self) -> None:
        text = (PROMPTS / "agents" / "supervisor.md").read_text(encoding="utf-8")
        for token in ("exploration", "supervised_execution", "human_collaboration", '"next_step"'):
            self.assertIn(token, text)

    def test_perception_and_vlm_prompts_use_exact_visual_attributes(self) -> None:
        combined = "\n".join(
            (PROMPTS / path).read_text(encoding="utf-8")
            for path in (Path("agents/perception.md"), Path("modules/vlm_reviewer.md"))
        )
        for token in ("dominant_color", "transparency", "glossiness", "surface_texture", "edge_fracture", "shape_form"):
            self.assertIn(token, combined)
        self.assertIn("recognition_status=review_required", combined)

    def test_planning_prompt_requires_one_action_and_no_weighted_score(self) -> None:
        text = (PROMPTS / "agents" / "action_planning.md").read_text(encoding="utf-8")
        self.assertIn("一次只输出一个 ActionPlan", text)
        self.assertIn("failed", text)
        self.assertIn("rank_candidates", text)
        self.assertIn("不得输出 `blocked_by`", text)

    def test_execution_prompt_defines_idempotency_and_attempt_boundary(self) -> None:
        text = (PROMPTS / "agents" / "execution.md").read_text(encoding="utf-8")
        self.assertIn("action_id", text)
        self.assertIn("physical_attempt_started", text)
        self.assertIn("new_scene_required=true", text)

    def test_only_expected_root_prompt_index_remains(self) -> None:
        self.assertEqual([path.name for path in PROMPTS.glob("*.md")], ["README.md"])
        for path in PROMPTS.rglob("*.md"):
            self.assertNotIn("$(System.Collections.DictionaryEntry.Value)", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
