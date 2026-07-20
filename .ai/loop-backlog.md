# Skill-improvement loop backlog

Approved 2026-07-19 ("work top-down, auto-merge on clean review"). Each iteration: take the top
`pending` item, work it on a branch, run the validation suite, open a PR, review it, resolve
findings, merge when clean, mark the item `done` with the PR number. Verdict evidence:
docs/brainstorm/external-eval-2026-07-19-1945.md.

## Iteration 0 — clear the deck
- [x] PR A: ship pending infra — status: done, merged as PR #8 (2026-07-20)
- [x] PR B: pr-feedback plugin v0.1.0 — status: done, merged as PR #10 (2026-07-20; original
      stacked PR #9 was auto-closed by GitHub when #8's base branch was deleted — lesson: don't
      delete a stacked PR's base branch on merge, or retarget the child first)

## Tier 1 — small lifts (verdicts in hand)
- [x] Ponytail safety floor — status: done, merged as PR #11 (2026-07-20): git-archaeologist
      0.1.4 names simplify-framed removals in its trigger surface + battery controls; SHORTLIST
      row closed
- [x] natural-writing 1.0.3: grounding rule — status: done, merged as PR #12 (2026-07-20)
- [x] session-memory 1.0.5 + critical-thinking 0.1.2: settled-decisions provenance — status:
      done, merged as PR #13 (2026-07-20). Tier 1 complete.

## Tier 2 — audit existing 8 skills against docs/skill-authoring-notes.md
- [x] Sweep all shipped SKILL.md bodies against the failure-mode checklist — status: done in
      PR #14 (2026-07-20): zero behavior-changing findings; record in skill-authoring-notes.md
- [x] tools/check_doc_claims.py + CI wiring + tests — status: done, merged as PR #14
      (2026-07-20). Tier 2 complete. LOOP STOPPED here by design: everything below is
      demand-gated per the eval panel.

## Tier 3 — new builds (BUILD verdicts; queue each behind its first PR-able slice)
- [x] solutions-loop skill — status: done, merged as PR #15 (2026-07-20): session-memory 1.1.0
      `solutions` skill; retrieval-payoff eval included; SHORTLIST row marked BUILT
- [~] pr-kit readiness review — status: in-progress (user request 2026-07-20): static review +
      deterministic script smoke + the two committed behavioral controls; NOT a Phase-0
      substitute — the 6-case blind gate still decides publication
- [ ] grilling (elicitation primitive, anti-triggers vs critical-thinking) — status: pending
- [ ] debugging-discipline (composes with test-discipline repro) — status: pending
- [ ] project-vocabulary (domain glossary; boundary with lessons-learned declared both ways) — status: pending
- [ ] wayfinder / to-tickets / codebase-design+survey / tdd / ce-dogfood — status: parked until
      concrete demand (panel condition)

## Out of loop scope
- pr-kit Phase-0 execution (dedicated session; behavioral controls first)
- mp `prototype` ADOPT-AS-IS (user installs upstream; no repo change)
