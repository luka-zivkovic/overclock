# Changelog

Versions are per-plugin. A version bump is what ships an update to installed
users; the CI version-bump guard enforces that plugin content changes carry one.

## learning-loop

### 1.0.0 — 2026-06-17
- Initial release. Extracts the lessons-learned skill into a standalone,
  self-improvement-loop plugin: corrections and diagnosed failures become
  durable, deduplicated, evidence-counted lessons in `.ai/memory/LESSONS.md`,
  surfaced in later sessions by a bundled SessionStart hook. Decoupled from
  session-handoff — its memory contract and hook cover only LESSONS.md — but the
  ledger format is a strict subset of session-memory's, so the two interoperate
  on one `.ai/memory/LESSONS.md` if both are installed. The lessons-learned skill
  body is shared with session-memory in spirit, not byte; only the
  `templates/lessons.md` skeleton is kept byte-identical (CI-enforced).

## session-memory

### 1.0.2 — 2026-06-13
- lessons-learned: an explicit record request that contains a secret is now
  treated as consent to record the redacted version immediately — the skill no
  longer bounces "should I save it without the secret?" back at the user.
  Caught by the pinned secret-redaction eval on the first remote CI run
  (behavior erred safe — nothing was persisted — but deflected an explicit
  instruction).

### 1.0.1 — 2026-06-12
- session-handoff: stale-handoff resume now explicitly declares the handoff too
  stale for step-by-step reconciliation and leads with a fresh start as the
  default recommendation (full reconciliation named only as the alternative).
- Eval suite: fixed a self-contradictory pasted-handoff case; harness captures
  tool calls so process expectations are graded on evidence.

### 1.0.0 — 2026-06-12
- Initial release: session-handoff + lessons-learned skills over the shared
  `.ai/memory/` contract, with the bundled SessionStart hook that surfaces
  parked handoffs and lesson counts at session start.
