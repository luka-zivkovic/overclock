export const meta = {
  name: 'skill-brainstorm',
  description: 'Brainstorm the next skill to build for Overclock: generate candidates from diverse lenses, ground each against existing tools, simulate scenarios, adversarially score, and append verdicts to docs/brainstorm/.',
  whenToUse: 'Run (manually or via /loop) to accrue well-grounded skill candidates without re-litigating settled questions. Reads docs/strategy.md + docs/brainstorm/SHORTLIST.md so it never re-proposes judged ideas.',
  phases: [
    { title: 'Generate', detail: '5 idea-generator agents, distinct lenses' },
    { title: 'Dedup', detail: 'merge + drop already-judged candidates' },
    { title: 'Ground', detail: 'baseline-gap test per candidate' },
    { title: 'Simulate', detail: 'artificial scenario: skill-in-use vs baseline' },
    { title: 'Score', detail: '3-vote adversarial creation-bar panel' },
    { title: 'Synthesize', detail: 'write run log + update shortlist' },
  ],
}

// ---- Shared context every agent must read first ----
const REPO = '.'
const CONTEXT = `
You are working inside the Overclock repo at ${REPO} — a SERIOUS, well-tested
collection of Claude Code plugins/skills (it has CI, eval harnesses, a strategy doc).

BEFORE doing anything, read these to ground yourself (use Read/Bash/Glob):
- ${REPO}/docs/strategy.md        — operating principles + the candidate ledger (verdicts already reached)
- ${REPO}/README.md               — what already ships
- ${REPO}/docs/brainstorm/SHORTLIST.md  — prior brainstorm verdicts (may not exist yet; that's fine)
- list ${REPO}/plugins/**/skills/ — the skills that already exist

THE BAR IS USEFULNESS (clarified by the user 2026-06-22 — this overrides any older
"moat = memory + right-sizing" framing you may infer from strategy.md):
1. USEFUL FIRST. The one thing every candidate must be: genuinely useful for EVERYDAY
   development or working-with-AI — something a developer would actually reach for, often.
   A skill does NOT have to be stateful, adaptive, or exploit any "moat" to qualify. A
   plain, stateless, well-designed skill that saves real time every day is a GOOD skill.
2. NON-REDUNDANT — SCOPED TO THE KIT. Grounding against built-ins (/simplify, code-simplifier,
   /code-review, /verify), official plugins (feature-dev, pr-review-toolkit), cloud features
   (Ultraplan), and the wider ecosystem is RESEARCH — it informs the design, it does not kill the
   idea. The only redundancy that kills is true duplication of a skill ALREADY IN ${REPO}/plugins
   (would they collide on the same trigger?). Overlap with the ecosystem or with the base model's
   latent ability is NOT redundancy: reliable triggering of a wanted behavior is real value EVEN IF
   the base model could do it when asked, or a published skill already does it. The question is
   "would I reach for this?" — never "does it have a moat?" or "does this exist somewhere?".
3. WELL-DESIGNED (quality, not a gate). Serious repo: a candidate should be right-sized
   (not annoying ceremony on trivial tasks), have sensible anti-triggers, and be shippable
   with should-NOT-trigger evals. Treat this as design quality to assess, not a moat to pass.
4. MOAT IS A BONUS, NOT A REQUIREMENT. Memory (persistence-across-sessions) and right-sizing
   (scaling-rigor-to-blast-radius) are PROVEN especially-defensible axes — when a candidate
   hits one, note it as extra strength. But NEVER reject a useful, non-redundant skill for
   "touching neither moat axis". That was a past mistake. Other axes (determinism, cost
   economy, portability, artifact-to-action) are equally welcome if they make a useful skill.

DON'T RE-PROPOSE JUDGED IDEAS:
- The repo already contains session-handoff, lessons-learned (distributed by session-memory
  and learning-loop), natural-writing, test-discipline, and git-archaeologist, and has a
  STRONG candidate (PR-reviewer). DO NOT propose a mode/variant/wrapper of those, of CLAUDE.md,
  or anything already carrying a verdict in strategy.md / SHORTLIST.md. If the pitch could
  just be appended to an existing skill as "also it can X", it's already covered — skip it.
- Explore broadly across the daily-work surface: data/schema, observability/logs,
  dependency & supply-chain hygiene, infra & env config, performance, migrations, API/
  contract work, docs/onboarding, the token/cost economy of agents, multi-repo, team
  collaboration, AND the everyday inner-loop (debugging, repro, test-writing, refactors).
  Stateless "does a useful thing" skills are fully welcome — usefulness is the bar.

The goal is skills that genuinely help EVERYDAY development and working-with-AI — useful
enough to reach for often, and not redundant with what already ships. Be skeptical of an
idea's usefulness and redundancy, but do NOT reject it for lacking a moat. It is still a
SUCCESS to conclude "build nothing
new" — but only after exploring genuinely new ground, not adjacency.
`

