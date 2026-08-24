# Contract-audit candidate tournament — 2026-08-17

**Verdict: the broad semantic `review-contract-gaps` arm wins the screen, but requires replication
and simplification before publication or automatic composition.**

The tournament completed the missing empirical comparison between the two independently designed
contract-audit candidates. It reused the exact ten frozen base-review blocks from the earlier live
matrix; no base review or narrow audit was regenerated. The broad arm received only the committed
base/head range and its matched frozen review and could not inspect the narrow candidate's output.

## Matched result

| Candidate | Findings | Wins | Ties | Losses | Valid ledgers |
| --- | ---: | ---: | ---: | ---: | ---: |
| Narrow lexical `audit-consumer-contracts` | 0 | 0 | 10 | 0 | 7/10 |
| Broad semantic `review-contract-gaps` | 3 | 3 | 7 | 0 | 8/10 |

All three non-identical broad reviews won their blinded pairwise judgment without unsupported
findings. Append-only retention held in all ten blocks, and both frozen-error negative blocks stayed
unchanged. The three accepted additions were:

- Agent guardrails / built-in review: the new `>= 3.1` guard leaves still-supported typeVersion 3
  Agent nodes without the new disabled-option signal.
- Node registry / built-in review: moving the lazily populated `this.loaded` cache reset to the end
  can discard cache writes made while the asynchronous registry rebuild is in progress.
- Instance AI write lock / pr-kit review: putting the lock assertion inside the shared save method
  makes the existing setup-decline revert throw during an editor-lock race and leave test mutations
  unreverted.

The wins span three PRs and both reviewer families. This is real source-valid lift in the screen,
not merely a safer no-op.

## What it still missed

The broad arm did **not** recover the original unreachable-description defect when the built-in
review omitted it. It found the separate version-gating issue instead. Against the pr-kit review,
which already contained the description defect, the broad audit did trace that contract and
correctly classified it `covered`. The semantic process can reach the contract, but attention
allocation is still sample-dependent.

This means the result overturns the lexical candidate selection, not the concern that a second pass
can miss a known root cause. The broad candidate demonstrates useful complementarity; it does not
demonstrate complete contract coverage.

## Reliability and cost

- Run root: `qa/_work/review-contract-tournament.5imBcr`.
- 23 attempts: 19 accepted and 4 failed; total cost **$27.31802775**.
- Audit attempts plus repairs cost **$25.25185335**; three blind judges cost **$2.0661744**.
- Only two raw ledgers validated directly. Six more became valid after bounded repair; two failed
  closed after their repair sessions failed, leaving 8/10 eligible blocks.
- Permission denials: 28. The most expensive failures came from the skill trying to create a
  temporary payload and invoke its validator despite the parent-validation handoff.
- Every case repository remained clean.

The broad arm therefore costs roughly twice the narrow arm's analysis-only cost and is too brittle
to ship in its present form. Its positive review value makes it worth replicating, but not worth
promoting unchanged.

## Decision

Do not publish either contract-audit skill and do not enable automatic composition yet. Retire the
lexical ranking direction. Preserve `review-contract-gaps` as the semantic upper-bound candidate and
replicate its matched lift on fresh samples. If the lift repeats, distill the useful mechanism into
a smaller skill with deterministic source-line materialization and parent-side evidence assembly so
the model reasons semantically without serializing every anchor itself.
