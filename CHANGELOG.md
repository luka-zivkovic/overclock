# Changelog

Versions are per-plugin. A version bump is what ships an update to installed
users; the CI version-bump guard enforces that plugin content changes carry one.

## eval-stack

### 0.1.0 — 2026-08-26 (initial release)
- Add a local-first workflow that connects Ironside trace capture, Coeval judged
  evaluation with human adjudication, calibrated judge projects, and Casefile
  scanning without presenting localhost defaults as production architecture.
- Ship deterministic Claude Code and Codex post-hoc importers plus a live pi
  tracer. All three use the same byte caps and redact quoted JSON assignments,
  environment-style secrets, bearer credentials, and Ironside read/write-scoped
  token formats before ingest.
- Add behavioral and routing evidence for setup order, secret and model-spend
  boundaries, session import, and the explicit production multi-user anti-trigger.
- The workflow verifies live components and pauses before credential writes or
  paid judge calls; it never silently turns calibration into an unbounded
  auto-judging job.

## agent-bridge

### 0.1.2 — 2026-08-16
- Give implementation delegations a realistic 60-minute default while keeping
  read-only consultations at 15 minutes. Explicit bounded runs may request up to
  two hours, and every result records the resolved timeout without weakening
  process cleanup or patch-integration gates.

### 0.1.1 — 2026-08-15 (initial release)
- New plugin. `$agent-bridge` lets the current harness use an installed Claude,
  Codex, or Gemini CLI as a bounded leaf collaborator while retaining parent-task
  ownership. Consultation is read-only; implementation delegation requires the
  user's existing write authority, an exact clean base, allowed paths, acceptance
  criteria, and an explicit `--allow-write` runtime gate.
- Run delegated implementation only in a private local clone under the user's
  cache directory (never the shared system temp dir, which provider sandboxes can
  write to). The clone's `origin` remote is removed after cloning, so "never
  pushes" is structural. Return a provider-attributed result, changed paths, an
  ASCII Git binary patch, and SHA-256 integrity anchors; refuse out-of-scope
  changes and never auto-commit, push, publish, or let two agents write the
  active checkout concurrently.
- Add digest-locked inspect/apply operations that revalidate repository identity,
  base SHA, clean state, patch integrity, path scope, and `git apply --check`
  before changing the active working tree. Scope inspection and both apply steps
  consume the digest-verified in-memory patch bytes via stdin, so nothing between
  verification and application can substitute the file on disk. A completed
  delegation that changed nothing reports `no_changes` instead of a misleading
  apply error. Provider failures, same-harness recursion, timeouts, and
  unavailable CLIs fail closed without fallback.
- Create bridge-owned job files (`result.json`, `result.patch`) with
  `O_EXCL|O_NOFOLLOW`, so a leaf-planted symlink or pre-created file fails loudly
  instead of redirecting an unsandboxed bridge write.
- Reject symlink-touching patches by parsing git file-mode headers, which also
  catches retargeting an existing tracked symlink (a bare `index … 120000`
  header) and stops false positives on patch content that merely mentions a
  mode. The `.git` path guard is case-insensitive for case-insensitive
  filesystems.
- After provider success or timeout, kill the leaf's entire process group and sweep
  for same-user processes carrying its unique per-run marker before repository
  inspection. This also terminates descendants that created a new session; fail
  closed with `process_cleanup_failed` when they cannot be inspected or killed.
- Harden delegation against a leaf-controlled clone. Reset the clone's `.git`
  configuration to its pristine post-clone state and run every bridge-side git
  command with global/system configuration masked, so a worker-written
  `.git/config` (`core.fsmonitor`, `diff.external`) can no longer execute commands
  in the bridge process.
- Enforce delegated scope against the patch itself. Derive the built patch's target
  paths with `git apply --numstat`, require them to fit the allowlist and match the
  observed changes, and refuse symbolic-link patches — at both build and apply time,
  instead of trusting only the self-recorded changed-file list.
- Forward only an allowlisted, provider-scoped environment to the child process so
  unrelated parent secrets are not disclosed to the external provider.
- Start Codex children without user configuration or exec-policy rules and disable
  their multi-agent tools so MCP servers, hooks, rules, and subagents cannot broaden
  the bounded leaf role.
- Verify consultation against a pre/post `HEAD` and working-tree snapshot and report
  `workspace_changed`; add `workspace_tampered` for a clone whose `.git` was replaced.
- Honor `is_error` results from Claude, bound bridge-side git commands with a timeout,
  and derive the state directory per-user with an ownership check.
