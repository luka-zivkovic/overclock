# Broad semantic contract-audit replication — 2026-08-17

**Verdict: semantic review value replicates; the model-authored evidence protocol fails. Preserve
the reasoning approach and redesign mechanics before any fresh-PR A/B or publication.**

The unchanged `review-contract-gaps` candidate ran two new independent samples against the same ten
frozen reviewer/case blocks used in sample 1. Candidate-tree and base-review digests were verified
before any paid call. Sessions could inspect only the committed repository and their matched frozen
review; they could not inspect sample 1, sibling samples, or experiment results.

## Pre-registered result

| Sample | Wins | Ties | Losses | Unsupported | Behavior gate |
| --- | ---: | ---: | ---: | ---: | --- |
| 2 | 1 | 9 | 0 | 0 | Pass |
| 3 | 5 | 5 | 0 | 0 | Pass |
| Replication total | 6 | 14 | 0 | 0 | Pass |

Every admitted delta won its blinded comparison. The wins span four non-negative PRs and both
reviewer families, the frozen-error negative remained unchanged in both samples, every final review
retained the base bytes, and no judge identified an unsupported candidate finding.

Combined with sample 1, the broad candidate produced **9 wins, 21 ties, and 0 losses across 30
matched blocks**. This is enough to conclude that the semantic second pass has repeatable
complementary review value; the 3-0 screen was not a one-off.

## The motivating miss recovered

Both new built-in-review samples independently found the exact contract defect the first sample
missed: the real Agent `auto` option already has a non-null description, so the new nullish fallback
for the disabled reason is unreachable. Both findings were mechanically admitted and independently
verified by blind judges.

Across the three samples, this root cause was recovered in samples 2 and 3 but not sample 1. That
confirms the semantic process can reach the contract while also showing meaningful sample variance.

The sample-3 wins also included:

- a concurrent node-registry lazy-cache write discarded by the delayed `this.loaded` swap, repeating
  a root cause found in sample 1;
- `archiveIfAiTemporary` bypassing the new editor write-lock guard;
- Instance AI `unarchive` missing the write-lock check and open-editor broadcast; and
- chat-hub tool configuration modals reaching ResourceMapper without disabling schema auto-refresh.

## Mechanics failed decisively

The separate mechanics gate required at least 90% valid ledgers and no more than 25% repair
dependency. Actual results were:

- 15/20 valid ledgers after the bounded repair policy: **75% validity**;
- 15/20 raw ledgers required repair: **75% repair dependency**;
- five blocks failed closed after repair, including one accepted repair payload that remained
  mechanically invalid;
- 48 attempts: 37 accepted and 11 failed;
- 68 permission denials; and
- **$52.1585826** total replication cost, including $13.2527763 in repair attempts.

Exact line copying, merge-base references, changed-line membership, and finding/row anchor equality
caused most invalid states. Several sessions also spent their full budget trying to materialize or
validate payloads that the parent harness was already responsible for validating. Fail-closed
composition protected review quality, but the protocol is too expensive and unreliable to ship.

Across sample 1 and the replication, the broad candidate alone cost **$79.47661035** over 71
attempts, with 23/30 ledgers requiring repair and 7/30 remaining invalid.

## Decision

Do not park the semantic idea, and do not run another unchanged sample. Do not publish or enable
automatic composition. The next experiment should keep the semantic inventory, contract tracing,
coverage subtraction, and scenario reasoning unchanged while moving exact source-line
materialization, commit selection, counts, and final ledger assembly into a deterministic parent
helper. Compare that mechanically simplified candidate with the frozen semantic behavior before
spending on fresh PRs.
