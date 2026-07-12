# Blind review rubric

Judge the outputs without knowing which system produced them. Score useful reviewer value, not prose
style or number of comments.

## Per-output score (0–10)

### Correctness and evidence — 0 to 4

- **4:** findings are technically correct, traceable to changed behavior, and survive source/test
  inspection.
- **2–3:** mostly correct with minor uncertainty or one weak claim.
- **1:** plausible but poorly evidenced.
- **0:** materially wrong, fabricated, or unsafe.

### Actionability — 0 to 3

- **3:** comments identify the failure mode, point to the right changed lines, and propose a concrete
  fix or decisive question.
- **1–2:** useful direction but incomplete anchoring or remediation.
- **0:** generic advice, style commentary, or no usable finding.

### Selectivity and coverage — 0 to 3

- **3:** catches the highest-risk issue(s) without padding; an empty review earns 3 when there is no
  defensible finding.
- **1–2:** useful but misses an important risk or adds avoidable noise.
- **0:** comment spray, repeated variants of one issue, or misses a clear severe regression.

## Finding labels

Label every proposed comment:

- `confirmed`: directly supported by code, tests, or a reproducible path;
- `plausible`: technically coherent but needs one fact the available evidence cannot establish;
- `unsupported`: contradicted, fabricated, outside the diff, or too vague to verify;
- `nit`: true but not worth reviewer attention.

A precedent citation counts only when the referenced PR exists in the supplied precedent set and its
actual change strengthens the reasoning. Citation volume alone earns nothing.

## Pairwise verdict

Choose `A`, `B`, or `tie`, then state the two or three concrete differences driving the verdict.
Ignore formatting polish. Prefer an empty precise review over a confident false positive.
