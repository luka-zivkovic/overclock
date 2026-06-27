# Gauntlet eval — roadmap-anchor (2026-06-25)

**Summary:** Single-candidate gauntlet run, requested directly by the repo user ("a roadmap-oriented
skill — see where the app is going, the direction, a clear plan to continue, avoid loss of planning").
Packaging was pre-decided by the user: ship it as a **third skill inside the `session-memory` plugin**,
beside `session-handoff` (tactical) and `lessons-learned` (corrections), over the `.ai/memory/`
markdown contract. Ran the full gauntlet — baseline-gap grounding → scenario simulation → 3-vote
adversarial panel. **Verdict: PARKED** (1/3 build vote; not STRONG, not KILL). A real seam that
`session-handoff` explicitly disclaims, carried by the strongest prong-1 demand signal in the ledger
(a direct user request, not fabricated/inferred), but gated on demand recurrence **and** two
load-bearing design fixes before it could enter the build queue.

This candidate is distinct from the prior KILLs `decision-log` ("a mode of session-memory") and
`spec-anchor` ("drift-check is a mode of session-handoff") — it confronts both directly below.

---

## Candidate: roadmap-anchor

A durable, long-horizon **product roadmap** the agent maintains across sessions: where the app is
going, the direction, the **sequencing of major work** (next/later milestones), and the **rationale**
("why billing before teams"). Intended to stop planning being lost when conversations compact and
tactical handoffs are archived. Maintains e.g. `.ai/memory/ROADMAP.md` (milestones, shipped/next/later,
direction rationale) with a periodic reconcile against shipped reality. Evaluated **as a third
session-memory skill**, not standalone.

---

## 1. Baseline-gap grounding → REDUNDANT (as pitched)

Decomposed into four legs; classified each against installed tools, published skills, the native
convention, and the two prior KILLs.

| Leg | Finding |
|---|---|
| (a) forward direction + sequencing (the north-star artifact) | **Owned externally.** Published, installable skills do exactly this: `jezweb/claude-skills` `roadmap` (multi-phase roadmap + executes it across sessions), `deanpeters/Product-Manager-Skills` `roadmap-planning`, `arach/claude-roadmap-commands` (`/roadmap` `/next` `/progress`); plus the documented native pattern (agent-maintained `ROADMAP.md` + a `CLAUDE.md` "always read it first" line). These are in-repo and agent-consumed — the candidate's claimed open territory. |
| (b) rationale / why-this-direction | **Native-LLM-collapse** + partly owned: durable "why" already fits `lessons-learned` / session-handoff "Decisions with rationale". |
| (c) drift-check (does shipped code still match the direction) | **The already-KILLed `spec-anchor`** — an anchor-staleness check, a mode of session-handoff (which already captures git branch/HEAD/dirty-list at save and quantifies drift at resume). Long horizon doesn't change the mechanism. |
| (d) update-discipline / anti-rot | Only leg with non-collapse texture (triggering + write-discipline is legitimately what makes session-handoff valuable), **but** it's a thin wrapper over owned legs, and the honest "is it still true?" check must re-read the code it summarizes — the **freshness trap** that KILLed `env-known-good` / `repo-recon-memory`. |

**Decisive grounding reason:** as pitched, the headline leg (a) is true-duplicated by shipping roadmap
skills + the native `ROADMAP.md`+`CLAUDE.md` convention; the rest collapse or reduce to already-KILLed
modes. Sources: [jezweb roadmap](https://claudemarketplaces.com/skills/jezweb/claude-skills/roadmap),
[deanpeters roadmap-planning](https://github.com/deanpeters/Product-Manager-Skills/blob/main/skills/roadmap-planning/SKILL.md),
[arach/claude-roadmap-commands](https://github.com/arach/claude-roadmap-commands),
[Ben Newton — agent-maintained roadmap](https://benenewton.com/blog/claude-code-roadmap-management),
[DrBradStanfield/roadmap CLAUDE.md pattern](https://github.com/DrBradStanfield/roadmap/blob/main/CLAUDE.md).

**Counter that the panel credited:** the duplication is weaker than it looks. The published skills are
**not installed here**, and "CLAUDE.md owns direction" conflates an *always-loaded facts file* with an
*evolving, sequenced milestone ledger* — stuffing the latter into CLAUDE.md bloats every turn and has
no save/update ritual. Against the **installed** tools, roadmap-anchor fills the exact long-horizon hole
`session-handoff` disclaims by design (single-task, archived-and-replaced each save, stale-after-14-days,
north-star explicitly out of scope) and `lessons-learned` doesn't cover (corrections, not forward plan).

---

## 2. Scenario simulation → avgDelta 5.4

| # | Scenario | Δ |
|---|---|---|
| 1 | Sequencing re-litigated across a 6-week build — auth→billing→teams decided week 1; week 4 a customer pull toward teams; the *why* lived in a compacted convo and the early handoffs were archived. Skill surfaces the standing direction + rationale so deviation is conscious, not accidental drift. | **8** |
| 2 | Cold "where is this product heading?" after a 2-week gap — handoff is stale-by-design + single-task; skill gives faithful north-star recall (milestones, shipped/next/later, rationale). | **7** |
| 3 | One-off bug fix / throwaway prototype — skill correctly **stays silent**; firing here would dilute the north-star signal. Right-sizing test. | **1** |
| 4 | **Rot trap** — `ROADMAP.md` says "next: billing" but billing shipped + teams was pulled forward, unreconciled. Naive skill confidently misstates → **worse than baseline** (which reads git log). Only a real reconcile discipline (diff vs merged PRs since the anchor) turns the trap into a caught discrepancy. | **6** (negative without reconcile) |
| 5 | Mid-project pivot ("switch sharing from public-links to invite-only — does it blow up the roadmap?") — skill surfaces milestone dependencies + persists the decided pivot; but the durable-direction slice is contested vs `decision-log` / `product-strategist`. | **5** |

**Read:** real cross-task seam in S1/S2 that session-handoff explicitly disclaims; but the trigger
surface ("major milestone/direction" vs "ordinary feature work") is **fuzzy**, and the rot risk is
**existential** — the load-bearing feature is a rigorous, anchor-based reconcile.

---

## 3. Adversarial panel → 1 build / 2 no-build (both NOs are fixable defers, not hard kills)

- **Skeptic 1 — non-redundancy lens → BUILD.** Against installed tools it fills the slot session-handoff
  disclaims and lessons-learned doesn't cover; published skills are uninstalled (weaker duplication);
  CLAUDE.md is a facts file, not an evolving sequenced ledger — so no true duplication against what
  exists *here*. *Self-counter:* if the only differentiated mechanic is the reconcile/freshness
  discipline, that was already KILLed as `spec-anchor` and S4 goes negative without it — risk of
  collapsing into a thin freshness-wrapper around a hand-maintainable file.
- **Skeptic 2 — usefulness/demand lens → NO (explicit DEFER).** Demand is a single articulation
  (Count 1), failing creation-bar prong 1 (needs ≥2–3×). A direct user request raises priority but is
  still one data point; it *lowers the cost of waiting* (the user will re-surface a real pain). *Self-
  counter:* this isn't a fabricated candidate — the user named a live pain and S1/S2 (Δ7–8) hit a seam
  handoff refuses to cover; if "rationale that outlives archived handoffs" is genuinely homeless, the
  redundancy finding overstates coverage and waiting just keeps eating a Δ8 pain. **"If a future
  occurrence confirms recurrence, this flips to true — it's a defer, not a hard kill."**
- **Skeptic 3 — design/safety lens → NO as-briefed, designable IF fixed.** Net-positive rides entirely
  on a reconcile discipline that, for a *durable* artifact, **cannot** borrow session-handoff's
  expire-and-replace staleness defense (you can't expire a roadmap after 14 days without defeating its
  purpose), so the only honest reconcile re-derives code reality = the freshness trap. Trigger is fuzzier
  than both siblings (which fire on crisp events: stop/resume; you-corrected-me), risking over-fire and
  signal-dilution. *Self-counter:* a roadmap reconcile diffing **git log / shipped milestones**
  (high-signal, already-summarized) is cheaper than the KILLed whole-codebase freshness checks; and if
  the trigger fired only on **explicit user direction-setting** ("here's our roadmap", "we're pivoting
  to X", "what's our direction") rather than inferred milestone-ness, "both objections soften
  considerably."

---

## Verdict — PARKED

Not STRONG (1/3 build), not KILL (real disclaimed seam + the ledger's strongest prong-1 signal). Mirrors
the `super-plan-mode` PARK: a genuine gap whose build is gated on evidence + a specific design fix.

**Two load-bearing conditions to clear before it enters the build queue (both surfaced by the panel's
self-counters):**

1. **Demand recurrence.** Watch for the same "loss of planning / where is this going / why this before
   that" pain to recur **≥2–3×** in real multi-week work. The direct user request is Count 1 — a warm
   park, not a cold one (the user will re-surface it if it's real).
2. **Two design fixes** that convert the 2 NO votes:
   - **Re-anchor the trigger to explicit user direction-setting events** ("here's our roadmap", "we're
     pivoting to X", "what's the product direction / what's next") — NOT the model inferring
     "is this milestone-level?" (the fuzzy-gate failure). Ship should-NOT-trigger evals: one-off
     bugfix, prototype, ordinary feature work, "continue this task" → silent.
   - **Git-anchored reconcile, not a self-re-read.** Diff `ROADMAP.md` against merged PRs / shipped
     milestones since its anchor date (the session-handoff staleness mechanism pointed at a longer
     horizon) so the anti-rot check reads high-signal markers, not the whole codebase — dodging both the
     freshness trap and the `spec-anchor` collapse. A stale-but-undetected roadmap is below the safety
     floor; the reconcile is the feature, not a nice-to-have.

**Honest conclusion:** design it as a third session-memory skill with the two fixes above; **do not
build until the planning-loss pain recurs ≥2–3×.** Packaging is settled (user's call: third
session-memory skill); demand + the trigger/reconcile design are the remaining gates.
