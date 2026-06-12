# Overclock

**Claude Code plugins that run your model past spec.**

```
/plugin marketplace add luka-zivkovic/overclock
/plugin install session-memory@overclock
```

## Plugins

### session-memory — stop losing your working state

Claude Code sessions are stateless. Close one (or hit compaction) and the next session starts cold: it re-derives decisions, re-tries approaches that already failed, and keeps building on plans that are no longer true. Corrections you've given evaporate, and you give them again.

`session-memory` fixes both, with two cooperating skills over one shared storage contract:

- **session-handoff** — say *"save our state"* and it writes a structured handoff (goal, plan status, decisions **with rationale**, failed approaches **with diagnosed cause**, next steps, git anchors) to `.ai/memory/HANDOFF.md`. Say *"resume where we left off"* and it verifies those anchors against the live repo, quantifies any drift instead of trusting a stale plan, handles rewritten history and weeks-old handoffs gracefully, and gives you a ≤15-line warm-start brief — then confirms direction before acting. No saved state? It says "cold start" plainly. It never fabricates.
- **lessons-learned** — corrections (*"no, use pnpm, not npm"*) and diagnosed failures become evidence-counted entries in `.ai/memory/LESSONS.md`. Repeated corrections deduplicate by meaning — the count goes up, no duplicates pile up. At 3+ reinforcements it *proposes* a CLAUDE.md line and only edits with your explicit yes. Requirement changes, one-off choices, and anything containing secrets are explicitly never recorded.

Everything lives in plain, diffable markdown under your project's `.ai/memory/` — a deliberately **tool-agnostic** location. The skills run in Claude Code, but the memory belongs to your project, not to a vendor: teammates on Cursor, Codex, or anything else can read the same handoffs and lessons, and write their own in the documented format. Commit `.ai/memory/` to share warm state with your team, or gitignore it to keep it local — the skills never auto-commit, never write outside `.ai/memory/`, and never persist secrets (hard rules, tested).

## This plugin ships a hook (read this)

`session-memory` bundles a **SessionStart hook** that activates when you install the plugin. At session start it runs one shell command that:

- checks for `.ai/memory/HANDOFF.md` and `.ai/memory/LESSONS.md` at the repo root (read-only — it never writes anything);
- if found, injects a short note so the session offers to resume your parked work and consults recorded lessons;
- prints nothing — a complete no-op — in projects that have no `.ai/memory/`.

That hook is what makes resume automatic instead of something you must remember to ask for. The exact command is in [`plugins/session-memory/hooks/hooks.json`](plugins/session-memory/hooks/hooks.json) — it's a dozen lines of `sh`, auditable in ten seconds. Don't want it? Disable the plugin's hooks in `/plugin`, or install the two skills standalone (copy `plugins/session-memory/skills/*` into `~/.claude/skills/`) and skip the hook entirely.

## Evidence, not vibes

Both skills were benchmarked A/B (live `claude -p` sessions in git fixtures, with and without the skill installed, graded independently by a different model than the author). With the skill: 100% of assertions across all cases, including should-NOT-trigger negative controls. Baseline sessions, faced with the same fixtures, executed stale plans without asking, overwrote handoffs without archiving, and edited CLAUDE.md without approval — exactly the failure modes the skills exist to prevent.

## License

MIT
