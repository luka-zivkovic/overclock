# Packaging design — the discipline-gate family

**Status:** implemented on 2026-07-03 as `plugins/discipline-gates/`. This document is retained as
the historical packaging rationale. Its pre-build demand gate was superseded by
`docs/strategy.md` principle 4: a direct request or concrete use is sufficient demand. Sections
below preserve the reasoning that led to the two-skill package; statements such as “do not build”
describe the decision state before implementation, not the current repository state.

---

## Context

Repeated `skill-brainstorm` runs surfaced **four STRONG candidates** that share one shape: a
**stateless, PRE-action discipline gate** that enforces a step AI agents reliably skip, backed by a
**real deterministic oracle or concrete artifact** (the test runner; git history) rather than the model
auditing itself:

- **repro-first** — before fixing a reported bug, commit a test that fails *for the stated reason*, then
  fix to green. (`rejudge-2026-06-22-1806.md`)
- **characterization-tests** — before refactoring untested code, pin current behavior as committed
  GREEN tests, confirm green on the pre-edit code, keep them green through the edit. (`run-2026-06-23-0046.md`)
- **test-actually-fails** — after writing a NEW green test, mutate the code under test → rerun ONLY that
  test → demand red → restore. Kills tautological / mock-and-assert-the-mock / snapshot-without-reading
  tests. (`run-2026-06-24-0047.md`)
- **git-archaeologist** — before deleting/weakening defensive code, recover its intent via
  blame → introducing commit → linked PR/issue, surfacing a Chesterton's-fence check. (`run-2026-06-23-0046.md`)

Across every run the skeptic panel independently flagged the **same unresolved concern**: these overlap
("commit a test around your edit") and carry **colliding should-NOT-trigger surfaces**, so they probably
want to be **one multi-mode skill** rather than four skills competing for the same routing space. That
packaging decision — left open by the brainstorm — is what this doc settles.

Two panel critiques are folded in so a future build session does not rediscover them:

1. **git-archaeologist's as-pitched trigger is subjective and self-referential** ("surprising or
   load-bearing code"). The agent must already judge code surprising before the gate engages — the very
   blind-spot the skill exists to backstop, so it risks *not firing exactly when most needed*. The
   trigger must be re-anchored to a **structural defensive-code action-class**
   (guard / early-return / retry / sleep / lock / clamp / "redundant" check).
2. **The four anti-trigger surfaces collide.** Resolved here by making the should-NOT-trigger surface
   **shared and single-sourced**, not duplicated four times.

**Out of scope on purpose:** PR-reviewer and review-comment-resolver. They are the **review** family
(produce-side and consume-side respectively), a different packaging question — not part of this
discipline-gate cluster.

**The bar (from `strategy.md`, clarified 2026-06-22, and `.ai/memory/LESSONS.md`):** usefulness +
non-redundancy. Memory/right-sizing is a *bonus*, never a gate. All four candidates clear that bar on
design. What they lack is **prong-1 demand** — evidenced recurring in-repo incidents — which is ≈ zero
for all four. **Demand gates *when* to build, not the design.** A valid conclusion, and the one reached
here, is: *design it as the structure below now; do not build until demand shows up.*

---

## 1. Recommendation — ONE plugin, TWO skills

Package the family as one plugin, **`discipline-gates`**, containing **two skills** over a **shared
`references/` contract** that single-sources the anti-trigger surface and the right-sizing rule:

- **Skill A — `test-discipline` (multi-mode):** consolidates **repro-first + characterization-tests +
  test-actually-fails** into one skill with three modes (`repro`, `characterize`, `validate`).
- **Skill B — `git-archaeologist` (single skill, same plugin):** kept separate; shares the family shape
  and the shared anti-trigger references, but not the test-runner mechanism.

This mirrors the repo's own precedent: **`session-memory` is one plugin housing two cooperating skills**
(`session-handoff` + `lessons-learned`) over a shared `references/memory-contract.md`. Same pattern here.

### Why the test trio is ONE skill, not three

- **Same object, one anti-trigger surface.** All three act on *tests around a code edit* and share a
  near-identical should-NOT-trigger surface. Three separate descriptions would **fight for the same
  routing space** — exactly the collision the panel flagged. The repo's `qa/trigger_battery.py`
  optimizes a skill's frontmatter `description` for routing precision; three overlapping descriptions
  degrade it, while one coherent "make the tests around your edit trustworthy" description improves it.
