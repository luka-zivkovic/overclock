# PR Edge Role Matrix — Phase 0

This experiment asks where an implementation-blind edge-case analysis belongs in code review. It
compares distinct workflow roles instead of assuming that a longer review or an extra model pass is
automatically better. Nothing here publishes or modifies either experimental skill.

## Questions

1. Does the edge artifact improve the final review when exposed before, beside, or after the primary
   implementation review?
2. Does strict confirmation prevent plausible-but-unreachable risks from reducing selectivity?
3. Is one batch verifier, one isolated verifier per risk, a coverage filter, or a test-scenario
   translation the best admission path?
4. Is the skill more useful as a human sidecar, a preflight artifact, or a routing signal than as an
   automatic source of review comments?
5. Does the answer depend on the strength of the frozen primary reviewer?

The experiment tests distinct causal roles, not every wording permutation. An exhaustive Cartesian
product of prompt variants, reviewers, and PRs would spend more while making attribution worse.

## Three evaluation lanes

Do not rank outputs from different lanes as though they were interchangeable.

### Automatic final-review lane

Every arm in this lane ends as an ordinary draft PR review. Compare it blindly with its matched
reviewer control using `judge-rubric.md` and `judge-output-schema.json`.

| Approach | Placement | Final-review policy |
| --- | --- | --- |
| `base-review` | none | frozen independent review; matched control |
| `upfront-full-brief` | before primary review | full brief may influence the whole review; historical boundary control |
| `upfront-probes-only` | before primary review | compact scenarios and probes, without brief reasoning or evidence |
| `parallel-independent-challenger` | beside frozen review | edge-aware challenger never sees the base review; strict confirmed-only merge |
| `late-batch-confirmed` | after frozen review | one verifier sees all risks and the base review; strict confirmed-only merge |
| `late-per-risk-confirmed` | after frozen review | one fresh verifier per risk; strict deterministic aggregation |
| `coverage-filtered-per-risk` | after frozen review | no-diff coverage filter first, then isolated verification of only uncovered risks |
| `test-scenario-confirmed` | after frozen review | translate each risk into a concrete scenario, then verify reachability and handling |
| `conditional-no-findings-challenger` | after frozen review | run isolated verification only when the frozen review has zero actionable findings |
| `conditional-high-impact-challenger` | after frozen review | run isolated verification only for sealed risks marked high impact |

`upfront-full-brief` and the earlier permissive late-reveal design are historical controls. Their
existing results establish failure boundaries; do not spend screening budget rerunning them unless
the protocol itself changes materially.

All append-only arms use `assemble_review.py`. It admits only `confirmed-new-finding` decisions that
carry a changed-line anchor, change causality, a reachable producer or caller, checked guards, and
implementation evidence. Empty confirmation results ensure the assembler returns the frozen review
byte-for-byte, with no empty appendix. The helper fails closed on stale hashes, unknown risks,
non-changed lines, duplicate risks, duplicate root causes, malformed paths, or unsupported priorities.

### Reviewer-support lane

These modes intentionally do not turn hypotheses into review comments. Test them in randomized
human review sessions and record results with `support-session-schema.json`.

| Approach | Reviewer receives | Intended value |
| --- | --- | --- |
| `raw-human-sidecar` | frozen review and the sealed full brief as separate artifacts | independent questions without automatic merging |
| `coverage-map-human-sidecar` | frozen review plus risks classified as covered, unclear, or uncovered | attention to possible omissions |
| `test-scenario-human-sidecar` | frozen review plus concise manual reproduction or test scenarios | concrete verification assistance |

Use different support-study PRs for repeated human sessions and rotate packet order. Once a reviewer
has inspected a PR, never show that reviewer another packet for the same PR; memory would dominate
the sidecar effect. Measure useful new probes, confirmed findings, unsupported claims, elapsed time,
and cognitive load. Do not compare the length of sidecars.

### Diagnostic lane

`author-preflight` scores the sealed risks against the eventual implementation, tests, and review
outcomes. `risk-router-only` predicts whether an extra challenger is worth its cost. These outputs
can establish standalone or conditional usefulness even if no automatic composition wins. Validate
risk attribution with `risk-audit-schema.json`; do not expose implementation-derived labels to any
reviewer arm.

## Ordered protocol

### 1. Freeze the experiment

Before any screening run, commit or otherwise digest-lock this directory, both candidate skill
directories, model/effort settings, and the case manifest. Store all transcripts, hashes, costs,
permission denials, and generated packets under `qa/_work/`; generated output is not source.

### 2. Generate one clean-room edge artifact per case

In a fresh context, run the experimental `anticipate-edge-cases` skill using only public intent and
the exact pinned base. Do not expose the head SHA, diff, changed-file list, CI discussion, review
comments, or prior experiment results. Seal:

- the complete Markdown risk brief; and
- `edge-index.json`, a compact transcription of only the brief's surviving prioritized risks,
  validated against `edge-index-schema.json`.

The index gives risks stable IDs (`R1`, `R2`, ...), scenarios, impact signals, base evidence, and
probes. It must be produced before any implementation access and must not add risks absent from the
brief. An empty index is valid and makes every confirmed-only arm an exact-base result. Use the same
sealed artifacts in every matched approach for that case.

### 3. Generate and freeze independent controls

Run built-in code review and experimental `pr-kit:review-pr` independently at the exact base/head
pair. Neither sees the edge artifact. Freeze each complete review and SHA-256 digest before any
composition pass. Normalize only the number of actionable findings for the two conditional arms;
do not rewrite findings or reveal another arm.

