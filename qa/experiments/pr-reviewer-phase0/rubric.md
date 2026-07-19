# Blind PR review rubric

Judge outputs without knowing which system produced them. Score reviewer value, not prose polish,
comment count, or apparent effort.

## Per-output core score (0–10)

### Correctness and evidence — 0 to 4

- **4:** findings are technically correct, traceable to changed behavior, anchored to changed
  lines, and survive source/test/configuration inspection.
- **2–3:** mostly correct with minor uncertainty or one weak claim.
- **1:** plausible but poorly evidenced.
- **0:** materially wrong, fabricated, or unsafe.

### Actionability — 0 to 3

- **3:** comments identify a reachable failure mode, explain impact, point to the right changed
  lines, and propose a concrete fix or decisive question.
- **1–2:** useful direction but incomplete anchoring, impact, or remediation.
- **0:** generic advice, style commentary, or no usable finding.

### Selectivity and risk coverage — 0 to 3

- **3:** catches the highest-risk issue(s) across the activated correctness/security/edge-case
  surfaces without padding; an empty review earns 3 when no finding is defensible.
- **1–2:** useful but misses an important risk or adds avoidable noise.
- **0:** comment spray, repeated variants of one issue, or a miss on a clear severe regression.

## Finding labels

Label every proposed comment:

- `confirmed`: directly supported by code, tests, configuration, or a reproducible path;
- `plausible`: technically coherent but depends on one unavailable material fact;
- `unsupported`: contradicted, fabricated, outside the diff, or too vague to verify;
- `nit`: true but not worth reviewer attention.

High-confidence findings labeled `plausible`, `unsupported`, or `nit` are an output-discipline
failure. Prefer an empty precise review over a confident false positive.

## Pairwise judgments

Judge all three blind pairs (`A` versus `B`, `A` versus `C`, `B` versus `C`). For each pair choose
`left`, `right`, or `tie`, then give two or three concrete differences. A score difference does not
force a pairwise win when the higher-scoring output misses the case's dominant risk.

After unblinding, the decoded comparisons used by the gate are:

- generic versus baseline;
- initialized versus generic.

## Repository-context audit after unblinding

For every claim, prioritization decision, omission, or precedent that appears to depend on the
profile, label the use:

- `material`: source-valid and meaningfully improves the review;
- `decorative`: correct but adds no decision value;
- `unsupported`: the cited source does not support it;
- `leaked`: depends on post-base state, target-PR discussion, merge result, or forbidden data.

A precedent counts only when its immutable PR/commit exists in the supplied base-time evidence and
its actual change strengthens the reasoning. Citation volume earns nothing.

## Security audit

For every security-labeled claim, identify:

- the attacker-controlled or untrusted input;
- the trust-boundary crossing or missing control;
- reachability through the changed code;
- the concrete consequence;
- whether the output's confidence matches the evidence.

Generic secure-coding advice, threat-name dropping, and conditional concerns presented as confirmed
vulnerabilities are unsupported.

## Historical review comparison

Reveal historical comments only after blind judging. Treat them as corroboration and missed-signal
evidence, not ground truth: humans can miss bugs, misunderstand code, and leave preference nits.