const CANDIDATE_SCHEMA = {
  type: 'object',
  required: ['candidates'],
  properties: {
    candidates: {
      type: 'array',
      items: {
        type: 'object',
        required: ['name', 'pitch', 'moatAxis', 'everydayUseCase', 'demandEvidence'],
        properties: {
          name: { type: 'string', description: 'kebab-case skill name' },
          pitch: { type: 'string', description: 'one sentence: what it does and for whom' },
          moatAxis: { type: 'string', description: 'OPTIONAL bonus signal only: if the skill happens to lean on memory, right-sizing, or a named axis (determinism, cost-economy, portability, artifact-to-action), note it. "none (stateless utility)" is completely fine and NOT a mark against it — usefulness is the bar.' },
          everydayUseCase: { type: 'string', description: 'a concrete recurring moment in daily dev/AI work where it fires' },
          demandEvidence: { type: 'string', description: 'honest evidence the pain is real and recurring, or "speculative" if none' },
        },
      },
    },
  },
}

const DEDUP_SCHEMA = {
  type: 'object',
  required: ['fresh', 'droppedAlreadyJudged'],
  properties: {
    fresh: {
      type: 'array',
      description: 'up to 8 unique candidates NOT already carrying a verdict in strategy.md or SHORTLIST.md, prioritized by promise',
      items: {
        type: 'object',
        required: ['name', 'pitch', 'moatAxis', 'everydayUseCase', 'demandEvidence'],
        properties: {
          name: { type: 'string' },
          pitch: { type: 'string' },
          moatAxis: { type: 'string' },
          everydayUseCase: { type: 'string' },
          demandEvidence: { type: 'string' },
        },
      },
    },
    droppedAlreadyJudged: { type: 'array', items: { type: 'string' }, description: 'names skipped because already judged' },
  },
}

const GROUND_SCHEMA = {
  type: 'object',
  required: ['name', 'verdict', 'existingTools', 'gapAnalysis'],
  properties: {
    name: { type: 'string' },
    verdict: { type: 'string', enum: ['useful-and-distinct', 'narrow', 'redundant'], description: 'redundant = an existing tool does the same job as well or better (true duplication / strictly worse); narrow = useful only in a thin slice; useful-and-distinct = genuinely useful for daily work AND worth reaching for vs the alternatives. Do NOT downgrade for "lacks a moat".' },
    existingTools: { type: 'string', description: 'which built-ins/plugins/cloud features overlap, and exactly what they do' },
    gapAnalysis: { type: 'string', description: 'why a developer would still reach for this over the existing tools (the real added value), OR — if redundant — why the existing tool already does it as well/better' },
  },
}

const SIM_SCHEMA = {
  type: 'object',
  required: ['name', 'scenarios', 'avgDelta'],
  properties: {
    name: { type: 'string' },
    scenarios: {
      type: 'array',
      items: {
        type: 'object',
        required: ['situation', 'withSkill', 'baseline', 'deltaScore'],
        properties: {
          situation: { type: 'string', description: 'a concrete, realistic dev/AI moment' },
          baseline: { type: 'string', description: 'what happens TODAY with existing tools only' },
          withSkill: { type: 'string', description: 'what happens with the candidate skill' },
          deltaScore: { type: 'number', description: '1-10 how much better the skill makes this moment (1=no real difference)' },
        },
      },
    },
    avgDelta: { type: 'number' },
  },
}

const VOTE_SCHEMA = {
  type: 'object',
  required: ['worthBuilding', 'reason', 'weakestLink'],
  properties: {
    worthBuilding: { type: 'boolean', description: 'Is this worth Overclock building? TRUE if it is genuinely useful for everyday dev/AI work AND non-redundant (a developer would reach for it over the alternatives) AND can be well-designed (right-sized, sane anti-triggers). Do NOT require a memory/right-sizing moat — usefulness is the bar. Vote FALSE only for genuine redundancy, marginal/novelty value, or undesign-able sprawl.' },
    reason: { type: 'string' },
    weakestLink: { type: 'string', description: 'the single weakest part of the case (e.g. real overlap with an existing tool, or thin usefulness)' },
  },
}

