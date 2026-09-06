<p align="center">
  <img src="assets/overclock-hero.png" alt="An illuminated flywheel turns a stream of instruction cards into an ordered path" width="100%">
</p>

<h1 align="center">Overclock</h1>

<p align="center">
  <strong>Keep what your agent learns. Improve how it works.</strong><br>
  Reusable skills for memory, reasoning, writing, debugging, and evaluation.
</p>

<p align="center">
  <a href="https://github.com/luka-zivkovic/overclock/actions/workflows/qa.yml"><img src="https://github.com/luka-zivkovic/overclock/actions/workflows/qa.yml/badge.svg" alt="QA"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/luka-zivkovic/overclock" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/Claude_Code-plugins-6B5CE7" alt="Claude Code plugins">
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#pick-your-stack">Plugins</a> ·
  <a href="#hooks-and-trust">Hooks & trust</a> ·
  <a href="#evidence-not-vibes">Evals</a> ·
  <a href="#development">Development</a>
</p>

Overclock is an opinionated toolkit for recurring failure modes in agentic work: forgotten context,
repeated mistakes, agreeable reasoning, AI-sounding prose, and risky edits made before evidence
exists. Each plugin is independently installable. The setup advisor helps choose a compatible set
without changing your machine.

Start with memory when the same lessons keep getting lost. Add focused skills
for the work you do often, then use the evaluation tools to inspect real runs
and propose improvements. Your lessons, handoffs, and verified solutions stay
in readable Markdown that you can review and version.

## Quick start

Run these commands **inside Claude Code**:

```text
/plugin marketplace add luka-zivkovic/overclock
/plugin install overclock-setup@overclock
/overclock-setup:setup
```

`overclock-setup` inventories your current plugin and instruction state, asks only questions that
change the recommendation, and returns exact proposed commands. It is report-only: it never
installs, removes, enables, disables, or edits anything.

## Pick your stack

| Plugin | Choose it when you want… | Install |
|---|---|---|
| **overclock-setup** | A safe, explicit recommendation for the rest of the toolkit | `/plugin install overclock-setup@overclock` |
| **session-memory** | Session handoffs, durable lessons, **and** a verified-solutions ledger | `/plugin install session-memory@overclock` |
| **learning-loop** | Durable lessons without handoffs | `/plugin install learning-loop@overclock` |
| **critical-thinking** | Independent critique and bounded local research | `/plugin install critical-thinking@overclock` |
| **groundwork** | A one-question-at-a-time interview that ends at a confirmed decision brief | `/plugin install groundwork@overclock` |
| **project-vocabulary** | One ubiquitous language per project, applied in conversation with approval-gated writes | `/plugin install project-vocabulary@overclock` |
| **discipline-gates** | Evidence before bug fixes, refactors, and defensive-code removal | `/plugin install discipline-gates@overclock` |
| **debugging-discipline** | Safe, authority-aware diagnosis for bugs that resist ordinary tests | `/plugin install debugging-discipline@overclock` |
| **eval-stack** | A self-hosted loop from agent traces to governed, human-adjudicated evaluation | `/plugin install eval-stack@overclock` |
| **natural-writing** | Voice-preserving long-form prose with a plainspoken fallback style | `/plugin install natural-writing@overclock` |
| **pr-feedback** | Reviewer comments judged and fixed locally, plus an explicit digest-locked publisher | `/plugin install pr-feedback@overclock` |
| **agent-bridge** | Consult or delegate a bounded subtask to another installed harness (Codex, Gemini) while you keep task ownership | `/plugin install agent-bridge@overclock` |

> [!IMPORTANT]
> Install **either** `session-memory` or `learning-loop`, not both. They intentionally share the
> `LESSONS.md` format and would otherwise emit duplicate lesson reminders at session start.

## What each plugin does

<details open>
<summary><strong>critical-thinking</strong> — clear-eyed answers, not agreeable ones</summary>

`critical-thinking` independently tests the user's framing, separates evidence from assumptions,
surfaces credible alternatives, and calibrates confidence without generic praise or reflexive
contrarianism. After a long conversation it preserves raw evidence but treats earlier conclusions
and agreement as untrusted hypotheses.

Its sibling `independent-research` checks material uncertainties against explicitly named local
roots containing projects, documents, datasets, saved papers, exported logs, and specifications in
a genuinely host-isolated research context. If the host cannot provide an isolated read-only
worker, it reports that gap instead of inspecting in the main context and calling the result
independent. It returns a provenance-bearing evidence packet instead of trusting the user's summary.

