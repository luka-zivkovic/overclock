# Overclock

**Claude Code plugins that run your model past spec.**

```
/plugin marketplace add luka-zivkovic/overclock
/plugin install overclock-setup@overclock
/overclock-setup:setup
```

## Plugins

### overclock-setup — choose the right Overclock setup

```
/plugin install overclock-setup@overclock
/overclock-setup:setup
```

`overclock-setup` is a manual, report-only advisor for people arriving at the marketplace. It
inventories installed Overclock plugins across Claude scopes, detects overlapping standalone
skills and instruction-file conditions, asks what capabilities and hook behavior you actually
want, and returns an ordered set of exact commands. It never installs, enables, disables, or
removes anything itself. Its portable bundled inventory requires Claude Code 2.1.196 or later.

The advisor enforces package conflicts instead of treating every plugin as freely composable. In
particular, it recommends exactly one of `session-memory` (handoff plus lessons) or `learning-loop`
(lessons only). It can propose minimal project-local CLAUDE.md diffs and detect an existing
`AGENTS.md`, but it never edits either file. Its capability graph is provider-neutral; the current
inventory and command renderer are intentionally Claude-specific, with other provider adapters
left for a separate change.

### session-memory — stop losing your working state

```
/plugin install session-memory@overclock
```

Claude Code sessions are stateless. Close one (or hit compaction) and the next session starts cold: it re-derives decisions, re-tries approaches that already failed, and keeps building on plans that are no longer true. Corrections you've given evaporate, and you give them again.

`session-memory` fixes both, with two cooperating skills over one shared storage contract:

- **session-handoff** — say *"save our state"* and it writes a structured handoff (goal, plan status, decisions **with rationale**, failed approaches **with diagnosed cause**, next steps, git anchors) to `.ai/memory/HANDOFF.md`. Say *"resume where we left off"* and it verifies those anchors against the live repo, quantifies any drift instead of trusting a stale plan, handles rewritten history and weeks-old handoffs gracefully, and gives you a ≤15-line warm-start brief — then confirms direction before acting. No saved state? It says "cold start" plainly. It never fabricates.
- **lessons-learned** — corrections (*"no, use pnpm, not npm"*) and diagnosed failures become evidence-counted entries in `.ai/memory/LESSONS.md`. Repeated corrections deduplicate by meaning — the count goes up, no duplicates pile up. At 3+ reinforcements it *proposes* a CLAUDE.md line and only edits with your explicit yes. Requirement changes and one-off choices are never recorded; secret values are always omitted or redacted.

Everything lives in plain, diffable markdown under your project's `.ai/memory/` — a deliberately **tool-agnostic** location. The skills run in Claude Code, but the memory belongs to your project, not to a vendor: teammates on Cursor, Codex, or anything else can read the same handoffs and lessons, and write their own in the documented format. Commit `.ai/memory/` to share warm state with your team, or gitignore it to keep it local — the skills never auto-commit, never write outside `.ai/memory/`, and never persist secrets (hard rules, tested).

### learning-loop — a self-improvement loop

```
/plugin install learning-loop@overclock
```

Want the lessons without the handoff machinery? `learning-loop` is the `lessons-learned` skill on its own. Same loop — corrections (*"no, use pnpm, not npm"*) and diagnosed failures become evidence-counted entries in `.ai/memory/LESSONS.md`, deduplicate by meaning, propose a CLAUDE.md line at 3+ reinforcements (only with your yes), and never persist secrets — but with a memory contract and SessionStart hook scoped to `LESSONS.md` alone, no `session-handoff` anywhere. Drop it into your own workflow as an automatic self-improvement loop, or run it standalone.

The `LESSONS.md` format is a strict subset of `session-memory`'s, so the two are interoperable on one ledger. **Pick one, though:** install `session-memory` if you want handoff **and** lessons, or `learning-loop` if you want **only** the learning loop. Installing both double-counts the lesson reminder at session start (both ship a hook that reads `LESSONS.md`).

### natural-writing — make AI prose sound human

```
/plugin install natural-writing@overclock
```

`natural-writing` drafts and edits blog posts, articles, newsletters, and other multi-paragraph prose. It removes common AI tells such as em-dashes, canned framing, decorative bold, tell vocabulary, and uniform sentence rhythm while preserving quoted text verbatim and keeping real caveats. It stays out of code, commit messages, documentation strings, UI microcopy, and one-line edits.

