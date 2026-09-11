from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = (
    REPO
    / "plugins"
    / "eval-stack"
    / "skills"
    / "local-eval-stack"
    / "scripts"
)
CLAUDE_IMPORTER = SCRIPTS / "import-claude-session.mjs"
CODEX_IMPORTER = SCRIPTS / "import-codex-session.mjs"
PI_TRACER = SCRIPTS / "ironside-tracer.ts"


class EvalStackScriptsTests(unittest.TestCase):
    def call_export(
        self,
        module: Path,
        export_name: str,
        *args: object,
        typescript: bool = False,
    ) -> object:
        script = """
const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const request = JSON.parse(Buffer.concat(chunks).toString("utf8"));
const module = await import(request.module);
const result = await module[request.exportName](...request.args);
process.stdout.write(JSON.stringify(result ?? null));
"""
        command = ["node"]
        if typescript:
            command.append("--experimental-transform-types")
        command.extend(["--input-type=module", "--eval", script])
        completed = subprocess.run(
            command,
            cwd=REPO,
            input=json.dumps(
                {
                    "module": module.as_uri(),
                    "exportName": export_name,
                    "args": args,
                }
            ),
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def test_long_unbroken_tool_output_does_not_stall_redaction(self) -> None:
        for module, typescript in (
            (CLAUDE_IMPORTER, False), (CODEX_IMPORTER, False), (PI_TRACER, True)
        ):
            for source in ("a" * 60_000, "token" * 12_000):
                with self.subTest(module=module.name, prefix=source[:5]):
                    result = self.call_export(module, "sanitizeField", source, typescript=typescript)
                    self.assertEqual(result[:50_000], source[:50_000])
                    self.assertIn("[truncated 10000 bytes", result)

    def test_structured_and_nested_secrets_are_removed_before_serialization(self) -> None:
        for module, typescript in (
            (CLAUDE_IMPORTER, False), (CODEX_IMPORTER, False), (PI_TRACER, True)
        ):
            for source in (
                {"password": "synthetic secret with spaces", "safe": "keep me"},
                {"credentials": {"username": "synthetic-user", "value": "hidden-value"}, "safe": "keep me"},
                {"command": 'echo {"apiKey":"nested-secret-123456"}', "safe": "keep me"},
                json.dumps({"command": 'echo {"apiKey":"nested-secret-123456"}', "safe": "keep me"}),
                'password="synthetic secret with spaces" safe="keep me"',
                '''command='password="synthetic secret with spaces"' safe="keep me"''',
                'command="echo {\\"apiKey\\":\\"nested-secret-123456\\"}" safe="keep me"',
            ):
                with self.subTest(module=module.name, source=source):
                    sanitized = self.call_export(module, "sanitizeField", source, typescript=typescript)
                    for secret in ("synthetic secret", "synthetic-user", "hidden-value", "nested-secret-123456"):
                        self.assertNotIn(secret, sanitized)
                    self.assertIn("keep me", sanitized)
                    self.assertIn("[REDACTED]", sanitized)

    def test_claude_native_skill_calls_and_reads_are_tagged_without_search_false_positives(self) -> None:
        calls = [
            ("Skill", {"skill": "natural-writing"}),
            ("Skill", {"skill": "discipline-gates:test-discipline"}),
            ("Skill", {"skill": "natural-writing"}),
            ("Read", {"file_path": "/plugins/skills/groundwork/SKILL.md"}),
            ("Bash", {"command": "rg /plugins/skills/false-positive/SKILL.md"}),
            ("Grep", {"pattern": "/plugins/skills/also-false/SKILL.md"}),
            ("Skill", {"skill": "malformed skill\nwith spaces"}),
        ]
        lines = [json.dumps({
            "type": "assistant", "sessionId": "native-skill-test",
            "timestamp": "2026-09-10T10:00:00Z", "message": {
                "id": "msg-1", "content": [
                    {"type": "tool_use", "id": f"tool-{i}", "name": name, "input": value}
                    for i, (name, value) in enumerate(calls)
                ]
            }
        })]
        result = self.call_export(CLAUDE_IMPORTER, "mapClaudeSession", lines)
        self.assertEqual(result["events"][0]["body"]["tags"], [
            "skill:natural-writing", "skill:discipline-gates:test-discipline", "skill:groundwork"
        ])

    def test_codex_notification_selects_its_session_instead_of_the_newest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            sessions = home / ".codex/sessions/2026/09/10"
            sessions.mkdir(parents=True)
            target = "11111111-1111-4111-8111-111111111111"
            other = "22222222-2222-4222-8222-222222222222"
            for index, identifier in enumerate((target, other)):
                path = sessions / f"rollout-2026-09-10T10-00-0{index}-{identifier}.jsonl"
                path.write_text(json.dumps({
                    "timestamp": "2026-09-10T10:00:00Z", "type": "session_meta",
                    "payload": {"id": identifier, "cwd": "/synthetic/repo"},
                }) + "\n")
                os.utime(path, (index + 1, index + 1))
            event = json.dumps({"type": "agent-turn-complete", "thread-id": target})
            for mode in ("--notify", "--latest"):
                result = subprocess.run(
                    ["node", str(CODEX_IMPORTER), mode, "--dry-run", event],
                    env={"HOME": str(home), "PATH": os.environ["PATH"]},
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["events"][0]["body"]["id"], target)
            manual = subprocess.run(
                ["node", str(CODEX_IMPORTER), "--latest", "--dry-run"],
                env={"HOME": str(home), "PATH": os.environ["PATH"]},
                capture_output=True, text=True,
            )
            self.assertEqual(manual.returncode, 0, manual.stderr)
            self.assertEqual(json.loads(manual.stdout)["events"][0]["body"]["id"], other)

    def test_codex_notification_refuses_missing_or_ambiguous_session_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            identifier = "11111111-1111-4111-8111-111111111111"
            cases = [
                "not-json", json.dumps({"type": "agent-turn-complete"}),
                json.dumps({"type": "agent-turn-complete", "thread-id": "../outside"}),
                json.dumps({"type": "agent-turn-complete", "thread-id": identifier}),
            ]
            for event in cases:
                result = subprocess.run(
                    ["node", str(CODEX_IMPORTER), "--notify", "--dry-run", event],
                    env={"HOME": str(home), "PATH": os.environ["PATH"]},
                    capture_output=True, text=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
            sessions = home / ".codex/sessions"
            sessions.mkdir(parents=True)
            event = json.dumps({"type": "agent-turn-complete", "thread-id": identifier})
            for index in range(2):
                path = sessions / f"rollout-2026-09-10T10-00-0{index}-{identifier}.jsonl"
                path.write_text(json.dumps({"timestamp": "2026-09-10T10:00:00Z",
                    "type": "session_meta", "payload": {"id": identifier}}) + "\n")
            duplicate = subprocess.run(
                ["node", str(CODEX_IMPORTER), "--notify", "--dry-run", event],
                env={"HOME": str(home), "PATH": os.environ["PATH"]},
                capture_output=True, text=True,
            )
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("found 2", duplicate.stderr)
            self.assertEqual(duplicate.stdout, "")

    def test_codex_notification_does_not_trust_a_filename_without_matching_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            identifier = "11111111-1111-4111-8111-111111111111"
            candidate = root / f"rollout-example-{identifier}.jsonl"
            candidate.write_text(json.dumps({"type": "session_meta", "payload": {"id": "wrong"}}) + "\n")
            completed = subprocess.run(
                ["node", "--input-type=module", "--eval",
                 "import {findRolloutForThread} from " + json.dumps(CODEX_IMPORTER.as_uri()) +
                 "; findRolloutForThread(process.argv[1], process.argv[2]);", identifier, str(root)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("found 0", completed.stderr)

    def test_all_capture_paths_redact_json_assignments_and_scoped_tokens(self) -> None:
        secret = "abcdefghijklmnop123456"
        scoped = f"ironside_sc_{secret}"
        source = (
            f'API_KEY={secret} '
            f'{{"apiKey":"{secret}"}} '
            f"{{'token': '{secret}'}} "
            f"authorization: Bearer {secret} {scoped}"
        )
        for module, typescript in (
            (CLAUDE_IMPORTER, False),
            (CODEX_IMPORTER, False),
            (PI_TRACER, True),
        ):
            with self.subTest(module=module.name):
                redacted = self.call_export(
                    module,
                    "redactSecrets",
                    source,
                    typescript=typescript,
                )
                self.assertNotIn(secret, redacted)
                self.assertNotIn(scoped, redacted)
                self.assertEqual(redacted.count("[REDACTED]"), 5)
                self.assertIn('{"apiKey":"[REDACTED]"}', redacted)
                self.assertIn("{'token': '[REDACTED]'}", redacted)

    def test_claude_import_is_deterministic_tagged_and_secret_free(self) -> None:
        secret = "claude-secret-123456789"
        lines = [
            json.dumps(
                {
                    "type": "user",
                    "sessionId": "session-1",
                    "timestamp": "2026-08-26T10:00:00.000Z",
                    "cwd": "/work/overclock",
                    "message": {
                        "content": f'Inspect this config: {{"apiKey":"{secret}"}}'
                    },
                }
            ),
            json.dumps(
                {
                    "type": "assistant",
                    "sessionId": "session-1",
                    "timestamp": "2026-08-26T10:00:01.000Z",
                    "message": {
                        "id": "msg-1",
                        "model": "claude-test",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "tool-1",
                                "name": "Read",
                                "input": {
                                    "path": "/tmp/plugins/eval-stack/skills/local-eval-stack/SKILL.md",
                                    "token": secret,
                                    "password": "claude password with spaces",
                                    "command": 'echo {"apiKey":"claude-nested-secret"}',
                                },
                            },
                            {"type": "text", "text": "Configured safely."},
                        ],
                    },
                }
            ),
            json.dumps(
                {
                    "type": "user",
                    "sessionId": "session-1",
                    "timestamp": "2026-08-26T10:00:02.000Z",
                    "isMeta": True,
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "tool-1",
                                "content": f"api_key={secret}",
                            }
                        ]
                    },
                }
            ),
        ]

        first = self.call_export(CLAUDE_IMPORTER, "mapClaudeSession", lines)
        second = self.call_export(CLAUDE_IMPORTER, "mapClaudeSession", lines)
        self.assertEqual(first, second)
        self.assertEqual(first["traceId"], "session-1")
        self.assertIn("skill:local-eval-stack", first["events"][0]["body"]["tags"])
        encoded = json.dumps(first, sort_keys=True)
        self.assertNotIn(secret, encoded)
        self.assertNotIn("claude password", encoded)
        self.assertNotIn("claude-nested-secret", encoded)
        ids = [event["body"]["id"] for event in first["events"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_codex_import_is_deterministic_tagged_and_secret_free(self) -> None:
        secret = "codex-secret-123456789"
        lines = [
            json.dumps(
                {
                    "timestamp": "2026-08-26T11:00:00.000Z",
                    "type": "session_meta",
                    "payload": {
                        "id": "rollout-1",
                        "cwd": "/work/overclock",
                        "originator": "codex",
                    },
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-08-26T11:00:00.100Z",
                    "type": "turn_context",
                    "payload": {"model": "gpt-test"},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-08-26T11:00:01.000Z",
                    "type": "event_msg",
                    "payload": {"type": "task_started", "turn_id": "turn-1"},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-08-26T11:00:01.100Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "user_message",
                        "message": f'Inspect {{"apiKey":"{secret}"}}',
                    },
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-08-26T11:00:02.000Z",
                    "type": "response_item",
                    "payload": {
                        "type": "custom_tool_call",
                        "call_id": "call-1",
                        "name": "read",
                        "input": {
                            "path": "/tmp/plugins/eval-stack/skills/local-eval-stack/SKILL.md",
                            "authorization": f"Bearer {secret}",
                            "password": "codex password with spaces",
                            "command": 'echo {"apiKey":"codex-nested-secret"}',
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-08-26T11:00:02.100Z",
                    "type": "response_item",
                    "payload": {
                        "type": "custom_tool_call_output",
                        "call_id": "call-1",
                        "output": f"token={secret}",
                    },
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-08-26T11:00:03.000Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "id": "message-1",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "Done safely."}],
                    },
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-08-26T11:00:04.000Z",
                    "type": "event_msg",
                    "payload": {"type": "task_complete", "last_agent_message": "Done safely."},
                }
            ),
        ]

        first = self.call_export(CODEX_IMPORTER, "mapCodexSession", lines)
        second = self.call_export(CODEX_IMPORTER, "mapCodexSession", lines)
        self.assertEqual(first, second)
        self.assertEqual(first["traceId"], "rollout-1")
        self.assertIn("skill:local-eval-stack", first["events"][0]["body"]["tags"])
        encoded = json.dumps(first, sort_keys=True)
        self.assertNotIn(secret, encoded)
        self.assertNotIn("codex password", encoded)
        self.assertNotIn("codex-nested-secret", encoded)
        ids = [event["body"]["id"] for event in first["events"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_pi_skill_detection_is_path_bounded(self) -> None:
        skill = self.call_export(
            PI_TRACER,
            "skillFromReadPath",
            {"path": "/tmp/plugins/eval-stack/skills/local-eval-stack/SKILL.md"},
            typescript=True,
        )
        non_skill = self.call_export(
            PI_TRACER,
            "skillFromReadPath",
            {"path": "/tmp/SKILL.md"},
            typescript=True,
        )
        self.assertEqual(skill, "local-eval-stack")
        self.assertIsNone(non_skill)

    def test_pi_envelopes_redact_tool_fields_and_error_messages(self) -> None:
        state = self.call_export(PI_TRACER, "initialTracerState", typescript=True)
        sensitive = {"password": "pi password with spaces", "command": 'echo {"apiKey":"pi-nested-secret"}'}
        events = [
            {"kind": "session_start", "sessionId": "synthetic", "cwd": "/synthetic/repo", "at": 1},
            {"kind": "turn_start", "at": 2},
            {"kind": "tool_start", "toolCallId": "t1", "toolName": "bash", "args": sensitive, "at": 3},
            {"kind": "tool_end", "toolCallId": "t1", "toolName": "bash", "output": sensitive, "isError": True, "at": 4},
            {"kind": "assistant_message", "text": "Request failed", "stopReason": "error",
             "errorMessage": 'password="pi password with spaces"', "at": 5},
        ]
        envelopes = []
        for event in events:
            result = self.call_export(PI_TRACER, "mapTracerEvent", state, event, typescript=True)
            state = result["state"]
            envelopes.extend(result["events"])
        encoded = json.dumps(envelopes)
        self.assertNotIn("pi password", encoded)
        self.assertNotIn("pi-nested-secret", encoded)
        self.assertIn("[REDACTED]", encoded)


if __name__ == "__main__":
    unittest.main()