The two reviewer families are blocking factors, not contestants. Prior evidence showed the same
edge addition helping a weak review and hurting a strong one, so report every result matched to its
own reviewer control.

### 4. Run the wide screen

Run each automatic approach whose `screening_action` is `run` in `approaches.json` on both
screening cases and both reviewer families. Run diagnostic approaches once per case, derive the two
conditional approaches from the isolated-per-risk artifacts, and defer human sessions to their
separate uncontaminated case set. Follow the exact exposure boundaries in `approach-prompts.md`.

- Start every model-generated artifact in a fresh context.
- Reuse the sealed edge artifact and frozen controls; never regenerate them per approach.
- For `late-per-risk-confirmed`, start one fresh verifier per risk.
- For `coverage-filtered-per-risk`, seal the no-diff coverage decision before starting verifiers.
- For conditional arms, record both trigger decisions and avoided cost. A non-triggered output must
  equal the frozen base bytes.
- Use `collect_changed_lines.py` to create the exact changed-line allowlist and
  `assemble_review.py` for every confirmed-only output.
- No arm may post, edit repository files, execute project code, commit, push, or fetch during
  analysis.

Judge one candidate/control pair at a time. Randomize left/right independently and hide the
approach, edge artifacts, audit records, and prior judgments. A judge verifies both outputs against
the exact head and returns schema-valid JSON before unblinding.

### 5. Audit contribution and cost

After judgment, audit each risk and each proposed addition. Record:

- `confirmed-new-finding`, `already-covered`, `defeated`, `unreachable`, or `unresolved`;
- whether the contribution was a new finding, material strengthening, useful test guidance,
  decorative duplication, or unsupported noise;
- original base-finding retention for replacement-review arms;
- accepted and attempted cost, tokens, wall time, tool failures, and permission denials;
- exact byte preservation for append-only and non-triggered arms.

One root cause counts once even if several risks or reviewers phrase it differently.

### 6. Promote approaches, then select untouched confirmation cases

Screening is eliminatory, not proof. An automatic approach advances only if it:

1. causes zero implementation leakage, remote mutation, or unauthorized local mutation;
2. adds zero unsupported or merely plausible high-confidence findings;
3. loses no original confirmed base finding unless it replaces that finding with a demonstrably
   stronger statement of the same root cause;
4. records at least one matched win or one material new contribution across the screen; and
5. has non-negative net pairwise value (`wins - losses >= 0`) in each reviewer family where it ran.

Advance at most three automatic approaches. Break ties by confirmed distinct root causes per dollar,
then lower cognitive/output overhead. Freeze the winners and prompts before selecting three
confirmation cases according to `cases.json`: merged behavioral PRs, diverse surfaces, locally
available immutable endpoints, no prior edge-composition run, and no target-PR discussion in the
experiment context. Pin cases from metadata only; do not inspect their diffs while selecting them.

### 7. Confirm the role

Run the baseline and promoted approaches on all three untouched cases with both reviewer families.
An automatic role is supported only if all safety conditions pass and it achieves:

- at least two matched wins;
- no matched losses;
- confirmed material lift on at least two distinct cases;
- no unsupported high-confidence addition;
- 100% original confirmed-finding retention for append-only approaches; and
- positive reviewer value after accounting for cost and added reading burden.

A support role is supported only from uncontaminated human sessions with no increase in unsupported
claims and a repeatable improvement in useful probes, confirmed findings, or time to useful
coverage. A routing role is supported only if it avoids work on no-lift cases while retaining at
least 80% of cases where the best confirmed-only challenger adds material value.

Possible conclusions are deliberately plural: automatic confirmed-only composition, conditional
composition, human sidecar, author preflight, routing-only, standalone explicit use, or park.
A win in one lane does not authorize behavior in another.

## Historical evidence handling

The four cases in `cases.json` under `historical_calibration` are contaminated for confirmation but
valuable as fixed boundary evidence:

- upfront full-brief composition produced 1 win, 1 tie, and 2 losses;
- permissive late reveal preserved base bytes but produced 1 win, 2 ties, and 1 loss on its two
  generalization cases;
- strict identity-consumer analysis recovered the known data-table miss;
- the scheduler case showed why plausible, unreachable additions must not be admitted.

Use these only to validate mechanics, prompts, and expected failure detection. Do not count them in
screening or confirmation gates.

## Files

- `approaches.json` — role matrix, exposure boundaries, and execution status.
- `cases.json` — historical controls, screening pins, and confirmation selection policy.
- `approach-prompts.md` — fixed prompts and per-approach context boundaries.
- `edge-index-schema.json` — sealed pre-implementation risk index.
- `review-index-schema.json` — hash-bound review-only metadata for filtering and conditional use.
- `coverage-map-schema.json` — no-diff edge-risk coverage classification.
- `candidate-schema.json` — verifier decision contract.
- `changed-lines-schema.json` — deterministic changed-line allowlist contract.
- `judge-rubric.md` and `judge-output-schema.json` — blind matched-pair grading.
- `risk-audit-schema.json` — post-unblinding risk attribution.
- `support-session-schema.json` — human sidecar session metrics.
- `router-output-schema.json` — implementation-blind route-or-stop decision.
- `collect_changed_lines.py` — exact-commit changed-line collector.
- `assemble_review.py` — strict confirmed-only admission and byte-preserving assembly.
