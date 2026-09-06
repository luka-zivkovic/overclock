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

### agent-bridge — BUILD, v0.1 published; cross-provider validation pending (2026-08-04)
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
- **Next:** the shipped code paths (isolation, git-environment hardening, patch-derived
  scope enforcement, environment allowlist, consult integrity snapshot) are covered by
  deterministic tests. Real Claude→Codex use was validated 2026-08-08 against codex-cli
  0.144.2 on a scratch repository using local CLI auth: consult returned a correct answer
  with the active tree verified unchanged, and delegate produced a digest-locked
  single-file patch in the uid-scoped isolated clone that passed inspect and apply with
  scope enforced from the patch itself. Live behavioral evals pass 5/5 on Sonnet, and the
  routing battery passes both install modes against the sibling stack (skill 47/48, stack
  47/48; precision 94.7%, recall 100%, specificity 96.7% — all above the 90/80/90 gate).
  Claude→Gemini remains unvalidated (CLI not installed); record one real bounded Gemini run
  before treating that provider as supported. Only after that, consider persistent threads,
  background jobs, dirty-worktree snapshots, or full handoff.

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
- **Edge-composition pilot (2026-08-16): FAILED.** A two-PR 2×2 run compared built-in and generic
  pr-kit reviews with and without one frozen implementation-blind edge brief. Relative to plain
  pr-kit, `+edge` won once and tied once; across both reviewers it produced 1 win, 1 tie, and 2
  losses. The brief therefore does not rescue pr-kit or authorize an orchestration layer.
- **Mechanics hardening (2026-07-17):** grounding against EveryInc's compound-engineering plugin
  added delta-aware profile-input digests, deterministic risk-scope signals, exact changed-line
  finding validation, a silent-pass verification lens, and positive/negative behavioral controls.
  The candidate deliberately kept one local read-only reviewer: no fixed persona swarm, external
  code egress, auto-fixes, commits, posting, or writeful review mode. Those mutations are outside
  the product boundary, not deferred Phase-0 features.
- **Risks:** the historical corpus is still one repository; repository-profile quality and setup
  cost may vary substantially across codebases; stale profiles can mislead unless current-source
  precedence and source validation remain strict.

### anticipate-edge-cases — Phase-0 candidate (2026-08-16)
- **Demand:** direct maintainer request for an implementation-blind pass that reads a PR/issue or
  supplied change text, inspects relevant repository context, and anticipates material edge cases
  before the implementation can anchor the review.
- **Relation to PR-reviewer:** this is an upstream review artifact, not another implementation
  reviewer and not a revival of the failed repository-profile lift. V1 stops at a risk brief that a
  later built-in or plugin reviewer may consume; it never reads or judges the diff.
- **Product shape:** one explicit, independently installable `anticipate-edge-cases` skill in a fresh
  forked context. A deterministic helper resolves the exact pre-change commit and exposes only
  bounded base-tree listing, search, blob, history, GitHub intent, and bundled-lens operations. No
  setup, persistent profile, sibling dependency, hook, implementation mode, or writeful mode.
- **Trust and right-sizing:** PR/issue text, repository source, tests, docs, and history are untrusted
  evidence. The output labels explicit requirements, inference, and product questions; potential
  risks are never reported as code findings. Wording/formatting-only work is a compact no-op rather
  than a generic checklist.
- **Evidence:** the non-shipping candidate and target-only controls live under
  `qa/experiments/anticipate-edge-cases/`. The 2026-08-16 pilot passed the positive control (6/6)
  and negative control (4/4) with zero permission denials, implementation leakage, or repository
  mutation. The positive control hid a naive webhook retry on the feature head and produced the
  required base-evidenced timeout-after-remote-success/idempotency risk; the negative control
  returned a two-line no-op. Those controls established mechanics but not real-case lift.
