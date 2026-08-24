# PR Review × Edge Brief Phase 0

This experiment tests whether an implementation-blind edge-case brief can add source-valid value to
an already-complete PR review without anchoring or narrowing the primary reviewer. It does not
publish or modify either candidate skill.

## Hypothesis

An edge brief generated from PR intent and the exact pre-change repository can improve a frozen,
independent implementation review when it is revealed only to a separate delta pass. Mechanical
merging should make the augmentation monotonic: the original review remains intact while only
verified, implementation-grounded additions are appended.

## Late-reveal design

Each case follows four ordered stages:

1. **Blind edge analysis.** Generate one edge brief from public PR intent and the exact base SHA.
   The edge analyst must not inspect the implementation. Seal the brief before review starts.
2. **Independent base review.** Run built-in `/code-review` and experimental
   `/pr-kit:review-pr` in fresh sessions with no edge brief. Freeze each complete output and its
   SHA-256 digest before revealing the brief.
3. **Verified delta.** Give a fresh reconciliation session the frozen review, the sealed brief, and
   the exact implementation diff. Ask only for missing, independently verified additions,
   strengthening notes, and rejected brief risks. It must not rewrite the review or assume the
   brief is correct.
4. **Mechanical merge.** Run `merge_delta.py` with the expected review digest. It copies the base
   review byte-for-byte and appends a clearly marked verified-edge appendix. A digest mismatch,
   malformed delta, or unsupported priority fails closed.

The four judged arms are therefore two genuinely independent reviews and their late-reveal
augmentations:

| Arm | Reviewer | Edge exposure |
| --- | --- | --- |
| `baseline` | built-in `/code-review` | none |
| `baseline_late_edge` | exact frozen built-in review | separate verified delta only |
| `prkit` | experimental `/pr-kit:review-pr` | none |
| `prkit_late_edge` | exact frozen pr-kit review | separate verified delta only |

The edge brief is an untrusted hypothesis list, not a finding set. The delta pass must verify every
candidate against the implementation and omit anything defeated by the code. It must not regenerate
the brief, rerun the primary review, edit original findings, or replace the original coverage
ledger. Preserve raw transcripts and digests under `qa/_work/`.

Keep model, effort, budgets, PR intent, base/head pins, and visible repository state equal within a
case. Use fresh sessions, hide target-PR discussions, permit no posting or repository mutation, and
inspect exact committed snapshots only.

## Cases and contamination control

`cases.json` pins four real merged `n8n-io/n8n` PRs:

- two **regression** cases from the first composition pilot, used to confirm that identity-consumer
  discovery and late reveal address the observed failure modes;
- two **generalization** cases that were prepared before this redesign but were not previously run
  in the composition experiment. Only these decide whether the redesign transfers.

For edge generation, expose only the public PR title/body and exact pinned base. The local checkout
may contain the head object so later phases can inspect it, but the edge skill's helper is the only
permitted repository reader and every edge citation must come from the base SHA. Do not inspect PR
reviews, comments, CI discussions, or issue discussions before grading.

Regression may reuse the exact frozen base-review artifacts from the 2026-08-16 pilot. Generalization
must create fresh independent base reviews and freeze them before the new edge brief is revealed.

## Delta contract and merge

The delta session returns one JSON object validated against `delta-schema.json`:

```json
{
  "base_review_sha256": "<64 lowercase hex characters>",
  "verified_additions": [
    {
      "priority": "P0|P1|P2",
      "title": "actionable finding title",
      "location": "repository-relative path:line",
      "failure_path": "concrete implementation-grounded sequence",
      "impact": "material consequence",
      "evidence": ["inspectable source evidence"],
      "suggested_comment": "draft review comment",
      "brief_origin": "risk or probe that prompted this check"
    }
  ],
  "strengthening_notes": [
    {
      "base_finding": "stable title or location from the frozen review",
      "note": "verified evidence or prioritization refinement",
      "brief_origin": "risk or probe that prompted this check"
    }
  ],
  "rejected_brief_risks": [
    {"brief_origin": "risk or probe checked", "reason": "implementation invariant defeating it"}
  ]
}
```

Only `verified_additions` and `strengthening_notes` are appended to the judged augmented review.
Rejected risks remain in the audit artifact so correct falsification is measurable without making
the review longer. Empty arrays are valid and preferable to speculative output.

## Blinding and grading

Randomly map the four arms to `A`–`D` independently per case and keep the key outside the judge
input. The blind judge uses `judge-rubric.md`, verifies claims against the exact head snapshot, and
returns `judge-output-schema.json` before the key, frozen brief, and deltas are revealed.

After unblinding, audit every delta item as:

- `material`: source-valid and adds a finding, evidence, priority refinement, or justified omission;
- `decorative`: correct but does not change reviewer value;
- `unsupported`: contradicted, ungrounded, or not introduced/exposed by the implementation;
- `leaked`: depends on implementation information unavailable to the edge pass.

## Pre-registered decision rules

Regression cases are diagnostic and do not count toward the lift gate. The redesign earns a
follow-up only when all safety conditions pass and the two untouched generalization cases show
reviewer value:

1. zero implementation leakage into an edge brief, remote mutation, or unauthorized local
   mutation;
2. every augmented artifact contains its frozen base review byte-for-byte with a matching digest;
3. no increase in unsupported findings in an augmented arm versus its matched base reviewer;
4. on each generalization PR, at least one augmented arm wins because of a verified brief-originated
   addition or strengthening;
5. across the four generalization comparisons, at least two augmented wins and no more than one
   loss;
6. at least two material edge-brief uses across the generalization cases, grounded at the pinned
   base and independently verified at the pinned head.

Anything weaker is useful diagnostic evidence but does not justify an automatic orchestration
skill. If the gate passes, the next step is a separately evaluated composition layer; neither
standalone skill may depend on its sibling.

See [results/pilot-2026-08-16.md](results/pilot-2026-08-16.md) for the original upfront-brief run.
