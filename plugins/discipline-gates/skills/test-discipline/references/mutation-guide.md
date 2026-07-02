# Mutation guide — validate mode

How to pick and apply the mutation that proves a freshly-green test can actually fail. Read
when running test-discipline's validate mode.

## Picking the mutation

Mutate the exact behavior the test CLAIMS to check — the change a real regression would make.
In order of preference:

1. **Invert or hard-code the condition the test targets** (`if (x > limit)` → `if (false)`).
2. **Wrong constant / off-by-one** on the value the test asserts (`+ 1` → `+ 2`, `0.5` → `0`).
3. **Skip the guarded step** — early-return before the logic under test runs.
4. **Return a plausible-but-wrong value** from the function under test.

Avoid mutations that break compilation or imports: a crash only proves the test loads the
module, not that it observes behavior. Prefer a mutation that keeps the code runnable but wrong.

## Applying and restoring — the contract

- Mutate exactly ONE file. Never stack mutations.
- Choose the restore mechanism BEFORE mutating:
  - File clean vs HEAD (`git status --porcelain -- <file>` prints nothing): mutate, run, then
    `git checkout -- <file>`.
  - File has uncommitted changes (for example the fix you just applied): `cp <file> <file>.mutbak`,
    mutate, run, then `mv <file>.mutbak <file>`.
- Run ONLY the target test (single file or single test filter), never the whole suite.
- **Restore FIRST, unconditionally** — before reading results closely, before reporting,
  before asking the user anything, even if the runner crashed or something looks wrong.
- After restoring, rerun the test once to prove the tree is back to green.
- If a session is interrupted mid-mutation, recovery is one command (`git checkout -- <file>`
  or `mv <file>.mutbak <file>`); a leftover `.mutbak` file means restoration did not complete.

## Verdicts

- Mutated run went RED → the test is real. Report: validated — it fails when the code breaks.
- Mutated run stayed GREEN → the test is vacuous (tautology, mock-asserts-the-mock, snapshot
  never read). Restore first, then strengthen or rewrite the test so it observes real
  behavior, and validate the new version the same way.
