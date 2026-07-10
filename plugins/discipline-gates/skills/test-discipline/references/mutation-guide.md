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
- Back up the exact pre-mutation bytes BEFORE mutating: copy the file to a unique adjacent
  `<file>.mutbak` path. Refuse to overwrite an existing backup; investigate it first. This
  single mechanism protects both committed and uncommitted content and avoids restoring a
  different snapshot from HEAD.
- Run ONLY the target test (single file or single test filter), never the whole suite.
- **Restore FIRST, unconditionally** — before reading results closely, before reporting,
  before asking the user anything, even if the runner crashed or something looks wrong.
- After restoring, rerun the test once to prove the tree is back to green.
- If a session is interrupted mid-mutation, recovery is one command
  (`mv <file>.mutbak <file>`); a leftover `.mutbak` file means restoration did not complete.

## Verdicts

- Mutated run went RED → the test is real. Report: validated — it fails when the code breaks.
- Mutated run stayed GREEN → the test is vacuous (tautology, mock-asserts-the-mock, snapshot
  never read). Restore first, then strengthen or rewrite the test so it observes real
  behavior, and validate the new version the same way.