- **`validate` (test-actually-fails) composes with the other two — it is not a competing trigger.** It
  is the shared *test-validity oracle* that should run on **any freshly-green test**, including the green
  test `characterize` writes and the now-green test `repro` ends with. It is the **verification leg the
  other two modes reuse**, not a fourth thing fighting for a slot. That is the single strongest argument
  for consolidation.
- **One routing decision.** Polarity differs by mode (red→green / green→green-invariant /
  mutate→red→restore), but the *routing question is one structural check answered up front* (§2).

### Why git-archaeologist stays SEPARATE (not a fourth mode)

- **Disjoint object and mechanism.** Its object is **git history**; its mechanism is
  **blame → commit → linked PR**, with no test runner involved. Folding a history-recovery mode into a
  test skill produces an incoherent description ("write failing tests AND recover git history") that
  **hurts routing precision and eval clarity**.
- It stays *in the plugin* because it shares the family **shape** (stateless PRE-action gate over a real
  artifact) and the **shared anti-trigger references** — so the cluster is discoverable as one unit
  without muddying either description.

### Trade-off table (the decision)

| Option | Trigger collisions | Anti-trigger surface | Discoverability | Eval clarity | Verdict |
|---|---|---|---|---|---|
| One 4-mode mega-skill | None (single router) | Single | One entry, muddy "tests AND git history" description | **Poor** — disjoint mechanisms in one description hurt routing | ✗ |
| **2 skills / 1 plugin** | **None within the test trio**; archaeologist is structurally distinct | **Shared** via `references/` | Plugin groups the family; two clean descriptions | **High** — each description is coherent | ✓ **recommended** |
| Four separate skills | **High** — three descriptions fight for "touching code under test" | Four colliding surfaces | Four competing entries | **Low** — "refactor this fn" routes ambiguously to repro-first OR characterize | ✗ |

---

## 2. Per-mode triggers + anti-triggers

Routing is one structural question answered up front: *what concrete action is about to happen?* Triggers
are anchored to **structural actions**, never subjective cues.

| Mode / Skill | Fires when (STRUCTURAL trigger) | Mechanism / oracle | Polarity |
|---|---|---|---|
| `test-discipline` · **repro** | About to edit prod code to **fix a reported bug with an observable wrong behavior** (a stated symptom: error, wrong output, failing case) | Commit a RED test that fails *for the stated reason*; fix to green | red→green |
| `test-discipline` · **characterize** | About to **edit/refactor a function or module with NO behavioral test coverage** (grep/LSP: no test asserts its output values) | Pin current outputs as committed GREEN tests, confirm green on pre-edit code, keep green through the edit | green→green invariant |
| `test-discipline` · **validate** (test-actually-fails) | **Just wrote/edited a NEW test that is currently green** — chains automatically after `repro`/`characterize`, and fires on any standalone new test | Mutate the code under test → rerun ONLY that test → **demand red** → **restore-always** | mutate→red→restore |
| **`git-archaeologist`** | About to **delete or weaken a structural defensive construct**: guard clause, early return, retry/backoff, `sleep`, lock/mutex, clamp/bounds check, or a check commented/implied as "redundant"/"defensive" | blame → introducing commit → linked PR/issue → Chesterton's-fence warning | recover-intent-first |

