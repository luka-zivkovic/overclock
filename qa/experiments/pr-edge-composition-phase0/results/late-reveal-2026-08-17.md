# Late-reveal composition result — 2026-08-17

## Decision

**FAILED the generalization gate.** Late reveal fixed the known data-table miss and made loss of
original findings mechanically impossible, but it did not produce reliable unseen lift. Across the
two untouched PRs the augmented arms recorded one win, two ties, and one loss. The SSL case had no
augmented win, and there was only one distinct candidate edge-originated risk across the unseen set.
Do not publish or automatically compose either candidate from this result.

## What changed before the run

The `anticipate-edge-cases` candidate gained:

- an identity/reference-propagation lens activated only when an identifier, name, key, path, owner,
  or equivalent identity changes;
- a mandatory search for persisted/external consumers, including one plausible consumer outside the
  producing subsystem, with explicit raw-ID versus stable-key resolution analysis;
- prefix-scoped base search and stronger one-helper-per-command rules.

The experiment replaced upfront priming with late reveal:

1. generate and seal the base-only edge brief;
2. run and hash-freeze a primary review that never sees it;
3. give a separate read-only delta session the frozen review, brief, and implementation;
4. validate structured additions and mechanically append them to the original bytes.

`pr-kit:review-pr` also gained a no-stdin `--payload-json` validator path, a bounded committed-tree
search operation, exact helper command forms, and explicit bans on wrappers, redirects, temporary
files, shell search, SHA manipulation, and reference-directory probing.

## Cases and matched results

The two regression cases diagnose the known behavior and do not count toward the gate. The two
generalization cases were prepared before this redesign and had not been run in this composition
experiment.

| Phase | PR | Reviewer | Frozen | Late edge | Pair |
| --- | --- | --- | ---: | ---: | --- |
| Regression | #33820 credential/model selection | built-in | 8 | 8 | tie |
| Regression | #33820 credential/model selection | pr-kit | 10 | 10 | tie |
| Regression | #33867 data-table identity | built-in | 3 | 4 | tie |
| Regression | #33867 data-table identity | pr-kit | 3 | 10 | **late-edge win** |
| Generalization | #33970 scheduler provisioning | built-in | 4 | 7 | **late-edge win** |
| Generalization | #33970 scheduler provisioning | pr-kit | 10 | 7 | **late-edge loss** |
| Generalization | #33960 Rundeck SSL | built-in | 10 | 10 | tie |
| Generalization | #33960 Rundeck SSL | pr-kit | 6 | 6 | tie |

Scores are secondary to the blind pairwise judgment. The data-table built-in score increased by one,
but its matched pair was a tie.

## Attribution audit

### Regression

- **Credential switch:** the brief independently anticipated the confirmed A→B→C reload race, but
  both frozen reviews already contained it. The appendices were decorative corroboration or empty;
  both pairs tied.
- **Data-table identity:** the redesigned blind pass inspected
  `packages/nodes-base/nodes/DataTable/common/utils.ts` at the base commit and discovered that
  `mode: 'id'` and `mode: 'list'` replay the persisted raw `dataTableId`. The head rekeys the table
  without migrating or aliasing those workflow references. This was a material, non-leaked addition
  to the frozen pr-kit review and drove its 3→10 win. The built-in review already had the root
  finding; its added consumer evidence was useful but not pairwise decisive.

### Generalization

- **Scheduler:** both delta sessions added the same cross-scope global-name collision hypothesis.
  The blind judge found it well-evidenced but only `plausible`: reachability requires a caller to
  generate the same job name in two different scopes, and this PR does not contain that caller.
  It helped a weak built-in report (4→7) but made a strong, selective pr-kit report worse (10→7).
  This is the anchoring risk in a new form: late reveal cannot delete old findings, but it can append
  a plausible probe whose marginal value depends on the quality of the frozen review.
- **Rundeck SSL:** the brief converged on the credential-test/runtime mismatch already found by the
  built-in reviewer and on compatibility behavior already analyzed by pr-kit. The deltas added no
  finding; all strengthening notes were decorative for pairwise value, and both pairs tied.

There was therefore only one distinct unseen edge-originated risk (the scheduler name collision),
not two material uses across the two cases. Conservatively, its missing reachable producer makes it
an implementation-review question rather than a confirmed finding.

## Gate audit

| Rule | Result |
| --- | --- |
| Zero edge implementation leakage or mutation | pass |
| Frozen base review preserved byte-for-byte | pass (8/8 merges) |
| No unsupported-addition regression | not needed for decision; scheduler addition remained only plausible |
| At least one augmented win on each unseen PR | **fail** (SSL: two ties) |
| At least two wins and no more than one loss across unseen comparisons | **fail** (1 win, 2 ties, 1 loss) |
| At least two material edge uses across unseen cases | **fail** (one distinct scheduler probe, no SSL addition) |

## Mechanics and cost

- Edge skill: 4/4 successful, zero permission denials, no out-of-contract Bash, no head SHA in any
  brief, and clean worktrees.
- Final pr-kit generalization runs: SSL was clean; scheduler still made three denied attempts to read
  reference files with `cat` instead of `Read`. Command hygiene improved but is not solved by prose
  guardrails.
- Accepted delta/judge sessions incurred additional read-only permission denials because the eval
  allowlist rejected some Git command shapes. They still returned schema-valid outputs and left all
  worktrees clean; this is an eval-harness mechanics issue to fix before another run.
- Accepted evidence cost: **$13.1508584**. All preserved transcripts, including discarded mechanics
  reruns, total **$16.8650582**. The latter is a lower bound because the first wrong-working-directory
  edge invocation was overwritten; reused regression base-review costs belong to the prior pilot.

Raw artifacts and the machine summary live under
`qa/_work/pr-edge-late-reveal.vLDaJ3/` and remain generated, uncommitted evidence.

## What we learned

1. The v1 miss was fixable: explicit identity-consumer discovery transferred the needed base-code
   reasoning into the brief and recovered the exact known data-table failure.
2. Hiding the brief from the primary reviewer solves the destructive anchoring problem. The
   augmented artifact cannot forget or weaken original findings because the merge is mechanical.
3. Additive text is not automatically additive value. A plausible edge-derived item can improve a
   weak review while reducing the selectivity of a stronger one.
4. The next bottleneck is not broader risk brainstorming. It is a stricter delta admission rule:
   require a reachable producer/caller in the changed or existing system, deduplicate the same risk
   across reviewer families, and append only confirmed findings—not merely plausible probes.
5. Do not rerun the composition gate until command permissions are deterministic and the delta
   validator can mechanically enforce changed-line/reachability evidence comparable to pr-kit's
   finding validator.
