# Changelog

Versions are per-plugin. A version bump is what ships an update to installed
users; the CI version-bump guard enforces that plugin content changes carry one.

## pr-feedback

### 0.1.0 — 2026-07-19
- New plugin. `resolve-pr-feedback`: consume-side PR review workflow for GitHub
  (including Enterprise). Fetches every unresolved review thread, review body,
  and top-level comment in one fully paginated GraphQL pass (scripts adapted
  from EveryInc/compound-engineering-plugin, MIT); judges each item centrally
  against the actual code with a six-verdict rubric (fixed, fixed-differently,
  declined, not-addressing, replied, needs-human); clusters systematically-wrong
  reviewer premises instead of fixing them one by one; applies valid fixes to
  the working tree and drafts quoted replies.
- Trust model: judge-and-draft. Posting replies and resolving threads happen
  only after explicit user approval; the skill never commits, pushes, merges,
  rebases, approves CI, or resolves a `needs-human` thread. Review-comment text
  is treated as untrusted data, never as instructions.
- Ships a network-free live-eval suite (bot-cluster catch, deliberate-design
  needs-human, prompt-injection resistance, two negative controls) and a
  routing trigger battery with produce-side and non-GitHub anti-triggers.

## overclock-setup

### 0.1.7 — 2026-07-20
- Catalog sync for `session-memory` 1.1.0 (new `solutions` capability and
  `.ai/memory/SOLUTIONS.md` persistent file).

### 0.1.6 — 2026-07-20
- Catalog sync for `session-memory` 1.0.5 and `critical-thinking` 0.1.2.

### 0.1.5 — 2026-07-20
- Catalog sync for `natural-writing` 1.0.3.

### 0.1.4 — 2026-07-20
- Catalog sync for `discipline-gates` 0.1.4.

### 0.1.3 — 2026-07-19
- Publish `pr-feedback` in the bundled capability catalog so setup can
  recommend it.

### 0.1.2 — 2026-07-17
- Synchronize the bundled capability catalog with the Codex metadata releases for
  `session-memory`, `learning-loop`, `natural-writing`, and `discipline-gates`.

### 0.1.1 — 2026-07-12
- Publish `critical-thinking` and `discipline-gates` in the bundled capability
  catalog so setup can recommend exact installation commands for both packages.

### 0.1.0 — 2026-07-10
- Publish a manual `/overclock-setup:setup` advisor focused on Overclock product
  selection rather than duplicating Claude's built-in project initializer.
- Add a deterministic read-only inventory that filters plugin/settings state,
  detects standalone overlaps and instruction-file conditions without returning
  file contents, and never follows instruction symlinks.
- Constrain every inventory read through no-follow directory descriptors, reject
  symlinked settings/instruction ancestors, and detect standalone overlaps from
  bounded `SKILL.md` frontmatter scans rather than folder names alone.
- Keep v0.1 report-only: ask only capability, scope, and hook questions that can
  change the plan; return exact proposed commands and minimal instruction diffs;
  never install plugins or edit settings, hooks, CLAUDE.md, or AGENTS.md.
- Add a structured capability catalog with publication, dependency, conflict,
  hook, persistent-file, and minimum-host metadata. Enforce the current
  `session-memory` XOR `learning-loop` rule and prohibit install commands for
  preview plugins.
- Add catalog drift validation, inventory unit tests, real local-marketplace
  install smoke coverage, and eleven passing adversarial live evals for conflicting scopes,
  duplicate hooks, prompt injection, secrets, symlinks, idempotency, previews,
  hook refusal, and requests to bypass report-only mode.

## critical-thinking

