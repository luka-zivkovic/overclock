from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from qa.eval_sandbox import build_settings, require_supported_version
from qa.read_eval_api_key import read_key


class EvalSandboxTests(unittest.TestCase):
    def test_sandbox_is_fail_closed_networkless_and_source_denied(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            work = base / "work"
            plugins = base / "plugins"
            runtime = base / "runtime"
            tools = base / "tools"
            auth = base / "auth"
            repository = base / "source"
            settings = build_settings(
                work=work,
                plugin_root=plugins,
                runtime_root=runtime,
                tool_root=tools,
                repository=repository,
                auth_root=auth,
                api_key_helper="/safe/helper",
            )

            sandbox = settings["sandbox"]
            self.assertTrue(sandbox["enabled"])
            self.assertTrue(sandbox["failIfUnavailable"])
            self.assertFalse(sandbox["allowUnsandboxedCommands"])
            self.assertEqual(sandbox["excludedCommands"], [])
            self.assertEqual(sandbox["network"]["deniedDomains"], ["*"])
            self.assertIn(str(repository), sandbox["filesystem"]["denyRead"])
            self.assertIn(str(repository), sandbox["filesystem"]["denyWrite"])
            self.assertIn(str(work), sandbox["filesystem"]["allowRead"])
            self.assertIn(str(work), sandbox["filesystem"]["allowWrite"])
            self.assertIn(str(runtime), sandbox["filesystem"]["allowWrite"])
            self.assertIn("WebFetch", settings["permissions"]["deny"])
            self.assertIn("Bash(gh *)", settings["permissions"]["deny"])
            self.assertEqual(settings["env"]["PYTHONHASHSEED"], "0")
            self.assertIn("/dev/urandom", sandbox["filesystem"]["allowRead"])
            self.assertIn("/dev/random", sandbox["filesystem"]["allowRead"])
            self.assertFalse(
                any(
                    rule.startswith(("Glob(", "Grep("))
                    for rule in settings["permissions"]["deny"]
                )
            )
            if sys.platform == "darwin":
                self.assertNotIn("/home", sandbox["filesystem"]["denyRead"])
                self.assertNotIn("/home", sandbox["filesystem"]["denyWrite"])
                self.assertNotIn("/proc", sandbox["filesystem"]["denyRead"])
                self.assertIn("/private/etc", sandbox["filesystem"]["denyRead"])
            else:
                self.assertIn("/home", sandbox["filesystem"]["denyRead"])
                self.assertIn("/home", sandbox["filesystem"]["denyWrite"])

    def test_sandbox_collapses_sensitive_descendants(self) -> None:
        home = Path.home()
        settings = build_settings(
            work=Path("/tmp/work"),
            plugin_root=Path("/tmp/plugins"),
            runtime_root=Path("/tmp/runtime"),
            tool_root=Path("/tmp/tools"),
            repository=home / "source" / "repo",
            auth_root=Path("/tmp/auth"),
            api_key_helper="/safe/helper",
        )
        denied = settings["sandbox"]["filesystem"]["denyRead"]
        self.assertTrue(
            any(
                os.path.commonpath([root, str(home)]) == root
                for root in denied
            ),
            f"no denied root covers home directory {home}: {denied}",
        )
        self.assertNotIn(str(home / "source" / "repo"), denied)

    def test_requires_a_sandbox_capable_claude_version(self) -> None:
        require_supported_version("2.1.145 (Claude Code)")
        with self.assertRaisesRegex(ValueError, "2.1.145"):
            require_supported_version("2.1.144 (Claude Code)")
        with self.assertRaisesRegex(ValueError, "parse"):
            require_supported_version("secret-looking diagnostics")

    def test_key_reader_refuses_links_and_permissive_modes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            key = root / "key"
            key.write_text("sk-test\n", encoding="utf-8")
            key.chmod(0o600)
            self.assertEqual(read_key(key), "sk-test")

            key.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "group or other"):
                read_key(key)

            key.chmod(0o600)
            linked = root / "linked"
            linked.symlink_to(key)
            with self.assertRaises(OSError):
                read_key(linked)


if __name__ == "__main__":
    unittest.main()