### critical-thinking — clear-eyed answers, not agreeable ones

```
/plugin install critical-thinking@overclock
```

The plugin contains two cooperating skills:

- **critical-thinking** independently tests your framing before it answers. It separates evidence from assumptions, points out causal leaps and credible alternatives, calibrates uncertainty, and gives the conclusion directly without generic praise. When invoked after a long discussion, it preserves raw evidence but treats prior user/assistant conclusions as untrusted hypotheses, so repetition and sunk cost do not masquerade as corroboration.
- **independent-research** verifies material uncertainties from authorized local projects, documents, datasets, saved papers, exported logs, and checked-in specifications instead of relying on the user's summary. It runs through Claude Code's built-in Explore agent, which starts fresh without conversation history or project/user instruction memory and uses read-only inspection. It returns a provenance-bearing evidence packet to critical-thinking while leaving subjective preferences to the user.

Critical-thinking calls research only when resolving the uncertainty could change its verdict. It passes a neutral brief without the preferred conclusion, and each local research pass is capped at eight source artifacts. Repository content is treated as hostile data, never instructions. Explore may still expose read-only shell inspection; the skill forbids writes, repository code/test execution, web use, and nested research as workflow rules, not as an enforced tool sandbox. Local path scope is behavioral too: available inspection tools can address other readable paths, so the skill refuses ambiguous containment and reports that limitation instead of claiming technical enforcement. Current web claims use the host's normal research tools in the main context and are labeled accordingly. It is not a devil's-advocate gimmick or an excuse for endless research: when the evidence is already strong, it says so; when research would not affect the answer, it skips it.

Skill routing is not a reliable always-on tone setting. If you never want congratulatory filler, also put a direct rule such as `Do not praise my questions or agree for social reasons; evaluate claims on evidence` in your user-level `~/.claude/CLAUDE.md`. Use the plugin for the heavier audit and research workflow.

### discipline-gates — evidence before risky edits

```
/plugin install discipline-gates@overclock
```

`discipline-gates` contains two skills:

- **test-discipline** — reproduce a reported bug with a red test before fixing it, characterize untested behavior before refactoring it, and mutation-check freshly green tests so vacuous tests cannot pass unnoticed.
- **git-archaeologist** — recover the history behind guards, retries, locks, clamps, and other defensive code before deleting or weakening them.

Both are pre-action gates with explicit silent no-op boundaries for trivial changes, new features, generated files, and already-covered code.

## These plugins ship a hook (read this)

`session-memory` bundles a **SessionStart hook** that activates when you install the plugin. At session start it runs one shell command that:

- checks for `.ai/memory/HANDOFF.md` and `.ai/memory/LESSONS.md` at the repo root (read-only — it never writes anything);
- if found, injects a short note so the session offers to resume your parked work and consults recorded lessons;
- prints nothing — a complete no-op — in projects that have no `.ai/memory/`.

That hook is what makes resume automatic instead of something you must remember to ask for. The exact command is in [`plugins/session-memory/hooks/hooks.json`](plugins/session-memory/hooks/hooks.json) — it's a dozen lines of `sh`, auditable in ten seconds. Don't want it? Disable the plugin's hooks in `/plugin`, or install the two skills standalone (copy `plugins/session-memory/skills/*` into `~/.claude/skills/`) and skip the hook entirely.

`learning-loop` bundles the same idea, scoped down: its [`plugins/learning-loop/hooks/hooks.json`](plugins/learning-loop/hooks/hooks.json) checks only `.ai/memory/LESSONS.md`, injects the lesson count when present, and is a complete no-op otherwise. Disable or install-standalone the same way. (As above: don't run both plugins — the lesson reminder would print twice.)

## Evidence, not vibes

The repository carries 66 unique live eval cases, with the lessons suite run against both plugin distributions. Sessions run in isolated git fixtures and are graded independently by a different model using the transcript, tool calls, and resulting file/git state. The suites include should-NOT-trigger controls and pinned safety traps such as secret redaction, stale handoffs, archive retention, byte-identical quote preservation, mutation restoration, long-context anchoring, prompt injection, symlink escape, destructive tests, deployment drift, contradictory project evidence, duplicate plugin hooks, report-only bypass attempts, and real open-source git history. Live runs can optionally execute a no-skill baseline and record per-case cost, latency, turns, and token usage.

## License

MIT