- Keep working when a host sandbox denies the entropy device: job naming falls back to
  a non-cryptographic unique suffix (creation stays exclusive in the user-owned state
  root).
- Sharpen the routing description with concrete second-reviewer/critique/delegate
  trigger phrasings and an explicit rule that the bridge, not ad hoc provider CLI
  commands, is the sanctioned cross-provider path.

## project-vocabulary

### 0.1.2 — 2026-07-26
- Crash durability: an apply killed between claiming CONCEPTS.md and installing
  the replacement no longer leaves the glossary missing — the next apply
  restores a stale stranded claim (no-replace rename, so a concurrent glossary
  is never overwritten).
- Make mixed terminology-and-workflow prompts an explicit positive routing case:
  project-vocabulary owns only the domain-language half while preserving its
  standalone no-write fallback for the optional workflow owner.

### 0.1.1 — 2026-07-23
- Separate implicit assistance from write authority. Automatic routing may inspect
  untrusted project vocabulary, challenge a fuzzy term, and present an exact proposal;
  only an explicit add/update request or approval of that proposal may change
  `CONCEPTS.md`.
- Add a root-confined helper that refuses linked, special, escaped, or concurrently
  changed inputs, previews digest-locked diffs, and atomically applies only the
  approved glossary candidate. Expand unit, behavioral, and installed-together
  lessons/vocabulary controls.
- Keep mixed terminology/workflow corrections safe when installed alone: handle only
  the vocabulary half, leave lesson storage untouched, and name the unavailable
  optional owner instead of implying it ran.

### 0.1.0 — 2026-07-20
- New plugin. `project-vocabulary`: maintain the project's ubiquitous
  language in a repo-root CONCEPTS.md glossary and apply it in conversation,
  merged from the two best published takes (mattpocock domain-modeling + the
  compound-engineering concepts-vocabulary rules) under the external-audit
  BUILD verdict (external-eval-2026-07-19-1945.md; the ADR half dropped per
  the verdict). File craft: definitions stand on their own (no file paths or
  current config values — state the behavior, not the number), one term per
  concept with retired synonyms as aliases, a Flagged Ambiguities tail,
  inline updates, lazy creation. Terms enter by accretion (settled in
  conversation) and seeding (core nouns of an area before sustained work).
  In conversation: fuzzy usage is challenged when it matters, overloaded
  nouns are pinned before building on them, new definitions get stress-
  tested with an edge case, and glossary-vs-code mismatches are surfaced
  honestly.
- Boundary declared from both sides per the eval panel: terminology
  corrections ("we call that a Workspace") land in the glossary; behavior
  and workflow corrections stay with lessons-learned; a correction carrying
  both splits. This skill never writes LESSONS.md or .ai/memory/.
- Four behavioral evals (glossary-applied term challenge, accretion +
  seeding, split-correction routing with both files present, non-domain
  negative control) and a routing battery whose negatives are dominated by
  lessons-learned collision prompts.

## debugging-discipline

### 0.1.1 — 2026-07-23
- Make diagnosis read-only by default and require explicit implementation authority
  before source edits or instrumentation. Add safe production/replay rules, a
  fail-soft path when reproduction is unsafe, and proportionate flake/performance
  evidence guidance.
- Replace forced 3–5 hypothesis ceremony with 1–5 credible hypotheses, calibrate
  causal claims, and add a real installed-together composition case with
  discipline-gates plus production-safety coverage.

### 0.1.0 — 2026-07-20
- New plugin. `debugging-discipline`: systematic diagnosis for bugs that
  resist the ordinary red-test path, merged from the two best published
  takes (mattpocock diagnosing-bugs + EveryInc ce-debug) under the
  external-audit BUILD verdict (external-eval-2026-07-19-1945.md). The hard
  gate: a tight, red-capable feedback loop must exist before any causal
  theory — with a ranked ladder of loop constructions (flaky reruns with
  raised reproduction rate, curl/CLI harnesses, diff and replay loops,
  bisection, perf measurement). Then: minimize the failure, audit
  assumptions (verified vs assumed), show 3-5 ranked falsifiable hypotheses
  before testing them, and state predictions before probes — a fix that
  works while its prediction fails is a symptom, not the cause. Tagged
  removable debug probes; escalation to a design-level look when surviving
  hypotheses span subsystems.
- Composition per the eval panel's condition: seamed bugs with stated
  symptoms get their red artifact from discipline-gates/test-discipline's
  repro contract — this skill never restates that gate; it owns the no-seam
  loop constructions and the hypothesis epistemics. Trivial bugs whose cause
  is evident fast-path out with zero ceremony.
