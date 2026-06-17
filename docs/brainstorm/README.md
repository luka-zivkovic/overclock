# Brainstorm log

Machine-generated output of the **`skill-brainstorm` workflow** — an automated loop that
proposes the next skill Overclock should build, grounded in the rules in
[`../strategy.md`](../strategy.md).

This directory is *evidence accrual*, not decisions. Human-blessed verdicts still live in
`docs/strategy.md`. The loop deliberately reads both this folder and `strategy.md` so it
**never re-litigates a candidate that already carries a verdict**.

## What each run does

The engine lives at [`../../.claude/workflows/skill-brainstorm.js`](../../.claude/workflows/skill-brainstorm.js)
and runs six phases as a multi-agent fan-out:

1. **Generate** — 5 idea generators, each through a distinct lens: memory-axis,
   right-sizing-axis, everyday dev friction, working-with-AI friction, and an
   adversarial anti-bloat lens.
2. **Dedup** — merge semantic duplicates; drop anything already judged.
3. **Ground** — the baseline-gap test per candidate (vs built-ins, official plugins, cloud
   features; web search allowed). Duplicative candidates are killed here.
4. **Simulate** — 2 concrete artificial scenarios per survivor: skill-in-use vs baseline,
   scored by delta.
5. **Score** — a 3-vote adversarial skeptic panel against the full creation bar.
   `>=2 yes` -> STRONG, `1 yes` -> PARKED, else KILL.
6. **Synthesize** — write `run-<timestamp>.md` and update `SHORTLIST.md`.

## Files

- `run-<timestamp>.md` — full evidence record of a single run.
- `SHORTLIST.md` — rolling table of every candidate ever judged, STRONG at the top.

## Running it

One pass (manual):

```
/skill-brainstorm
```

or, from the orchestrator, `Workflow({ scriptPath: ".claude/workflows/skill-brainstorm.js" })`.

Recurring loop (self-paced or interval):

```
/loop /skill-brainstorm
```

A KILL-heavy run is a **success**: the saturated plan/build/review space means "build
nothing new" is the correct answer most of the time. Promote a candidate to
`docs/strategy.md` only after a human reviews its run log.
