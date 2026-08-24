# Contract-gap deterministic-assembly V3 — 2026-08-18

**Verdict: V3 recovered two claims that V2 lost, but its any-fragment resolver also manufactured an
unrelated changed anchor. Behavior and mechanics both fail. Preserve this run as negative evidence;
do not publish, auto-compose, or advance to fresh PRs.**

V3 reused the exact five commits, two reviewer families, and ten frozen sample-1 reviews from V2.
It kept the same review-blind semantic discovery and subtraction workflow, Claude Sonnet 5 at medium
effort, and strict gates. The only candidate change was allowing deterministic resolution from
one-line, multi-line, or ellipsis-abbreviated evidence hints. The candidate, gate, runner, cases, and
reviews were digest-frozen before paid calls. The counted run is
`qa/_work/review-contract-mechanics-v3.2CJarI`.

## Pre-registered result

| Measure | V3 | V2 | Gate |
| --- | ---: | ---: | --- |
| Wins / ties / losses | **4 / 5 / 1** | 2 / 8 / 0 | At least 1 win; 0 losses |
| Unsupported findings | **2** | 0 | 0 |
| Negative-case findings | **0** | 0 | 0 |
| Base-review retention | **10/10** | 10/10 | 10/10 |
| Discovery success | **5/5 (100%)** | 5/5 | At least 90% |
| Fully materialized discoveries | **4/5 (80%)** | 2/5 | At least 90% |
| Rejected semantic claims | **1/4 (25%)** | 3/4 | At most 10% |
| Coverage-complete blocks | **10/10** | 10/10 | At least 90% |
| Repair sessions | **0** | 0 | 0 |
| Permission denials | **0** | 0 | At most 5 |
| Total cost | **$8.987814** | $7.5303897 | At most $35 |

The resolver doubled full materialization and cut rejected claims by two thirds, but neither gate
passed. The preregistered decision is `park-or-diagnose-semantics` before more spend.

## What V3 genuinely fixed

The known guardrails defect materialized correctly: the real Agent `auto` option always supplies a
description, so the newly added nullish fallback is unreachable. The built-in review omitted that
root cause and the blind judge preferred the augmentation; the pr-kit review already covered it, so
subtraction correctly produced a tie.

V3 also continued to materialize the node-registry cache-swap claim. Both judges preferred the
augmented review. One judge nevertheless marked its impact wording unsupported: the outer lazy-cache
write is lost, but the lower-level loader cache means it does not reconstruct the credential class as
claimed. That makes claim precision, not just evidence mechanics, part of the next admission problem.

## The dangerous failure

The Instance AI discovery supplied an `archiveIfAiTemporary` method block as its changed hint. That
method was not changed by the PR. V3 split the block into fragments and accepted any matching fragment
on a changed line. It resolved the claim to line 643, whose entire text was only `workflowId,`, because
that generic fragment happened to occur in an unrelated changed hunk near the approximate hint.

This satisfied the mechanical changed-line check while destroying its meaning. The built-in blind
judge correctly treated the added finding as out of scope and preferred the base review. The pr-kit
judge considered the omitted sibling path a valid scope gap, illustrating the semantic ambiguity, but
the false exact anchor is independently disqualifying. Multi-line support cannot be implemented as
"any fragment matches anywhere nearby."

## The remaining rejection was correct

The saved-agent discovery claimed that sibling chat-hub tool modals should also disable resource-mapper
auto-refresh. Its contract hint declared `base`, but the cited injection-key line was introduced by the
change and does not exist in the base tree. The helper rejected it. Relaxing that rejection would hide
a semantic/ref error, not repair clerical transcription.

## Decision

Freeze V3 as negative evidence. A successor, if pursued, should require either a strong match to the
intended source line or a coherent ordered multi-line neighborhood, discard short/generic fragments,
and verify that the resolved line represents the hint's stated role. It must keep invalid base-contract
refs closed. Claim admission also needs causal-scope and impact-precision controls before another
frozen replay. Do not tune directly to the four historical answers or start the fresh-PR A/B yet.
