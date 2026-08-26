---
name: local-eval-stack
description: "Stand up a local, self-hosted evaluation stack for agent skills and sessions: ironside (trace store) via docker compose, coeval (governed LLM judging with human adjudication) via docker + dev servers, headless bootstrap of judge projects with calibrated rubrics, a pi session tracer that tags skill usage, and casefile scanning of the skills being judged. Use when someone wants to self-host agent evals locally, trace pi/agent sessions to their own machine, judge a skill's real runs with a governed rubric, or asks to set up ironside/coeval/the eval stack. Do NOT use for writing eval content or rubric doctrine (see the evidence-tiers doc in overclock), for CI gating of an existing coeval instance (coeval's gate.mjs docs cover that), for hosted/SaaS eval platforms, or for production multi-user deployments — this skill's scope is one developer's machine."
---

# Local eval stack

Stand up the full loop on one machine: **work → traces (ironside) → judged
runs (coeval) → human adjudication → golden sets**, with the skills under
judgment scanned by casefile. Everything runs locally; the only external
call is the judge model API (or an explicit mock).

Read the reference for each phase before executing it — they contain the
exact commands, the failure modes, and the order-sensitive steps.

## Phases (in order; each is independently useful)

1. **ironside** — trace store. Docker compose stack; **owner-setup before
   seed** (order matters); write-scoped machine credential for ingest,
   owner session for reads. → `references/ironside-setup.md`
2. **Capture** — pi sessions → ironside. Install the bundled tracer
   extension (`scripts/ironside-tracer.ts`); it maps sessions→traces,
   turns→spans, LLM calls→generations, tools→spans, tags traces with
   `skill:<name>` on any SKILL.md read, redacts secret-shaped strings, and
   fails open. → `references/pi-tracer.md`. Claude Code and Codex sessions
   import post-hoc from their on-disk logs with the same mapping
   (`scripts/import-claude-session.mjs`, `scripts/import-codex-session.mjs`)
   → `references/importing-claude-codex.md`
3. **coeval** — judging. Postgres in docker, api+web dev servers, headless
   bootstrap of one bench project per judged skill.
   → `references/coeval-setup.md`
4. **Judges** — one rubric per skill, probes not vibes, then a
   calibration batch (pass exemplar / fail exemplar / anti-trigger probe)
   before trusting anything. → `references/judge-authoring.md`
5. **casefile** — `npm i -g casefile`, scan the skills repo, keep the
   suppression policy operator-owned (`--config`), wire a post-merge hook
   if the skills are live-loaded into an agent.

## Non-negotiable gotchas (learned the hard way)

- Coeval judging **costs real tokens per verdict**. Pin a mid-tier judge
  model; never connect an auto-judging tracer integration to a project
  whose volume you haven't estimated.
- A judge with no golden set produces **opinions, not evidence**. The
  calibration batch is judge QA, not skill QA; real captured runs build
  the golden set.
- Verify claims against the running services, not docs or memory — every
  version bump moved something here (ports, auth, seed order).
- All credentials in this flow are local-only. The moment any service
  leaves localhost, rotate keys and revisit every step marked SECURITY in
  the references.

## Definition of done

A test trace visible in ironside's UI carrying a `skill:` tag; a
calibration batch judged in coeval at full agreement with the anti-trigger
verdict adjudicated by the human; casefile scanning the skills repo green.
