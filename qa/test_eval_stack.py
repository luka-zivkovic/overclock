from __future__ import annotations

import json
import subprocess
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
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

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


if __name__ == "__main__":
    unittest.main()