The git-archaeologist trigger is the **pattern-list above**, **not** "surprising code" (panel critique #1).

### Shared should-NOT-trigger surface

Single-sourced in `references/anti-triggers.md`; shipped as **should-NOT-trigger evals from day one**
(strategy.md creation-bar prong 3). These are real anti-triggers — a gate that fires on them is bloat:

- Trivial typos / copy / string fixes
- Config / version / dependency bumps
- Pure renames / signature-only changes with no behavior change
- Formatting / whitespace / import reordering / lint-only diffs
- **New feature work → defer to feature-dev**
- Generated / vendored / lockfile hunks
- *Mode-specific:* code **already covered by behavioral tests** (→ `characterize` does not fire); code
  with **no prior git history** / pure additions (→ `git-archaeologist` has nothing to recover)

---

## 3. Delegation / coexistence boundaries

- **/verify, /run — POST-action mirrors.** They confirm behavior *after* a change. The gates are
  **PRE-action**: they ensure the safety artifact (failing test / pinned behavior / recovered intent)
  exists *before* the edit lands. `repro`'s "fix to green" and `characterize`'s "keep green" may **hand
  off to /verify** for run-the-app confirmation, but *writing the test first* is upstream and unowned by
  verify. (Confirmed in `rejudge-2026-06-22-1806.md`: verify is the post-fix mirror, repro is the
  pre-fix gate — complementary, not overlapping.)
- **/code-review, /simplify — POST-diff.** /code-review finds bugs once a diff exists; /simplify cleans
  a diff. The gates fire *before* the diff. A gate never reviews or simplifies; it makes the safety
  artifact exist, then the diff flows onward to /code-review.
- **feature-dev — NEW feature implementation, end-to-end.** Explicit **anti-trigger**: new-feature work
  defers to feature-dev (feature-shaped, with grep-confirmed zero bug-repro / characterization / history
  content). The gates are for **bug-fix / refactor / delete on EXISTING code**.
- **plan mode — produces a plan, not an executable artifact.** Orthogonal; a gate may fire after
  planning but performs the concrete test/history step plan mode does not.

---

## 4. Right-sizing rule

One binary triage **up front**: does a **structural trigger** (§2) apply *and* is there observable
behavior / defensive intent at stake? If the change matches any shared anti-trigger → **silent no-op**.
The gate engages only when the structural precondition holds — the action-class check **is** the
right-size gate; there is no ceremony on trivial edits. `validate` mode additionally carries a hard
**restore-always safety contract**: the mutation is reverted unconditionally, including on test failure
or interruption.

---

## 5. Summary of the recommended structure

```
plugins/discipline-gates/
  .claude-plugin/plugin.json
  references/
    anti-triggers.md          # shared should-NOT-trigger surface (§2)
    right-sizing.md           # shared triage rule (§4)
  skills/
    test-discipline/SKILL.md  # modes: repro | characterize | validate
    git-archaeologist/SKILL.md
```

(Structure is illustrative of the packaging decision — **not** a build instruction.)

---

## 6. Demand-validation plan

Prong-1 demand is ≈ zero for all four candidates. **Build nothing** until a mode's incident tally clears
the creation bar (the same unmet need seen **≥2–3×, evidenced — not imagined**).

| Mode | Real, recurring usage signal that would justify building | Capture method |
|---|---|---|
| `repro` | "fix this bug / it's throwing X / wrong output" turns where the agent patched **without** first committing a failing test (especially where it fixed a nearby-but-wrong cause) | Passive transcript mining (the same grep the brainstorm already runs for prong-1); manual incident tally |
| `characterize` | "refactor / clean up this function" on **untested** code where behavior silently changed | Same |
| `validate` | A shipped **green test later found vacuous** (tautological, mock-asserts-mock, snapshot-without-reading) | Caught when a later bug slips past a "passing" test; log the incident when observed |
| `git-archaeologist` | "I almost deleted a deliberate fix" — a guard/retry/clamp removed and a regression reappeared | Manual tally on occurrence |

**How to capture cheaply, without building the skill:**

- **Passive transcript mining** — reuse the prong-1 grep methodology the brainstorm runs; filter
  `type:user` turns and discard this brainstorm's own contamination (the recurring false-positive trap
  noted across runs).
- **A one-line CLAUDE.md probe** — e.g. "before fixing a reported bug, write a test that fails for the
  stated reason" — and watch whether the discipline actually gets reached for in real work. Cheap signal
  on whether the gate earns a trigger.
- **A manual incident tally** in `docs/brainstorm/` or `.ai/memory/`, incremented on each genuine
  observation in day-to-day work.

**Build trigger:** the first mode whose tally reaches **≥2–3 distinct, evidenced incidents** enters the
build queue — implemented as a *mode of `test-discipline`* (or as the `git-archaeologist` skill), per the
packaging settled here. No mode ships standalone, and `validate` ships as the chained verification leg of
`test-discipline`, never as a fourth trigger.

---

## Honest conclusion

Design it as the **two-skill `discipline-gates` plugin** (Skill A `test-discipline` with `repro` /
`characterize` / `validate` modes; Skill B `git-archaeologist`), with a **shared, single-sourced
anti-trigger surface** and the **git-archaeologist trigger re-anchored** to the structural
defensive-code action-class. **Do not build until prong-1 demand (§6) shows up.** Packaging is decided
here; demand is the remaining gate on build order.
