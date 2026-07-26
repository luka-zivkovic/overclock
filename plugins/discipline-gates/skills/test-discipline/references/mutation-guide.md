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
- Prefer the transaction wrapper:

  Resolve the current host's installed `test-discipline` directory and authorized project root to
  absolute paths, then substitute those actual values:

  ```bash
  python3 "/absolute/installed/test-discipline/scripts/mutation_trial.py" src/module.py \
    --root "/absolute/project/root" --old 'EXACT ORIGINAL' --new 'MUTATION' \
    -- TARGET_TEST_COMMAND...
  ```

  It backs up, applies exactly one replacement, runs only the target test, and attempts restore in
  `finally`. Restoration is a compare-before-replace operation: it proceeds only while the target
  still matches the captured mutant SHA-256. If anything changed the file during the trial, the
  current file and backup are both preserved and the wrapper reports a recovery conflict.
- The adjacent `<file>.mutbak` is an atomic integrity container: it stores the original bytes plus
  size, SHA-256, path, and mode metadata. Both helpers refuse a pre-existing backup, symlink,
  hard-linked file, special file, linked parent, or out-of-project target.
- If exact replacement cannot express the mutant, use the absolute installed path to
  `mutation_backup.py backup` before a manual mutation. Immediately after applying the mutant,
  capture its digest with the helper's `digest` action. In cleanup, call `restore` with
  `--expected-current-sha256 MUTANT_SHA`. A mismatch refuses to overwrite and retains the backup.
  Do not substitute `cp`, `mv`, a HEAD snapshot, or a hand-rolled command.

  ```bash
  python3 "/absolute/installed/test-discipline/scripts/mutation_backup.py" \
    backup src/module.py --root "/absolute/project/root"
  # Apply exactly one reviewed mutation to src/module.py.
  python3 "/absolute/installed/test-discipline/scripts/mutation_backup.py" \
    digest src/module.py --root "/absolute/project/root"
  # Copy the printed digest exactly as MUTANT_SHA, run only the target test, then:
  python3 "/absolute/installed/test-discipline/scripts/mutation_backup.py" \
    restore src/module.py --root "/absolute/project/root" \
    --expected-current-sha256 MUTANT_SHA
  ```

  If restore reports a digest conflict, stop. The current target and `.mutbak` are intentional
  recovery artifacts; show both paths/digests and ask the user how to reconcile them.
- Run ONLY the target test (single file or single test filter), never the whole suite.
- After successful restoration, rerun the target test once. A leftover `.mutbak` means either
  cleanup did not complete or a concurrent edit blocked safe restoration. Inspect the reported
  digests; never force the backup over a changed target.

## Verdicts

- Mutated run was NONZERO → inspect the failure output. It detected the selected regression only
  when the intended behavioral assertion failed for the predicted reason. Syntax/import/setup
  errors, timeouts, signals, and unrelated assertion failures are wrong-red and inconclusive.
- Mutated run stayed GREEN → the test did not detect this mutation. First check whether the
  mutant is meaningful and non-equivalent. If it is, strengthen the test. Use “vacuous” only
  when separate inspection shows the test never exercises or observes the production behavior.
