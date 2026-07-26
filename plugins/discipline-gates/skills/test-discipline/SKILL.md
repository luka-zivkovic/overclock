---
name: test-discipline
description: "Mandatory pre-edit test gate for changes to existing code. Use before fixing a reported regression, crash (including an HTTP 500), invalid-input failure, error, or wrong output—even when the user only says 'fix it' and never requests a test. For a refactor or cleanup, use only when the named behavior lacks behavioral tests; any adequate behavioral coverage is already the pin. Also use proportionately when asked only to write a unit/regression test for named existing behavior, or explicitly asked to validate whether a freshly-green test detects its claimed regression. Reproduce fixes red-before-green, characterize untested behavior before refactoring, and mutation-check only when the workflow or user requests it. Never stage or commit artifacts. Do NOT use for diagnosis-only requests, typos/copy, config/version/dependency bumps, behavior-preserving renames or control-flow rewrites, formatting, generated/vendored/lockfile changes, or ordinary new-feature implementation."
---

# Test Discipline

Three gates agents reliably skip, plus a proportional explicit test-only path, enforced by the
real test runner instead of self-audit: the
failing test before a bug fix, the behavior pin before a refactor of untested code, and the
can-this-test-actually-fail check after a new test goes green. Each gate runs BEFORE the edit
lands (or, for validate, immediately after a test is written), so the safety artifact exists
when it still has power.

## Triage first — silent no-op on trivial work

Before engaging any mode, read `references/right-sizing.md` and `references/anti-triggers.md`.
If the change matches an anti-trigger (typo fix, dependency bump, rename, formatting,
new-feature implementation without an explicit validate request, generated files,
already-covered code), do the requested work and never mention this skill. The structural check
below IS the right-size gate; there is no ceremony on trivial edits.

## Mode routing — one question

What concrete action is about to happen?

| About to… | Mode | Polarity |
|---|---|---|
| Fix a reported bug with a stated symptom (error, wrong output, failing case) | `repro` | red → green |
| Edit or refactor code with no behavioral test coverage | `characterize` | green → green invariant |
| Write only a test for named existing behavior | `test-only` | run and report; no production edit |
| Explicitly validate a fresh green test, or validate a repro/characterization test | `validate` | mutate → observe → restore |
| Anything matching `references/anti-triggers.md` | none | silent no-op |

`validate` is not a competing implicit trigger: it chains after `repro` and `characterize`, and
fires standalone only when the user explicitly asks to validate a freshly-green test. New-feature
implementation stays out of scope; an explicit post-test mutation-check is allowed because it
validates the test rather than taking over the feature workflow.

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
5. **Preserve the red test in the working tree.** Do not stage, commit, push, or alter unrelated
   index/worktree state. The red output is the pre-edit evidence; capture it in the response or
   eval record rather than repository history.
6. **Fix the production code.** Rerun the test → green. Rerun any suite the project treats as
   the pre-commit bar.
7. **Chain into `validate`** on the repro oracle after it turns green. This includes a
   pre-existing committed test that was red before the fix; “newly green” describes the observed
   transition, not whether the test file itself was newly written.
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
4. **Run them against the pre-edit code — all green.** Keep the pins in the working tree and
   record the pre-edit output. Do not stage or commit them.
5. **Chain each new pin through `validate`** (below) so a vacuous pin can't fake safety.
6. **Perform the edit, keeping the pins green.** A red pin means behavior changed: stop, and
   either revert the change or get explicit confirmation that the behavior change is intended,
   then update the pin deliberately without staging or committing it.

## Mode: test-only — honor the narrow request

When the user asks only to add a unit or regression test for named existing behavior:

1. Inspect the project's conventions and existing behavioral coverage; extend an appropriate test
   instead of duplicating it.
2. Establish the expected behavior from the user's request, an authoritative specification, or
   current behavior. Ask one focused question if the intended assertion is genuinely ambiguous.
3. Write the smallest behavioral test and run only the relevant test target.
4. Do not edit production code. If the test is red, report the observed mismatch; a test-only
   request does not authorize fixing it. If green, report it as passing.
5. Do not mutation-check automatically. Run `validate` only if the user explicitly asked to assess
   the test's sensitivity. Never stage, commit, or push the test.

## Mode: validate — prove the green test can fail

A green test that cannot go red is worse than no test. Right after a repro/characterization oracle
becomes green—including a pre-existing repro test that failed before the fix—prove it observes real
behavior. A test-only request does not opt into mutation. Read
`references/mutation-guide.md` for mutation selection; the contract:

1. **Pick one mutation** in the code under test — the regression the test claims to catch
   (invert the fixed condition, wrong constant, skip the guard). One file only.
2. **Run one transactional trial.** Prefer:

   First resolve the current host's installed `test-discipline` directory and authorized project
   root to absolute paths. Substitute those actual absolute paths, rather than assuming a
   provider-specific environment variable:

   ```bash
   python3 "/absolute/installed/test-discipline/scripts/mutation_trial.py" src/module.py \
     --root "/absolute/project/root" --old 'EXACT ORIGINAL' --new 'MUTATION' \
     -- TARGET_TEST_COMMAND...
   ```

   The wrapper publishes one integrity-checked adjacent backup atomically, applies one exact
   replacement, runs only the supplied target test, and attempts restoration in `finally`. It
   restores only when the target still has the captured mutant digest; if a test, user, or other
   process changed it, the wrapper preserves that current file and the backup, then stops with a
   recovery conflict instead of clobbering the edit. Otherwise it verifies the original digest and
   reruns the target test. It refuses linked, hard-linked, special, or out-of-project targets. If
   exact replacement cannot represent the mutation, use the lower-level helper with its captured
   current-digest restore contract; never use `cp`, `mv`, a HEAD snapshot, or hand-rolled backup.
3. **Interpret only this mutation.** The wrapper reports `nonzero` or `survived`, never
   “detected.” A nonzero exit counts as detection only after inspecting the target-test output and
   confirming the intended assertion failed because of the selected behavior mutation. Import,
   syntax, setup, timeout, signal, and unrelated assertion failures are wrong-red/inconclusive.
   A surviving mutation means this test did not detect it; inspect whether the mutant is
   behaviorally equivalent or poorly chosen before concluding the test is weak. Call the test
   vacuous only with independent evidence, such as discovering that it never imports production
   code.
4. If a meaningful mutant survives, strengthen the test and repeat. If no meaningful safe
   mutation can be formed, report the validation gap rather than forcing one.

Never silently leave a mutation in the tree. A leftover `.mutbak` normally means cleanup did not
complete. If the target digest changed concurrently, do not overwrite it: stop, report both paths
and digests, and let the user reconcile the preserved current file with the verified backup.

## Boundaries

- `/verify` and `/run` are post-action mirrors: they confirm behavior after a change. These
  gates run before the edit lands; `repro` and `characterize` may hand off to them after green.
- `/code-review` and `/simplify` are post-diff. A gate never reviews or simplifies; it makes
  the safety artifact exist, then the diff flows onward.
- New feature work belongs to feature-dev end-to-end. These gates protect existing behavior.
- Plan mode produces a plan; these gates produce narrow working-tree test artifacts. They never
  stage or commit, and may run after planning.

## Reference files

- `references/anti-triggers.md` — test-discipline's should-NOT-fire surface. Read during triage.
- `references/right-sizing.md` — test-discipline's one-question triage rule. Read during triage.
- `references/mutation-guide.md` — mutation selection and restore mechanics. Read when
  running validate mode.