- Four behavioral evals (flaky-race loop-first, seamed-bug composition
  control, symptom-vs-cause prediction discipline, trivial-typo negative
  control) and a routing battery whose negatives are dominated by
  test-discipline collision prompts.

## groundwork

### 0.1.1 — 2026-07-23
- Make the skill stop at a provenance-labelled, confirmed decision brief. Groundwork
  no longer implements or plans after elicitation.
- Bound blanket delegation to reversible, low-impact defaults; high-impact privacy,
  authorization, retention, billing, and destructive choices must be asked or
  explicitly deferred. Add an objective stopping rule, scoped inspection guidance,
  and a plugin-loaded multi-turn correction/confirmation case.

### 0.1.0 — 2026-07-20 (renamed from `grilling` the same day, pre-adoption)
- Renamed `grilling` → `groundwork` on maintainer preference before any
  external adoption; skill behavior unchanged. "Grill me about this" remains
  a routing trigger phrase.
- New plugin (originally shipped as `grilling`): requirements elicitation as a discipline, rebuilt
  from mattpocock/skills' grilling primitive under the external-audit BUILD
  verdict (external-eval-2026-07-19-1945.md). One question per turn, each
  with a recommended answer; facts the repository can answer are looked up,
  never asked (the facts-vs-decisions split); questions walk the decision
  tree in dependency order; no question cap — depth steers by natural
  language. A refuse-to-act gate summarizes the shared understanding and
  waits for confirmation before anything is built; "just build it" locks in
  the recommended defaults, stated explicitly. Confirmed choices align with
  session-handoff's [user-directed]/[user-approved] provenance labels.
- Trigger seam per the eval panel: elicitation-only triggers with explicit
  anti-triggers routing critique/stress-test/verdict requests to
  critical-thinking (the collision that failed ADOPT-AS-IS), plus
  ask-one-ordinary-question right-sizing for single-ambiguity tasks.
- Four behavioral evals (facts-not-asked elicitation, delegated-answers gate
  handling, natural-language pacing, critique-request negative control) and
  a routing battery whose negatives are dominated by critical-thinking
  collision prompts.

## pr-feedback

### 0.2.1 — 2026-07-26
- Fetch robustness: paginated GraphQL page sets are handed to `jq` through
  `--slurpfile` temp files instead of `--argjson` argv values, so very large
  PRs no longer abort on the ARG_MAX limit.
- Route prefetched GitHub review data, open-review-comment requests, and approved
  resolver-plan follow-ups explicitly to `resolve-pr-feedback`, while keeping all
  remote mutation reserved for manual `$publish-pr-feedback`.
- Carry a falsified shared premise and its decisive evidence into every affected
  bot-thread verdict and reply, rather than weakening sibling items to generic
  "not applicable" explanations.
- Require a persistent uncommitted regression test file for executable
  reviewer-reported symptoms; inline runtime probes and manual traces no longer
  substitute for a red/green artifact.
- Make the local report name explicit `$publish-pr-feedback` on the handoff
  sentence instead of relying on a pronoun-only reference.

### 0.2.0 — 2026-07-23
- Split local judgment from remote authority. `resolve-pr-feedback` now only fetches,
  judges, fixes within approved local scope, and drafts replies; it cannot post,
  react, or resolve even after conversational approval.
- Add manual-only `$publish-pr-feedback`. It accepts only a sealed plan path plus its
  exact SHA-256 digest, verifies the GitHub host/repository/PR node/open state/head
  OID and every source/action before mutation, and never judges feedback or changes
  code.
- Add fully paginated, author-independent sequential-retry/source scans, exact plan
  sealing, linked-file refusal, non-overwriting atomic output, all-actions preflight,
  a final head re-pin, a required single-publisher assertion, and structured
  partial-failure reporting. Concurrent publishers remain unsupported because the
  marker check and GitHub comment creation are not atomic. Remove the resolver's
  direct reply/resolve scripts and add four explicit publication-boundary evals.
- Make approved-plan preparation work from a standalone `resolve-pr-feedback`
  installation: the resolver now carries its own read-only GitHub client and local
  plan contract, while the publisher independently revalidates its own contract copy
  and sealed digest.
- Keep resolver safety gates intact without sibling skills: reviewer-reported bugs get
  a direct uncommitted red test when test-discipline is absent, defensive weakening
  gets local history/current-state checks when git-archaeologist is absent, and a
  missing publisher is reported as an unavailable remote capability.

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