// ============================================================
phase('Generate')
const LENSES = [
  { key: 'everyday-inner-loop', focus: 'THE DAILY INNER LOOP. The high-frequency moments every developer hits: writing/running tests, reproducing a bug, debugging, small refactors, reading unfamiliar code, wiring a new dependency, chasing a failing CI. Where is a USEFUL, often-reached-for skill that saves real time here? Stateless is fine — usefulness is the bar. Check it is not already covered as well by /simplify, /code-review, /verify, feature-dev.' },
  { key: 'untouched-domains', focus: 'DOMAINS THE REPO HAS NOT TOUCHED. data & schema/migration work, observability & log triage, dependency & supply-chain hygiene, infra/env/config drift, performance hunting, API/contract evolution, docs/onboarding. Where does a daily pain meet a skill a dev would genuinely reach for? Pick the domain first, then the concrete recurring pain.' },
  { key: 'agent-economy', focus: 'THE COST/ECONOMY OF RUNNING THE AGENT ITSELF. Token/context budgeting, model selection per task, context-window management, reusing prompt/spec assets, knowing when an agent run is not worth it. Official tools are blind to their own cost — is there a useful skill here?' },
  { key: 'artifact-to-action', focus: 'TURNING ARTIFACTS INTO ACTION. A skill that TRANSFORMS something the dev does by hand repeatedly: a stack trace -> a failing repro test; a flaky CI log -> a ranked root-cause hypothesis; a vague ticket -> a scoped contract; an error -> a minimal reproduction. The value is the transform; stateless is fine.' },
  { key: 'beyond-single-repo', focus: 'BEYOND THE SINGLE LOCAL REPO. Multi-repo / cross-repo work, human<->AI TEAM handoff (not session<->session), tool-agnostic portability across AI clients (Cursor/Codex/etc — the README brags .ai/ is portable; is there an unbuilt skill exploiting that?), shared team context. Useful angles the official single-session tools do not serve well.' },
]
const generated = await parallel(LENSES.map(l => () =>
  agent(
    `${CONTEXT}\n\nYOUR LENS: ${l.focus}\n\nPropose 3-5 candidate skills through THIS lens only. ` +
    `For each: everydayUseCase = the concrete recurring moment it helps; demandEvidence = honest read ` +
    `of how often a dev actually hits this ("daily", "weekly", or "speculative" if you're guessing — ` +
    `don't inflate); moatAxis = name a defensible axis if it has one, or "none (stateless utility)" — ` +
    `which is FINE. Optimize for genuine everyday usefulness, not cleverness. Prefer fewer, stronger ` +
    `candidates. Avoid anything already judged in strategy.md / SHORTLIST.md.`,
    { label: `gen:${l.key}`, phase: 'Generate', schema: CANDIDATE_SCHEMA }
  )
))
const allCandidates = generated.filter(Boolean).flatMap(g => g.candidates)
log(`Generated ${allCandidates.length} raw candidates across ${LENSES.length} lenses`)

// ============================================================
phase('Dedup')
const dedup = await agent(
  `${CONTEXT}\n\nHere are raw candidates from 5 lenses (JSON):\n${JSON.stringify(allCandidates, null, 2)}\n\n` +
  `Merge semantic duplicates into one entry each (keep the sharpest pitch). Then DROP any candidate ` +
  `that already carries a verdict in docs/strategy.md's ledger or docs/brainstorm/SHORTLIST.md, and ` +
  `any that is just a mode/variant/wrapper of session-handoff, lessons-learned, PR-reviewer, or ` +
  `CLAUDE.md (if the pitch is "existing-skill + also X", it's covered — drop it). ` +
  `Return up to 8 fresh candidates, prioritized by EVERYDAY USEFULNESS and non-redundancy ` +
  `(how often a dev would reach for it, and whether it beats the existing alternative) — NOT by ` +
  `whether they fit a memory/right-sizing moat. List names you dropped.`,
  { label: 'dedup', phase: 'Dedup', schema: DEDUP_SCHEMA }
)
const candidates = (dedup?.fresh ?? []).slice(0, 8)
log(`Dedup -> ${candidates.length} fresh candidates; dropped already-judged: ${(dedup?.droppedAlreadyJudged ?? []).join(', ') || 'none'}`)
if (candidates.length === 0) {
  return { summary: 'No fresh candidates this run — everything generated was already judged. Nothing to write.', candidates: [] }
}

