# Consumer-contract composition pilot — 2026-08-17

**Verdict: stop after sample 1; do not run samples 2–3 and do not promote automatic composition.**

The selected `audit-consumer-contracts` candidate produced zero confirmed additions across five
frozen PRs and both reviewer families. Because composition is append-only and fail-closed, every
eligible final review equals its frozen base review: 0 wins, 10 deterministic ties, and 0 losses.
Blind judges were unnecessary because there was no changed candidate text to compare.

## Frozen pilot

- Run root: `qa/_work/review-contract-matrix.pdoyMY`.
- Model: `claude-sonnet-5`, medium effort.
- Reviewers: built-in `/code-review` and experimental generic `pr-kit:review-pr`.
- Cases: the frozen-error negative and agent-guardrails contract calibration, plus three PRs chosen
  from title/metadata only before diff inspection: node-registry replacement, Instance AI editor
  write locks, and saved Agent tool schemas.
- Planned design: three independent samples. Completed design: one pilot sample, stopped before
  replication for zero signal, cost, and admission brittleness. This is a pragmatic early stop, not
  a completed three-sample statistical result.
- Target-only controls passed: two positives admitted, the alias negative was defeated, and the
  wording-only negative short-circuited without a model call.

## The intended case failed

The strongest result is not merely “no lift.” The new audit missed the exact producer-contract bug
that motivated it when the ordinary reviewer also missed it:

- The sample-1 built-in review of agent guardrails returned no findings.
- The sample-1 pr-kit review independently found that the real `auto` option already has a non-empty
  `description`, making the new `?? autoRequiresChatTriggerDescription` hint unreachable.
- The post-review audit over the built-in miss verified only extractor surfaces S1 (`auto`) and S2
  (`disabled`), classified them unreachable, and skipped the remaining fourteen surfaces.
- The decisive `description` surface ranked S11, beyond the skill's ten-surface inspection cap, and
  therefore never reached verification. The audit added nothing.

This explains the failure mechanism directly: lexical frequency/ranking spent the bounded analysis
budget on generic tokens before the load-bearing contract token. The deterministic gate prevented
anchoring losses but did not prioritize the evidence needed to recover the miss.

## Aggregate audit ledger

Across ten reviewer/case blocks, the extractor emitted 112 surfaces. The audit verified 54 and
skipped 58. The verified decisions were 4 already covered, 22 defeated, 28 unreachable, 0
unresolved, and **0 confirmed**.

Three final non-finding ledgers remained mechanically invalid after the bounded repair policy. Five
real ledgers were repaired into valid exact-evidence form, two were valid directly, and none of the
invalid ledgers contained a proposed confirmed finding. Fail-closed behavior therefore remains
safe, but the evidence format is expensive and brittle even when producing no additions.

## Cost and safety

- 36 model attempts: 30 accepted, 6 failed.
- Accepted cost: **$23.9059887**; failed-attempt cost: **$6.76942365**; total:
  **$30.67541235**.
- Ten audit analyses alone cost **$11.2769877**, before repair attempts.
- Permission denials: 17. They were nonessential helper/read attempts; all case repositories
  remained clean.
- Two base-review attempts exhausted their budget; both recovered on retry. Several repair attempts
  also exhausted their smaller budget.

## Decision

Park the current lexical-surface composition design. Do not spend the remaining two samples: the
pilot produced no candidate additions, failed its intended known-miss block, and added material cost
and serialization failure modes.

A future attempt would need a different gate, not prompt tuning: rank semantic contract endpoints
such as changed precedence operators, persisted/public keys, schema declarations, and unchanged
producer definitions ahead of generic lexical matches. That replacement should first recover the
agent description case in target-only evaluation without being told the answer, then pass a fresh
negative before automatic composition is reopened.