- **Real-case composition result (2026-08-16): FAILED.** On n8n PRs #33820 and #33867, frozen edge
  briefs fed into built-in and pr-kit reviewers produced 1 matched win, 1 tie, and 2 losses. One
  brief-derived ResourceLocator probe became a confirmed finding that plain pr-kit missed, but the
  data-table brief missed the dominant workflow-reference breakage found by the no-brief baseline.
  There was no implementation leakage or repository mutation. Do not auto-compose the skills; fix
  helper-command hygiene and identity-consumer discovery before rerunning the same gate.
- **Late-reveal redesign (2026-08-17): FAILED generalization.** Identity-consumer discovery fixed
  the known miss: the base-only data-table brief found raw workflow `dataTableId` consumers and a
  separate delta lifted the frozen pr-kit review from 3→10. Hash-frozen late reveal also prevented
  any original finding from being dropped. On untouched scheduler and Rundeck SSL cases, however,
  matched outcomes were 1 win, 2 ties, and 1 loss. The scheduler's cross-scope-name hypothesis
  improved a weak built-in review but reduced a strong pr-kit review; SSL added no finding. Do not
  auto-compose. Before another run, require reachable-producer evidence for every delta addition,
  admit only confirmed findings, and make helper permissions deterministic.
- **Role-matrix screen (2026-08-17): FAILED; no automatic arm promoted.** On two preselected PRs,
  two reviewer families, and eight automatic placements, upfront probes produced 2 wins and 2
  losses while dropping confirmed base findings in one block; the seven strict
  challenger/confirmation/conditional arms produced 28 byte-identical ties and zero confirmed edge
  root causes. All six sealed risks were handled, unreachable, or decorative. The router sent all
  four reviewer/case blocks to challengers despite zero material contributions, and author-preflight
  found no material risk value. Safety held: no implementation leakage or mutation. Stop before
  confirmation-case selection; do not auto-compose or use the router. The full result and promotion
  audit live under `qa/experiments/pr-edge-role-matrix-phase0/results/screen-2026-08-17.md` and the
  generated run root. Human-sidecar usefulness remains a separate, unrun study.
- **Consumer-contract pivot prepared (2026-08-17):** at the maintainer's request, Codex and Claude
  independently designed implementation-aware second-pass candidates. The comparison selects the
  narrower Claude-seeded `audit-consumer-contracts` boundary, with Codex's explicit
  producer/consumer contract matrix and fail-closed evidence validation cherry-picked into it.
  `qa/experiments/review-contract-gaps-phase0/` preserves both candidates, the certified Agent
  Bridge proposal, deterministic controls, and the selection rationale. The selected extractor now
  surfaces the known agent `promptType`/description producer contract without consuming the failed
  edge brief, but it also routes the clean frozen-error calibration case; routing selectivity and
  live reviewer lift remain unproven. This is a new non-shipping candidate, not authorization to
  reopen automatic composition or publish a plugin.
- **Consumer-contract live pilot (2026-08-17): FAILED; stopped after sample 1.** The selected
  implementation-aware audit ran after frozen built-in and pr-kit reviews across five PRs. It
  produced zero confirmed additions in ten reviewer/case blocks, so append-only composition yielded
  ten deterministic ties. More importantly, it failed its motivating case: the built-in review
  missed the Agent `description ?? newHint` defect, and the audit also missed it because generic
  lexical tokens occupied the bounded surface budget while `description` ranked S11. The pr-kit base
  review found the defect unaided. Ten audit analyses cost $11.2769877; total pilot attempts cost
  $30.67541235, and three non-finding evidence ledgers remained invalid after bounded repair. Stop
  before samples 2–3, park the lexical-surface design, and do not auto-compose or publish it. Any
  future attempt needs a semantic contract-endpoint gate that first recovers this miss without answer
  leakage and passes a fresh negative. Full evidence lives in
  `qa/experiments/review-contract-gaps-phase0/results/live-matrix-pilot-2026-08-17.md`.
