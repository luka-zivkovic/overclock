from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

SCRIPT_DIR = (
    Path(__file__).resolve().parent.parent
    / "plugins/natural-writing/skills/natural-writing/scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))
from build_revision_report import build, validate  # noqa: E402


class MarkupCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.elements.append((tag, dict(attrs)))


class RevisionReportTest(unittest.TestCase):
    def test_embeds_hostile_and_unicode_text_as_base64_json(self) -> None:
        hostile = '</script><script>window.pwned = true</script> café'
        data = {
            "title": "Safety check",
            "original": hostile,
            "revised": "The literal marker stays text. Café.",
            "changes": [
                {
                    "type": "rewrite",
                    "before": hostile,
                    "after": "The literal marker stays text. Café.",
                    "reason": "clarity",
                }
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

    def test_rejects_changes_that_do_not_reconstruct_original(self) -> None:
        with self.assertRaisesRegex(ValueError, "reconstruct original"):
            validate({
                "original": "whole original",
                "revised": "whole revised",
                "changes": [
                    {
                        "type": "rewrite",
                        "before": "partial",
                        "after": "whole revised",
                        "reason": "clarity",
                    }
                ],
            })

    def test_rejects_changes_that_do_not_reconstruct_revised(self) -> None:
        with self.assertRaisesRegex(ValueError, "reconstruct revised"):
            validate({
                "original": "whole original",
                "revised": "whole revised",
                "changes": [
                    {
                        "type": "rewrite",
                        "before": "whole original",
                        "after": "partial",
                        "reason": "clarity",
                    }
                ],
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
        data = {
            "original": "a",
            "revised": "b",
            "changes": [
                {"type": "rewrite", "before": "a", "after": "b", "reason": "clarity"}
            ],
        }
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
        data = {
            "original": "outside",
            "revised": "outside",
            "changes": [{"type": "keep", "text": "outside"}],
        }
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
        data = {
            "original": "a",
            "revised": "b",
            "changes": [
                {"type": "rewrite", "before": "a", "after": "b", "reason": "clarity"}
            ],
        }
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

    def test_refuses_hardlinked_input(self) -> None:
        data = {"original": "a", "revised": "a", "changes": [{"type": "keep", "text": "a"}]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "data.json"
            source.write_text(json.dumps(data), encoding="utf-8")
            os.link(source, root / "second-name.json")

            with self.assertRaisesRegex(ValueError, "hard links"):
                build(source, root / "report.html", root=root)

            self.assertFalse((root / "report.html").exists())

    def test_refuses_replacing_hardlinked_output(self) -> None:
        data = {"original": "a", "revised": "a", "changes": [{"type": "keep", "text": "a"}]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "data.json"
            source.write_text(json.dumps(data), encoding="utf-8")
            output = root / "report.html"
            output.write_text("old report", encoding="utf-8")
            second_name = root / "shared-report.html"
            os.link(output, second_name)

            with self.assertRaisesRegex(ValueError, "hard links"):
                build(source, output, root=root, replace=True)

            self.assertEqual(output.read_text(encoding="utf-8"), "old report")
            self.assertEqual(second_name.read_text(encoding="utf-8"), "old report")

    def test_report_has_complete_aria_tab_contract_and_keyboard_controls(self) -> None:
        data = {
            "original": "before",
            "revised": "after",
            "changes": [
                {
                    "type": "rewrite",
                    "before": "before",
                    "after": "after",
                    "reason": "clarity",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "data.json"
            output = root / "report.html"
            source.write_text(json.dumps(data), encoding="utf-8")
            build(source, output, root=root)
            html = output.read_text(encoding="utf-8")

        parser = MarkupCollector()
        parser.feed(html)
        tablists = [
            attrs
            for _tag, attrs in parser.elements
            if attrs.get("role") == "tablist"
        ]
        tabs = [
            attrs
            for tag, attrs in parser.elements
            if tag == "button" and attrs.get("role") == "tab"
        ]
        panels = {
            attrs["id"]: attrs
            for _tag, attrs in parser.elements
            if attrs.get("role") == "tabpanel"
        }

        self.assertEqual(len(tablists), 1)
        self.assertEqual(len(tabs), 3)
        self.assertEqual(set(panels), {"original", "revised", "diff"})
        for tab in tabs:
            panel_id = tab["aria-controls"]
            self.assertIn(tab["aria-selected"], {"true", "false"})
            self.assertIn(tab["tabindex"], {"0", "-1"})
            self.assertEqual(panels[panel_id]["aria-labelledby"], tab["id"])
        self.assertEqual(
            [tab["aria-selected"] for tab in tabs],
            ["true", "false", "false"],
        )
        self.assertEqual([tab["tabindex"] for tab in tabs], ["0", "-1", "-1"])
        for key in ("ArrowRight", "ArrowLeft", "Home", "End"):
            self.assertIn(f'event.key === "{key}"', html)
        self.assertIn('btn.addEventListener("keydown"', html)
        self.assertIn("event.preventDefault()", html)
        self.assertIn("next.focus()", html)
        self.assertIn('tab.setAttribute("aria-selected", String(selected))', html)
        self.assertIn("panel.hidden = !selected", html)

    def test_change_reasons_are_visible_and_inserted_with_textcontent(self) -> None:
        hostile_reason = '</span><script>window.reasonPwned = true</script>'
        data = {
            "original": "before",
            "revised": "after",
            "changes": [
                {
                    "type": "rewrite",
                    "before": "before",
                    "after": "after",
                    "reason": hostile_reason,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "data.json"
            output = root / "report.html"
            source.write_text(json.dumps(data), encoding="utf-8")
            build(source, output, root=root)
            html = output.read_text(encoding="utf-8")

        self.assertNotIn(hostile_reason, html)
        self.assertIn('reason.className = "reason"', html)
        self.assertIn("reason.textContent = `Reason: ${text}`", html)
        self.assertIn("container.appendChild(reason)", html)
        self.assertNotIn(".title =", html)
        self.assertNotIn(".innerHTML", html)


if __name__ == "__main__":
    unittest.main()
