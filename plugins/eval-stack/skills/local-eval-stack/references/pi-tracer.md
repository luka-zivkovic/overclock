# pi session tracer — capture into ironside

The bundled `scripts/ironside-tracer.ts` is a pi extension: every pi
session becomes an ironside trace with turns as spans, LLM calls as
generations (token usage included), and tool executions as child spans.
Reading any `…/skills/<name>/SKILL.md` tags the trace `skill:<name>` —
sessions become queryable by the skills they used.

## Install

```bash
cp scripts/ironside-tracer.ts ~/.pi/agent/extensions/
cat > ~/.pi/agent/ironside-tracer.json <<'EOF'
{ "url": "http://localhost:8788", "apiKey": "<ironside_sc_… from seed>", "environment": "dev" }
EOF
```

Restart pi (or `/reload`). Already-running sessions keep the old config.

## Properties you can rely on

- **Fail-open**: ironside down or misconfigured never breaks a session;
  errors log once and drop.
- **Redaction**: secret-shaped strings (keys/tokens) are replaced with
  `[REDACTED]` before leaving the process; large fields truncate at 50KB.
- **Kill switch**: `IRONSIDE_TRACER_DISABLE=1`.
- The config file holds a credential — keep it OUT of any dotfiles/backup
  sync (SECURITY).

## Verify

Run one pi session, wait for it to end, then check the ironside UI: a
`pi:<repo>` trace with turn/generation/tool structure and, if a skill
fired, its `skill:` tag. If nothing lands, check ironside's ingest
dead-letter queue and the credential's ingest scope.

## Other harnesses

Claude Code and Codex both import post-hoc from their on-disk session
logs via the bundled importers (`scripts/import-claude-session.mjs`,
`scripts/import-codex-session.mjs`) — same envelope, same redaction and
truncation rules, idempotent re-runs, with hook recipes for automatic
capture. → `references/importing-claude-codex.md`. For skill-run capture
into coeval specifically, coeval's bundled `coeval-audit` skill capture
hook (per-repo opt-in) still applies to Claude Code.
