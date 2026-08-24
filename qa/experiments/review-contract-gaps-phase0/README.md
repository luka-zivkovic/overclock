# Review Contract Gaps — Phase 0

This non-shipping experiment changes the input to automatic PR-review composition. The prior role
matrix showed that moving the same implementation-blind edge brief before, beside, or after a review
did not produce confirmed additions. These candidates instead inspect the implementation actually
chosen and trace it against contracts already present in the base repository.

## Independent candidates

### Codex: `review-contract-gaps`

The locally designed candidate inventories every material implementation decision, records a base
contract, producer, consumers, guards, scenario, and review coverage, and admits only uncovered
contract violations. Its strengths are generality and a strict evidence ledger. Its weakness is that
it has no cheap deterministic gate, so it risks becoming another broad second review and spending
model budget on every invocation.

### Claude: `audit-consumer-contracts`

Claude Code independently proposed a narrower external-consumer sweep with a deterministic changed-
surface extractor before model verification. The certified consultation is preserved verbatim in
`candidates/claude/PROPOSAL.md`; `candidates/claude/provenance.json` records the Agent Bridge result.
The parent materialized the proposed skill because write delegation was correctly unavailable on
the dirty active checkout.

The first mechanical calibration found the proposed lexical extractor too noisy: it treated common
words in tests, docs, changelogs, and repository skill files as consumers and emitted hundreds of
kilobytes on both PRs. The parent narrowed extraction to production changed lines, string/property
contract tokens, bounded production matches, and one representative hit per high-frequency file.
On the agent-guardrails calibration it then surfaced `promptType` with the relevant Agent, Chain, and
`utils/descriptions.ts` base paths. It still surfaced seven contract tokens on the clean frozen-error
PR, so deterministic routing selectivity is not yet established.

## Selection and cherry-pick

Select the Claude-seeded `audit-consumer-contracts` candidate for forward evaluation, with two
material corrections cherry-picked from the Codex candidate:

1. Treat extractor output as neutral external contract matches. The known description defect is a
   pre-existing producer feeding changed consumer code, not an external consumer. Verification must
   classify producer/consumer direction and trace the full edge.
2. Keep the Codex candidate's exact changed-line, base-contract, reachable-sequence, guard,
   root-cause, review-hash, and coverage-count validation rather than trusting prompt prose.

The selected source remains under `candidates/claude/skills/audit-consumer-contracts/` to preserve
its provenance. The sibling Codex candidate remains intact as comparison evidence; do not install
both because their explicit second-pass scopes overlap.

## Product boundary

- Explicit invocation only; no collision with generic `review-pr` or pre-implementation
  `anticipate-edge-cases`.
- Exact committed base/head input; current source outranks supplied text.
- Read-only and report-only; no project execution, edits, posting, commits, pushes, or fetching.
- Optional frozen base review; output is an append-only delta, so base-finding retention is
  structural.
- No implementation-blind risk brief and no learned router.
- Findings require an external base contract endpoint, concrete producer-to-consumer reachability,
  checked guards, changed-line causality, and root-cause deduplication.

## Evaluation order

1. Run deterministic unit and calibration tests for extraction, admission, stale hashes, changed-line
   anchoring, duplicate root causes, unsupplied external claims, and compact no-op behavior.
2. Run `behavioral-controls.json` in target-only `skill` mode. The two positives cover shadowed
   fallback and raw persisted-key consumers; negatives cover an alias and wording-only no-surface
   change.
3. Run `routing-controls.json` for explicit positive and sibling/generic/fix negative prompts.
4. Only after controls pass, select fresh PRs from metadata and compare frozen base review versus
   append-only audit with both reviewer families. Historical heads are calibration-only.

## Live composition pilot

The 2026-08-17 2×2 pilot stopped after its first of three planned samples. Across five PRs and both
reviewer families the audit proposed zero confirmed additions, yielding ten deterministic ties. It
also missed the motivating unreachable-description defect when the built-in review missed it:
`description` ranked S11 behind generic lexical tokens and fell outside the ten-surface inspection
budget. The audit analyses alone cost $11.2769877; all attempts, including controls, base reviews,
repairs, and failures, cost $30.67541235. Three non-finding ledgers remained mechanically invalid.

See `results/live-matrix-pilot-2026-08-17.md` and its JSON companion. Do not run the remaining
samples or claim automatic-composition lift for the current lexical-surface design.

## Matched candidate tournament

The 2026-08-17 tournament reused the pilot's ten frozen base-review blocks and ran the previously
untested broad semantic `review-contract-gaps` candidate. It produced three admitted findings, and
all three augmented reviews won blinded comparison: 3 wins, 7 deterministic ties, and 0 losses,
spanning three PRs and both reviewer families. The narrow lexical arm remained at 0 wins and 10
ties. The broad arm kept the negative clean but still missed the motivating description defect when
the built-in review missed it, validated only 8/10 ledgers after repair, and cost $27.31802775 for
the extension. Treat this as a passed screen requiring replication, not publication authorization.
The full comparison is in `results/candidate-tournament-2026-08-17.md`.

## Unchanged-candidate replication

Samples 2 and 3 reused the exact candidate, cases, and base reviews. They produced 6 additional
blind wins, 14 ties, and 0 losses, with zero unsupported candidate findings and both samples passing
the pre-registered behavior gate. Both built-in-review replications independently recovered the
motivating unreachable-description defect. Combined with sample 1, the broad semantic candidate is
9 wins, 21 ties, and 0 losses across 30 blocks.

