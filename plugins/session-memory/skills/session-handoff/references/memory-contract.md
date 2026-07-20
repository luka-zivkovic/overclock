# Memory Storage Contract

Shared persistence contract for the session-handoff, lessons-learned, and solutions skills. Each skill ships a byte-identical copy of this file. Read it before any read or write under `.ai/memory/` — file locations, formats, caps, and safety rules come from here, never from improvisation. If the copies ever disagree, treat that as a bug: the skills must stay format-compatible.

## Location

All persistent state lives in `.ai/memory/` at the **target project root**. The `.ai/` directory is deliberately tool-agnostic: these skills run in Claude Code, but the memory format is plain markdown that any agent (Cursor, Codex, a ChatGPT workflow, the next tool) can read and write, so a team's handoffs and lessons are not locked to one LLM. In a monorepo or when the agent was started in a subdirectory, walk up to the repository root (where `.git/` lives) and use that `.ai/memory/` — one project, one memory location.

```
.ai/memory/
├── HANDOFF.md          # single current handoff (latest wins) — owned by session-handoff
├── archive/            # superseded handoffs, timestamped — retention cap: last 5
│   └── HANDOFF-2026-06-10T14-30-00.md
├── LESSONS.md          # accumulated lessons — owned by lessons-learned, surfaced at resume
└── SOLUTIONS.md        # verified problem solutions — owned by solutions, surfaced at resume
```

Create directories as needed (`mkdir -p .ai/memory/archive`). Never assume they exist; never fail because they don't.

## Ownership and interaction

| File | Written by | Read by |
|---|---|---|
| `HANDOFF.md` | session-handoff only | session-handoff |
| `archive/HANDOFF-*.md` | session-handoff only | session-handoff (on request) |
| `LESSONS.md` | lessons-learned only | all — session-handoff surfaces relevant entries at resume |
| `SOLUTIONS.md` | solutions only | all — session-handoff surfaces matching entries at resume |

Cross-skill rule: each file is written by exactly one skill; the others read it. session-handoff reads `LESSONS.md` and `SOLUTIONS.md` but never writes them; lessons-learned and solutions never touch `HANDOFF.md` or each other's file. This keeps each file's history attributable to one skill.

Precedence rule: when a `LESSONS.md` entry contradicts a Decision recorded in `HANDOFF.md`, the lesson wins — lessons are durable and evidence-counted, handoff decisions are session-scoped. Surface the conflict (e.g. as a drift item in the warm-start brief) rather than silently picking either side.

## Schema versioning

Every file starts with a schema-version comment on line 1 so future skill versions can detect and migrate old formats:

```markdown
<!-- memory-schema: v1 -->
```

When reading a file with a missing or unknown schema marker, treat it as hand-edited or foreign: read what is salvageable, do not rewrite it to "fix" the format without telling the user.

## HANDOFF.md format (v1)

Stable section order — never reorder, so diffs stay readable:

```markdown
<!-- memory-schema: v1 -->
# Session Handoff
Saved: <ISO-8601 date and time>

## Current goal
## Plan
## Decisions
## Failed approaches
## Open questions
## Next steps
## Key files
## Environment anchors
```

`## Environment anchors` records, at save time: git branch, HEAD sha (short), dirty-file list, and the save date. In a non-git project, record the date and the mtimes of the key files instead — staleness checks degrade but still work.

Size cap: **~150 lines.** If a handoff would exceed it, compress prose (the plan and failed approaches carry the value; trim decisions narrative first), don't drop the anchors.

## LESSONS.md format (v1)

```markdown
<!-- memory-schema: v1 -->
# Lessons

## <short imperative lesson title>
- **When:** <trigger condition — the situation where this lesson applies>
- **Wrong:** <the approach that failed or was corrected>
- **Right:** <the approach to use instead>
- **Evidence:** <what actually happened — quote the correction or failure>
- **Count:** <integer, times reinforced>
- **Last reinforced:** <ISO-8601 date>
```

One `##` section per lesson. Stable field order within an entry. Updating an existing lesson means editing its `Count` and `Last reinforced` lines in place — do not append a duplicate section and do not reorder entries (reordering churns git diffs).

Size cap: **~200 lines.** When an addition would exceed it, curate: prune or merge the lowest-count, oldest entries first. Never refuse to write a new lesson because the file is full, and never silently discard a high-count lesson.

## SOLUTIONS.md format (v1)

```markdown
<!-- memory-schema: v1 -->
# Solutions

## <short problem-shaped title>
- **Symptoms:** <observable failure — exact error text or wrong behavior>
- **Context:** <module, stack, and situation where this applies>
- **What didn't work:** <attempted fixes that failed, each with why when diagnosed>
- **Solution:** <what actually fixed it, concretely>
- **Why it works:** <the root cause the fix addresses>
- **Verified:** <how the fix was confirmed — the test run, the observed behavior>
- **Date:** <ISO-8601 date of capture or last update>
```

One `##` section per solution. Stable field order. Updating an existing entry (same root
cause, same fix) means editing it in place — refresh `Date`, enrich `Symptoms`/`What didn't
work`; do not append a duplicate section and do not reorder entries.

Size cap: **~250 lines.** When an addition would exceed it, curate: merge overlapping entries
and retire entries whose Context no longer exists. Never silently drop a recent entry.

Staleness rule: a solution describes the codebase as of its `Date`. Current source always
outranks a stored solution — verify the cited context still exists before applying one, and
route mismatches to the solutions skill's suggestion-first refresh flow.

## Archive and retention

Before replacing `HANDOFF.md`, move the existing file to `archive/HANDOFF-<ISO-8601-timestamp>.md` (colons replaced with `-` for filesystem safety). Never silently overwrite.

Retention cap: keep the **5 newest** archived handoffs; delete older ones when archiving a new one. The archive also bounds damage from concurrent sessions: two agent sessions in one repo are last-writer-wins on `HANDOFF.md`, and the archive preserves the loser. Document this limitation when it is relevant; do not build locking.

## Write safety — hard rules

1. **Writes are confined to `.ai/memory/`.** The only exception is an explicitly user-approved addition to `CLAUDE.md` (lessons-learned promotion path). Never delete or modify anything outside `.ai/memory/`.
2. **No secrets, ever.** Credentials, API keys, tokens, passwords, connection strings with passwords, and personal data must never be written to any memory file — even when they appear in the conversation, error output, or environment. Redact (`<redacted: AWS key>`) or omit. This rule has no exceptions and overrides user convenience.
3. **Unparseable files are read-only evidence.** A corrupted or hand-edited file is read for whatever is salvageable and reported as-is. Never overwrite it destructively without telling the user first; archiving the damaged file before writing fresh is the destructive-write escape hatch.
4. **No auto-commit.** Never run `git add`/`git commit` on memory files. The user decides whether to version them. Document both options when asked:
   - **Commit** `.ai/memory/` to share state across machines/teammates (it is plain markdown and diffs cleanly).
   - **Gitignore** it (`echo '.ai/memory/' >> .gitignore`) to keep memory local and private.

## Format principles

- Plain, human-readable markdown — the consumers are an LLM and a human reviewer; readability and git-diffability beat strict parseability.
- Stable section ordering and no timestamps that churn every line; only `Saved:`/`Last reinforced:` lines change on update.
- Size caps keep resume-time context cost low — these files are loaded into context at session start, so every line costs tokens forever after.
