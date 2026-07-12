# Overclock — skill strategy

Durable decisions about *what* to build and *why*. Read this before proposing a new
skill: it records the operating rules, the candidates already assessed, and the
groundings already done — so we don't re-litigate settled questions.

This file is repo documentation, not shippable content. It lives outside `plugins/`,
so it ships to no user and needs no version bump.

## Operating principles

> **The bar is usefulness, full stop (clarified 2026-06-22, sharpened 2026-06-25).** Overclock is a
> personal toolkit, not a product line — skills exist to be useful to the people who use them, not to
> be defensible against a marketplace. The one test a skill must pass: does it reliably save effort or
> improve an outcome on something you actually do? **Reliable triggering of a wanted behavior counts
> as value even if the base model could do it when prompted** — automating a preference you'd
> otherwise re-type every time IS the gap, not a reason to skip it. The "memory + right-sizing moat"
> and every "defensible / marketplace / don't-reimplement" phrase in this repo's history are
> **DESCRIPTIVE, never gates.** Do not KILL a useful skill for "stateless", "no moat", "a published
> skill already does it", or "the base model could do it when asked."

1. **Usefulness is the only gate.** A skill earns its place if you'd reliably reach for it on real
   work. It does **not** need to be novel, stateful, adaptive, or unavailable elsewhere. The honest
   question is "would I reach for this," not "is this defensible."

2. **Two quality checks — on craft, not on existence.** Once a skill is worth having, it must be
   *well-made*:
   - **Right-sized.** Fires only when wanted, with real anti-triggers and should-NOT-trigger evals
     from day one. A skill that misfires on trivial work is worse than no skill. (This is the one
     genuinely load-bearing discipline — keep it strict.)
   - **No collision.** It must not fight another skill *already in this kit* for the same trigger.
     Non-redundancy is scoped to **your installed kit**, not the whole ecosystem.

3. **Grounding is research, not a gate.** Check what already exists — built-ins, official plugins,
   published skills, the base model's own ability — to build the skill **better** and avoid pointless
   reinvention. "It exists elsewhere" informs the design; it does not kill the skill. Wanting your own
   version, tuned to you and under your control, is a legitimate reason to build anyway. The only
   redundancy that kills is true duplication of something already *in this kit*.

4. **Demand: a real reason is enough; pure speculation still waits.** A direct request, or a concrete
   use you can name, is sufficient to build — you do not need ≥2–3 logged incidents for something you
   know you want. The guard remains only against speculative "might be nice" skills that nobody asked
   for and nothing points to.

## Skill candidate ledger

Append-only. Each candidate carries a verdict and the evidence behind it.

### PR-reviewer — STRONG, recommended (2026-06-16)
- **Demand:** two prior self-built attempts (`~/startups/n8n-pr-reviewer`, with a
  persona + precedent-PR + embeddings stack; plus an earlier pass). That *is* the
  candidate ledger at Count 2 — observed pain, not ideation.
- **Moat:** precedent memory ("PR #4521 fixed this same pattern; here's how", cited
  inline) + decaying, evidence-counted review learnings *per repo*. No official tool
  has this — `/code-review` (incl. ultra), pr-review-toolkit, `/security-review` are
  all amnesiac. This is the one candidate grounding made **stronger**.
- **Trust model already right:** drafts comments the human pastes; never auto-posts.
- **Next:** Phase-0 baseline head-to-head — persona+precedent stack vs the built-ins
  on real n8n PRs, blind-judged with our eval harness — *before* building. If it
  doesn't visibly beat the built-ins, we learn that for a few cents.
- **Phase-0 scaffolded (2026-07-12):** `qa/experiments/pr-reviewer-phase0/` pins six
  real merged n8n PRs, the current external candidate commit, a blind rubric, result
  schema, and a hard 4-of-6 build gate. The actual two-arm reviews remain deliberately
  manual and can accumulate during normal use; scaffolding is not a build verdict.
- **Risks:** product-sized (Phase 1 is real work); the n8n-specific corpus/few-shots
  need generalizing into a per-repo ingest story before it's marketplace material;
  the interactive triage needs negative-control evals so it doesn't over-question.

### super-plan-mode — PARKED, narrow at best (2026-06-16)
- **Intended:** deeper task analysis + better planning than current plan mode.
- **Grounding outcome:** the *methodology* is already shipped. The official
  **feature-dev** plugin (installed) implements ~80% of what we designed —
  understand → explore-the-codebase → **clarify after recon, before architecture**
  ("CRITICAL. DO NOT SKIP.") → 2–3 architecture approaches with a recommendation →
  implement → review. **Ultraplan** owns the heavy cloud/architectural case; plan
  mode owns the bare case.
- **Surviving gap (the only non-duplicative angle):** *right-sizing* — none of the
  three scale rigor to task size — and *task-type-agnostic* application (feature-dev
  is feature-shaped; bug investigations, refactors, perf hunts are unserved).
- **Verdict:** building the planning methodology = bloat (duplicates feature-dev).
  The only defensible version is a lightweight **planning-rigor router** that
  right-sizes and *delegates* upward ("real feature → `/feature-dev`"; "huge
  multi-file refactor → Ultraplan") rather than reimplementing them. Small skill.
  Build only if the right-sizing decision itself proves a recurring pain. Parked
  pending that evidence.

## Groundings performed (reference)

- **Ultraplan** (Claude Code, ~2026): hands planning to a cloud Opus 4.6 web session;
  Q&A brainstorm → plan; Simple/Visual/Deep modes; Deep uses sub-agents for risk;
  browser review with inline comments + diagrams. Requires v2.1.101+, GitHub-hosted
  repo, Pro/Max. Owns the large, multi-file, architectural case. Not available
  local/offline/non-GitHub.
- **feature-dev** (`claude-plugins-official`, installed): `/feature-dev` command,
  7 phases, parallel `code-explorer` / `code-architect` / `code-reviewer` agents.
  Owns local feature implementation end-to-end. No right-sizing — same ceremony for a
  config flag and an auth rebuild; feature-shaped only.
- **Built-in review** (`/code-review` incl. ultra, pr-review-toolkit's 5 agents,
  `/security-review`): strong but stateless — no precedent memory, no per-repo
  learning. This is the gap PR-reviewer exploits.

## Standing conclusion

Overclock is a personal toolkit. A skill is worth building when it reliably helps with real work and
is well-made (right-sized, with real anti-triggers, not colliding with another skill already in the
kit). Memory and right-sizing are great *when the task needs them*, but they are not the point and
never a requirement. Weigh new candidates on "would I reach for this, and is it well-made" — not on
defensibility, novelty, or whether something similar exists elsewhere.
