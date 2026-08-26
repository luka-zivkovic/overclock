# Importing Claude Code + Codex sessions into ironside

pi gets a live tracer (`references/pi-tracer.md`). Claude Code and Codex
don't expose equivalent hooks mid-stream, but both write complete session
logs to disk — these two zero-dependency importers (Node >= 18) parse a
log post-hoc into the same ironside ingest envelope, so all three
harnesses land in one trace store with the same shape.

Both scripts read config from `IRONSIDE_URL` + `IRONSIDE_API_KEY` env
vars, falling back to `~/.pi/agent/ironside-tracer.json`. Both redact
secret-shaped strings and truncate fields at ~50KB (same rules as the pi
tracer), batch POSTs at the 500-event ingest cap, and take `--dry-run`
to print the envelope instead of POSTing. Both are **idempotent by
construction**: every id derives from the session id plus a stable log
identifier, so re-importing a session upserts the same rows — sweeps and
repeated hook fires are safe.

## What each importer captures

**`scripts/import-claude-session.mjs`** — one transcript from
`~/.claude/projects/<project-slug>/<session-id>.jsonl`:

| transcript | ironside |
| --- | --- |
| session | trace `cc:<repo-or-slug>` (id = session id, `metadata.harness=claude-code`, cwd/branch/version) |
| user prompt → next prompt | span `turn N` |
| assistant API message (streamed chunks share `message.id`) | generation: model, text output, input/output/cache token usage |
| `tool_use` + matching `tool_result` | child span; `level=error` on `is_error` |
| tool input touching `…/skills/<name>/SKILL.md` | trace tag `skill:<name>` |

**`scripts/import-codex-session.mjs`** — one rollout from
`~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` (first record:
`session_meta`):

| rollout | ironside |
| --- | --- |
| `session_meta` | trace `codex:<repo-or-dir>` (id = rollout id, `metadata.harness=codex`, cwd/originator/cli version) |
| `task_started` → `task_complete`/`turn_aborted` | span `turn N` (id = the log's `turn_id`) |
| assistant `response_item:message` | generation: text output, model from `turn_context`, usage from the following `token_count` |
| `custom_tool_call`/`function_call`/`local_shell_call` + `*_call_output` (paired by `call_id`) | child span |
| `mcp_tool_call_end` | child span (start back-dated by the reported duration; `level=error` on tool error) |
| `patch_apply_end` | child span `apply_patch` (changed files as input) |

Unknown record types never crash an import — they are skipped and
counted on stderr. Verify an import the same way as any ingest: the
trace in the UI, and `GET /api/v1/projects/<proj>/ingest-failures`
staying empty.

## Auto-trigger recipes

**Claude Code — Stop hook.** The Stop hook's stdin JSON carries
`transcript_path`; `--hook-stdin` reads it. In
`~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node /path/to/scripts/import-claude-session.mjs --hook-stdin"
          }
        ]
      }
    ]
  }
}
```

Each Stop fire re-imports the whole transcript so far; idempotent
upserts make that a cheap refresh, not duplication.

**Codex — notify hook.** Codex's `notify` program receives a JSON
argument on `agent-turn-complete`, but it contains no rollout path — use
`--latest` (newest rollout by mtime, which is the one that just wrote).
In `~/.codex/config.toml`:

```toml
notify = ["node", "/path/to/scripts/import-codex-session.mjs", "--latest"]
```

**Either — manual or cron sweep.** Idempotency makes a blind sweep safe:

```bash
find ~/.codex/sessions -name 'rollout-*.jsonl' -mtime -1 \
  | xargs -n1 node /path/to/scripts/import-codex-session.mjs
```

## Honest limits

- **Post-hoc, not live.** Nothing lands until the hook fires or the
  sweep runs; a hard-crashed session imports only what reached the log.
- **Whatever the log format omits stays omitted.** Codex reasoning is
  encrypted in the rollout — it cannot be captured. Codex `token_count`
  is per API call: usage attaches to the assistant message it follows,
  so API calls that produced only tool calls contribute no generation
  row and their usage is dropped. Neither log records cost, so
  `costDetails` is always absent.
- **Known-skipped Codex records:** sub-agent activity
  (`sub_agent_activity`, `response_item:agent_message`,
  `inter_agent_communication_metadata`) and `web_search_end` are
  counted-and-skipped, not mapped.
- **Claude Code subagent transcripts**
  (`<session>/subagents/agent-*.jsonl`) reuse the parent sessionId; the
  importer refuses them because their rows would overwrite the parent
  trace. Only main `<session>.jsonl` files import.
- Timestamps are record-level: a tool span's duration is the gap between
  its call and result records, which includes any queueing/approval wait.
