# Contract-gap intended-line V5 — 2026-08-18

**Verdict: V5 solves deterministic materialization, but one semantically overgeneralized claim loses
against both base reviews. Mechanics passes; behavior fails. Freeze the resolver and move the next
experiment to causal-contract admission.**

V5 changed one V4 condition: it retained full-file intended-line resolution and the 16-character
fragment floor but allowed a source shape with one identifier. The same five commits, two reviewer
families, and ten frozen sample-1 reviews were used with Claude Sonnet 5 at medium effort. The counted
run is `qa/_work/review-contract-mechanics-v5.0gNhI3`.

## Pre-registered result

| Measure | V5 | Gate |
| --- | ---: | --- |
| Wins / ties / losses | **2 / 6 / 2** | At least 1 win; 0 losses |
| Unsupported findings | **2** | 0 |
| Negative-case findings | **0** | 0 |
| Base-review retention | **10/10** | 10/10 |
| Discovery success | **5/5 (100%)** | At least 90% |
| Fully materialized discoveries | **5/5 (100%)** | At least 90% |
| Rejected semantic claims | **0/3 (0%)** | At most 10% |
| Coverage-complete blocks | **10/10** | At least 90% |
| Repair sessions | **0** | 0 |
| Permission denials | **3** | At most 5 |
| Total cost | **$9.3240135** | At most $35 |

The mechanics gate passed for the first time. The behavior gate failed, so the preregistered decision
is `park-or-diagnose-semantics`; do not publish, auto-compose, or start fresh-PR evaluation.

## Two additions were independently valuable

The guardrails discovery again proved that the real `auto` option's existing description makes the
new disabled-state fallback unreachable. The built-in review missed it and the blind judge preferred
the augmentation; pr-kit already covered it.

The saved-agent discovery found that two ChatHub tool-config modals render the same
`NodeToolSettingsContent` → ResourceMapper path but do not provide the new auto-refresh opt-out. The
built-in review already covered that scope; pr-kit did not. The blind judge verified both live modal
paths and preferred the augmentation.

These are the desired composition pattern: distinct, source-valid root causes added only to the base
review that omitted them.

## Why behavior failed

The Instance AI discovery argued that an old trigger-test snapshot restore should adopt the new
`expectedChecksum` guard added to `handleUpdate`. Its exact evidence materialized correctly, but both
blind judges rejected the finding:

- the restore call predates the PR and is untouched by the diff;
- the finding was attached to the new `handleUpdate` checksum line rather than the actual restore;
  and
- one base controller call using `expectedChecksum` does not establish the stated universal contract
  that every write-after-read path must supply it.

This is not a resolver failure. The model generalized one guarded example into a repository-wide
invariant without evidence that the invariant covers intentional snapshot rollback. Because the same
unsupported addition appeared against both reviewer families, V5 records two losses and two
unsupported findings.

## Decision

Freeze V5's evidence mechanics. Do not tighten snippets again: all submitted claims materialized,
the V3 false anchor stayed closed, and all deterministic safety invariants passed. The next candidate
should change only semantic admission: a contract statement must be entailed by its cited base
evidence, and an unchanged omitted path must be demonstrably inside the changed decision's scope—not
merely another caller of the same API or an instance of the same broad bug class. Replay behavior on
the frozen blocks before considering fresh PRs.