Mechanics failed: only 15/20 replication ledgers were valid after bounded repair and 15/20 required
repair. The replication cost $52.1585826; broad-candidate attempts across all three samples cost
$79.47661035. Preserve the semantic reasoning but do not run another unchanged sample, publish, or
auto-compose it. The next candidate must move exact evidence materialization and ledger assembly to
a deterministic parent helper. See `results/replication-2026-08-17.md`.

## V2 mechanics redesign

`candidates/codex-v2/` preserves the broad candidate's semantic inventory and contract tracing but
changes the execution boundary:

- one review-blind discovery runs per PR rather than once per reviewer;
- the model emits semantic claims with path, approximate line, and source snippet only;
- `scripts/assemble_delta.py` resolves commits, exact lines, changed-line membership, review hashes,
  deduplication, and counts, rejecting malformed claims individually;
- a separate narrow context subtracts materialized cards from each frozen review by root cause; and
- no model repair session exists.

`mechanics-redesign-gate.json` pre-registers the same ten frozen review blocks, behavior and mechanics
gates, and a $35 all-attempt cap. `run_mechanics_redesign.py` installs only the selected target plugin
and fails the run as invalid on provider quota/capacity errors. The first attempted replay consumed $0
and inspected no case because Claude Code returned an account spend-limit 429. Do not treat that
transport-only attempt as a behavioral or mechanical sample.

The valid fresh-root replay then produced **2 wins, 8 ties, and 0 losses**, with zero unsupported or
negative-case findings and full base-review retention. Both node-registry additions won blinded
comparison. Review-blind discovery also independently recovered the known unreachable-description
root cause, the Instance AI write-lock bypass, and a saved-agent schema-refresh gap.

Mechanics still failed: only 2/5 discoveries fully materialized and 3/4 semantic claims were rejected.
Claude returned multi-line or abbreviated source hints even though the prompt requested one line;
the helper rejected them instead of resolving an exact anchor from the safe path and approximate
line. Coverage was complete, repairs and permission denials were zero, and the entire valid replay
cost $7.5303897. Preserve the architecture, fix multi-line/path-plus-line-hint resolution, and rerun
the frozen gate before fresh PRs. See `results/mechanics-redesign-v2-2026-08-17.md`.

## V3 bounded-hint replay

`candidates/codex-v3/` keeps V2's semantic workflow and lets the deterministic helper resolve
one-line, multi-line, and ellipsis-abbreviated snippets. `mechanics-redesign-v3-gate.json` freezes the
same cases and thresholds, while the parameterized runner keeps candidate choice explicit.

The replay improved full materialization from **40% to 80%** and reduced rejected claims from **75%
to 25%**. It correctly recovered the known guardrails finding. It also exposed a more serious
resolver bug: an unchanged `archiveIfAiTemporary` method block contained the generic fragment
`workflowId,`, which matched an unrelated changed line and falsely satisfied changed-anchor
admission. The blind result was **4 wins, 5 ties, and 1 loss**, with two unsupported findings. A
separate saved-agent claim was correctly rejected because it declared a newly introduced line as a
base-tree contract. Total cost was $8.987814, with zero repairs or denials.

Both behavior and mechanics fail. Preserve V3 as negative evidence. Any successor must require a
strong intended-line match or coherent ordered neighborhood, reject generic fragments, retain strict
base/ref checks, and improve causal-scope and impact precision before another replay. See
`results/mechanics-redesign-v3-2026-08-18.md`.

## V4 strict-anchor replay

`candidates/codex-v4/` resolves the intended evidence line across the complete file before checking
changed-line membership and rejects fragments shorter than 16 characters or containing fewer than
two identifiers. This removed V3's unsafe anchor: discovery used the genuinely added `archive()` lock
line to identify the omitted `unarchive()` guard, and the augmentation beat pr-kit without a loss or
unsupported finding.

Behavior passed at **1 win, 9 ties, and 0 losses**, but mechanics failed at 60% fully materialized
discoveries and 50% rejected claims. The two-identifier condition rejected legitimate exact source
shapes: `...promptTypeOptions,` and `<NodeToolSettingsContent`. Total cost was $6.6242931. See
`results/mechanics-redesign-v4-2026-08-18.md`.

## V5 intended-line replay

`candidates/codex-v5/` removes only V4's two-identifier requirement while retaining full-file
intended-line resolution, changed-line verification, base-contract verification, and the 16-character
floor. A no-spend replay materialized all four V4 claims, then a fresh live replay passed mechanics:
100% discovery and full materialization, 0/3 rejected claims, complete coverage, zero repairs, three
permission denials, and $9.3240135 total cost.

Behavior failed at **2 wins, 6 ties, and 2 losses**. The guardrails addition beat the built-in base and
the ChatHub ResourceMapper addition beat pr-kit. A third claim generalized one base
`expectedChecksum` call into a universal write-after-read contract and criticized a pre-existing,
unchanged snapshot-restore path; both blind judges rejected it as out of scope. Freeze V5's evidence
resolver and move the next experiment to causal-contract admission. See
`results/mechanics-redesign-v5-2026-08-18.md`.
