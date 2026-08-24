# Claude 5 Context-Engineering Review and Reduction Plan

Status: proposal for external review
Prepared: 2026-07-26
Repository: Overclock
Implementation prerequisite: merge [PR #21](https://github.com/luka-zivkovic/overclock/pull/21)
before branching this work from the updated `master`

## Why this document exists

This review was prompted by the Anthropic article:

- [The new rules of context engineering for Claude 5 generation models](https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models)

The user asked:

> Can you analyze this and tell me if we're using these best practices?

After the repository was compared with the article, the user asked for an implementation plan and
then requested that the complete reasoning and plan be written to a file for assessment by another
agent harness.

The question being evaluated is:

> Does Overclock use Claude 5-era context-engineering practices, and if only partially, how should
> its skill context be simplified without weakening routing, standalone execution, authority
> boundaries, or safety?

This is not a request to blindly conform to one vendor article. Overclock is provider-neutral and
ships independently installable Claude Code plugins. The article is an important new model-specific
signal, but every proposed reduction must still earn its place through repository evidence.

## Source thesis

The article reports that Anthropic removed more than 80% of Claude Code's system prompt for newer
Claude 5-generation models without measurable loss on its coding evaluations. Its practical
recommendations can be summarized as:

1. Prefer model judgment over blanket behavioral rules.
2. Design expressive tools and interfaces instead of teaching primarily through examples.
3. Use progressive disclosure instead of putting every procedure into initial context.
4. Keep tool and skill descriptions simple and avoid repeating instructions across context layers.
5. Keep `CLAUDE.md` lightweight and focused on repository-specific gotchas rather than obvious
   information or miscellaneous memory.
6. Prefer auto-memory for personal/session memory rather than using `CLAUDE.md` as a memory dump.
7. Use rich, high-fidelity references such as code, tests, schemas, artifacts, and rubrics.
8. Simplify context and use evaluations to determine whether removed material was actually needed.

The article also preserves an important exception: highly consequential safety and authority areas
may still require explicit constraints. Therefore, this plan distinguishes hard safety invariants
from compressible judgment and presentation guidance.

## Repository baseline

These measurements were taken from the post-PR-#21 working tree on 2026-07-26.

### Repository-level context

- `CLAUDE.md`: one line, 11 bytes; it imports `AGENTS.md`.
- `AGENTS.md`: 83 lines, 4,791 bytes.
- `docs/strategy.md`: 131 lines, 9,422 bytes, loaded only when proposing or building a skill.

The top-level context is already relatively lightweight and repository-specific. The strongest
opportunity is not deleting the maintainer contract; it is moving branch-specific verification
mechanics behind a deterministic interface where practical.

### Always-loaded skill metadata

Across a theoretical installation containing all 15 skill distributions:

- Skill-description text: 13,236 characters.
- Rough description budget: approximately 3,309 tokens using the repository's `chars / 4`
  estimator.

Actual supported installations are smaller because `session-memory` and `learning-loop` are
mutually exclusive. Nevertheless, descriptions are the highest-leverage reduction target because
available-skill metadata is present before any skill body is selected.

Description sizes currently range from approximately 542 to 1,258 characters. Several descriptions
encode:

- positive routing triggers;
- anti-triggers;
- collision ownership;
- optional-sibling fallbacks;
- isolation requirements;
- execution authority; and
- output behavior.

Much of that is execution detail rather than routing interface.

### Selected skill bodies

All skill bodies total approximately 30,382 estimated tokens, but progressive skill loading means
only selected bodies should enter context. The largest individual bodies are:

| Distribution | Estimated body tokens |
|---|---:|
| `critical-thinking/critical-thinking` | 3,057 |
| `session-memory/session-handoff` | 2,939 |
| `pr-feedback/resolve-pr-feedback` | 2,433 |
| `discipline-gates/test-discipline` | 2,432 |
| `learning-loop/lessons-learned` | 2,175 |
| `session-memory/lessons-learned` | 2,142 |
| `critical-thinking/independent-research` | 2,026 |
| `debugging-discipline/debugging-discipline` | 2,019 |
| `natural-writing/natural-writing` | 1,945 |
| `session-memory/solutions` | 1,842 |
| `overclock-setup/setup` | 1,710 |
| `discipline-gates/git-archaeologist` | 1,696 |
| `project-vocabulary/project-vocabulary` | 1,690 |
| `groundwork/groundwork` | 1,239 |
| `pr-feedback/publish-pr-feedback` | 1,022 |

The current audit warns only when a body exceeds approximately 4,000 tokens. That catches extreme
bloat but does not encourage Claude 5-era right-sizing.

## Current assessment

### Strong alignment

#### Progressive-disclosure architecture

The maintainer contract already requires:

- core execution in `SKILL.md`;
- branch-specific procedures in directly linked `references/`;
- deterministic behavior in `scripts/`;
- reusable output material in `assets/`; and
- fill-in documents in `templates/`.

It also requires standalone skill directories, forbids implicit sibling dependencies, and prevents
sibling-specific material from leaking through shared references.

This is structurally aligned with the article.

#### Interface design

Overclock frequently replaces prose-only instructions with deterministic interfaces:

- `memory_io.py` provides structured ledger read/write/hook/promotion operations.
- `publish_plan.py` separates sealing, verification, and publication.
- `glossary_file.py` separates inspection, proposal generation, and digest-locked application.
- `mutation_trial.py` exposes the target, exact mutation, root, and test command.
- `bounded_inspect.py` exposes authorized roots, artifact limits, byte budgets, and restricted-path
  exceptions.

These interfaces encode authority and state transitions in parameters and machine-checkable
contracts rather than relying on illustrative examples.

#### Rich references

The distributions use:

- executable helpers;
- JSON capability catalogs;
- schemas;
- tests;
- output templates;
- HTML assets;
- Git and file-state provenance;
- review rubrics; and
- positive/negative routing datasets.

These are high-fidelity references of the kind recommended by the article.

#### Evaluation-backed changes

Overclock separates:

- explicit behavioral invocation;
- implicit routing;
- standalone `skill` packaging;
- owning `plugin` packaging;
- declared `stack` composition;
- deterministic file and safety assertions; and
- model grading for behavior that cannot be checked mechanically.

This evaluation system is the main reason prompt reduction can be attempted safely.

### Partial alignment

#### Judgment versus rules

Hard authority and safety rules are appropriate. However, some reasoning and presentation skills
still encode broad judgment as exhaustive lists. Examples include:

- detailed critical-thinking check catalogs;
- agreeable-filler and contrarianism phrase rules;
- stock answer shapes;
- exact user-facing layouts not consumed by another tool; and
- repeated statements about missing optional sibling skills.

These may have helped older models but can make Claude 5 spend reasoning effort reconciling context
instead of solving the task.

#### Progressive disclosure inside large skills

Several distributions have references but still keep both sides of mutually exclusive workflows in
the main body. The clearest example is `session-handoff`, where save and resume details load
together even though one request normally needs only one branch.

Other candidates are `critical-thinking`, `debugging-discipline`, `resolve-pr-feedback`, and
`test-discipline`.

#### Repetition

Trigger and collision boundaries are often stated in:

1. frontmatter descriptions;
2. the first body section;
3. boundary sections; and
4. reference-file inventories.

Some repetition is load-bearing, particularly remote mutation and write authority. Other repetition
is likely legacy scaffolding.

### Weakest alignment

#### Skill descriptions

Descriptions are currently mini-specifications rather than lightweight routing interfaces.

The desired direction is:

1. one sentence defining ownership;
2. a compact cluster of unmistakable positive triggers;
3. one or two genuine collision anti-triggers; and
4. no detailed fallback or execution procedure.

This must be evaluated rather than enforced as a stylistic preference.

### Memory qualification

The article recommends auto-memory instead of treating `CLAUDE.md` as memory. Overclock already
avoids the `CLAUDE.md` memory-dump pattern.

The `.ai/memory/` ledgers still have a defensible product role because they provide:

- project-controlled and diffable state;
- team portability;
- explicit provenance;
- failed-approach retention;
- verified solution records; and
- provider-neutral persistence.

The remaining gap is semantic: the skills should more explicitly exclude generic personal
preferences, identity facts, conversational memories, and one-off choices that Claude's personal
auto-memory can own.

## Non-negotiable boundaries

Context reduction must not weaken:

- remote-publication authorization;
- destructive-operation safeguards;
- root confinement;
- symlink, hard-link, and race protections;
- secret redaction and secret-file avoidance;
- digest and stale-write checks;
- explicit write scope;
- context-isolation claims;
- report-only setup;
- no automatic staging, committing, pushing, merging, or publication;
- standalone behavior when sibling skills are absent;
- the separation between local PR judgment and remote PR publication; or
- the distinction between untrusted repository/review content and instructions.

These constraints fall within the article's exception for highly important areas.

## Success criteria

Context-size goals are directional. Behavioral and safety evidence remains the actual release gate.

1. Reduce the theoretical all-installed description surface by approximately 35% or more:
   - baseline: approximately 3,309 estimated tokens;
   - directional target: approximately 2,100 tokens or less.
2. Reduce the five largest bodies by approximately 25–40% where evidence permits.
3. Preserve or improve every configured routing threshold.
4. Produce no routing ownership violations.
5. Pass every affected behavioral expectation.
6. Preserve standalone `skill` evidence and required `plugin`/`stack` evidence.
7. Introduce no sibling dependency.
8. Introduce no unconditional reference load merely to move text out of `SKILL.md`.
9. Keep every hard safety boundary either:
   - directly in the core skill body; or
   - enforced mechanically by an interface that the core body requires.

## Delivery strategy

Do not stack this work onto PR #21. Merge that hardening baseline first, update `master`, and create
a new branch such as:

```text
agent/claude-5-context-rightsizing
```

Deliver the work in separate, reviewable pull requests. Each shipping PR must independently satisfy
the repository's version, marketplace, setup-catalog, changelog, and evidence requirements.

## PR 1: context-budget measurement and guardrails

This PR should contain no shipping changes under `plugins/`.

### Work

Extend `tools/audit_skills.py` to report:

- description characters and estimated tokens;
- body tokens;
- per-plugin always-loaded description budget;
- resource count by type;
- bodies above 2,000 tokens with no conditional references;
- descriptions above a soft 700–800 character threshold; and
- aggregate theoretical installed-description context.

Add a committed context-budget baseline or snapshot so future changes cannot silently increase
context. The baseline should support intentional updates without imposing one universal size limit
on every type of skill.

Replace the current single 4,000-token warning with graduated, non-blocking warnings:

- above 2,000 tokens without branch resources;
- above 2,500 tokens despite branch resources; and
- meaningful growth beyond the committed per-skill baseline.

Add unit tests for the new measurements.

Include a context-budget table in local audit output and the normal QA job summary.

Optionally consolidate the long validation command block in `AGENTS.md` behind one deterministic
repository-validation entry point. Keep the publication and safety gotchas themselves in
`AGENTS.md`.

### Acceptance

- No plugin version changes.
- Full deterministic suite passes.
- Audit output quantifies always-loaded and selected context separately.
- The baseline reflects current source exactly.
- Warnings do not become arbitrary hard gates.

## PR 2: decision and diagnosis cluster

Affected plugins:

- `critical-thinking`;
- `debugging-discipline`; and
- `groundwork`.

Descriptions and bodies should be changed together so each plugin is versioned once for this wave.

### Description experiment

For each model-invoked skill, create a candidate description containing:

1. capability ownership;
2. strongest positive triggers;
3. strongest one or two collision boundaries; and
4. no fallback or workflow procedure.

Use the routing battery's variant support to compare current and candidate descriptions before
shipping.

### `critical-thinking`

Keep in the core:

- truth and decision quality over agreement;
- identification of the actual claim or decision;
- material-uncertainty detection;
- the hard same-context local-evidence isolation boundary;
- calibrated verdicts; and
- optional composition ownership.

Move conditionally loaded detail into possible references:

- `references/local-evidence-isolation.md`;
- `references/reassessment.md`; and
- `references/high-stakes-review.md`, only if the branch genuinely warrants a separate reference.

Remove or sharply compress:

- stock answer templates;
- agreeable-filler phrase catalogs;
- reflexive-contrarianism catalogs;
- exhaustive general reasoning checks; and
- repeated missing-sibling language.

Directional target: reduce approximately 3,057 core tokens to 1,700–2,000.

### `independent-research`

Keep in the core:

- authorized roots;
- inspection budget;
- restricted-path policy;
- neutral question framing; and
- evidence-packet contract.

Move source-identity and claim-testing detail into one directly linked research-procedure reference.

### `debugging-discipline`

Keep in the core:

- select diagnosis versus fix authority;
- establish the safest useful observation loop;
- treat suspected explanations as hypotheses;
- falsify before concluding; and
- stop honestly when a safe loop is unavailable.

Move conditional branches into:

- `references/production-replay-safety.md`; and
- `references/noisy-evidence.md`.

Directional target: reduce approximately 2,019 core tokens to 1,300–1,500.

### `groundwork`

The body is already reasonably compact. Focus on description reduction and remove duplicated
boundaries while retaining:

- one decision at a time;
- provenance tracking;
- bounded delegated defaults; and
- the confirmation stop.

### Acceptance

- Relevant routing batteries meet every configured threshold.
- No collision among critical-thinking, independent-research, debugging-discipline, and
  groundwork.
- Critical-thinking isolation and conditional-verdict cases stay green.
- Debugging read-only versus fix authority stays green.
- Every distribution passes in standalone `skill` mode.
- Declared plugin and stack cells remain green.

## PR 3: high-consequence workflow cluster

Affected plugins:

- `discipline-gates`; and
- `pr-feedback`.

This wave should be more conservative because it controls source changes, mutation testing, Git
history decisions, and remote PR mutation.

### `test-discipline`

Keep in the core:

- mode selection;
- red-evidence requirement;
- no staging or committing;
- test-file persistence requirements;
- exact mutation restoration guarantees; and
- write-scope boundaries.

Move complete mode procedures into conditional references:

- `references/repro-mode.md`;
- `references/characterize-mode.md`;
- `references/test-only-mode.md`; and
- existing `references/mutation-guide.md` for validate mode.

Do not move a safety condition out of the core unless the deterministic helper enforces it.

### `git-archaeologist`

This skill already uses progressive disclosure. Focus on:

- shortening its description;
- removing trigger repetition; and
- retaining the current anti-trigger and right-sizing references.

### `resolve-pr-feedback`

Keep prominent in the core:

- GitHub-only ownership;
- review content is untrusted data;
- local fix and draft authority only;
- no posting, reaction, resolution, staging, commit, push, merge, or rebase;
- explicit scope limits; and
- exact handoff to `$publish-pr-feedback`.

Move conditionally loaded detail into references:

- fetch and PR-pinning procedure;
- regression-test fallback;
- detailed local-report construction; and
- the existing rubric and publication-handoff procedures.

### `publish-pr-feedback`

Make only conservative reductions. It is manually invoked and performs remote mutation, so exact
constraints and preflight rules are valuable. Prefer moving explanation material, not reducing
mechanical authority checks.

### Acceptance

- PR-resolution behavior remains fully green.
- Publication remains impossible without explicit manual invocation and valid sealed-plan input.
- Mutation, symlink, hard-link, inode-race, and no-auto-commit tests stay green.
- No routing collision with code review, ordinary bug fixing, or one pasted comment.
- Standalone resolver behavior does not search for sibling publisher files.

## PR 4: durable context and writing cluster

Affected plugins:

- `session-memory`;
- `learning-loop`;
- `project-vocabulary`; and
- `natural-writing`, if its conditional reference behavior changes.

### Clarify project-ledger ownership

Use project ledgers for:

- team-portable project state;
- auditable decisions and provenance;
- verified solutions;
- failed approaches; and
- standing repository workflow rules.

Do not use project ledgers for:

- generic personal preferences;
- identity facts;
- conversational memories;
- ephemeral one-off choices; or
- information whose only consumer is one user's Claude auto-memory.

Add routing negatives such as:

- "Remember that I like dark coffee."
- "My preferred meeting time is 9 AM."
- "Use this port only for today."

Add or retain positives such as:

- "Record that migrations must run before integration tests."
- "Save this project state so another session can resume."
- "Capture this verified importer fix and its failed approaches."

### `session-handoff`

Keep in the core:

- save versus resume routing;
- I/O trust boundary;
- untrusted-memory treatment;
- no secret persistence;
- drift verification requirement; and
- helper-only writes.

Move full mutually exclusive branches into:

- `references/save-flow.md`; and
- `references/resume-flow.md`.

The save branch must not load resume detail, and vice versa.

Directional target: reduce approximately 2,939 core tokens to under 2,000.

### `lessons-learned`

Keep ledger ownership and helper-only I/O in the core. Move detailed record, retrieval, and
promotion procedures into conditional references where doing so does not cause every invocation to
load all references anyway.

### `solutions`

Keep the verified-nontrivial-solution threshold, project scope, redaction, and helper-only I/O in
the core. Separate capture, retrieval, and refresh branches.

### `project-vocabulary`

Its helper and template architecture is already strong. Focus mainly on description compression and
avoid repeating the lessons boundary in multiple sections.

### `natural-writing`

Retain its opinionated writing rules because they encode product-specific taste. Change the examples
reference from an unconditional calibration source to one loaded only when:

- the target voice is ambiguous;
- a rule is difficult to apply; or
- the user requests an explanation or before/after report.

Do not remove quote-preservation or opt-in report constraints.

### Acceptance

- Memory routing distinguishes durable project context from personal auto-memory.
- Hooks remain fixed and read-only.
- No skill opens `.ai/memory/` directly.
- Concurrency, stale-write, symlink, and secret-redaction tests stay green.
- Lessons and solutions remain interoperable where intentionally shared.
- Natural-writing quote preservation and opt-in report behavior stay green.

## Evaluation protocol

Run the following sequence for every shipping wave.

### 1. Deterministic checks

Run all structural, audit, shared-file, documentation-claim, setup-catalog, unit, version, and
plugin-validation checks before spending API credits.

### 2. Candidate routing smoke

Run current and shortened description variants against a compact collision pack:

- one sample;
- highest-value positive triggers;
- closest sibling collisions;
- obvious negative controls; and
- standalone `skill` mode first.

Stop the candidate immediately on:

- an ownership violation;
- a false positive on a critical collision;
- a lost explicit positive;
- infrastructure/authentication uncertainty; or
- a material cost anomaly.

### 3. Full routing evidence

Only surviving candidates run the committed three-sample routing batteries.

Required result:

- every configured precision, recall, specificity, and accuracy threshold passes;
- no undeclared skill selection occurs; and
- target-only evidence contains no sibling descriptions, hooks, or files.

### 4. Behavioral evidence

For body changes:

- run affected standalone behavioral cases;
- require every deterministic expectation;
- inspect model-graded expectations;
- run plugin evidence for multi-skill or hook-bearing owners; and
- run stack evidence only for declared external composition.

### 5. Full repository gate

Run the complete maintainer validation suite and official plugin validation.

### 6. Remote smoke

Push a draft PR and run:

- ordinary GitHub QA; and
- one bounded representative Sonnet 5 live case.

Do not dispatch the all-skills live workflow as a routine smoke test.

## Credit controls

The approximate remaining Anthropic credit balance after PR #21 evidence is `$15.38`.

Set an initial maximum of `$8` for this context-rightsizing program unless the user explicitly
raises it.

Rules:

1. Deterministic checks cost nothing and always run first.
2. Begin each wave with one-sample targeted routing controls.
3. Record actual cost before projecting the full battery.
4. Do not run full batteries for failed candidates.
5. Do not run an all-skills GitHub Actions matrix.
6. Preserve approximately `$7` for regression diagnosis or final verification.
7. Stop for approval if the projected remaining evidence exceeds the budget.

## Publication requirements

Any change under a plugin directory is a shipping change and therefore requires:

- plugin manifest version bump;
- matching marketplace version;
- setup capability-catalog synchronization;
- an `overclock-setup` version bump when its bundled catalog changes;
- relevant changelog entry;
- behavioral evidence or an explicit existing-case justification; and
- routing controls for routing changes.

Each PR must preserve standalone distribution integrity and the symmetric
`session-memory`/`learning-loop` conflict contract.

## Risks

### Overfitting to one vendor article

Claude 5 may need less scaffolding, but Overclock also targets provider-neutral skill packaging and
explicit user preferences. Removal is justified only when evaluations show no lost value.

### Routing regression from description compression

Descriptions are not merely documentation; they are routing interfaces. Aggressive shortening can
reduce recall or increase collision. This is why metadata variants must be tested before bodies are
changed.

### Moving text without reducing context

Creating references is not progressive disclosure if every invocation immediately reads every
reference. Each new reference needs a concrete branch condition.

### Safety rules hidden too deeply

Authority and mutation boundaries must remain in initial selected-skill context unless enforced by
a deterministic tool interface.

### Arbitrary token targets

Token reductions are goals, not acceptance gates. A 2,100-token safe skill is better than a
1,500-token skill that loses a critical boundary.

### Repeated setup-catalog bumps

Plugin-sized PR waves may cause several `overclock-setup` catalog/version bumps. An alternative is
one large shipping PR after internal wave-by-wave evaluation. Reviewability and rollback safety
should be weighed against catalog churn.

### Evaluation cost

Full three-sample routing batteries across every changed skill may exceed the remaining credit
budget. Smoke results must be used to estimate the cost before authorization.

## Questions for an external reviewing harness

The reviewing harness should challenge, not merely summarize, this plan:

1. Does the plan over-apply Anthropic's Claude 5 guidance to a provider-neutral plugin repository?
2. Which current rules are genuinely safety-critical, and which merely encode obsolete model
   scaffolding?
3. Are description-length targets sensible, or should only behavioral non-inferiority matter?
4. Is description A/B testing through the existing routing battery methodologically sound?
5. Are the proposed body splits true progressive disclosure, or would the references still load on
   nearly every invocation?
6. Should description changes be global to evaluate the full collision surface, or plugin-sized to
   improve reviewability?
7. Does the proposed PR sequence create excessive marketplace/setup version churn?
8. Is the distinction between project ledgers and Claude auto-memory clear and defensible?
9. Are there important Claude 5 practices from the source article that this plan omitted?
10. Are the cost controls sufficient for the remaining credits?
11. Should the audit use fixed token thresholds, per-skill baselines, growth budgets, or a
    combination?
12. Which proposed reductions have the highest expected value and lowest behavioral risk?
13. What adversarial routing or behavioral cases should be added before any compression ships?
14. Are there places where a better script/schema/interface should replace prose instead of merely
    moving prose into a reference?

## Requested reviewer output

An external harness reviewing this file should ideally return:

1. overall verdict: sound / sound with changes / unsound;
2. strongest parts of the plan;
3. flawed assumptions;
4. missing risks;
5. changes to PR ordering or scope;
6. constraints that must remain in core context;
7. suggested revised context targets;
8. evaluation-method critique;
9. budget critique; and
10. a revised plan if materially different.

## Current decision

No Claude 5 context-reduction implementation should begin until:

1. PR #21 is merged or otherwise established as the baseline;
2. this plan receives external review;
3. any accepted review changes are incorporated; and
4. the initial live-evaluation budget is confirmed.