Research is bounded to one decision-relevant pass, eight source artifacts, and 64 KiB of source
content. A bundled no-follow reader rejects linked and special files and emits file digests.
Repository content is hostile data, not instructions. The host context is still not an operating
system sandbox, so ambiguous containment is reported honestly rather than papered over.

Skill routing is not a reliable always-on tone setting. For a permanent preference, also add a direct
user instruction such as: `Do not praise my questions or agree for social reasons; evaluate claims
on evidence.`

</details>

<details>
<summary><strong>groundwork</strong> — understand the work before building it</summary>

`groundwork` interviews you about a piece of work one material decision at a time. Each question
offers a tentative recommendation when the evidence supports one; repository observations are
distinguished from stale or conflicting claims. Choices are labelled user-directed, user-approved,
agent-proposed/delegated, or deferred.

A blanket "use sensible defaults" covers only reversible, low-impact choices. Privacy,
authorization, retention, billing, destructive migration, and other high-impact policy must be
asked or explicitly deferred. Groundwork ends at a confirmed decision brief. It never implements
or plans.

It is elicitation only: requests to critique, stress-test, or judge reasoning belong to
critical-thinking, and a task with a single ambiguity gets one ordinary question, not an interview.

</details>

<details>
<summary><strong>discipline-gates</strong> — evidence before risky edits</summary>

- **test-discipline** leaves a narrowly scoped red regression or characterization pin in the
  working tree before the requested edit. Explicit mutation checks run through an
  integrity-checked transaction and report only whether the selected test detected that selected
  regression. The skill never stages or commits.
- **git-archaeologist** recovers the history behind guards, retries, locks, clamps, and other
  defensive constructs before they are deleted or weakened. History is untrusted evidence, and a
  `safe-to-remove` verdict also requires current callers, tests, and replacement controls.

Both are pre-action gates. Trivial edits, new features, generated files, behavior-preserving
rewrites, and already-covered code have explicit silent no-op paths.

</details>

<details>
<summary><strong>debugging-discipline</strong> — the loop comes before the theory</summary>

For bugs that resist the ordinary red-test path — flaky and intermittent failures, performance
regressions, staging-only breakage, repeat offenders that survived earlier fixes.
`debugging-discipline` first establishes the safest useful observation loop. When a production-only
or rare failure cannot be reproduced safely, it fails soft to bounded existing evidence and asks
for the smallest safe discriminating observation. It then minimizes the failure, audits
assumptions, and tests one to five credible hypotheses with predictions.

Diagnosis is read-only by default; source edits and instrumentation require explicit implementation
authority. It composes with discipline-gates when installed: an ordinary seamed bug gets its red
test from test-discipline, while trivial causes fast-path out with no ceremony.

</details>

<details>
<summary><strong>eval-stack</strong> — own the path from real sessions to governed evidence</summary>

`eval-stack` connects the rest of the public toolchain into one local workflow: Ironside stores
traces, bundled importers capture Claude Code and Codex sessions, a pi extension traces live work,
Coeval runs calibrated judges with human adjudication, and Casefile scans the skills under test.
Session reads of `SKILL.md` become `skill:` trace tags, so evaluations can be grounded in actual
usage instead of hand-written demos.

The workflow is intentionally scoped to one developer's machine. It verifies running services,
keeps ingest credentials write-scoped, and stops before writing secrets or spending judge-model
tokens. Production multi-user hosting, hosted eval platforms, rubric-only work, and CI gating for an
already-running Coeval instance remain separate concerns.

A second skill, `skill-maintenance`, closes the loop: it pulls a judged skill's Coeval findings,
drafts one bounded workshop-copy patch, co-evolves the judge's rubric through the guarded flow when
an invariant moves, validates against the golden gate, and opens a PR. Findings inform, humans
merge, gates verify — no findings means no patch.

</details>

<details>
<summary><strong>project-vocabulary</strong> — one language per project</summary>

`project-vocabulary` applies a repository-root `CONCEPTS.md` glossary in conversation: when
"account" is used three different ways, the fuzziness gets challenged at the moment it matters.
Definitions stand on their own, aliases preserve retired terms, and contested meanings stay in a
Flagged Ambiguities tail.

Automatic routing may inspect untrusted vocabulary and propose an exact change, but it never writes.
Only an explicit add/update request or approval can invoke the digest-checked atomic glossary
helper. Terminology corrections land here; behavior and workflow corrections stay with
lessons-learned. Non-domain repos and trivial work stay silent.