- **Contract-audit candidate tournament (2026-08-17): BROAD ARM PASSES SCREEN.** Reusing the exact
  ten frozen base-review blocks, the previously untested broad semantic `review-contract-gaps` arm
  produced three source-valid additions. All three won blind comparison, yielding 3 wins, 7 ties,
  and 0 losses across three PRs and both reviewer families; the frozen-error negative stayed clean
  and append-only retention held. This overturns the paper selection of the narrow lexical arm,
  which remains at 0 wins and 10 ties. The broad arm did not recover the motivating unreachable-
  description defect over the built-in miss, validated only 8/10 ledgers after bounded repair, and
  cost $27.31802775 for 23 attempts including judges. Keep it as a semantic upper-bound candidate,
  not a shippable skill: replicate on fresh samples, then replace model-authored exact anchors with
  deterministic parent-side evidence assembly before reconsidering automatic composition. Full
  evidence lives in `qa/experiments/review-contract-gaps-phase0/results/candidate-tournament-2026-08-17.md`.
- **Broad semantic replication (2026-08-17): BEHAVIOR PASSES; MECHANICS FAIL.** Two unchanged
  samples reused the exact ten frozen base reviews. Sample 2 produced 1 win and 9 ties; sample 3
  produced 5 wins and 5 ties. Both had zero losses, unsupported additions, negative-case findings,
  or retention failures, and wins spanned four PRs and both reviewer families. Both new built-in
  samples independently recovered the motivating unreachable-description defect. Combined with
  sample 1, the candidate is 9 wins, 21 ties, and 0 losses over 30 matched blocks, so semantic
  complementary value is replicated. Mechanics fail the separate pre-registered gate: 15/20
  replication ledgers were valid, 15/20 required repair, replication cost $52.1585826, and the broad
  arm cost $79.47661035 across all three samples. Do not run another unchanged sample, publish, or
  auto-compose. Preserve semantic inventory/contract tracing but move commit selection, exact line
  materialization, counts, and ledger assembly to a deterministic parent helper before a fresh-PR
  A/B. Full evidence lives in
  `qa/experiments/review-contract-gaps-phase0/results/replication-2026-08-17.md`.
- **Deterministic-assembly V2 (2026-08-17): BEHAVIOR PASSES; HINT RESOLUTION FAILS.** A separate
  non-shipping `codex-v2` candidate keeps semantic implementation inventory and contract tracing but
  moves commit resolution, exact source lines, changed-line checks, review hashes, deduplication, and
  counts into a bundled deterministic helper. Discovery is review-blind and shared across reviewer
  families; root-cause subtraction runs afterward in a narrow context; malformed claims fail closed
  individually and there is no repair session. The same ten frozen blocks and separate behavior/
  mechanics gates are committed in `mechanics-redesign-gate.json` and
  `run_mechanics_redesign.py`. An initial account-limit 429 was excluded at zero cost and before
  inference. The valid replay produced 2 wins, 8 ties, and 0 losses; both node-registry additions won
  blind comparison, with zero unsupported/negative findings and full retention. Review-blind
  discovery also recovered the known description miss, the Instance AI write-lock bypass, and a
  saved-agent schema-refresh gap, but the one-line-only helper rejected those three claims because
  Claude returned multi-line or abbreviated hints. Fully materialized discovery was 40% and rejected
  claim rate 75%, despite 100% coverage completion, zero repairs/denials, and only $7.5303897 total
  cost. Keep the architecture, add safe multi-line/path-plus-line-hint resolution, and rerun the
  frozen mechanics gate before fresh PRs. Full evidence lives in
  `qa/experiments/review-contract-gaps-phase0/results/mechanics-redesign-v2-2026-08-17.md`.
