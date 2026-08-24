# Contract-gap deterministic-assembly V2 — 2026-08-17

**Verdict: review-blind semantic discovery still adds valid review findings, but the first
deterministic evidence boundary rejects too many otherwise useful claims. Behavior passes; mechanics
fails. Fix the hint resolver before a fresh-PR comparison.**

V2 reused the exact five cases, two reviewer families, and ten frozen sample-1 reviews. One semantic
discovery ran per PR without seeing either review. A deterministic helper then resolved evidence and
a separate narrow context subtracted materialized candidate cards from each frozen review.

The candidate, gate, runner, cases, and reviews were digest-frozen before paid calls. An earlier
quota-only attempt is excluded: Claude returned HTTP 429 before inference, inspected no case, and
cost $0. The counted run is `qa/_work/review-contract-mechanics-v2.phDa9r`.

## Pre-registered result

| Measure | Result | Gate |
| --- | ---: | --- |
| Wins / ties / losses | **2 / 8 / 0** | At least 1 win; 0 losses |
| Unsupported findings | **0** | 0 |
| Negative-case findings | **0** | 0 |
| Base-review retention | **10/10** | 10/10 |
| Discovery success | **5/5 (100%)** | At least 90% |
| Fully materialized discoveries | **2/5 (40%)** | At least 90% |
| Rejected semantic claims | **3/4 (75%)** | At most 10% |
| Coverage-complete blocks | **10/10** | At least 90% |
| Repair sessions | **0** | 0 |
| Permission denials | **0** | At most 5 |
| Total cost | **$7.5303897** | At most $35 |

The behavior gate passed and the mechanics gate failed, so the preregistered decision is
`redesign-mechanics`. Do not publish, auto-compose, or start the fresh-PR A/B.

## The admitted finding remained valuable

The node-registry discovery found that moving `this.loaded` to a final atomic swap widens the async
window in which lazy cache writes target the old object and are discarded. The candidate survived
materialization and was independently classified as absent from both frozen reviews.

Both blind judges verified the root cause and preferred the augmented review. The built-in base
already discussed overlapping `postProcessLoaders()` calls, but the judge found the discarded
lazy-cache-write path distinct. The pr-kit base contained no actionable finding. Neither judge
identified unsupported content.

## Semantic discovery was stronger than admission shows

Review-blind discovery produced four claims across the four non-negative PRs:

- the real Agent `auto` option's existing description makes the new fallback hint unreachable;
- `archiveIfAiTemporary` bypasses the editor write-lock guard;
- the node-registry final swap discards concurrent lazy-cache writes; and
- successful saved-agent executions can refetch schemas without respecting the auto-refresh flag.

Only the node-registry claim materialized. The known description miss was therefore **rediscovered
without review or answer leakage but not admitted**.

## Why mechanics failed

The model-facing contract requested a path, approximate line, and one source-line snippet, but the
JSON schema could only require a non-empty string. Claude often returned the semantically useful
multi-line expression or block:

- guardrails used the two-line nullish expression and a full option-definition block;
- Instance AI used an archive-method block and abbreviated `...` evidence; and
- saved-agent schemas used a watcher block and multi-line documentation contract.

The helper treated every newline as invalid and otherwise required exact normalized matching. That
kept false anchors out, but it rejected three source-valid semantic claims wholesale. This is much
cheaper and cleaner than V1—nine accepted calls, no repairs, no denials, and $7.53 total—but it does
not yet satisfy the purpose of deterministic assembly.

## Decision

Preserve the V2 architecture and semantic instructions. The next candidate should let the parent
resolve a multi-line or abbreviated hint from the safe path plus approximate line, while still
requiring the chosen changed anchor to be an actual changed line and recording the exact source line
it materializes. Pre-register a second frozen replay; do not tune prompts against these answers or
move to fresh PRs until materialization passes.