### 0.1.18 — 2026-08-26
- Publish Eval Stack 0.1.0 in the capability catalog so the report-only setup
  advisor can recommend the local tracing and governed-evaluation workflow.

### 0.1.17 — 2026-08-17
- Synchronize the bundled capability catalog with Natural Writing 1.0.5.

### 0.1.16 — 2026-08-16
- Synchronize the bundled capability catalog with Agent Bridge 0.1.2.

### 0.1.15 — 2026-08-08
- Update the bundled capability catalog to the hardened Agent Bridge (0.1.1) and the
  mutation-restore fix in discipline-gates (0.1.6).

### 0.1.14 — 2026-08-04
- Publish Agent Bridge in the bundled capability catalog for bounded cross-harness
  consultation and isolated implementation delegation.

### 0.1.13 — 2026-07-26
- Synchronize the bundled catalog for critical-thinking 0.1.4, pr-feedback 0.2.1,
  and project-vocabulary 0.1.2.

### 0.1.12 — 2026-07-23
- Keep the default inventory project-scoped. User-level instruction metadata now
  requires an explicit opt-in rerun and file contents remain omitted.
- Fix standalone overlap detection for skill frontmatter beyond the old 8 KiB read,
  use effective write access instead of mode-bit guesses, and match every shipped
  skill name through the capability catalog.
- Keep inventory diagnostics metadata-only: linked instruction targets, unexpected
  CLI output, and plugin-command stderr are never echoed into the report.
- Extend catalog validation to require manifest/marketplace version equality and an
  exact `skill_names` list for every independently installable plugin.
- Add a host-resolved absolute-path fallback for the bundled inventory helper when
  the host does not expand Claude Code's skill environment variables.

### 0.1.11 — 2026-07-20
- Catalog rename: `grilling` → `groundwork`.

### 0.1.10 — 2026-07-20
- Publish `project-vocabulary` in the bundled capability catalog so setup
  can recommend it.

### 0.1.9 — 2026-07-20
- Publish `debugging-discipline` in the bundled capability catalog so setup
  can recommend it.

### 0.1.8 — 2026-07-20
- Publish `grilling` in the bundled capability catalog so setup can
  recommend it.

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

### 0.1.4 — 2026-07-26
- Put explicit critical-thinking requests and decision-plus-local-evidence prompts
  first in the routing description, and keep the complete listing below Claude
  Code's description truncation limit.
- Promote missing context isolation to an early hard gate: the critical-thinking
  context may not inspect the referenced local root as a fallback, even when the
  user requests direct research or same-context evidence appears decisive.
- Resolve optional-skill availability from the host declaration rather than
  searching user directories, plugin caches, or the filesystem.

### 0.1.3 — 2026-07-23
- Tighten right-sizing for low-stakes requests and make reconsideration of an earlier
  user-settled choice explicit rather than socially automatic. Bound delegated local
  research to one material pass.
- Require independent-research callers to name exact roots and exclusions. Add an
  8-artifact/64 KiB cumulative budget, dirty-worktree provenance, and a deterministic
  no-follow reader that rejects links and special files while emitting SHA-256
  evidence metadata.
- Make isolation claims host-conditional: Claude Code uses its forked Explore worker;
  other hosts must provide an equivalent fresh read-only worker or the skill reports
  an isolation gap without inspecting sources.
- Expand prompt-injection, budget, access, and long-context behavioral controls and
  installed-together routing exclusions. A standalone critical-thinking install now
  treats independent-research as optional and returns a conditional verdict rather
  than implying that a missing sibling ran.

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

### 1.0.5 — 2026-08-17
- Remove performed-casual phrasing, unsupported value language, cadence-only
  contrasts, redundant summary buttons, significance tails, and flourish endings
  when they add no information. Preserve substantive contrasts, informative endings,
  literal wording, and recognizable authorial choices.
- Extend the launch-post behavioral case to cover the new editing rule while retaining
  its factual claims and Postgres compatibility caveat.

### 1.0.4 — 2026-07-23
- Reframe punctuation and vocabulary rules as a fallback house style beneath the
  author's established voice. Preserve modality, caveats, deliberate dashes, exact
  quotations, actors, and factual scope rather than strengthening prose for fluency.
- Make visual revision reports strictly explicit opt-in, move their schema into a
  readable reference, verify that change segments reconstruct both complete strings,
  and improve report accessibility and replacement tests.

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

