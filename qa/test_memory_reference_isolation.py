from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
SESSION = REPO / "plugins" / "session-memory" / "skills"
LOOP = REPO / "plugins" / "learning-loop" / "skills" / "lessons-learned"

MEMORY_SKILLS = (
    SESSION / "session-handoff",
    SESSION / "lessons-learned",
    SESSION / "solutions",
    LOOP,
)


class MemoryReferenceIsolationTests(unittest.TestCase):
    def test_io_contract_is_small_and_byte_identical_across_distributions(self) -> None:
        copies = [
            (skill / "references" / "memory-contract.md").read_bytes()
            for skill in MEMORY_SKILLS
        ]
        self.assertTrue(all(body == copies[0] for body in copies[1:]))
        text = copies[0].decode("utf-8")
        self.assertLessEqual(len(text.splitlines()), 70)
        self.assertNotIn("## HANDOFF.md format", text)
        self.assertNotIn("## LESSONS.md format", text)
        self.assertNotIn("## SOLUTIONS.md format", text)

    def test_compatible_ledger_schemas_are_byte_identical(self) -> None:
        lesson_copies = [
            SESSION / "session-handoff" / "references" / "lessons-schema.md",
            SESSION / "lessons-learned" / "references" / "lessons-schema.md",
            LOOP / "references" / "lessons-schema.md",
        ]
        solution_copies = [
            SESSION / "session-handoff" / "references" / "solutions-schema.md",
            SESSION / "solutions" / "references" / "solutions-schema.md",
        ]
        for paths in (lesson_copies, solution_copies):
            bodies = [path.read_bytes() for path in paths]
            self.assertTrue(all(body == bodies[0] for body in bodies[1:]))

    def test_each_writer_loads_only_its_own_schema(self) -> None:
        expected = {
            SESSION / "lessons-learned": {"lessons-schema.md"},
            LOOP: {"lessons-schema.md"},
            SESSION / "solutions": {"solutions-schema.md"},
        }
        schema_re = re.compile(r"references/([a-z-]+-schema\.md)")
        for skill, schemas in expected.items():
            with self.subTest(skill=skill):
                text = (skill / "SKILL.md").read_text(encoding="utf-8")
                self.assertEqual(set(schema_re.findall(text)), schemas)

    def test_handoff_loads_optional_schemas_only_during_resume(self) -> None:
        text = (SESSION / "session-handoff" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        save, resume = text.split("## Resume flow", 1)
        self.assertNotIn("references/lessons-schema.md", save)
        self.assertNotIn("references/solutions-schema.md", save)
        self.assertIn("An absent optional", resume)
        self.assertIn("references/lessons-schema.md", resume)
        self.assertIn("references/solutions-schema.md", resume)

    def test_markdown_commands_do_not_require_claude_environment(self) -> None:
        for skill in MEMORY_SKILLS:
            for path in skill.rglob("*.md"):
                with self.subTest(path=path):
                    text = path.read_text(encoding="utf-8")
                    self.assertNotIn("${CLAUDE_SKILL_DIR}", text)
                    self.assertNotIn("${CLAUDE_PROJECT_DIR}", text)


if __name__ == "__main__":
    unittest.main()
