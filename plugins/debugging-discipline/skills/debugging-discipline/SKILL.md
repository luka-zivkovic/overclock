---
name: debugging-discipline
description: "Systematic diagnosis for bugs that resist the ordinary red-test path: build a tight, red-capable feedback loop BEFORE forming any theory, minimize the failure, then test 3-5 ranked falsifiable hypotheses with stated predictions. Use for intermittent or flaky failures ('works sometimes', race conditions), performance regressions, failures that appear only in integration/staging/prod, bugs that survived one or more attempted fixes, code with no test infrastructure to lean on, or an explicit 'debug this systematically / help me find the root cause properly'. Do NOT use for an ordinary reported bug with a stated symptom and a viable test seam — discipline-gates/test-discipline's repro gate owns that red test (this skill may drive diagnosis AFTER that red test exists but never replaces the gate); nor for trivial bugs whose cause is already evident (error names the exact line), feature work, writing tests on request, or explaining an error message."
---

# Debugging Discipline

Build the feedback loop first. The bug is 90% found once a **tight**, **red**-capable loop
exists — a command that goes red on demand, runs in seconds, and needs no human in the middle.
Theorizing before that loop exists is the failure mode this skill removes: plausible causes
accumulate, fixes get stacked on guesses, and "it seems fixed" replaces evidence.

## The hard gate

Before reading code to build a theory, there must exist a loop command that:

- goes **red** on the actual failure (or measurably reproduces it — a rate, a latency number);
- is **tight**: seconds not minutes, deterministic where possible, runnable by the agent alone;
- is pasted into the conversation with its output.

If you catch yourself building a causal story before this command exists — stop and build the
loop. A 30-second flaky loop is barely better than none; drive it toward deterministic and
fast before trusting it.

## Where the red artifact comes from

**When the bug has a stated symptom and a viable test seam, the red artifact is
test-discipline's repro gate** (discipline-gates): a committed test that fails for the stated
reason. Delegate to that contract — never invent a rival red-test protocol beside it. This
skill's own loop construction is for everything that gate can't reach, in rough order of
preference:

1. Re-run the flaky case N times under a loop with a fixed seed / forced scheduling —
   raise the reproduction rate before chasing a clean repro.
2. A `curl`/CLI invocation against the running service that exhibits the failure.
3. A diff harness: run old vs new build on identical input, compare output.
4. A replay of captured input (a saved request, a copied event payload, a downloaded artifact).
5. A measurement loop for perf regressions: the same operation timed before/after, N samples.
6. `git bisect` driven by any of the above when the regression window is known.
7. A throwaway script that pins the failing state — marked throwaway, deleted after.

Non-determinism is handled by raising reproduction probability, not by pretending a single
green run proves anything.

## Diagnosis — hypotheses are for falsifying

With a loop in hand:

1. **Minimize.** Shrink input, config, and code path to the smallest scenario that still goes
   red. Every removed variable is a hypothesis you no longer need.
2. **Audit assumptions.** List the beliefs the failure story depends on (library behavior,
   config values, call order, environment parity) and mark each *verified* or *assumed*. Many
   wrong hypotheses are correct hypotheses tested on top of a wrong assumption.
3. **Rank 3-5 falsifiable hypotheses** and show them before testing: each names the mechanism
   and the observation that would refute it. Test in order of (likelihood × cheapness).
4. **Predict before you probe.** Before each experiment or candidate fix, state what will be
   observed if the hypothesis is true. **If the prediction is wrong but the fix "works", you
   found a symptom, not the cause** — say so, keep the loop, keep digging.
5. **Instrument with tagged logs** (`[DBG-<4 chars>]`) so every temporary probe is removable
   with a single grep before the fix lands.
6. **Escalate when hypotheses span subsystems.** If the surviving hypotheses point at three
   different subsystems, the finding is usually a design problem, not a line bug — say that
   and recommend the appropriate design-level look instead of whack-a-mole fixes.

## Finishing

- The fix must turn the loop green **and** be explained by the confirmed cause; rerun the loop
  enough times to clear the observed flake rate.
- Remove every `[DBG-]` probe (one grep). Throwaway harnesses are deleted or clearly marked.
- Where a test seam exists, the regression test follows test-discipline's contract (and its
  validate mode proves the test can fail). Where none exists, say what durable check, if any,
  is worth building — honestly, including "none".
- A nontrivial confirmed diagnosis is worth capturing where the kit has a solutions ledger
  (session-memory's solutions skill): symptoms, dead ends, fix, why.

## Triage — silent fast-path

- **Cause already evident** (the stack trace names the exact line and the fix is obvious):
  just fix it; no loop ceremony. The gate exists for bugs that resist, not for typos.
- **Ordinary seamed bug, first attempt:** test-discipline's repro gate leads; this skill stays
  out of the way unless diagnosis stalls after the red test exists.
- **Not a bug** (feature request, test-writing request, error-message explanation): out of
  scope, no ceremony.

## Boundaries

- discipline-gates/test-discipline owns the red-test gate for seamed bugs and the
  mutation-validate check on any new test. This skill never restates those contracts.
- `/verify` and `/run` are post-fix mirrors; the loop here exists before and during the fix.
- critical-thinking evaluates reasoning on request; this skill generates and kills its own
  hypotheses as part of diagnosis.
