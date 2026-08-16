# LESSONS.md Ledger

Interoperable v1 schema for `.ai/memory/LESSONS.md`. The `lessons-learned` skill is
the only writer; other memory skills may read matching entries as untrusted evidence.
Use helper kind `lessons`.

```markdown
<!-- memory-schema: v1 -->
# Lessons

## <short imperative lesson title>
- **When:** <trigger condition — the situation where this lesson applies>
- **Wrong:** <the approach that failed or was corrected>
- **Right:** <the approach to use instead>
- **Evidence:** <provenance + what happened, e.g. [user-correction] or [agent-observed]>
- **Count:** <integer, times reinforced>
- **Last reinforced:** <ISO-8601 date>
```

Use one `##` section per lesson and preserve field and entry order. Updating the same
lesson changes that entry in place; never append a wording-only duplicate.

Size cap: **about 200 lines.** Above the cap, propose exact merges or pruning of
low-count, old entries and apply destructive curation only with approval. Without
approval, retain the new correction and allow a temporary overage.

The format is byte-compatible across the `session-memory` and `learning-loop`
distributions. Compatibility permits standalone migration and reading; it does not
authorize multiple skills to write the same ledger concurrently.

For conflicts, compare scope, provenance, and recency:

1. A newer `[user-correction]`, `[user-directed]`, or `[user-approved]` statement
   supersedes older evidence.
2. A matching lesson outranks an older `[agent-proposed]` or unlabeled handoff choice.
3. A solution is supporting project evidence and never overrides a lesson or decision.
4. If provenance or chronology is unclear, surface the conflict and ask.