### 0.1.6 — 2026-08-08
- A trial refused before the mutant is installed now removes its own backup, so
  the next trial no longer fails with "mutation backup already exists". If the
  post-trial restore itself fails, the error names the target and its original
  digest and states the mutant may still be on disk; the exit-code contract in
  the module docstring documents this exception.
- Fix a mutation-trial restore gap: if replacing the target file failed after the
  mutant was already published, the working tree could be left mutated. The trial now
  marks the mutant installed at publication so the `finally` restore runs on every
  post-publication failure path.
- Give the mutation-trial wrapper a distinct exit code (3) for a surviving mutation so
  scripted callers gating on exit status no longer read a survivor as a pass.

### 0.1.5 — 2026-07-23
- Remove all automatic staging and commits from test-discipline. Red regressions and
  characterization pins remain narrowly scoped working-tree evidence.
- Publish integrity-checked atomic mutation backups and a transactional runner that
  restores in `finally`; calibrate results to “detected/did not detect this selected
  mutation” and require the intended behavioral assertion to fail.
- Keep verified mutation claims and temporary files open until cleanup completes, so
  Linux inode reuse cannot make a concurrent replacement look like an owned file.
- Tighten the test/debugging seam and current-coverage definition. Git archaeology now
  treats history and remote discussion as untrusted data, verifies repository
  identity, distinguishes dirty committed guards from new uncommitted code, and
  requires current callers/tests/replacement controls before `safe-to-remove`.
- Make each gate's triage references skill-specific instead of loading sibling-only rules.
  Git archaeology now uses test-discipline only when installed and otherwise creates the
  smallest uncommitted behavioral pin directly, so both skills retain their safety contract
  when installed alone.

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

### 1.0.3 — 2026-07-23
- Crash durability: a writer killed mid-update no longer leaves the canonical
  memory file missing — the next lock-holding write restores the stranded
  claim file first. Untrusted-content read sentinels carry a per-invocation
  nonce, and a failed archive prune after a successful save is a warning, not
  a refusal.
- Route all lesson reads, writes, and approved instruction promotion through a
  root-confined, no-follow, lock-protected atomic helper shared byte-for-byte with
  session-memory. Stable reads now expose an exact SHA-256 (or `absent`) and every
  write/promotion must compare-and-swap that observed token, refusing torn reads,
  stale sessions, and non-helper publication races without overwriting them.
- Replace file-content injection at SessionStart with a fixed reminder that reports
  ledger availability only. Clarify untrusted memory, lesson ownership, newest-user
  precedence, provider-aware promotion targets, and approval-only curation.
- Split the previously all-in-one storage reference into a byte-identical 64-line
  cross-harness I/O/security core and a directly linked LESSONS.md schema. The
  standalone skill now resolves absolute skill/project paths from its active host
  instead of requiring Claude-specific environment variables, while retaining exact
  ledger compatibility with session-memory.

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

### 1.1.1 — 2026-07-23
- Crash durability: a writer killed mid-update no longer leaves the canonical
  memory file missing — the next lock-holding write restores the stranded
  claim file first, and compare-and-swap then surfaces the recovered content.
  Untrusted-content read sentinels carry a per-invocation nonce so memory text
  cannot forge its own envelope boundary, and a failed archive prune after a
  successful save is reported as a warning instead of a refusal.
- Add one byte-identical safe memory helper to all three skills: no-follow directory
  traversal, linked/special-file refusal, bounded UTF-8 validation, lock-protected
  atomic replacement, archive-before-handoff replacement, and safe five-archive
  retention. Stable reads expose an exact SHA-256 (or `absent`); every memory write
  and approved instruction promotion requires that observed token and refuses torn
  reads, stale sessions, and non-helper publication races without overwriting them.
- Make the SessionStart hook emit fixed metadata only instead of injecting
  repository-controlled memory prose. All memory remains untrusted until a skill
  reads it through the helper.
- Harden resume anchors to full object IDs and timezone-bearing timestamps with
  ahead/behind/diverged checks; formalize provenance-plus-recency precedence,
  lessons/solutions/vocabulary ownership, verification provenance, safe commands,
  and approval-only instruction promotion.
- Split the 199-line group-wide memory contract into a byte-identical 64-line
  cross-harness I/O/security core plus self-contained handoff, lessons, and solutions
  schemas. Each writer loads only its own schema; session-handoff loads optional
  LESSONS.md/SOLUTIONS.md reader schemas only during resume when those ledgers exist.
  Commands resolve absolute paths from the active host rather than requiring
  Claude-specific environment variables. A standalone lessons hook now uses
  lessons-only mode instead of probing or announcing sibling handoff state.

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