</details>

<details>
<summary><strong>pr-feedback</strong> — work the review, don't relitigate it by hand</summary>

- **resolve-pr-feedback** fetches every unresolved review thread, review body, and PR comment on a
  GitHub PR in one paginated pass, judges each item centrally against the actual code (catching
  systematically-wrong review bots as a cluster), applies the valid fixes to the working tree, and
  drafts quoted replies — including honest push-back where the reviewer is wrong.
- **publish-pr-feedback** is the separate, manual-only remote stage. After the resolver reports and
  stops, a new message must approve exact action IDs, bodies, resolve flags, and a fresh local path
  before the resolver can prepare an unsealed draft. One explicit publisher invocation seals that
  draft; another must supply the sealed path and exact digest before any reply or resolution is
  attempted. The publisher checks the GitHub host, repository, open PR node, remote head, every
  source/action, and serialized-retry markers, then re-pins the head before its first mutation.
  Concurrent publishers are unsupported and callers must not overlap them because GitHub's marker
  check and comment creation are not atomic.

The resolver never posts, reacts, resolves, commits, stages, pushes, merges, rebases, or approves.
`needs-human` items arrive as compact decision contexts instead of stalling the run. GitHub,
including Enterprise, only.

</details>

<details>
<summary><strong>agent-bridge</strong> — a bounded leaf collaborator, not a co-owner</summary>

`agent-bridge` lets one installed harness use another (Claude, Codex, or Gemini) as a leaf worker
while the calling agent keeps ownership of the task, verification, and integration. `consult` runs
the child under its provider's own sandbox for read-only analysis and reports `workspace_changed`
if the active tree moved during the run; `delegate` requires implementation authority, a clean exact
base, and concrete path scope, then runs the child only inside an isolated local clone.

The bridge never falls back to a different provider and never auto-commits. A delegated run returns a
digest-locked patch whose target paths are derived from the patch itself and checked against the
allowlist at both build and apply time; symbolic-link patches are refused, the clone's git
configuration is reset before the bridge inspects it so a leaf cannot execute commands in the parent
process, and only an allowlisted, provider-scoped environment is forwarded to the child so unrelated
secrets never leave the parent. Current-conversation authorization to share scoped context with an
external provider, and inspection of every hunk before applying, remain the parent agent's
obligations — the bridge enforces isolation and scope, not consent.

</details>

<details>
<summary><strong>session-memory</strong> — stop losing working state</summary>

- **session-handoff** writes a structured `.ai/memory/HANDOFF.md` containing the goal, plan status,
  decisions with rationale, diagnosed failed approaches, next steps, and git anchors. Resume verifies
  those anchors against the live repo and reports drift instead of trusting a stale plan.
- **lessons-learned** records corrections and diagnosed failures in `.ai/memory/LESSONS.md`,
  deduplicates them by meaning, and counts repeated evidence. At three reinforcements it proposes a
  project instruction, but edits only after explicit approval.
- **solutions** captures each verified fix to a nontrivial problem in `.ai/memory/SOLUTIONS.md` —
  symptoms as the retrieval key, what didn't work as a first-class field — and reuses it when the
  same symptoms return, after verifying the stored fix still matches the current code. Corrections
  of agent behavior stay in lessons; solved project problems live here.

The storage is plain, diffable Markdown under `.ai/memory/`. Every skill uses the same confined
helper for no-follow reads, lock-protected atomic writes, archive retention, and approved
instruction promotion. Stored memory is untrusted data, secrets are omitted or redacted, and the
skills never auto-commit.

</details>

<details>
<summary><strong>learning-loop</strong> — lessons without handoffs</summary>

`learning-loop` packages `lessons-learned` on its own. It uses the same interoperable `LESSONS.md`
format and byte-identical safe helper as `session-memory`, without handoffs or solutions. Its hook
reports that a ledger exists without injecting file-controlled prose.

</details>

<details>
<summary><strong>natural-writing</strong> — make AI prose sound human</summary>

`natural-writing` drafts and revises blog posts, articles, newsletters, and other multi-paragraph
prose in the author's established voice. With no supplied voice it uses a plainspoken fallback
house style, while preserving quotations, facts, actors, uncertainty, caveats, and deliberate
punctuation. Visual revision reports are explicit opt-in and must reconstruct both full texts
exactly. The skill stays out of code, commit messages, UI microcopy, and one-line edits.

