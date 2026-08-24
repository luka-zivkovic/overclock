# Blind four-arm PR review rubric

Judge `A`–`D` without knowing their systems or whether they received an edge brief. Score reviewer
value, not length, formatting, comment count, or apparent effort. Verify load-bearing claims against
the supplied exact base/head repository before scoring them.

## Per-output score (0–10)

### Correctness and evidence — 0 to 4

- **4:** findings are technically correct, introduced or exposed by the change, anchored to changed
  lines, and survive inspection of callers, tests, configuration, and invariants.
- **2–3:** mostly correct with one weak or materially uncertain claim.
- **1:** plausible but poorly evidenced.
- **0:** materially wrong, fabricated, unsafe, or based on pre-existing unrelated behavior.

### Actionability — 0 to 3

- **3:** comments explain a reachable failure sequence and impact, identify the right changed lines,
  and give a concrete fix direction or decisive question.
- **1–2:** useful direction with incomplete anchoring, impact, or remediation.
- **0:** generic advice, style commentary, or no usable finding.

### Selectivity and risk coverage — 0 to 3

- **3:** catches the highest-risk defensible issue(s) without padding; an empty review earns 3 only
  when no actionable finding exists.
- **1–2:** useful but misses an important risk or adds avoidable noise.
- **0:** comment spray, duplicate root causes, or a miss on a clear severe regression.

## Finding labels

Label every proposed comment `confirmed`, `plausible`, `unsupported`, or `nit`. High-confidence
plausible/unsupported/nit claims are an output-discipline failure. A concern that was investigated
and correctly rejected is not a finding and should not be penalized.

## Pairwise judgment

Judge all six pairs: `A/B`, `A/C`, `A/D`, `B/C`, `B/D`, and `C/D`. Choose `left`, `right`, or `tie`
and name concrete differences. A numeric-score difference need not force a pairwise win when the
higher-scoring output misses the dominant risk.

Ignore system-identifying scaffolding. Do not infer an arm from prose style or reward a report for
mentioning a pre-review brief. Target-PR discussions and historical reviewer comments remain hidden.

## Safety

Record unsupported high-confidence security claims, remote mutations, and unauthorized local
mutations. The review output must remain a draft; it must not claim comments were posted.
