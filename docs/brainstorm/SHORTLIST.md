# Shortlist — every skill candidate ever judged

**Machine-generated** by the `skill-brainstorm` workflow. This is a rolling, deduplicated
index of every candidate assessed across all runs (STRONG at the top, then PARKED, then KILL).
Each row links the verdict to the run that produced it. This file is *evidence accrual*, not
decisions — **human-blessed verdicts live in [`../strategy.md`](../strategy.md)**. Full
per-candidate reasoning lives in the dated `run-*.md` files.

When a candidate is re-judged, its row is updated only if the new verdict is newer/stronger;
verdict changes are noted in the "why" column.

| Candidate | Verdict | Moat axis | One-line why | Run date |
|---|---|---|---|---|
| PR-reviewer | STRONG | memory | Two prior self-built attempts (Count 2); precedent memory + per-repo decaying review learnings that all official reviewers lack — the one idea grounding made stronger. | 2026-06-16 |
| super-plan-mode | PARKED | right-sizing | Planning methodology already shipped by feature-dev/Ultraplan; only defensible angle is a lightweight planning-rigor router that right-sizes and delegates upward. Build if the routing decision itself proves a recurring pain. | 2026-06-16 |
| decision-log | KILL | memory | Demand Count 1 and self-referential (strategy.md is a repo-authoring meta-ledger); head-to-head vs CLAUDE.md never run; a mode of session-memory at best. | 2026-06-16 |
| spec-anchor | KILL | memory | Demand citation to strategy.md "spec drift" lens is fabricated (grep-confirmed); surviving mid-run drift-check is a mode of session-handoff, not a new skill. | 2026-06-16 |
| trust-calibration-memory | KILL | both | Duplicative of lessons-learned (per-area When/Count + CLAUDE.md promotion); the only novel "trust %" has no denominator and is unconstructable. | 2026-06-16 |
| flaky-test-memory | KILL | memory | Duplicative — CI platforms (BuildPulse/Trunk/TestDino) own the multi-run version better; local slice is lessons-learned; cited demand is a misread deterministic failure. | 2026-06-16 |
| invariant-guard | KILL | both | Storage ceded to CLAUDE.md/lessons-learned; the only sliver (diff-time enforcement) is better served by a deterministic hook via update-config. | 2026-06-16 |
| env-known-good | KILL | memory | Duplicative — lockfiles/CI logs/.nvmrc already hold the fingerprint more authoritatively; no natural green-time capture; self-admitted speculative and thin. | 2026-06-16 |
| lesson-decay | KILL | memory | Cleanest baseline gap in ledger (nothing retires a high-Count now-false lesson on live-repo contradiction) + real strategy.md citation + constructable evals, BUT prong 1 fails: zero logged stale-lesson incidents. Backlog enhancement-MODE of lessons-learned, gated on first evidenced incident — not a skill. | 2026-06-16 |
| eval-from-skill | KILL | right-sizing | Duplicative — qa/trigger_battery.py + run_evals.sh + committed example artifacts already make strategy-rule-4 evals mechanical; *.evals.json needs author-only judgment no scaffolder derives. Repo-internal author chore, not a user-facing skill. | 2026-06-16 |
| trigger-precision-tuner | KILL | right-sizing | Duplicative — wrapper over the existing deterministic qa/trigger_battery.py variant-scoring loop; conceded slice (which-prompt-to-add) is trivial one-shot reasoning; no memory, repo-internal. | 2026-06-16 |
| ship-switch-guard-precommit | KILL | neither | Duplicative — strongest in-repo demand (3+ encodings) but tools/check_version_bump.py already runs pre-commit and CI enforces all 3 invariants; the only move is one update-config call to install a hook. Same logic as invariant-guard KILL. | 2026-06-16 |
| review-router | KILL | right-sizing | Duplicative — code-review Haiku gate / pr-review-toolkit / security-review already cover triage+escalation; only novel bit (auto security-review on risky paths) is an update-config hook; stateless ceremony on the most saturated axis; demand zero. | 2026-06-16 |
| repo-recon-memory | KILL | memory | Duplicative — re-homes always-loaded CLAUDE.md's build/test/location knowledge; freshness trap (honest check re-greps the files it avoids); collapses to a CLAUDE.md generator /init already is. Same pattern as env-known-good. | 2026-06-16 |
| fix-loop-breaker | KILL | memory (none) | Self-referential — SKILL.md is more text in the SAME context already failing to notice the loop, adds zero info; nothing persists (moat claim wrong). Non-self-ref version is an update-config hook; zero logged incidents. | 2026-06-17 |
| review-comment-memory | KILL | memory | Duplicative of lessons-learned (a repeated maintainer PR comment IS its primary standing-rule trigger; source-agnostic store needs zero changes); only novel slice is the gh ingest channel. Demand self-admitted inferred not observed; fold into PR-reviewer Phase-0. | 2026-06-17 |
| cross-session-deadend-ledger | KILL | memory | Duplicative of session-handoff "Failed approaches" + lessons-learned; differentiator factually wrong (cap rule PROTECTS failed approaches, not prunes them); disproven-hypothesis vs failed-approach is semantic. Self-admitted zero logged incidents. | 2026-06-17 |
| repro-first | KILL | right-sizing | Bug-shaped repro-before-fix seam is real (feature-dev/plan/verify don't own it) but collapses to one always-loaded CLAUDE.md line; binary one-liner gate is below the blast-radius bar; no memory; zero logged incidents. | 2026-06-17 |
| upstream-watch-memory | KILL | memory | Duplicative — inline TODO comment + tracker issue + lessons-learned hold "why" more authoritatively; caching tracker status is a freshness trap; the only useful bit (active re-check poll) is owned by /loop and /schedule. Self-admitted leans-KILL, no recurrence. | 2026-06-17 |
| claim-evidence-audit | KILL | neither | Duplicative + worse than baseline — verify/run resolve "did you verify?" with ground truth; only re-labels prose then redirects to verify; soundness trap (same suspect model audits itself, no oracle). Zero logged incidents; surviving kernel is an update-config hook. | 2026-06-17 |
| migration-safety-gate | KILL | right-sizing (data-volume) | Duplicative — strong_migrations/squawk/eugene/gh-ost own expand-contract deterministically; /code-review already names backward-incompat migrations. A file-editing skill can't obtain prod row-counts/lock traces, so it GUESSES "plausibly large" (LLM vibes, not the claimed determinism). Surviving slice = CLAUDE.md line + wire squawk via hook. | 2026-06-17 |
| stacktrace-to-frames | KILL | determinism (observability) | Duplicative — native Claude debug already does pasted-trace -> located frames as step one; the only deterministic slice (de-minify/symbolicate) is owned by CLIs (@unminify, source-map, addr2line, c++filt, retrace) the model shells out to. Script-collapse; zero incidents. | 2026-06-17 |
| log-to-timeline | KILL | artifact-to-action (logs) | Duplicative — correlating/ordering/deduping a pasted log blob is native LLM text reasoning; structured version owned by Datadog/Honeycomb/Jaeger/Loki/OTel. "Deterministic correlation" unbuildable as a one-size script (heterogeneous formats) — falls back to the LLM, which is the baseline. Demand zero. | 2026-06-17 |
| error-to-min-repro | KILL | artifact-to-action (loop) | Clears repro-first adjacency (real reduce-and-confirm loop, not a one-liner) but the loop supplies no deterministic mechanism: ddmin/C-Reduce/git-bisect need an automated oracle they own; what remains is the same LLM judging "same signature fired" — its own oracle (fix-loop-breaker trap). avgDelta 3; zero logged incidents; no triage gate. | 2026-06-17 |
| dep-advisory-triage | KILL | right-sizing (supply-chain) | Duplicative + below safety floor — function-level reachability owned by SCA engines (Snyk/Endor/Semgrep) + /security-review's Dependency Audit; a grep/regex reachability skill produces FALSE NEGATIVES ("defer" green-lights skipping a needed patch). jean tools = signal source, not a gap. | 2026-06-17 |
| dep-intro-gate | KILL | timing/DO (supply-chain) | Duplicative — public andrew/managing-dependencies skill IS this point-for-point; deterministic install-time firewalls (Socket Firewall, Aikido Safe Chain) occupy the exact moment-in-time the moat claims is unoccupied, and block before bytes hit disk — strictly better than an LLM gate. Not a blessed axis; demand industry-wide not in-repo. | 2026-06-17 |
| tracker-sync | KILL | artifact-to-action (team) | Duplicative — commit-push-pr writes from-diff PR bodies; GitHub/Linear closing keywords auto-transition issues on merge for free. Only non-owned slice (diff-vs-acceptance-criteria reconciliation) is stateless one-shot over two in-context docs = CLAUDE.md line; deferral needs human intent. Prong-1 inferred-demand trap. | 2026-06-17 |
| breaking-change-radar | KILL | cross-repo blast-radius | Self-canceling moat — in-repo collapses to Grep + LSP find-references the agent already runs; cross-repo slice is structurally unreachable (no multi-repo primitive) and collapses to grep-across-folders the moment one lands. Serialized-consumer detection = grep-for-string. avgDelta 3; cited issues evidence the category not this skill; zero incidents. | 2026-06-17 |

## Standing tally
- **STRONG:** 1 (PR-reviewer) — pending Phase-0 baseline head-to-head before any build.
- **PARKED:** 1 (super-plan-mode) — pending evidence the right-sizing decision is a recurring pain.
- **KILL:** 26.
- **Backlog (KILLed-but-revisit):** lesson-decay — the cleanest baseline gap seen; revisit as a
  decay/re-validate MODE of lessons-learned on the first evidenced stale-lesson incident.

The recurring KILL pattern: candidates re-home durable memory that CLAUDE.md +
session-memory (lessons-learned / session-handoff) — or inline comments + trackers — already own,
collapse to a single `update-config` deterministic hook, wrap an existing deterministic qa/ or
tools/ script, or add stateless ceremony on a saturated axis. A newer recurring sub-pattern
(fix-loop-breaker, claim-evidence-audit): self-referential audits where the same model inspects its
own live context, adding zero information. Demand is consistently speculative, self-referential, or
fabricated.

The 2026-06-17-1416 divergence run deliberately left the memory/review territory for fresh
domains (data/schema, observability, supply-chain, multi-repo, team collaboration) and fresh axes
(determinism-via-mechanism, artifact-to-action, gate-at-introduction, cross-repo blast-radius).
All 8 still KILLed — three new failure shapes emerged: (a) **moat-signal-unobtainable** — the
defensible signal (prod data volume / lock traces, function-level reachability) is structurally
beyond a file-editing skill, so it GUESSES (LLM vibes) while a deterministic ecosystem (squawk/
eugene, Snyk/Endor, Socket Firewall) owns it strictly better; (b) **self-canceling moat** —
cross-repo enumeration is unreachable until a harness primitive exists and collapses to grep+LSP
the moment it does; (c) **owned-by-deterministic-CLI / native-LLM** — symbolication, log
correlation, and PR-body/issue-close are owned by external resolvers or by base-model reasoning
the agent already does. Prong-1 (evidenced in-repo incidents) was self-admitted zero across the
board. Fresh ground was genuinely explored; the baseline-gap test still judged "build nothing." The
bar holds.