// ============================================================
// Ground -> Simulate -> Score, pipelined per candidate (no barriers).
const evaluated = await pipeline(
  candidates,
  // Stage 1: baseline-gap grounding (web search allowed)
  (c) => agent(
    `${CONTEXT}\n\nCANDIDATE: ${JSON.stringify(c)}\n\n` +
    `Run the NON-REDUNDANCY TEST. Identify every built-in command, official plugin, and cloud feature ` +
    `that overlaps, and state exactly what each does (use WebSearch if unsure of a tool's current scope). ` +
    `Then decide: would a developer genuinely reach for THIS over the existing tools for an everyday task? ` +
    `Mark "redundant" only if an existing tool does the same job as well or better. Mark "useful-and-distinct" ` +
    `if it adds real daily value — it does NOT need a memory/right-sizing moat to qualify.`,
    { label: `ground:${c.name}`, phase: 'Ground', schema: GROUND_SCHEMA }
  ).then(g => ({ ...c, ground: g })),

  // Stage 2: simulate scenarios (skip if grounding killed it)
  (r) => {
    if (!r || r.ground?.verdict === 'redundant') return { ...r, sim: null }
    return agent(
      `${CONTEXT}\n\nCANDIDATE: ${r.name} — ${r.pitch}\nGrounding gap: ${r.ground?.gapAnalysis}\n\n` +
      `Construct 2 CONCRETE, realistic dev/AI scenarios where this skill would fire. For each, play out ` +
      `honestly what happens TODAY (baseline, existing tools only) vs WITH the skill, and score the delta ` +
      `1-10 (1 = no real difference). Do not flatter the skill; if baseline already handles it, say so with a low delta.`,
      { label: `sim:${r.name}`, phase: 'Simulate', schema: SIM_SCHEMA }
    ).then(s => ({ ...r, sim: s }))
  },

  // Stage 3: 3-vote adversarial creation-bar panel, then verdict
  async (r) => {
    if (!r) return null
    if (r.ground?.verdict === 'redundant') return { ...r, finalVerdict: 'KILL', votes: [], rationale: 'Redundant — an existing tool does the same job as well or better.' }
    const votes = (await parallel([0, 1, 2].map(i => () =>
      agent(
        `${CONTEXT}\n\nYou are REVIEWER #${i + 1}, judging whether Overclock should build this. Be skeptical, ` +
        `but the bar is USEFULNESS + non-redundancy + design quality — NOT a memory/right-sizing moat.\n\n` +
        `CANDIDATE: ${r.name} — ${r.pitch}\nMoat axis (if any): ${r.moatAxis}\nHow often hit: ${r.demandEvidence}\n` +
        `Everyday use case: ${r.everydayUseCase}\nGrounding: verdict=${r.ground?.verdict}; ${r.ground?.gapAnalysis}\n` +
        `Simulation avgDelta vs baseline: ${r.sim?.avgDelta ?? 'n/a'}\n\n` +
        `Vote worthBuilding=true if it is genuinely useful for everyday dev/AI work, a dev would reach for it ` +
        `over the alternatives, and it can be well-designed (right-sized, sane anti-triggers). Vote false only ` +
        `for genuine redundancy, marginal/novelty value, or undesign-able sprawl. Name the single weakest link.`,
        { label: `vote${i + 1}:${r.name}`, phase: 'Score', schema: VOTE_SCHEMA }
      )
    ))).filter(Boolean)
    const yes = votes.filter(v => v.worthBuilding).length
    const finalVerdict = yes >= 2 ? 'STRONG' : (yes === 1 ? 'PARKED' : 'KILL')
    return { ...r, votes, finalVerdict, rationale: votes.map(v => v.weakestLink).join(' | ') }
  }
)

const results = evaluated.filter(Boolean)
const strong = results.filter(r => r.finalVerdict === 'STRONG')
const parked = results.filter(r => r.finalVerdict === 'PARKED')
log(`Scored: ${strong.length} STRONG, ${parked.length} PARKED, ${results.length - strong.length - parked.length} KILL`)

// ============================================================
phase('Synthesize')
const synth = await agent(
  `${CONTEXT}\n\nYou are the SCRIBE. Below is the full structured result of one brainstorm run (JSON):\n` +
  `${JSON.stringify(results, null, 2)}\n\n` +
  `Do exactly this, writing files with the Write tool:\n` +
  `1. Get a timestamp: run \`date +%Y-%m-%d-%H%M\` via Bash.\n` +
  `2. Write a run log to ${REPO}/docs/brainstorm/run-<timestamp>.md. Include: a one-line run summary; ` +
  `   then per candidate a section with verdict (STRONG/PARKED/KILL), the moat axis, the baseline-gap finding, ` +
  `   the two simulated scenarios with deltas, the skeptic votes, and the single decisive reason for the verdict. ` +
  `   Be concise and honest — this is an evidence record, not marketing.\n` +
  `3. Update (create if missing) ${REPO}/docs/brainstorm/SHORTLIST.md: a rolling table of every candidate ever ` +
  `   judged across runs (name | verdict | moat axis | one-line why | run date). Merge today's results in; ` +
  `   if a name already exists, update its row only if today's verdict is newer/stronger and note the change. ` +
  `   Keep STRONG candidates at the top. Add a short header explaining this file is machine-generated by the ` +
  `   skill-brainstorm workflow and that human-blessed verdicts live in docs/strategy.md.\n` +
  `4. Do NOT modify docs/strategy.md (that is the human-curated source of truth).\n` +
  `Return a 3-5 line plain-text summary of what you wrote and the headline recommendation.`,
  { label: 'scribe', phase: 'Synthesize' }
)

return {
  summary: synth,
  counts: { strong: strong.length, parked: parked.length, total: results.length },
  strong: strong.map(s => s.name),
}
