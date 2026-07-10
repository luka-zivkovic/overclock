from __future__ import annotations

import base64
import json
import re
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
            build(source, output)
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


if __name__ == "__main__":
    unittest.main()
