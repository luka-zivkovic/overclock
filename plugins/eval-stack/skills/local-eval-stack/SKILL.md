---
name: local-eval-stack
description: "Stand up a local, self-hosted evaluation stack for agent skills and sessions: ironside (trace store) via docker compose, coeval (governed LLM judging with human adjudication) via docker + dev servers, headless bootstrap of judge projects with calibrated rubrics, a pi session tracer that tags skill usage, and casefile scanning of the skills being judged. Use when someone wants to self-host agent evals locally, trace pi/agent sessions to their own machine, judge a skill's real runs with a governed rubric, or asks to set up ironside/coeval/the eval stack. Do NOT use for writing eval content or rubric doctrine (see the evidence-tiers doc in overclock), for CI gating of an existing coeval instance (coeval's gate.mjs docs cover that), for hosted/SaaS eval platforms, or for production multi-user deployments — this skill's scope is one developer's machine."
---

# Local eval stack

Set up the parts of the local evaluation loop the user needs: recorded work
in Ironside, focused checks and human review in Coeval, and Casefile inspection
when skills are under evaluation. Services are local, but model-based judging
can send example content to an external provider; an explicit mock is only a
wiring check. Installation may also need network access.

## Choose a starting point before setup

Use choices already supplied in the conversation or a website-generated
prompt. A concrete import or inspection request can establish the goal without
another question. Do not repeat answered questions or turn a bounded phase
request into a full-stack installation.

For an open-ended setup request, ask what the user wants to understand before
installing services or reading session data. Offer concrete starting points:

- **Understand a failed task:** inspect a selected trace; a judge is optional.
- **Check task completion:** suggest an observable check, such as whether a
  success claim has supporting verification, then let the user edit it.
- **See whether a skill helps:** identify the skill and behavior to compare on
  the same tasks with and without it; record actual skill use.
- **Compare versions:** identify baseline and candidate, use the same examples
  and criterion, and keep improvements and regressions separate.
- Accept the user's own question without forcing one of these categories.

Establish only the missing details: the question or inspection goal, coding
agent (Claude Code, Codex, pi, or a supported custom source), selected examples,
and the requested phase. Suggest a small synthetic sample when no data is
chosen. Ask one decision at a time; read-only prerequisite checks can proceed
while a goal is unresolved, but do not inspect session contents yet.

Summarize the chosen scope and success check before mutations. Inspection-only
work can stop at a useful Ironside trace without Coeval, judging, or a Casefile
scan. If the user explicitly requested all components, preserve that choice.

## Keep capture and evaluation scoped

- Production traces can contain customer data, private code, and credentials.
  Before reading or importing real examples, establish the authorized data
  scope, destination, access, and retention. Prefer synthetic/non-sensitive
  examples for an initial trial; redaction and truncation are not clearance to
  use data and cannot guarantee that sensitive content has been removed.
- Preview a selected Claude Code or Codex log with the bundled importer's
  `--dry-run` before ingest. Do not expand a selected file into `--latest`, a
  directory sweep, a hook, or a scheduled import. A dry run can display
  sensitive content too; keep its output inside the authorized scope.
- pi live capture, import scheduling, and auto-judging are separate opt-ins.
  Installing the stack or selecting an example does not enable them. Preserve
  existing choices without requesting the same authorization again.
- Before external model calls, make the proposed examples, provider/model,
  volume or spending limit, and data destination clear and obtain authorization.
  Do not print credentials, put them in command arguments, or commit them;
  pause before credential writes unless that exact action is already authorized.

Read the reference for each phase before executing it — they contain the
exact commands, the failure modes, and the order-sensitive steps.

## Phases (keep this order for the components in scope)

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
4. **Judges** — for an evaluation goal, agree on one observable criterion and
   start with a small development batch before independent human validation.
   For skill judging, use the skill's contract and relevant positive, failure,
   and anti-trigger cases. → `references/judge-authoring.md`
5. **casefile** — `npm i -g casefile`, scan the skills repo, keep the
   suppression policy operator-owned (`--config`); propose a post-merge hook
   separately if the user wants it for live-loaded skills.

## Non-negotiable gotchas (learned the hard way)

- Coeval judging **costs real tokens per verdict**. Pin a mid-tier judge
  model; never connect an auto-judging tracer integration to a project
  whose volume you haven't estimated.
- Keep development feedback separate from independent human validation.
  Agreement on a few crafted cases is a wiring/development result, not proof
  of evaluator accuracy, skill benefit, or release readiness. Do not silently
  turn insufficient evidence into a pass; leave unsupported cases unresolved
  when the current verdict format cannot represent them.
- Verify claims against the running services, not docs or memory — every
  version bump moved something here (ports, auth, seed order).
- All credentials in this flow are local-only. The moment any service
  leaves localhost, rotate keys and revisit every step marked SECURITY in
  the references.

## Definition of done

Report against the selected goal and requested phase. For capture/inspection,
verify the selected trace in Ironside and explain coverage gaps; require a
`skill:` tag only when the source records that skill use. For evaluation,
show the criterion, example scope, versions being compared when relevant,
human-review status, and unresolved disagreements. Include Casefile findings
when skill inspection was requested; a clean scan does not prove behavioral
quality. Verify running services before claiming setup is complete and name
anything still awaiting data, authorization, or validation.
