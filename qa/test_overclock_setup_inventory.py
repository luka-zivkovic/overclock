import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "plugins/overclock-setup/skills/setup/scripts/inspect_overclock.py"
SPEC = importlib.util.spec_from_file_location("inspect_overclock", SCRIPT)
assert SPEC and SPEC.loader
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


class OverclockSetupInventoryTests(unittest.TestCase):
    def make_fake_claude(self, directory: Path) -> None:
        executable = directory / "claude"
        executable.write_text(
            """#!/usr/bin/env python3
import json, sys
if sys.argv[1:] == [\"--version\"]:
    print(\"2.1.206 (Claude Code)\")
elif sys.argv[1:] == [\"plugin\", \"list\", \"--json\"]:
    print(json.dumps([
      {\"id\": \"session-memory@overclock\", \"version\": \"1.0.3\", \"scope\": \"user\", \"enabled\": True, \"installPath\": \"/secret/cache\"},
      {\"id\": \"github@official\", \"version\": \"1\", \"scope\": \"user\", \"enabled\": True, \"mcpServers\": {\"headers\": {\"Authorization\": \"real-secret\"}}}
    ]))
else:
    raise SystemExit(2)
""",
            encoding="utf-8",
        )
        executable.chmod(0o755)

    def test_filters_cli_and_settings_to_overclock_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".claude").mkdir()
            (root / ".claude/settings.json").write_text(
                json.dumps(
                    {
                        "enabledPlugins": {
                            "session-memory@overclock": True,
                            "learning-loop@overclock": True,
                            "unrelated@private": True,
                        },
                        "apiToken": "must-not-escape",
                    }
                ),
                encoding="utf-8",
            )
            (root / "README.md").write_text("fixture\n", encoding="utf-8")

            bin_dir = root / "bin"
            bin_dir.mkdir()
            self.make_fake_claude(bin_dir)
            env = dict(os.environ)
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            env["CLAUDE_CONFIG_DIR"] = str(root / "user-config")

            result = inventory.collect_inventory(root, env)
            serialized = json.dumps(result)
            self.assertIn("session-memory@overclock", serialized)
            self.assertIn("learning-loop@overclock", serialized)
            self.assertNotIn("unrelated@private", serialized)
            self.assertNotIn("must-not-escape", serialized)
            self.assertNotIn("real-secret", serialized)
            self.assertNotIn("/secret/cache", serialized)

    def test_symlink_metadata_does_not_follow_or_disclose_target(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "project"
            root.mkdir()
            outside = base / "outside-secret.md"
            outside.write_text("TOKEN=top-secret-value\n", encoding="utf-8")
            (root / "CLAUDE.md").symlink_to(outside)
            env = dict(os.environ)
            env["CLAUDE_CONFIG_DIR"] = str(base / "user-config")
            env["PATH"] = ""

            before = sorted(str(path.relative_to(base)) for path in base.rglob("*"))
            result = inventory.collect_inventory(root, env)
            after = sorted(str(path.relative_to(base)) for path in base.rglob("*"))
            serialized = json.dumps(result)

            claude = next(item for item in result["instruction_files"] if item["path"].endswith("CLAUDE.md"))
            self.assertEqual(claude["kind"], "symlink")
            self.assertNotIn("sha256", claude)
            self.assertNotIn("top-secret-value", serialized)
            self.assertEqual(before, after)

    def test_instruction_metadata_records_format_without_contents(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "CLAUDE.md").write_bytes(b"\xef\xbb\xbfline one\r\nsecret-looking-line")
            env = dict(os.environ)
            env["CLAUDE_CONFIG_DIR"] = str(root / "user-config")
            env["PATH"] = ""

            result = inventory.collect_inventory(root, env)
            item = next(entry for entry in result["instruction_files"] if entry["path"].endswith("CLAUDE.md"))
            self.assertTrue(item["bom"])
            self.assertTrue(item["crlf"])
            self.assertFalse(item["final_newline"])
            self.assertNotIn("secret-looking-line", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
