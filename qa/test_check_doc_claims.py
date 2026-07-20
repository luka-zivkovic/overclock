"""Unit tests for tools/check_doc_claims.py."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHECKER = REPO / "tools" / "check_doc_claims.py"


def run_checker(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECKER), str(root)],
        capture_output=True,
        text=True,
    )


def make_skill(root: Path, plugin: str, skill: str) -> Path:
    skill_dir = root / plugin / "skills" / skill
    (skill_dir / "references").mkdir(parents=True)
    return skill_dir


class CheckDocClaimsTest(unittest.TestCase):
    def test_resolving_citations_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_skill(root, "p1", "s1")
            (skill / "references" / "guide.md").write_text("content\n")
            (skill / "scripts").mkdir()
            (skill / "scripts" / "helper.py").write_text("print('hi')\n")
            (skill / "SKILL.md").write_text(
                "Read `references/guide.md` during triage.\n"
                'Run `python3 "${CLAUDE_SKILL_DIR}/scripts/helper.py" --root x`.\n'
                "URLs are skipped: https://example.com/scripts/fake.py is fine.\n"
                "Wildcards skipped: references/*.md and <references/placeholder.md>.\n"
            )
            result = run_checker(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("OK", result.stdout)

    def test_var_prefixed_missing_script_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_skill(root, "p1", "s1")
            (skill / "SKILL.md").write_text(
                'Run `python3 "${CLAUDE_SKILL_DIR}/scripts/renamed.py" x`.\n'
            )
            result = run_checker(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("scripts/renamed.py", result.stderr)

    def test_missing_citation_fails_with_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_skill(root, "p1", "s1")
            (skill / "SKILL.md").write_text(
                "Read `references/ghost.md` before anything.\n"
            )
            result = run_checker(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("references/ghost.md", result.stderr)
            self.assertIn("SKILL.md", result.stderr)

    def test_citation_inside_reference_doc_is_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_skill(root, "p1", "s1")
            (skill / "references" / "guide.md").write_text(
                "See templates/absent.md for the fill-in skeleton.\n"
            )
            (skill / "SKILL.md").write_text("Read `references/guide.md`.\n")
            result = run_checker(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("templates/absent.md", result.stderr)

    def test_empty_root_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_checker(Path(tmp))
            self.assertEqual(result.returncode, 1)
            self.assertIn("no skill directories", result.stderr)

    def test_real_tree_passes(self) -> None:
        result = run_checker(REPO / "plugins")
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
