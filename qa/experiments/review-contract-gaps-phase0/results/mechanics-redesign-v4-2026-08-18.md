# Contract-gap strict-anchor V4 — 2026-08-18

**Verdict: V4 removes V3's unsafe anchor and restores a clean behavioral pass, but its fragment
specificity rule rejects two legitimate claim shapes. Behavior passes; mechanics fails.**

V4 reused the same five commits, two reviewer families, and ten frozen sample-1 reviews. It resolved
the intended line across the complete file before checking changed-line membership, rejected short
generic fragments, required an actually changed causal anchor, and required base contracts to exist
at the merge base. The counted run is `qa/_work/review-contract-mechanics-v4.KST9oM`, using Claude
Sonnet 5 at medium effort.

Two earlier roots are excluded at $0: one hit the account spend limit before inference and one ran
after the OAuth session expired. Neither inspected a case through model inference or counts as a
sample.

## Pre-registered result

| Measure | V4 | Gate |
| --- | ---: | --- |
| Wins / ties / losses | **1 / 9 / 0** | At least 1 win; 0 losses |
| Unsupported findings | **0** | 0 |
| Negative-case findings | **0** | 0 |
| Base-review retention | **10/10** | 10/10 |
| Discovery success | **5/5 (100%)** | At least 90% |
| Fully materialized discoveries | **3/5 (60%)** | At least 90% |
| Rejected semantic claims | **2/4 (50%)** | At most 10% |
| Coverage-complete blocks | **10/10** | At least 90% |
| Repair sessions | **0** | 0 |
| Permission denials | **0** | At most 5 |
| Total cost | **$6.6242931** | At most $35 |

The behavior gate passed and the mechanics gate failed, yielding `redesign-mechanics`.

## The V3 safety failure is fixed

V4 did not rediscover or materialize the unchanged `archiveIfAiTemporary` block. Instead, discovery
identified the genuinely omitted `unarchive()` lock check and anchored it to the lock line actually
added to sibling `archive()` at head line 691. The built-in base review already covered this root
cause; pr-kit did not. The blind judge independently verified the omission, found it distinct from
pr-kit's existing finding, and preferred the augmentation without identifying unsupported content.

That is the intended composition behavior: a source-valid omission added only where the base review
missed it.

## Why mechanics still fail

The resolver requires a fragment of at least 16 characters and at least two distinct identifiers.
Full-file intended-line resolution makes the second condition unnecessarily strict:

- the guardrails producer was the exact spread-property line `...promptTypeOptions,`; after edge
  ellipsis handling it contained one 17-character identifier; and
- the saved-agent claim cited `<NodeToolSettingsContent` at two separate, line-hinted consumer paths;
  each exact component tag contains one identifier.

Both claims failed before subtraction. Neither resembles V3's dangerous `workflowId,` fragment,
which is only 11 characters and remains below the length floor.

## Decision

Keep intended-line-first resolution, full-file matching, changed-line verification, and the
16-character minimum. A narrow successor may allow one-identifier fragments only when they match an
exact source line or cover at least 65% of it; the approximate line and full-file resolution must
still choose the intended line before changed membership. Replay the frozen gate before fresh PRs.
