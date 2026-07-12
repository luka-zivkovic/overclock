<p align="center">
  <img src="assets/overclock-hero.jpg" alt="A precision mechanism routing accelerated energy through four controlled gates" width="100%">
</p>

<h1 align="center">Overclock</h1>

<p align="center">
  <strong>Claude Code plugins that run your model past spec.</strong><br>
  Memory, critical reasoning, writing, and engineering discipline with explicit boundaries.
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

## Quick start

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
| **session-memory** | Session handoffs **and** durable lessons | `/plugin install session-memory@overclock` |
| **learning-loop** | Durable lessons without handoffs | `/plugin install learning-loop@overclock` |
| **critical-thinking** | Independent critique and bounded local research | `/plugin install critical-thinking@overclock` |
| **discipline-gates** | Evidence before bug fixes, refactors, and defensive-code removal | `/plugin install discipline-gates@overclock` |
| **natural-writing** | Human-sounding long-form prose without canned AI tells | `/plugin install natural-writing@overclock` |

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

Its sibling `independent-research` checks material uncertainties against authorized local projects,
documents, datasets, saved papers, exported logs, and checked-in specifications in a fresh Explore
context. It returns a provenance-bearing evidence packet instead of trusting the user's summary.

Research is bounded to decision-relevant questions and eight source artifacts per pass. Repository
content is treated as hostile data, not instructions. Read-only behavior and path scope are workflow
contracts rather than a technical sandbox, so ambiguous containment is reported honestly.

Skill routing is not a reliable always-on tone setting. For a permanent preference, also add a direct
user instruction such as: `Do not praise my questions or agree for social reasons; evaluate claims
on evidence.`

</details>

<details>
<summary><strong>discipline-gates</strong> — evidence before risky edits</summary>

- **test-discipline** reproduces a reported bug with a red test before fixing it, characterizes
  untested behavior before refactoring, and mutation-checks newly green tests so vacuous tests cannot
  pass unnoticed.
- **git-archaeologist** recovers the history behind guards, retries, locks, clamps, and other
  defensive constructs before they are deleted or weakened.

Both are pre-action gates. Trivial edits, new features, generated files, behavior-preserving
rewrites, and already-covered code have explicit silent no-op paths.

</details>

<details>
<summary><strong>session-memory</strong> — stop losing working state</summary>

- **session-handoff** writes a structured `.ai/memory/HANDOFF.md` containing the goal, plan status,
  decisions with rationale, diagnosed failed approaches, next steps, and git anchors. Resume verifies
  those anchors against the live repo and reports drift instead of trusting a stale plan.
- **lessons-learned** records corrections and diagnosed failures in `.ai/memory/LESSONS.md`,
  deduplicates them by meaning, and counts repeated evidence. At three reinforcements it proposes a
  project instruction, but edits only after explicit approval.

The storage is plain, diffable Markdown under `.ai/memory/`. It is deliberately provider-neutral:
other agents can read and write the same contract. Secrets are omitted or redacted, and the skills
never auto-commit.

</details>

<details>
<summary><strong>learning-loop</strong> — lessons without handoffs</summary>

`learning-loop` packages `lessons-learned` on its own. It uses the same interoperable `LESSONS.md`
format, semantic deduplication, evidence counts, secret handling, and approval-only instruction
promotion as `session-memory`, without `session-handoff` or its broader startup reminder.

</details>

<details>
<summary><strong>natural-writing</strong> — make AI prose sound human</summary>

`natural-writing` drafts and revises blog posts, articles, newsletters, and other multi-paragraph
prose. It removes canned framing, decorative emphasis, tell vocabulary, and uniform sentence rhythm
while preserving quotations verbatim and retaining real caveats. It stays out of code, commit
messages, documentation strings, UI microcopy, and one-line edits.

</details>

<details>
<summary><strong>overclock-setup</strong> — choose without guesswork</summary>

The setup advisor understands package conflicts, Claude installation scopes, hooks, overlapping
standalone skills, `CLAUDE.md`, and `AGENTS.md`. It can propose minimal project instructions but never
writes them. The bundled portable inventory requires Claude Code 2.1.196 or later.

The capability graph is provider-neutral; the current inventory and command renderer are
Claude-specific. Other provider adapters belong in separate changes rather than hidden assumptions.

</details>

## Hooks and trust

Only the two memory packages ship SessionStart hooks:

| Plugin | Hook reads | When no memory exists |
|---|---|---|
| `session-memory` | `.ai/memory/HANDOFF.md` and `.ai/memory/LESSONS.md` | Prints nothing |
| `learning-loop` | `.ai/memory/LESSONS.md` only | Prints nothing |

The hooks are read-only and inject a short reminder when memory exists. Their exact shell commands
are small and auditable in
[`plugins/session-memory/hooks/hooks.json`](plugins/session-memory/hooks/hooks.json) and
[`plugins/learning-loop/hooks/hooks.json`](plugins/learning-loop/hooks/hooks.json). Disable them in
`/plugin`, or install individual skills standalone if you want the behavior without startup hooks.

## Evidence, not vibes

| 66 live cases | 9 audited skill distributions | Isolated git fixtures | Independent grading |
|:---:|:---:|:---:|:---:|
| Positive and negative controls | Secret and symlink traps | Mutation restore checks | Baseline comparison support |

Live sessions run in isolated fixtures and are graded by a different model using transcripts, tool
calls, and resulting file/git state. The corpus covers secret redaction, stale handoffs, archive
retention, byte-identical quote preservation, mutation restoration, long-context anchoring, prompt
injection, symlink escape, destructive tests, deployment drift, contradictory project evidence,
duplicate hooks, report-only bypass attempts, and real open-source git history.

Routing batteries are separate from behavioral evals. They support committed project fixtures,
bounded sessions, route-only early stopping, repeat sampling, precision/recall/specificity gates, and
immediate per-case progress. See [`qa/trigger-battery/README.md`](qa/trigger-battery/README.md).

## Development

- [`docs/strategy.md`](docs/strategy.md) records durable build/no-build decisions.
- [`docs/brainstorm/SHORTLIST.md`](docs/brainstorm/SHORTLIST.md) is evidence accrual, not a roadmap.
- [`qa/evals/`](qa/evals/) contains full behavioral suites.
- [`qa/trigger-battery/`](qa/trigger-battery/) contains routing precision suites.
- [`qa/experiments/pr-reviewer-phase0/`](qa/experiments/pr-reviewer-phase0/) contains the next
  falsifiable product experiment. It does **not** authorize building a PR-reviewer skill unless the
  candidate beats baseline.

Real-world misfires and useful triggers can be recorded with the repository's **Skill behavior
observation** issue form. Sanitize prompts before submitting; never paste credentials, customer data,
or private source.

## License

[MIT](LICENSE)
