# PR-reviewer Phase 0

This is a falsifiable head-to-head experiment, not the start of a new Overclock plugin.
`docs/strategy.md` requires the existing persona + precedent reviewer to beat the available built-in
reviewer before any packaging work begins.

## Question

Does the candidate reviewer produce materially better, lower-noise review findings than the
built-in reviewer on real n8n PRs?

Use an independently configured candidate checkout. The initial candidate pin is commit
`b95cd0dfbacd6c33daad733b7dfa7bd59d9e4c66`. Record a new SHA when the candidate changes; never
compare an unpinned working tree or rely on a developer-specific local path.

## Arms

- **Baseline:** the strongest generally available built-in code-review mode, with no candidate
  persona, precedent retrieval, or learned rules.
- **Candidate:** the existing default persona, precedent retrieval, finding validation, and
  decaying per-repo learnings. It drafts comments only and never posts to GitHub.

Keep the underlying model and review budget equal where the tools allow it. If they cannot be equal,
record the difference and treat a candidate win as provisional.

## Corpus

`cases.json` pins six merged `n8n-io/n8n` PRs by base/head SHA. They cover runtime semantics,
transactions, UI state, data preservation, AI-node contracts, and TLS defaults. One intentionally
large PR tests whether the candidate can remain selective rather than spraying comments.

For each case:

1. Check out the pinned base SHA and expose only the base-to-head diff plus repository source.
2. Hide existing PR discussions, review comments, and the merged result from both arms.
3. Run baseline and candidate independently. Save raw transcripts and normalized findings.
4. Randomly label the normalized outputs `A` and `B`; keep the key outside the judge input.
5. Have a judge use `rubric.md`, then reveal the key and record the result using
   `result.schema.json`.
6. Only after judging, compare findings with the historical review discussion. Historical comments
   are supporting evidence, not perfect ground truth: humans miss bugs and leave preference nits too.

## Build gate

Build a PR-reviewer skill only if all conditions hold:

- candidate wins at least 4 of 6 pairwise case judgments;
- median candidate score is at least 1 rubric point above baseline;
- unsupported-finding rate is no more than 5 percentage points worse than baseline;
- at least two precedent citations are both real and materially improve the associated finding;
- zero fabricated precedent numbers and zero high-confidence security claims that the code does not
  support.

Anything weaker means **do not build yet**. Record the result and either improve the candidate with a
specific diagnosed cause or stop. A polished demo is not evidence that the reviewer beats baseline.

## What remains manual

Running the two reviewer arms and blind judging are intentionally manual for Phase 0. Automating the
experiment before the candidate earns a build would create more harness than product evidence. The
case pins, rubric, normalization contract, and decision threshold are ready; actual review usage can
accumulate over time without moving the gate.
