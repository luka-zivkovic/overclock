# Skill-improvement loop backlog

Approved 2026-07-19 ("work top-down, auto-merge on clean review"). Each iteration: take the top
`pending` item, work it on a branch, run the validation suite, open a PR, review it, resolve
findings, merge when clean, mark the item `done` with the PR number. Verdict evidence:
docs/brainstorm/external-eval-2026-07-19-1945.md.

## Iteration 0 — clear the deck
- [ ] PR A: ship pending infra (Codex agent metadata + version bumps, qa hardening, pr-kit
      Phase-0 candidate, AGENTS.md/CLAUDE.md, strategy/SHORTLIST updates, external-audit docs,
      workflow args-fix, this backlog) — status: in-progress
- [ ] PR B: pr-feedback plugin v0.1.0 + evals + trigger battery + publication sync
      (marketplace/capabilities/CHANGELOG/README entries, overclock-setup 0.1.3) — status: pending

## Tier 1 — small lifts (verdicts in hand)
- [ ] Ponytail safety floor: never-simplify-away-safety guidance lift (SHORTLIST: unexecuted
      since 2026-06-22) — status: pending
- [ ] natural-writing 1.0.3: grounding rule from writing-beats (+1 eval case) — status: pending
- [ ] session-memory + critical-thinking: settled-decisions provenance labels in HANDOFF
      Decisions + resume brief (+ eval cases, bumps, shared-files entry if duplicated) — status: pending

## Tier 2 — audit existing 8 skills against docs/skill-authoring-notes.md
- [ ] Sweep all shipped SKILL.md/references for no-op lines, negation phrasing, non-checkable
      completion criteria, missing leading words; fix per-plugin with bumps — status: pending
- [ ] tools/check_doc_claims.py: paths cited in SKILL.md/references must exist (CE-inspired);
      wire into CI — status: pending

## Tier 3 — new builds (BUILD verdicts; queue each behind its first PR-able slice)
- [ ] solutions-loop skill (ce-compound-style, session-memory family; eval must gate on
      retrieval) — status: pending
- [ ] grilling (elicitation primitive, anti-triggers vs critical-thinking) — status: pending
- [ ] debugging-discipline (composes with test-discipline repro) — status: pending
- [ ] project-vocabulary (domain glossary; boundary with lessons-learned declared both ways) — status: pending
- [ ] wayfinder / to-tickets / codebase-design+survey / tdd / ce-dogfood — status: parked until
      concrete demand (panel condition)

## Out of loop scope
- pr-kit Phase-0 execution (dedicated session; behavioral controls first)
- mp `prototype` ADOPT-AS-IS (user installs upstream; no repo change)
