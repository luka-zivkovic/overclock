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
   - **Standalone first.** Every skill directory must execute correctly when installed by itself.
     Group packaging may improve routing or compose workflows, but sibling descriptions, hooks,
     scripts, and references are never implicit dependencies. Test target-only, owning-plugin, and
     intended-stack modes separately.

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

### agent-bridge — BUILD, v0.1 shipped (2026-08-04)
- **Demand:** direct maintainer request for one harness to consult or delegate a
  bounded implementation subtask to another provider while the original harness
  remains responsible for the overall task.
- **Grounding:** OpenAI's `codex-plugin-cc` confirms the local-auth/runtime pattern:
  a thin model-facing layer delegates through a deterministic companion, with
  readiness checks, provider-native sandbox selection, resumable/background jobs,
  and explicit result handling. Agent Bridge generalizes the useful core across
  Claude, Codex, and Gemini without copying the review gate or Codex-only app-server
  broker into v0.1.
- **Product shape:** one independently installable `agent-bridge` skill with two
  explicit modes. `consult` is read-only. `delegate` requires implementation
  authority, a clean exact base, non-empty path scope and acceptance criteria, and
  runs only in an isolated local clone. A digest-locked patch is separately inspected
  and applied by the parent; no background jobs, resume, auto-commit, push, publish,
  or in-place child writes in v0.1.
- **Trust model:** current-conversation authorization is required before sharing
  scoped repository context with another provider. Provider output is untrusted
  advice or an untrusted candidate patch; the parent verifies and owns integration.
- **Next:** validate real Claude↔Codex use on bounded tasks before adding persistent
  threads, background jobs, dirty-worktree snapshots, or full handoff.

### PR-reviewer / pr-kit — STRONG, Phase-0 candidate (updated 2026-07-17)
- **Demand:** two prior self-built attempts (`~/startups/n8n-pr-reviewer`, with a
  persona + precedent-PR + embeddings stack; plus an earlier pass). That *is* the
  candidate ledger at Count 2 — observed pain, not ideation.
- **Moat:** precedent memory ("PR #4521 fixed this same pattern; here's how", cited
  inline) + decaying, evidence-counted review learnings *per repo*. No official tool
  has this — `/code-review` (incl. ultra), pr-review-toolkit, `/security-review` are
  all amnesiac. This is the one candidate grounding made **stronger**.
- **Trust model settled:** drafts comments the human may paste; never auto-fixes, edits, commits,
  pushes, or posts. Implementation and comment publication are permanently outside `review-pr`.
- **Next:** run the three-arm Phase-0 comparison on real n8n PRs — built-in baseline, generic
  pr-kit, and initialized pr-kit — blind-judged with the committed rubric before publishing.
- **Original Phase-0 scaffold (2026-07-12):** `qa/experiments/pr-reviewer-phase0/` pinned six
  real merged n8n PRs, the external candidate commit, a blind rubric, result schema, and a hard
  build gate. The review runs remain deliberately manual; scaffolding is not a build verdict.
- **Product shape chosen (2026-07-17):** one independently installable `pr-kit` plugin with two
  explicit skills. `review-pr` must remain repository-agnostic, read-only, adversarial in discovery,
  conservative in reporting, and useful with no setup. `initialize-pr-kit` is a one-time/refresh
  initializer whose only write is a source-grounded `.ai/pr-kit/REPOSITORY.md`; it never edits
  instructions/settings or commits. Current source always outranks the profile.
- **Phase-0 expanded (2026-07-17):** the experiment now has built-in baseline, generic pr-kit, and
  initialized pr-kit arms. Generic must beat baseline independently; initialized context must then
  show material source-valid lift over generic. The skill-shaped candidate lives under the
  experiment directory and is intentionally unpublished until both gates pass.
- **Pilot result (2026-07-22): FAILED.** The initialized arm accumulated two losses, so its lift
  gate was mathematically failed before the remaining cases; the generic arm also had not earned
  publication. `pr-kit` remains unpublished. The next legitimate step is to diagnose those losses,
  revise the experimental candidate if warranted, and rerun the same committed gates. The scaffold
  is not a roadmap or publication authorization.
- **Mechanics hardening (2026-07-17):** grounding against EveryInc's compound-engineering plugin
  added delta-aware profile-input digests, deterministic risk-scope signals, exact changed-line
  finding validation, a silent-pass verification lens, and positive/negative behavioral controls.
  The candidate deliberately kept one local read-only reviewer: no fixed persona swarm, external
  code egress, auto-fixes, commits, posting, or writeful review mode. Those mutations are outside
  the product boundary, not deferred Phase-0 features.
- **Risks:** the historical corpus is still one repository; repository-profile quality and setup
  cost may vary substantially across codebases; stale profiles can mislead unless current-source
  precedence and source validation remain strict.

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
