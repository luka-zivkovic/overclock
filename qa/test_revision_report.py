from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = (
    Path(__file__).resolve().parent.parent
    / "plugins/natural-writing/skills/natural-writing/scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))
from build_revision_report import build, validate  # noqa: E402


class RevisionReportTest(unittest.TestCase):
    def test_embeds_hostile_and_unicode_text_as_base64_json(self) -> None:
        hostile = '</script><script>window.pwned = true</script> café'
        data = {
            "title": "Safety check",
            "original": hostile,
            "revised": "The literal marker stays text. Café.",
            "changes": [
                {"type": "rewrite", "before": hostile, "after": "safe", "reason": "clarity"}
            ],
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, output = root / "data.json", root / "report.html"
            source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            build(source, output, root=root)
            html = output.read_text(encoding="utf-8")

        self.assertNotIn(hostile, html)
        self.assertNotIn("__DATA_BASE64__", html)
        encoded = re.search(r'atob\("([A-Za-z0-9+/=]+)"\)', html)
        self.assertIsNotNone(encoded)
        decoded = json.loads(base64.b64decode(encoded.group(1)).decode("utf-8"))
        self.assertEqual(decoded, data)

    def test_rejects_rewrite_without_reason(self) -> None:
        with self.assertRaisesRegex(ValueError, "reason"):
            validate({
                "original": "a",
                "revised": "b",
                "changes": [{"type": "rewrite", "before": "a", "after": "b"}],
            })

    def test_refuses_output_symlink_without_touching_target(self) -> None:
        data = {
            "original": "before",
            "revised": "after",
            "changes": [
                {"type": "rewrite", "before": "before", "after": "after", "reason": "clarity"}
            ],
        }
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "project"
            root.mkdir()
            source = root / "data.json"
            source.write_text(json.dumps(data), encoding="utf-8")
            outside = base / "outside.txt"
            outside.write_text("must survive", encoding="utf-8")
            output = root / "report.html"
            output.symlink_to(outside)

            with self.assertRaises(FileExistsError):
                build(source, output, root=root)

            self.assertTrue(output.is_symlink())
            self.assertEqual(outside.read_text(encoding="utf-8"), "must survive")

    def test_refuses_symlinked_output_parent(self) -> None:
        data = {"original": "a", "revised": "b", "changes": []}
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "project"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            source = root / "data.json"
            source.write_text(json.dumps(data), encoding="utf-8")
            (root / "linked").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(OSError):
                build(source, root / "linked/report.html", root=root)

            self.assertFalse((outside / "report.html").exists())

    def test_refuses_symlinked_input(self) -> None:
        data = {"original": "outside", "revised": "outside", "changes": []}
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "project"
            root.mkdir()
            outside = base / "outside.json"
            outside.write_text(json.dumps(data), encoding="utf-8")
            source = root / "data.json"
            source.symlink_to(outside)

            with self.assertRaises(OSError):
                build(source, root / "report.html", root=root)

            self.assertFalse((root / "report.html").exists())

    def test_cli_runs_from_an_unrelated_project_directory(self) -> None:
        data = {"original": "a", "revised": "b", "changes": []}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data.json").write_text(json.dumps(data), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "build_revision_report.py"),
                    "data.json",
                    "report.html",
                    "--root",
                    str(root),
                ],
                cwd=root,
                env=dict(os.environ),
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((root / "report.html").is_file())


if __name__ == "__main__":
    unittest.main()
