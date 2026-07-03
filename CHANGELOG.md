# Changelog

Versions are per-plugin. A version bump is what ships an update to installed
users; the CI version-bump guard enforces that plugin content changes carry one.

## natural-writing

### 1.0.0 — 2026-07-03
- First published release (added to marketplace.json). A stateless prose
  writing/editing skill that strips AI tells — em-dashes, tell vocabulary
  ("delve"/"leverage"/"tapestry"), bot scaffolding, uniform rhythm, decorative
  bold — while preserving quotes verbatim, keeping load-bearing caveats, and
  staying silent on code, commit messages, and one-line edits. Ships with
  mined before/after examples and an opt-in HTML revision report.
- Live eval suite added (5 cases, including the caveat-must-survive and
  byte-identical-quote traps and two negative controls): 5/5 green.

## discipline-gates

### 0.1.0 — 2026-07-03
- Initial unpublished release (not yet in marketplace.json; publish gated on
  live-eval results). Two pre-action gates over real oracles, packaged per
  `docs/brainstorm/packaging-discipline-gates.md`:
  - **test-discipline** — one multi-mode skill: `repro` (commit a test that
    fails for the stated reason before fixing a reported bug), `characterize`
    (pin untested code's current behavior as committed green tests before
    refactoring), `validate` (mutate the code under a freshly-green test,
    demand red, restore unconditionally — kills vacuous tests).
  - **git-archaeologist** — before deleting/weakening a guard, retry, sleep,
    lock, clamp, or "redundant" check: blame → introducing commit → linked
    PR/issue → Chesterton's-fence warning with quoted evidence; never invents
    intent.
  - Shared should-NOT-trigger surface single-sourced as byte-identical
    per-skill references (CI-guarded via `tools/shared-files.txt`).
- Build decision: the packaging doc's §6 incident-tally demand gate is
  superseded by strategy.md principle 4 (direct request suffices) — built on
  the maintainer's direct pick, 2026-07-03.

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
