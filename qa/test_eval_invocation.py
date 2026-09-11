from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_invocation import command_name, explicit_prompt, invocation_evidence, setup_turn_record, record_setup_failure


class EvalInvocationTests(unittest.TestCase):
    def test_failed_setup_accounting_tolerates_malformed_metrics_without_a_grade(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            (out / "setup-0.jsonl").write_text("not-json\n" + json.dumps({
                "type": "result", "subtype": "error", "usage": "invalid",
                "total_cost_usd": "invalid", "duration_ms": -1, "num_turns": None,
            }))
            record_setup_failure(out, "baseline", 0, 2)
            metrics = json.loads((out / "metrics.json").read_text())
            self.assertEqual(metrics["infrastructure_error"], "setup_failed")
            self.assertEqual(metrics["total_cost_usd"], 0)
            self.assertEqual(metrics["input_tokens"], 0)
            self.assertFalse(json.loads((out / "invocation.json").read_text())["verified"])
            self.assertFalse((out / "grading.json").exists())

    def test_setup_record_retains_tool_actions_and_results_for_judging(self) -> None:
        call = {"type": "tool_use", "id": "edit-1", "name": "Edit", "input": {"file_path": "feature.md"}}
        output = {"type": "tool_result", "tool_use_id": "edit-1", "content": "saved"}
        result = {"type": "result", "subtype": "success", "session_id": "session-a", "result": "Dossier ready."}
        with tempfile.TemporaryDirectory() as temp:
            stream = Path(temp) / "stdout.jsonl"
            stream.write_text("\n" + "\n".join(json.dumps(event) for event in (
                {"type": "assistant", "message": {"content": [call]}},
                {"type": "user", "message": {"content": [output]}}, result,
            )))
            captured, context = setup_turn_record(stream, "Start the dossier.")
        self.assertEqual(captured, result)
        self.assertIn(json.dumps(call), context)
        self.assertIn(json.dumps(output), context)
        self.assertIn("Start the dossier.", context)
        self.assertIn("Dossier ready.", context)

    def test_setup_record_refuses_incomplete_or_failed_turns(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            stream = Path(temp) / "stdout.jsonl"
            for record in (
                {"type": "system", "subtype": "init"},
                {"type": "result", "subtype": "error_max_turns", "result": "Incomplete"},
                {"type": "result", "subtype": "success", "is_error": True},
            ):
                with self.subTest(record=record):
                    stream.write_text(json.dumps(record))
                    with self.assertRaisesRegex(ValueError, "setup turn"):
                        setup_turn_record(stream, "Start the dossier.")

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

    def test_continuation_requires_successful_explicit_setup_in_the_same_session(self) -> None:
        event = {
            "type": "system", "subtype": "init", "session_id": "session-a",
            "slash_commands": ["feature-dossier:feature-dossier"],
            "plugins": [{"name": "feature-dossier"}], "apiKeySource": "apiKeyHelper",
        }
        setup = {"type": "result", "subtype": "success", "is_error": False, "session_id": "session-a"}
        with tempfile.TemporaryDirectory() as temp:
            stream = Path(temp) / "stdout.jsonl"
            stream.write_text(json.dumps(event) + "\n")
            for result, prompt, expected in (
                (setup, "/feature-dossier:feature-dossier Start the dossier.", True),
                ({**setup, "session_id": "different"}, "/feature-dossier:feature-dossier Start.", False),
                ({**setup, "is_error": True}, "/feature-dossier:feature-dossier Start.", False),
                (setup, "The dossier was activated earlier.", False),
                (None, "/feature-dossier:feature-dossier Start.", False),
            ):
                with self.subTest(result=result, prompt=prompt):
                    evidence = invocation_evidence(
                        stream, plugin="feature-dossier", skill="feature-dossier",
                        effective_prompt="Implement the approved export option.",
                        setup_prompt=prompt, setup_result=result,
                    )
                    self.assertEqual(evidence["verified"], expected)
                    self.assertFalse(evidence["requested_directly"])


if __name__ == "__main__":
    unittest.main()
