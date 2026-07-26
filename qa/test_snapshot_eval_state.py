from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from qa import snapshot_eval_state


class EvalStateSnapshotTests(unittest.TestCase):
    def init_repo(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "fixture@example.com"],
            cwd=root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "fixture"],
            cwd=root,
            check=True,
        )
        (root / "tracked.txt").write_text("before\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=root, check=True)

    def test_normal_memory_git_and_untracked_content_are_captured(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "work"
            output = Path(temp) / "state"
            root.mkdir()
            self.init_repo(root)
            memory = root / ".ai/memory"
            memory.mkdir(parents=True)
            (memory / "LESSONS.md").write_text("safe lesson\n", encoding="utf-8")
            (root / "note.txt").write_text("untracked note\n", encoding="utf-8")
            (root / "tracked.txt").write_text("after\n", encoding="utf-8")

            snapshot_eval_state.capture(root, output)

            self.assertIn("safe lesson", (output / "memory.txt").read_text())
            self.assertIn("untracked note", (output / "untracked.txt").read_text())
            self.assertIn("+after", (output / "git_diff.txt").read_text())

    def test_memory_and_untracked_links_never_disclose_outside_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "work"
            output = base / "state"
            root.mkdir()
            self.init_repo(root)
            outside = base / "outside-secret"
            outside.write_text("HOST-TOKEN-DO-NOT-DISCLOSE\n", encoding="utf-8")
            memory = root / ".ai/memory"
            memory.mkdir(parents=True)
            (memory / "LESSONS.md").symlink_to(outside)
            (root / "untracked-link").symlink_to(outside)

            snapshot_eval_state.capture(root, output)
            serialized = "\n".join(
                path.read_text(encoding="utf-8", errors="replace")
                for path in output.iterdir()
            )

            self.assertNotIn("HOST-TOKEN-DO-NOT-DISCLOSE", serialized)
            self.assertIn("blocked symlink", serialized)

    def test_hardlinked_untracked_file_is_not_read(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "work"
            output = base / "state"
            root.mkdir()
            self.init_repo(root)
            outside = base / "outside-secret"
            outside.write_text("HARDLINK-SECRET\n", encoding="utf-8")
            os.link(outside, root / "linked")

            snapshot_eval_state.capture(root, output)
            text = (output / "untracked.txt").read_text(encoding="utf-8")

            self.assertNotIn("HARDLINK-SECRET", text)
            self.assertIn("blocked hard-linked file", text)

    def test_hostile_git_external_diff_and_fsmonitor_are_not_executed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "work"
            output = base / "state"
            root.mkdir()
            self.init_repo(root)
            sentinel = base / "must-not-exist"
            payload = root / "payload.sh"
            payload.write_text(
                f"#!/bin/sh\nprintf attacked > {sentinel}\n",
                encoding="utf-8",
            )
            payload.chmod(0o755)
            subprocess.run(
                ["git", "config", "diff.external", str(payload)],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "config", "core.fsmonitor", str(payload)],
                cwd=root,
                check=True,
            )
            (root / "tracked.txt").write_text("after\n", encoding="utf-8")

            snapshot_eval_state.capture(root, output)

            self.assertFalse(sentinel.exists())
            self.assertIn("+after", (output / "git_diff.txt").read_text())


if __name__ == "__main__":
    unittest.main()
