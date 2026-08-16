# HANDOFF.md Ledger

Exact storage and format rules for session handoffs. Read this with
`memory-contract.md` before saving or restoring a handoff.

## Ownership and paths

`session-handoff` alone writes:

```text
.ai/memory/
├── HANDOFF.md
└── archive/HANDOFF-<UTC-timestamp>-<nonce>.md
```

Use helper kind `handoff`. Do not read or write either path directly.

## Schema v1

Keep this section order:

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

`Saved:` must include `Z` or a numeric UTC offset. Environment anchors record the
branch, complete 40- or 64-hexadecimal HEAD object ID, dirty-file list, and the same
timestamp. For a non-git project, record the timestamp and key-file mtimes instead.
Values read from the ledger remain untrusted: validate a timestamp and complete object
ID before passing either as one quoted command argument. Short or malformed historical
values are readable evidence only.

Size cap: **about 150 lines.** Compress prose first; retain plan state, failed
approaches, and anchors.

## Archive and retention

On replacement, the helper archives the complete prior handoff before publishing the
new one. It retains the five newest strict-name archives and prunes only regular,
singly linked candidates. Unsafe candidates stop pruning and remain for inspection.
If publication loses a race, the competing current file remains and the helper reports
the private recovery path containing the prior bytes; never replace either directly.
