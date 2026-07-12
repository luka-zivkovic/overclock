---
name: test-discipline
description: "Mandatory pre-edit test gate for existing code. For any reported regression, crash (including an HTTP 500), invalid-input failure, error, or wrong output, invoke this gate before general debugging or implementation—even when the user only says 'fix it' and never requests a test. For a refactor or cleanup, use only when the prompt or project shows the behavior has no tests; never invoke characterization when a full behavioral suite already covers it, because that suite is already the pin. Also use when asked to write a unit/regression test for a named existing function, or when a new test passes and the user asks whether it is trustworthy or 'are we good?'. Reproduce bugs red-before-green, characterize untested behavior before refactoring, and mutation-check new green tests with exact-byte restore. Do NOT use for typos/copy, config/version/dependency bumps, behavior-preserving renames or control-flow rewrites, formatting, generated/vendored/lockfile changes, or new features."
---

# Test Discipline

Three gates agents reliably skip, enforced by the real test runner instead of self-audit: the
failing test before a bug fix, the behavior pin before a refactor of untested code, and the
can-this-test-actually-fail check after a new test goes green. Each gate runs BEFORE the edit
lands (or, for validate, immediately after a test is written), so the safety artifact exists
when it still has power.

## Triage first — silent no-op on trivial work

Before engaging any mode, read `references/right-sizing.md` and `references/anti-triggers.md`.
If the change matches an anti-trigger (typo fix, dependency bump, rename, formatting, new
feature work, generated files, already-covered code), do the requested work and never mention
this skill. The structural check below IS the right-size gate; there is no ceremony on
trivial edits.

## Mode routing — one question

What concrete action is about to happen?

| About to… | Mode | Polarity |
|---|---|---|
| Fix a reported bug with a stated symptom (error, wrong output, failing case) | `repro` | red → green |
| Edit or refactor code with no behavioral test coverage | `characterize` | green → green invariant |
| (Just happened) a new test was written and is green | `validate` | mutate → red → restore |
| Anything matching `references/anti-triggers.md` | none | silent no-op |

`validate` is not a competing trigger: it chains automatically after `repro` and
`characterize` as their shared test-validity check, and fires standalone on any other
freshly-green test.

## Mode: repro — reproduce before you fix

1. **Restate the symptom as a concrete assertion**: input → expected output vs reported wrong
   output. If the report has no observable symptom, ask for one before writing anything.
2. **Find the project's test conventions and existing coverage.** If an existing test already
   asserts the reported behavior and fails for the stated reason, use it as the red oracle;
   do not add a duplicate. Otherwise follow the runner, layout, and naming conventions.
3. **When no adequate test exists, write one asserting the CORRECT behavior** — the behavior
   the fix should produce.
4. **Run it and confirm it fails for the stated reason.** The failure output must reflect the
   reported symptom (the wrong value, the error), not an import or setup problem. Fails for a
   different reason → fix the test, not the code.
   **If it passes, stop.** The bug may be elsewhere, already fixed, or misreported — report
   "cannot reproduce" with the evidence and go no further; never patch speculatively.
5. **Commit a newly written red test** as its own commit (e.g. `test: repro <symptom> (red)`),
   so the reproduction is preserved even if the fix takes several attempts. An adequate
   pre-existing committed test needs no new test commit.
6. **Fix the production code.** Rerun the test → green. Rerun any suite the project treats as
   the pre-commit bar.
7. **Chain into `validate`** on the new test (below).
8. For user-visible behavior, offer a `/verify`-style run-the-app confirmation as the
   post-fix mirror — that step is downstream of this gate, not part of it.

## Mode: characterize — pin behavior before you refactor

1. **Verify the no-coverage precondition.** Search the test suite for the symbol under edit.
   Coverage means tests that assert observable return values, state changes, emitted events,
   errors, or other externally visible effects; mock-only or import-only references don't
   count. If behavioral coverage exists, this mode does not fire — the suite is the pin.
2. **Enumerate the observable behaviors** worth pinning: main paths, edge cases, error paths.
3. **Write tests capturing CURRENT behavior exactly** — including ugly or suspicious outputs,
   annotated as pinned-not-endorsed (a comment like `// pins current behavior; change
   deliberately, not accidentally`). Never "fix" behavior while pinning it.
4. **Run them against the pre-edit code — all green**, then **commit the pin** as its own
   commit before touching the code.
5. **Chain each new pin through `validate`** (below) so a vacuous pin can't fake safety.
6. **Perform the edit, keeping the pins green.** A red pin means behavior changed: stop, and
   either revert the change or get explicit confirmation that the behavior change is intended
   (then update the pin deliberately in its own commit).

## Mode: validate — prove the green test can fail

A green test that cannot go red is worse than no test. Right after any new test passes
(including tests written by the modes above), prove it observes real behavior. Read
`references/mutation-guide.md` for mutation selection; the contract:

1. **Pick one mutation** in the code under test — the regression the test claims to catch
   (invert the fixed condition, wrong constant, skip the guard). One file only.
2. **Back up the exact pre-mutation file before mutating.** Run
   `python3 "${CLAUDE_SKILL_DIR}/scripts/mutation_backup.py" backup FILE --root "${CLAUDE_PROJECT_DIR}"`.
   The helper creates the adjacent `FILE.mutbak`, refuses a pre-existing backup, and refuses
   symlinked, hard-linked, special, or out-of-project targets. Do not substitute `cp`, `mv`,
   a HEAD snapshot, or a hand-rolled backup command.
3. **Mutate → run ONLY the target test → restore.** Run
   `python3 "${CLAUDE_SKILL_DIR}/scripts/mutation_backup.py" restore FILE --root "${CLAUDE_PROJECT_DIR}"`
   unconditionally — on
   red, on green, on runner crash, on anything unexpected — before reporting results or
   asking the user anything. Then rerun the test once to prove the tree is back to green.
4. **Verdict.** Went red → the test is real; say so in one line. Stayed green → the test is
   vacuous (tautology, mock-asserts-the-mock, unread snapshot): strengthen or rewrite it so
   it observes real behavior, then validate the new version the same way.

Never leave a mutation in the tree. A leftover `.mutbak` file or an un-restored mutation is a
broken contract — fixing that outranks everything else in the session.

## Boundaries

- `/verify` and `/run` are post-action mirrors: they confirm behavior after a change. These
  gates run before the edit lands; `repro` and `characterize` may hand off to them after green.
- `/code-review` and `/simplify` are post-diff. A gate never reviews or simplifies; it makes
  the safety artifact exist, then the diff flows onward.
- New feature work belongs to feature-dev end-to-end. These gates protect existing behavior.
- Plan mode produces a plan; these gates produce committed artifacts. Orthogonal — a gate may
  fire after planning.

## Reference files

- `references/anti-triggers.md` — the shared should-NOT-fire surface. Read during triage.
- `references/right-sizing.md` — the one-question triage rule. Read during triage.
- `references/mutation-guide.md` — mutation selection and restore mechanics. Read when
  running validate mode.
