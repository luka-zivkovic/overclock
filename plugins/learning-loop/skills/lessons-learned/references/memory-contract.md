# Memory Storage Contract

Persistence contract for the lessons-learned skill. Read it before any read or write under `.ai/memory/` — file location, format, cap, and safety rules come from here, never from improvisation.

This contract is deliberately a strict subset of the `session-memory` plugin's contract: the `LESSONS.md` format below is byte-for-byte the same schema that plugin uses, so a ledger written by this skill is readable by that plugin's session-handoff resume flow, and vice versa. The two never need to be installed together — but when they are, they share one `.ai/memory/LESSONS.md` without conflict.

## Location

All persistent state lives in `.ai/memory/` at the **target project root**. The `.ai/` directory is deliberately tool-agnostic: this skill runs in Claude Code, but the memory format is plain markdown that any agent (Cursor, Codex, a ChatGPT workflow, the next tool) can read and write, so a team's lessons are not locked to one LLM. In a monorepo or when the agent was started in a subdirectory, walk up to the repository root (where `.git/` lives) and use that `.ai/memory/` — one project, one memory location.

```
.ai/memory/
└── LESSONS.md          # accumulated lessons — owned by lessons-learned
```

Create directories as needed (`mkdir -p .ai/memory`). Never assume they exist; never fail because they don't.

## Schema versioning

The file starts with a schema-version comment on line 1 so future skill versions can detect and migrate old formats:

```markdown
<!-- memory-schema: v1 -->
```

When reading a file with a missing or unknown schema marker, treat it as hand-edited or foreign: read what is salvageable, do not rewrite it to "fix" the format without telling the user.

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

## Write safety — hard rules

1. **Writes are confined to `.ai/memory/`.** The only exception is an explicitly user-approved addition to `CLAUDE.md` (the lessons-learned promotion path). Never delete or modify anything outside `.ai/memory/`.
2. **No secrets, ever.** Credentials, API keys, tokens, passwords, connection strings with passwords, and personal data must never be written to any memory file — even when they appear in the conversation, error output, or environment. Redact (`<redacted: AWS key>`) or omit. This rule has no exceptions and overrides user convenience.
3. **Unparseable files are read-only evidence.** A corrupted or hand-edited file is read for whatever is salvageable and reported as-is. Never overwrite it destructively without telling the user first.
4. **No auto-commit.** Never run `git add`/`git commit` on memory files. The user decides whether to version them. Document both options when asked:
   - **Commit** `.ai/memory/` to share lessons across machines/teammates (it is plain markdown and diffs cleanly).
   - **Gitignore** it (`echo '.ai/memory/' >> .gitignore`) to keep memory local and private.

## Format principles

- Plain, human-readable markdown — the consumers are an LLM and a human reviewer; readability and git-diffability beat strict parseability.
- Stable section ordering and no timestamps that churn every line; only the `Last reinforced:` line changes on update.
- The size cap keeps surfacing-time context cost low — this file is loaded into context when lessons are consulted, so every line costs tokens.
