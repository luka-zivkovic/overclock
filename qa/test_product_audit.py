from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO / "plugins/product-audit/skills/product-audit"
SCRIPT = SKILL_DIR / "scripts/history.py"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixtures.additional import (  # noqa: E402
    PRODUCT_AUDIT_REPORT,
    build_product_audit_bloat,
    build_product_audit_focused,
)

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.com",
    "GIT_COMMITTER_NAME": "fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.com",
}


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git(root: Path, *args: str, date: str | None = None) -> str:
    env = dict(GIT_ENV)
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    return subprocess.run(
        ["git", *args], cwd=root, env=env, check=True, capture_output=True, text=True
    ).stdout


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *args], env=GIT_ENV, capture_output=True, text=True, check=False
    )


def history(root: Path, *extra: str) -> dict:
    completed = run("--root", str(root), *extra)
    if completed.returncode != 0:
        raise AssertionError(completed.stderr)
    return json.loads(completed.stdout)


def tree_digest(root: Path) -> str:
    """Every byte under the root, the git directory included: the helper must write nothing."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        digest.update(path.relative_to(root).as_posix().encode())
        if path.is_file() and not path.is_symlink():
            digest.update(path.read_bytes())
    return digest.hexdigest()


class PlantedHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name) / "streakly"
        build_product_audit_bloat(cls.root)
        cls.facts = history(cls.root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_summary_is_measured_from_the_newest_commit(self) -> None:
        summary = self.facts["history"]
        self.assertTrue(self.facts["git"])
        self.assertEqual((summary["newest_commit"], summary["oldest_commit"]), ("2026-06-20", "2025-09-10"))
        self.assertEqual(summary["commits"], 9)
        self.assertFalse(summary["shallow_clone"])
        self.assertEqual(summary["uncommitted"], {"modified": 0, "untracked": 0})
        self.assertGreaterEqual(summary["days_since_newest_commit"], 0)
        self.assertEqual(self.facts["recent_window"], {"days": 180, "from": "2025-12-22", "to": "2026-06-20"})
        self.assertEqual(self.facts["recent_commit_count"], 7)
        narrow = history(self.root, "--window-days", "30")
        self.assertEqual((narrow["recent_window"]["from"], narrow["recent_commit_count"]), ("2026-05-21", 2))

    def test_areas_show_when_each_part_arrived_and_where_work_went(self) -> None:
        areas = {area["path"]: area for area in self.facts["areas"]}
        self.assertEqual(areas["app/recipes"]["first_seen"], "2026-04-03")
        self.assertEqual((areas["app/recipes"]["commits"], areas["app/recipes"]["recent_commits"]), (3, 3))
        self.assertEqual(areas["app/recipes"]["recent_by_month"], {"2026-04": 2, "2026-06": 1})
        self.assertEqual(areas["app/habits"]["first_seen"], "2025-09-10")
        self.assertEqual(areas["app/habits"]["recent_commits"], 0)
        self.assertNotIn("recent_by_month", areas["app/habits"])
        self.assertEqual(self.facts["notes"], [])
        self.assertEqual(areas["app/today"]["last_change"], "2025-09-10")
        self.assertEqual(areas["app/friends"]["first_seen"], "2026-06-20")
        paths = [area["path"] for area in self.facts["areas"]]
        top_level = [path for path in paths if "/" not in path]
        self.assertEqual(paths[: len(top_level)], top_level)  # top-level directories lead
        # app/recipes/[id] holds one file and so does its only content: one row is enough.
        self.assertIn("app/recipes/[id]", areas)
        self.assertEqual(self.facts["areas_not_shown"], 0)

    def test_quarters_and_recent_commits_show_the_drift(self) -> None:
        quarters = {row["quarter"]: row for row in self.facts["by_quarter"]}
        self.assertEqual(quarters["2026-Q2"]["commits"], 6)
        self.assertEqual(quarters["2025-Q3"]["commits"], 1)
        self.assertGreater(quarters["2025-Q3"]["new_files"], quarters["2026-Q2"]["new_files"])
        log = self.facts["recent_commits"]
        self.assertEqual(len(log), 7)
        self.assertEqual(log[0], {
            "date": "2026-06-20", "subject": "friends feed placeholder", "touched": ["app/friends", "components"],
        })
        self.assertEqual(log[-1]["subject"], "journal and stats")
        recipes = [entry for entry in log if any("recipes" in place for place in entry["touched"])]
        self.assertEqual(len(recipes), 4)
        self.assertFalse(any("habits" in place or "today" in place for entry in log for place in entry["touched"]))

    def test_the_helper_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "pace"
            build_product_audit_focused(root)
            write(root, "notes.txt", "uncommitted\n")
            before = tree_digest(root)
            facts = history(root)
            self.assertEqual(tree_digest(root), before)
            self.assertEqual(facts["history"]["uncommitted"], {"modified": 0, "untracked": 1})


class HistoryEdgeTests(unittest.TestCase):
    def test_a_renamed_directory_keeps_its_original_arrival_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root, "app/reports/page.tsx", "export default function Reports() {\n  return null;\n}\n")
            write(root, "app/home/page.tsx", "export default function Home() {\n  return null;\n}\n")
            git(root, "init", "-q", "-b", "main")
            git(root, "add", "-A")
            git(root, "commit", "-qm", "reports", date="2025-01-10T10:00:00")
            git(root, "mv", "app/reports", "app/insights")
            git(root, "commit", "-qm", "rename reports to insights", date="2026-03-01T10:00:00")
            areas = {area["path"]: area for area in history(root)["areas"]}
            self.assertNotIn("app/reports", areas)
            self.assertEqual(areas["app/insights"]["first_seen"], "2025-01-10")
            self.assertEqual(areas["app/insights"]["last_change"], "2026-03-01")

    def test_a_history_shorter_than_the_window_is_pointed_out(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "pace"
            build_product_audit_focused(root)
            notes = history(root)["notes"]
            self.assertEqual(len(notes), 1)
            self.assertIn("recent_by_month", notes[0])
            self.assertEqual(history(root, "--window-days", "30")["notes"], [])

    def test_without_git_it_says_so_instead_of_failing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            write(Path(temp), "main.py", "print('hi')\n")
            facts = history(Path(temp))
            self.assertFalse(facts["git"])
            self.assertIn("Ask the owner", facts["note"])

    def test_a_commit_touching_many_places_says_how_many_are_not_listed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index in range(13):
                write(root, f"area{index:02d}/file.py", "x = 1\n")
            write(root, "README.md", "# Everything\n")
            write(root, "src/features/billing/invoice.py", "x = 1\n")
            git(root, "init", "-q", "-b", "main")
            git(root, "add", "-A")
            git(root, "commit", "-qm", "everything at once", date="2026-02-01T10:00:00")
            entry = history(root)["recent_commits"][0]
            self.assertEqual(len(entry["touched"]), 10)
            self.assertEqual(entry["more_places"], 5)
            # The most specific place is kept; the repository root is the first to be dropped.
            self.assertIn("src/features/billing", entry["touched"])
            self.assertNotIn(".", entry["touched"])

    def test_dependencies_and_hidden_directories_are_not_areas(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root, "src/app.py", "x = 1\n")
            write(root, "node_modules/lib/index.js", "x\n")
            write(root, ".cache/blob", "x\n")
            git(root, "init", "-q", "-b", "main")
            git(root, "add", "-A", "-f")
            git(root, "commit", "-qm", "all", date="2026-02-01T10:00:00")
            self.assertEqual([area["path"] for area in history(root)["areas"]], ["src"])

    def test_depth_controls_how_far_down_directories_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root, "a/b/c/d/file.py", "x = 1\n")
            write(root, "a/other.py", "x = 1\n")
            git(root, "init", "-q", "-b", "main")
            git(root, "add", "-A")
            git(root, "commit", "-qm", "nested", date="2026-02-01T10:00:00")
            self.assertEqual([area["path"] for area in history(root)["areas"]], ["a", "a/b"])
            self.assertEqual([area["path"] for area in history(root, "--depth", "1")["areas"]], ["a"])

    def test_bad_arguments_fail_closed(self) -> None:
        missing = run("--root", "/nonexistent/product-audit-root")
        self.assertEqual(missing.returncode, 1)
        self.assertIn("not a directory", missing.stderr)
        with tempfile.TemporaryDirectory() as temp:
            window = run("--root", temp, "--window-days", "0")
            self.assertEqual(window.returncode, 1)
            self.assertIn("must be positive", window.stderr)


class SkillFilesTests(unittest.TestCase):
    def test_the_previous_audit_fixture_follows_the_shipped_template(self) -> None:
        template = (SKILL_DIR / "assets/report-template.md").read_text(encoding="utf-8")
        headings = [line for line in template.splitlines() if line.startswith("## ")]
        self.assertEqual(
            headings,
            ["## Where you are", "## Promise", "## Features", "## Complexity", "## Direction",
             "## Outside view", "## Next move", "## History"],
        )
        self.assertEqual([line for line in PRODUCT_AUDIT_REPORT.splitlines() if line.startswith("## ")], headings)

    def test_the_skill_points_only_at_files_it_ships(self) -> None:
        body = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        for relative in ("scripts/history.py", "references/outside-view.md", "assets/report-template.md"):
            self.assertIn(relative, body)
            self.assertTrue((SKILL_DIR / relative).is_file(), relative)
        shipped = sorted(p.relative_to(SKILL_DIR).as_posix() for p in SKILL_DIR.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        self.assertEqual(
            shipped,
            ["SKILL.md", "agents/openai.yaml", "assets/report-template.md", "references/outside-view.md", "scripts/history.py"],
        )


if __name__ == "__main__":
    unittest.main()
