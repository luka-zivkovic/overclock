# Overclock — skill strategy

Durable decisions about *what* to build and *why*. Read this before proposing a new
skill: it records the operating rules, the candidates already assessed, and the
groundings already done — so we don't re-litigate settled questions.

This file is repo documentation, not shippable content. It lives outside `plugins/`,
so it ships to no user and needs no version bump.

## Operating principles

1. **Baseline-gap before building.** Ground every candidate against what already
   exists — built-in commands, official plugins, cloud features — *before* writing a
   line. A skill earns existence only if existing tools do the job measurably worse.
   In this project the test has killed or narrowed every "workflow" idea we've had
   (see groundings below); it has only ever *strengthened* the memory-backed ones.

2. **The moat is memory + adaptivity, not workflow.** The official tools (plan mode,
   feature-dev, Ultraplan, /code-review, /security-review) are **stateless** and
   **one-size**. They will always out-resource any workflow ceremony we build. Our
   defensible edge is precisely what they structurally won't do:
   - **Persistence across sessions** — session-memory; a per-repo review precedent
     corpus; decaying learnings.
   - **Right-sizing** — scaling rigor to task size/blast-radius instead of running
     one fixed ceremony.
   Build those. Do not reimplement an official plugin's workflow.

3. **Right-size or it's bloat.** A skill that runs full ceremony on a trivial task is
   worse than no skill. Every skill needs a triage/altitude gate and real
   anti-triggers, or it fails its own baseline-gap test.

4. **Creation bar (all three required).** Observed recurring demand (the same unmet
   need seen ≥2–3×, evidenced — not imagined), a proven baseline gap, and it ships
   with should-NOT-trigger evals from day one. One observation never births a skill.

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

The dev-workflow space (plan, build, review) is saturated by capable, well-resourced
official tools. Overclock's wins come from the axes they ignore — **memory** and
**right-sizing** — not from better ceremony. Weight new candidates accordingly.