- **Bounded-hint V3 (2026-08-18): IMPROVED YIELD; UNSAFE ANCHOR AND BEHAVIOR LOSS.** The separate
  `codex-v3` candidate accepts multi-line and ellipsis-abbreviated evidence hints while retaining
  V2's review-blind discovery and deterministic parent assembly. Against the same frozen blocks it
  improved full materialization from 40% to 80% and reduced rejected claims from 75% to 25%, but the
  any-fragment matcher accepted the generic line `workflowId,` from an unchanged method block as an
  unrelated changed anchor. The blind result was 4 wins, 5 ties, and 1 loss with two unsupported
  findings; a saved-agent claim was separately and correctly rejected for citing a newly introduced
  line as a base contract. Both gates fail despite 100% discovery/coverage, zero repairs/denials, and
  $8.987814 total cost. Freeze V3 as negative evidence. A successor must require strong intended-line
  or coherent ordered-neighborhood matching, reject generic fragments, preserve strict ref checks,
  and tighten causal-scope/impact admission before another frozen replay. Do not publish,
  auto-compose, or start fresh-PR A/B. Full evidence lives in
  `qa/experiments/review-contract-gaps-phase0/results/mechanics-redesign-v3-2026-08-18.md`.
- **Strict-anchor V4 (2026-08-18): BEHAVIOR PASSES; SPECIFICITY IS TOO STRICT.** Full-file
  intended-line resolution removed V3's unsafe redirection and produced 1 win, 9 ties, 0 losses, and
  no unsupported findings. Mechanics remained below gate: 60% fully materialized discovery and 50%
  rejected claims because exact `...promptTypeOptions,` and `<NodeToolSettingsContent` source lines
  each contained only one identifier. Preserve the 16-character floor and intended-line-first
  ordering, but the two-identifier condition is not justified. Cost was $6.6242931. Full evidence:
  `qa/experiments/review-contract-gaps-phase0/results/mechanics-redesign-v4-2026-08-18.md`.
- **Intended-line V5 (2026-08-18): MECHANICS PASSES; CAUSAL ADMISSION FAILS.** Removing only the
  two-identifier condition yielded 100% discovery/full materialization, 0% rejected claims, complete
  coverage, zero repairs, and $9.3240135 total cost. The V3 false anchor stayed closed. Behavior was
  2 wins, 6 ties, and 2 losses: guardrails improved the built-in base and the ChatHub ResourceMapper
  scope gap improved pr-kit, but both judges rejected a snapshot-restore claim that generalized one
  base `expectedChecksum` example into an unsupported universal invariant over a pre-existing,
  unchanged path. Freeze V5's resolver. The next experiment must require base evidence to entail the
  stated contract and require unchanged omissions to be demonstrably inside the changed decision's
  scope. Do not publish, auto-compose, or start fresh-PR A/B. Full evidence:
  `qa/experiments/review-contract-gaps-phase0/results/mechanics-redesign-v5-2026-08-18.md`.
- **Publication gate:** require zero implementation leakage or mutation, green target-only controls,
  and source-valid lift on at least two real PR/issue cases over brainstorming after diff exposure.
  Longer generic risk lists are a failed result, not reviewer value.

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

### lateral-engineering — BUILD, v0.1 authored (2026-09-05)
- **Demand:** direct maintainer request for a reusable procedure that escapes conventional
  engineering answers when creative alternatives are wanted.
- **Grounding:** expose hidden assumptions through a private conventional draft; apply six move
  families plus an arbitrary constraint; prosecute conventional candidates before presenting
  distinct, grounded alternatives. The catalog transfers mechanisms across fields rather than
  treating precedent as a prerequisite for an idea.
- **Boundary:** owns deliberate engineering ideation, not general critique (`critical-thinking`),
  requirements elicitation (`groundwork`), debugging, implementation, or safe production advice.
  One standalone skill, no hooks, no sibling dependencies, no writes, no auto-commit, and no
  automatic execution of experiments.
- **Evidence:** tier `subjective`. The two requested author-run examples and qualitative review
  notes live in `qa/experiments/lateral-engineering/`; five committed behavioral cases and a
  target-only routing battery cover creative requests, reruns, thin input, and anti-triggers.
  No baseline lift or live routing success is claimed; isolated live runs require credentials
  unavailable during authoring. Structural checks do not establish creative quality.

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