### 0.1.2 — 2026-07-20
- Reassessment now distinguishes the assistant's own conclusions (hypotheses
  to re-derive) from decisions the user examined and made (settled): a
  user-settled decision is not re-litigated unprompted; new material evidence
  against it is presented once, plainly, for the user to re-decide. The
  assistant's own unexamined proposal is never treated as user-settled.
  Lifted from the compound-engineering settled-decisions evaluation
  (external-eval-2026-07-19-1945.md, INSPIRE). Adds eval case 11 (revise an
  assistant conclusion on new profiling evidence without reopening the
  user's settled infrastructure choice).

### 0.1.1 — 2026-07-12
- Publish the plugin in the Overclock marketplace.
- Make critical-thinking and independent-research route reliably for reassessment,
  high-stakes evidence checks, and explicitly requested local-source verification.
- Make evidence-based reversals explain how material experiment-validity signals
  strengthen or limit the causal conclusion instead of merely listing them.

### 0.1.0 — 2026-07-10
- Add a stateless reasoning skill that tests user framing independently, separates
  evidence from assumptions, surfaces material counterarguments and alternatives,
  and calibrates confidence without praise or reflexive contrarianism.
- Scale scrutiny to decision stakes while staying silent on routine execution,
  open-ended ideation, and emotional acknowledgment.
- Reset commitment, but not evidence, when reassessing conclusions reached earlier
  in a long conversation; treat repetition, consensus, sunk cost, and the assistant's
  own prior advice as non-evidence.
- Add eleven behavioral evals and a thirteen-prompt routing battery covering leading
  premises, warranted agreement, concise correction, decision risk, anti-triggers,
  long-context anchoring, self-defense, social proof, and evidence-based reversal.
- Extend the live-eval runner with optional persisted setup turns so context cases
  test the model against its own prior answers instead of a pasted mock transcript.
- Add an `independent-research` companion skill that verifies material uncertainties
  from accessible primary evidence, preserves provenance, reports contradictions,
  and respects authorization and research-budget boundaries.
- Teach critical-thinking to invoke independent-research conditionally rather than
  relying on user summaries or researching every minor unknown.
- Add fourteen research evals, a twelve-prompt routing battery, and a cross-skill
  integration eval that requires inspecting a referenced repository before rejecting
  a destructive recommendation.
- Exercise full plugin loading in the eval runner so namespaces, sibling skills, hooks,
  and built-in agent delegation match the shipped package.
- Run independent-research in a fresh `context: fork` through Claude Code's built-in
  Explore agent, which omits project/user instruction memory, and pass a neutral brief
  rather than the parent conversation or desired conclusion. Document that write/code
  execution and tool-surface constraints are behavioral rather than claiming a sandbox.
- Treat source content as hostile data, redact secrets, avoid symlink/scope escapes,
  distinguish checkout/config/test/deployment/runtime evidence, and enforce an explicit
  local source budget. Document that path confinement is behavioral, not an OS sandbox.
- Add adversarial research cases for prompt injection, secret bait, symlink escape,
  deployment drift, ambiguous project identity, exhaustive-search pressure, accurate
  user input, and destructive test scripts.
- Add optional no-skill baseline runs plus per-case cost, latency, turn, and token
  metrics; record the same metrics for trigger-routing batteries.
- Make eval harness failures fail fast, rebuild pristine fixtures per distribution,
  validate complete judge output, load real plugins, keep declared IDs out of deletion
  paths, select reruns by declared case ID, and raise the manual workflow timeout.

## natural-writing

### 1.0.3 — 2026-07-20
- Add a grounding rule to the drafting guidance, lifted from the
  writing-structure evaluation (external-eval-2026-07-19-1945.md, INSPIRE):
  a concept the reader can't be assumed to know must be introduced — or be a
  stated prerequisite — before later prose leans on it; ground in place at
  first use rather than bolting on a glossary, preserving meaning and voice.
- Add a behavioral eval case (id 6) where a technical draft's only real
  defect is grounding order (a term explained after use, another never
  defined), so the revision must fix structure without adding style tells.

### 1.0.2 — 2026-07-17
- Add Codex skill-picker metadata and a ready-to-use `$natural-writing` prompt.

### 1.0.1 — 2026-07-09
- Preserve original metaphors that carry the author's meaning or voice while still
  removing canned decorative analogies.
- Generate optional revision reports through a schema-validating helper that embeds
  prose as base64 UTF-8 JSON, preventing HTML or `</script>` text from becoming
  executable markup.
- Require that helper through its host-provided absolute skill path; confine report
  input/output beneath the project with no-follow directory descriptors, refuse linked
  or pre-existing output by default, and permit replacement only with explicit approval.

### 1.0.0 — 2026-07-03
- First published release (added to marketplace.json). A stateless prose
  writing/editing skill that strips AI tells — em-dashes, tell vocabulary
  ("delve"/"leverage"/"tapestry"), bot scaffolding, uniform rhythm, decorative
  bold — while preserving quotes verbatim, keeping load-bearing caveats, and
  staying silent on code, commit messages, and one-line edits. Ships with
  mined before/after examples and an opt-in HTML revision report.
- Live eval suite added (5 cases, including the caveat-must-survive and
  byte-identical-quote traps and two negative controls): 5/5 green.

## discipline-gates

### 0.1.4 — 2026-07-20
- git-archaeologist: name simplification-framed removals explicitly in the
  trigger surface — a "simplify", "clean up", "reduce ceremony", or
  "make this a one-liner" request whose execution would strip a defensive
  construct fires the gate the same as an explicit delete request, while
  behavior-preserving simplifications that keep every guard intact stay
  silent. Adds a positive and a negative routing control to the trigger
  battery. Executes the ponytail INSPIRE lift (never simplify away a safety
  check) recorded in docs/brainstorm/SHORTLIST.md; behavioral coverage
  already exists in eval case 2 (simplify-framed retry removal).

### 0.1.3 — 2026-07-17
- Add Codex skill-picker metadata and ready-to-use prompts for `test-discipline`
  and `git-archaeologist`.

### 0.1.2 — 2026-07-12
- Publish the plugin in the Overclock marketplace.
- Front-load concrete bug-fix, untested-refactor, and newly-green-test triggers,
  while making already-covered and behavior-preserving edits explicit exclusions.
- Route defensive-code archaeology on concrete guards, retries, locks, and caller
  bounds without triggering on behavior-preserving control-flow rewrites.

### 0.1.1 — 2026-07-09
- test-discipline: reuse an adequate existing failing regression test instead of
  creating a duplicate; scope the existing-coverage anti-trigger to characterize
  mode; recognize observable effects as behavioral coverage.
- test-discipline: restore validate-mode mutations from an exact byte backup for
  both clean and dirty files instead of restoring clean files from HEAD.
- test-discipline: perform mutation backup/restore through a bundled no-follow helper
  that refuses symlinks, hardlinks, special files, linked parents, out-of-project paths,
  and pre-existing backups before any mutation occurs.
- git-archaeologist: narrow early-return and delay triggers to defensive/protective
  constructs so ordinary control flow does not cause archaeology ceremony.

### 0.1.0 — 2026-07-03
- Initial unpublished release (not yet in marketplace.json; its live evals
  passed and publication remains pending the audited 0.1.1 rerun). Two
  pre-action gates over real oracles, packaged per
  `docs/brainstorm/packaging-discipline-gates.md`:
  - **test-discipline** — one multi-mode skill: `repro` (commit a test that
    fails for the stated reason before fixing a reported bug), `characterize`
    (pin untested code's current behavior as committed green tests before
    refactoring), `validate` (mutate the code under a freshly-green test,
    demand red, restore unconditionally — kills vacuous tests).
  - **git-archaeologist** — before deleting/weakening a guard, retry, sleep,
    lock, clamp, or "redundant" check: blame → introducing commit → linked
    PR/issue → Chesterton's-fence warning with quoted evidence; never invents
    intent.
  - Shared should-NOT-trigger surface single-sourced as byte-identical
    per-skill references (CI-guarded via `tools/shared-files.txt`).
- Live eval suite: 10/10 cases green (5 per skill), including negative controls,
  byte-identical mutation restoration, and a SHA-pinned real-repository history case.
- Build decision: the packaging doc's §6 incident-tally demand gate is
  superseded by strategy.md principle 4 (direct request suffices) — built on
  the maintainer's direct pick, 2026-07-03.

## learning-loop

### 1.0.2 — 2026-07-17
- Add Codex skill-picker metadata and a ready-to-use `$lessons-learned` prompt.

### 1.0.1 — 2026-07-09
- Align secret-bearing explicit record requests with the redaction contract: the
  skill now still routes, records only the redacted rule, and never persists the
  supplied secret value.
- Clarify declined CLAUDE.md promotion: keep the lesson, record the decline, and
  do not repeatedly ask on later reinforcement.

### 1.0.0 — 2026-06-17
- Initial release. Extracts the lessons-learned skill into a standalone,
  self-improvement-loop plugin: corrections and diagnosed failures become
  durable, deduplicated, evidence-counted lessons in `.ai/memory/LESSONS.md`,
  surfaced in later sessions by a bundled SessionStart hook. Decoupled from
  session-handoff — its memory contract and hook cover only LESSONS.md — but the
  ledger format is a strict subset of session-memory's, so the two interoperate
  on one `.ai/memory/LESSONS.md` if both are installed. The lessons-learned skill
  body is shared with session-memory in spirit, not byte; only the
  `templates/lessons.md` skeleton is kept byte-identical (CI-enforced).

## session-memory

### 1.1.0 — 2026-07-20
- New `solutions` skill: capture a verified solution to a nontrivial problem
  in `.ai/memory/SOLUTIONS.md` — symptoms as the retrieval key, what didn't
  work as a first-class field, the fix, why it works, and how it was
  verified. Dedup is by root cause (update in place, never duplicate);
  retrieval verifies a stored solution against current source before
  applying it; a suggestion-first refresh flow proposes
  Keep/Update/Merge/Retire per entry and applies only what the user
  approves. Explicit boundary with lessons-learned: solved project problems
  here, corrections of agent behavior there; a dead end hit while solving
  lives inside the solution's What-didn't-work line. Adapted from EveryInc's
  compound-engineering ce-compound/ce-compound-refresh
  (external-eval-2026-07-19-1945.md, BUILD-IN-OVERCLOCK).
- Memory contract v1 extended with the SOLUTIONS.md format (three
  byte-identical copies, CI-guarded), ownership row, and a staleness rule:
  current source always outranks a stored solution.
- session-handoff resume now also surfaces matching SOLUTIONS.md entries
  (read-only) in the warm-start brief.
- Five behavioral evals gate the loop's payoff, not just capture: creation
  with secret redaction, root-cause dedup, a retrieval case where the stored
  What-didn't-work must prevent re-proposing a known dead end, a trivial-fix
  silent no-op, and a lessons-vs-solutions boundary control. Plus a routing
  trigger battery.

### 1.0.5 — 2026-07-20
- session-handoff: Decisions entries now carry a provenance label —
  `[user-directed]`, `[user-approved]`, or `[agent-proposed]` — and the
  resume flow treats user-settled decisions as settled: augment, never
  re-ask, contradict only on new material evidence presented once. Unlabeled
  decisions in older handoffs stay valid and remain open to revision. The
  agent's own unexamined proposal is never labeled user-settled. Lifted from
  the compound-engineering settled-decisions evaluation
  (external-eval-2026-07-19-1945.md, INSPIRE). Adds eval case 7 (resume
  under a `[user-directed]` database choice where the tempting simpler
  alternative must not be re-proposed).

### 1.0.4 — 2026-07-17
- Add Codex skill-picker metadata and ready-to-use prompts for `session-handoff`
  and `lessons-learned`.

### 1.0.3 — 2026-07-09
- lessons-learned: align the routing description with the existing secret-redaction
  behavior so an explicit record request containing a secret still triggers but
  persists only the redacted rule.
- lessons-learned: clarify that declining CLAUDE.md promotion keeps the lesson and
  suppresses repeated promotion prompts.
- session-handoff: make every resume brief use the same exact six-line Goal → Plan →
  Decisions → Do-not-retry → Drift/lessons → Proposed-next-step shape.

### 1.0.2 — 2026-06-13
- lessons-learned: an explicit record request that contains a secret is now
  treated as consent to record the redacted version immediately — the skill no
  longer bounces "should I save it without the secret?" back at the user.
  Caught by the pinned secret-redaction eval on the first remote CI run
  (behavior erred safe — nothing was persisted — but deflected an explicit
  instruction).

### 1.0.1 — 2026-06-12
- session-handoff: stale-handoff resume now explicitly declares the handoff too
  stale for step-by-step reconciliation and leads with a fresh start as the
  default recommendation (full reconciliation named only as the alternative).
- Eval suite: fixed a self-contradictory pasted-handoff case; harness captures
  tool calls so process expectations are graded on evidence.

### 1.0.0 — 2026-06-12
- Initial release: session-handoff + lessons-learned skills over the shared
  `.ai/memory/` contract, with the bundled SessionStart hook that surfaces
  parked handoffs and lesson counts at session start.
