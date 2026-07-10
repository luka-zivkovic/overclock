from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
from validate_skill import parse_frontmatter  # noqa: E402


class IndependentResearchSecurityTest(unittest.TestCase):
    def test_fork_uses_bounded_read_only_agent(self) -> None:
        skill_path = REPO / "plugins/critical-thinking/skills/independent-research/SKILL.md"
        agent_path = REPO / "plugins/critical-thinking/agents/independent-researcher.md"
        skill, body = parse_frontmatter(skill_path.read_text(encoding="utf-8"))
        agent, _ = parse_frontmatter(agent_path.read_text(encoding="utf-8"))

        self.assertEqual(skill.get("context"), "fork")
        self.assertEqual(skill.get("agent"), "independent-researcher")
        self.assertIn("$ARGUMENTS", body)
        self.assertEqual(agent.get("maxTurns"), "8")

        tools = {tool.strip() for tool in agent.get("tools", "").split(",")}
        self.assertEqual(tools, {"Read", "Grep", "Glob", "WebFetch", "WebSearch"})
        self.assertTrue(tools.isdisjoint({"Write", "Edit", "Bash", "Agent"}))


if __name__ == "__main__":
    unittest.main()
