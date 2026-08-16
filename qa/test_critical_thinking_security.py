from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
from validate_skill import parse_frontmatter  # noqa: E402


class IndependentResearchSecurityTest(unittest.TestCase):
    def test_fork_uses_builtin_explore_and_admits_scope_limit(self) -> None:
        skill_path = REPO / "plugins/critical-thinking/skills/independent-research/SKILL.md"
        skill, body = parse_frontmatter(skill_path.read_text(encoding="utf-8"))
        normalized_body = " ".join(body.split())

        self.assertEqual(skill.get("context"), "fork")
        self.assertEqual(skill.get("agent"), "Explore")
        self.assertIn("$ARGUMENTS", body)
        self.assertIn("not a filesystem sandbox", body)
        self.assertIn("not an enforced tool", body)
        self.assertIn("8 local source artifacts", body)
        self.assertIn("64 KiB", body)
        self.assertIn("caller must name each authorized root exactly", normalized_body)
        self.assertIn("host-specific", body)
        self.assertIn("OpenAI metadata", body)
        self.assertIn("explicit isolation gap", body)
        self.assertTrue(
            (
                skill_path.parent
                / "scripts"
                / "bounded_inspect.py"
            ).is_file()
        )
        self.assertFalse(any((REPO / "plugins/critical-thinking/agents").glob("*.md")))


if __name__ == "__main__":
    unittest.main()
