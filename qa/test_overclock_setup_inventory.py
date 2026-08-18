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
            self.assertFalse(claude["link_target_disclosed"])
            self.assertNotIn("sha256", claude)
            self.assertNotIn("top-secret-value", serialized)
            self.assertNotIn("outside-secret.md", json.dumps(claude))
            self.assertEqual(before, after)

    def test_symlink_target_text_and_cli_diagnostics_are_never_echoed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "project"
            root.mkdir()
            (root / "CLAUDE.md").symlink_to("TOKEN=dont-disclose.md")
            bin_dir = base / "bin"
            bin_dir.mkdir()
            executable = bin_dir / "claude"
            executable.write_text(
                """#!/usr/bin/env python3
import sys
if sys.argv[1:] == ["--version"]:
    print("TOKEN=version-secret")
    raise SystemExit(0)
print("TOKEN=stderr-secret", file=sys.stderr)
raise SystemExit(7)
""",
                encoding="utf-8",
            )
            executable.chmod(0o755)
            env = dict(os.environ)
            env["PATH"] = f"{bin_dir}{os.pathsep}{os.defpath}"
            env["CLAUDE_CONFIG_DIR"] = str(base / "user-config")

            result = inventory.collect_inventory(root, env)
            serialized = json.dumps(result)

            self.assertNotIn("dont-disclose", serialized)
            self.assertNotIn("version-secret", serialized)
            self.assertNotIn("stderr-secret", serialized)
            self.assertEqual(result["host"]["version"], "unknown")
            self.assertEqual(
                result["host"]["error"],
                "claude plugin list exited 7",
            )

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

    def test_symlinked_claude_directory_is_blocked_before_reading(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "project"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            (outside / "CLAUDE.md").write_text(
                "PRIVATE_INSTRUCTION=do-not-disclose\n", encoding="utf-8"
            )
            (outside / "settings.json").write_text(
                json.dumps({"enabledPlugins": {"learning-loop@overclock": True}}),
                encoding="utf-8",
            )
            (root / ".claude").symlink_to(outside, target_is_directory=True)
            env = dict(os.environ)
            env["CLAUDE_CONFIG_DIR"] = str(base / "user-config")
            env["PATH"] = ""

            result = inventory.collect_inventory(root, env)
            serialized = json.dumps(result)

            blocked = [
                item
                for item in result["instruction_files"]
                if item["path"].endswith(".claude/CLAUDE.md")
            ]
            self.assertEqual(blocked[0]["kind"], "blocked")
            self.assertIn("symlinked path component", blocked[0]["reason"])
            self.assertNotIn("PRIVATE_INSTRUCTION", serialized)
            self.assertNotIn(
                "learning-loop@overclock",
                json.dumps(result["settings_overclock_state"]),
            )

    def test_standalone_scan_uses_frontmatter_after_first_hundred_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skills = root / ".claude" / "skills"
            skills.mkdir(parents=True)
            for index in range(120):
                folder = skills / f"filler-{index:03d}"
                folder.mkdir()
                (folder / "SKILL.md").write_text(
                    f"---\nname: filler-{index:03d}\ndescription: filler\n---\n",
                    encoding="utf-8",
                )
            renamed = skills / "z-renamed-lessons"
            renamed.mkdir()
            (renamed / "SKILL.md").write_text(
                "---\nname: lessons-learned\ndescription: durable lessons\n---\n",
                encoding="utf-8",
            )
            env = dict(os.environ)
            env["CLAUDE_CONFIG_DIR"] = str(root / "user-config")
            env["PATH"] = ""

            result = inventory.collect_inventory(root, env)

            self.assertEqual(
                [item["folder"] for item in result["standalone_overlaps"]],
                ["z-renamed-lessons"],
            )
            self.assertEqual(result["standalone_overlaps"][0]["name"], "lessons-learned")

    def test_standalone_scan_reads_frontmatter_from_large_real_skills(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skills = root / ".claude" / "skills"
            skills.mkdir(parents=True)
            catalog = inventory.load_catalog()
            expected = {
                name
                for entry in catalog["packages"]
                for name in entry["skill_names"]
            }
            source_by_name = {
                path.parent.name: path
                for path in (REPO / "plugins").glob("*/skills/*/SKILL.md")
            }
            source_skills = [source_by_name[name] for name in sorted(expected)]
            for index, source in enumerate(source_skills):
                target = skills / f"renamed-{index:02d}"
                target.mkdir()
                (target / "SKILL.md").write_bytes(source.read_bytes())
            env = dict(os.environ)
            env["CLAUDE_CONFIG_DIR"] = str(root / "user-config")
            env["PATH"] = ""

            result = inventory.collect_inventory(root, env)

            observed = {entry["name"] for entry in result["standalone_overlaps"]}
            self.assertEqual(observed, expected)
            self.assertGreater(
                max(source.stat().st_size for source in source_skills),
                8_192,
            )

    def test_standalone_scan_finds_name_after_old_eight_kib_prefix(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / ".claude" / "skills" / "renamed-memory"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\n"
                "description: >\n"
                f"  {'large frontmatter ' * 700}\n"
                "name: session-handoff\n"
                "---\n"
                "# Body\n",
                encoding="utf-8",
            )
            env = dict(os.environ)
            env["CLAUDE_CONFIG_DIR"] = str(root / "user-config")
            env["PATH"] = ""

            result = inventory.collect_inventory(root, env)

            self.assertEqual(
                [entry["name"] for entry in result["standalone_overlaps"]],
                ["session-handoff"],
            )

    def test_user_instruction_metadata_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "project"
            config = Path(temp) / "user-config"
            root.mkdir()
            config.mkdir()
            (config / "CLAUDE.md").write_text(
                "private user instructions\n", encoding="utf-8"
            )
            env = dict(os.environ)
            env["CLAUDE_CONFIG_DIR"] = str(config)
            env["PATH"] = ""

            default = inventory.collect_inventory(root, env)
            opted_in = inventory.collect_inventory(
                root, env, include_user_instructions=True
            )

            self.assertFalse(
                any(item["scope"] == "user" for item in default["instruction_files"])
            )
            self.assertTrue(
                any(item["scope"] == "user" for item in opted_in["instruction_files"])
            )
            self.assertNotIn("private user instructions", json.dumps(opted_in))

    def test_writable_reports_effective_access_not_any_mode_bit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "CLAUDE.md"
            target.write_text("instructions\n", encoding="utf-8")
            target.chmod(0o400)
            env = dict(os.environ)
            env["CLAUDE_CONFIG_DIR"] = str(root / "user-config")
            env["PATH"] = ""

            result = inventory.collect_inventory(root, env)
            item = next(
                entry
                for entry in result["instruction_files"]
                if entry["path"].endswith("CLAUDE.md")
            )

            self.assertEqual(item["writable"], inventory.effective_writable(target))
            self.assertEqual(
                item["writable_basis"], "effective access at inventory time"
            )


if __name__ == "__main__":
    unittest.main()