</details>

<details>
<summary><strong>overclock-setup</strong> — choose without guesswork</summary>

The setup advisor understands package conflicts, Claude installation scopes, hooks, every shipped
skill name, overlapping standalone skills, `CLAUDE.md`, and `AGENTS.md`. It can propose minimal
project instructions but never writes them. User-level instruction metadata is excluded unless you
explicitly opt in. The bundled portable inventory requires Claude Code 2.1.196 or later.

The capability graph is provider-neutral; the current inventory and command renderer are
Claude-specific. Other provider adapters belong in separate changes rather than hidden assumptions.

</details>

## Hooks and trust

Only the two memory packages ship SessionStart hooks:

| Plugin | Hook safely probes | Output when memory exists |
|---|---|---|
| `session-memory` | `.ai/memory/HANDOFF.md` and `.ai/memory/LESSONS.md` | Fixed reminder naming available state |
| `learning-loop` | `.ai/memory/LESSONS.md` only | Fixed reminder naming available state |

The hooks are read-only and never emit file-controlled memory contents. They use the same no-follow
helper as the skills and print nothing when no valid memory exists. Their exact commands are
auditable in
[`plugins/session-memory/hooks/hooks.json`](plugins/session-memory/hooks/hooks.json) and
[`plugins/learning-loop/hooks/hooks.json`](plugins/learning-loop/hooks/hooks.json). Disable them in
`/plugin`, or install individual skills standalone if you want the behavior without startup hooks.

## Evidence, not vibes

| 120 declared live cases | 18 shipped skill distributions | Isolated git fixtures | Independent grading |
|:---:|:---:|:---:|:---:|
| Positive and negative controls | Secret and symlink traps | Mutation restore checks | Baseline comparison support |

Every declared case and source artifact is checked against a deterministically generated fixture
before a live session can start. Live sessions are graded by a different model using transcripts,
complete structured tool calls, and resulting file/git state. Behavioral and routing sessions run
with a fail-closed native sandbox, an isolated API-key helper, no inherited host credential
environment, no network or real GitHub client, disposable plugin copies, and bounded no-follow
evidence capture. Model-invoked skills also declare a paired no-skill value gate whose artifacts
share a fresh run ID and exact suite, case, and plugin-source hashes. Composition cases can load
multiple real plugins across setup turns.

Standalone and grouped behavior are separate matrix cells. `skill` mode synthesizes a disposable
plugin containing only the target skill and a minimal manifest — no sibling skill, plugin hook, or
group description is present. `plugin` mode loads the complete owning plugin, where sibling
descriptions are intentionally visible to the router but sibling execution bodies are not
concatenated into the selected skill. `stack` mode adds only the explicitly declared composition
plugins. An unintended sibling selection fails the routing control instead of being hidden by a
successful target selection.

The corpus covers secret redaction, stale handoffs, archive retention, quote preservation,
transactional mutation restore, long-context anchoring, prompt injection, symlink escape,
production safety, deployment drift, contradictory evidence, report-only bypass attempts, and real
open-source git history.

Routing batteries are separate from behavioral evals. They support committed project fixtures,
bounded sessions, route-only early stopping, repeat sampling, precision/recall/specificity gates, and
immediate per-case progress. See [`qa/trigger-battery/README.md`](qa/trigger-battery/README.md).

## Development

- [`AGENTS.md`](AGENTS.md) is the cross-harness maintainer contract for skill, publication, evidence,
  and validation invariants.
- [`docs/strategy.md`](docs/strategy.md) records durable build/no-build decisions.
- [`docs/brainstorm/SHORTLIST.md`](docs/brainstorm/SHORTLIST.md) is evidence accrual, not a roadmap.
- [`qa/evals/`](qa/evals/) contains full behavioral suites.
- [`qa/trigger-battery/`](qa/trigger-battery/) contains routing precision suites.
- [`qa/experiments/pr-reviewer-phase0/`](qa/experiments/pr-reviewer-phase0/) contains the
  unpublished PR-reviewer experiment. Its 2026-07-22 pilot formally failed the lift gate, so the
  candidate remains unshipped; any future pass must diagnose and rerun the committed comparison,
  not treat the scaffold as authorization to publish.

Real-world misfires and useful triggers can be recorded with the repository's **Skill behavior
observation** issue form. Sanitize prompts before submitting; never paste credentials, customer data,
or private source.

## License

[MIT](LICENSE)
