from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_invocation import command_name, explicit_prompt, invocation_evidence


class EvalInvocationTests(unittest.TestCase):
    def test_explicit_prompt_uses_namespaced_plugin_command(self) -> None:
        self.assertEqual(
            explicit_prompt("critical-thinking", "critical-thinking", "Check this."),
            "/critical-thinking:critical-thinking Check this.",
        )

    def test_explicit_prompt_does_not_duplicate_existing_command(self) -> None:
        prompt = "/overclock-setup:setup Audit this project."
        self.assertEqual(explicit_prompt("overclock-setup", "setup", prompt), prompt)

    def test_command_names_are_confined(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsafe plugin"):
            command_name("../escape", "skill")

    def test_invocation_evidence_requires_prompt_command_and_loaded_plugin(self) -> None:
        event = {
            "type": "system",
            "subtype": "init",
            "slash_commands": ["critical-thinking:critical-thinking"],
            "skills": ["critical-thinking:critical-thinking"],
            "plugins": [{"name": "critical-thinking"}],
            "apiKeySource": "apiKeyHelper",
        }
        with tempfile.TemporaryDirectory() as temp:
            stream = Path(temp) / "stdout.jsonl"
            stream.write_text(json.dumps(event) + "\n", encoding="utf-8")
            evidence = invocation_evidence(
                stream,
                plugin="critical-thinking",
                skill="critical-thinking",
                effective_prompt=(
                    "/critical-thinking:critical-thinking Stress-test this plan."
                ),
            )

        self.assertTrue(evidence["verified"])
        self.assertTrue(evidence["requested_directly"])
        self.assertTrue(evidence["command_available"])
        self.assertTrue(evidence["target_plugin_loaded"])
        self.assertTrue(evidence["isolated_auth"])

    def test_invocation_evidence_fails_when_only_discovered_not_requested(self) -> None:
        event = {
            "type": "system",
            "subtype": "init",
            "slash_commands": ["critical-thinking:critical-thinking"],
            "plugins": [{"name": "critical-thinking"}],
            "apiKeySource": "apiKeyHelper",
        }
        with tempfile.TemporaryDirectory() as temp:
            stream = Path(temp) / "stdout.jsonl"
            stream.write_text(json.dumps(event) + "\n", encoding="utf-8")
            evidence = invocation_evidence(
                stream,
                plugin="critical-thinking",
                skill="critical-thinking",
                effective_prompt="Stress-test this plan.",
            )

        self.assertFalse(evidence["verified"])
        self.assertFalse(evidence["requested_directly"])


if __name__ == "__main__":
    unittest.main()
