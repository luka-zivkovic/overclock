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
const REPO = '/Users/makina/startups/overclock'
const CONTEXT = `
You are working inside the Overclock repo at ${REPO} — a SERIOUS, well-tested
collection of Claude Code plugins/skills (it has CI, eval harnesses, a strategy doc).

BEFORE doing anything, read these to ground yourself (use Read/Bash/Glob):
- ${REPO}/docs/strategy.md        — operating principles + the candidate ledger (verdicts already reached)
- ${REPO}/README.md               — what already ships
- ${REPO}/docs/brainstorm/SHORTLIST.md  — prior brainstorm verdicts (may not exist yet; that's fine)
- list ${REPO}/plugins/**/skills/ — the skills that already exist

NON-NEGOTIABLE RULES (from strategy.md — internalize them):
1. BASELINE-GAP FIRST. A skill earns existence only if built-in commands, official
   plugins (feature-dev, pr-review-toolkit), and cloud features (Ultraplan, /code-review
   incl. ultra, /security-review) do the job MEASURABLY worse. The dev-workflow space
   (plan/build/review) is SATURATED — assume duplication until proven otherwise.
2. DEFENSIBLE EDGE, not workflow ceremony. Official tools are stateless and one-size, so
   memory (persistence-across-sessions) and right-sizing (scaling-rigor-to-blast-radius)
   are PROVEN defensible axes — but they are NOT the only ones, and the repo has now mined
   them heavily. You are EXPECTED to propose a genuinely NEW defensible axis (e.g.
   determinism-via-mechanism, cost/token economy of the agent itself, tool-agnostic
   portability across AI clients, cross-repo/multi-repo state, human<->AI team handoff,
   turning-artifacts-into-action) — as long as you can name why official tools structurally
   won't do it. Reimplementing an official workflow is still bloat = reject.
3. RIGHT-SIZE OR IT'S BLOAT. A skill that runs full ceremony on a trivial task is worse
   than no skill. Every candidate needs a triage/altitude gate and real anti-triggers.
4. CREATION BAR (all three required): observed recurring demand (same unmet need seen
   >=2-3x, EVIDENCED not imagined) + a proven baseline gap + ships with should-NOT-trigger
   evals from day one. One imagined use never births a skill.

DIVERGENCE MANDATE (this is the point of THIS run):
- The repo already ships session-handoff, lessons-learned, and has a STRONG candidate
  (PR-reviewer). DO NOT propose anything that is a mode, sub-mode, variant, wrapper, or
  adjacent extension of those, of CLAUDE.md, or of the plan/build/review trio. Those are
  judged. If your idea's one-line pitch could be appended to an existing skill as "also it
  can X", it is BANNED here.
- Deliberately leave the memory + review territory. Explore problem DOMAINS the repo has
  never touched (data/schema, observability/logs, dependency & supply-chain hygiene, infra
  & env config, performance, large-scale migration, API/contract work, docs/onboarding,
  the token/cost economy of running agents, multi-repo work, team collaboration) and
  MODALITIES it has never used (a skill that DOES/transforms/generates, not one that
  remembers). Reach for the fresh take, then let the baseline-gap test be the judge.

The goal is skills that genuinely help EVERYDAY development and working-with-AI — not
clever-sounding novelties, and NOT another flavor of what already ships. Be skeptical of
the idea, but bold about WHERE you look. It is still a SUCCESS to conclude "build nothing
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
          moatAxis: { type: 'string', description: 'the defensible axis: memory, right-sizing, OR a named novel axis (e.g. determinism, cost-economy, portability, multi-repo, team-handoff, artifact-to-action). "neither" is a red flag.' },
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
    verdict: { type: 'string', enum: ['gap-real', 'narrow', 'duplicative'], description: 'duplicative = an existing tool already does it; narrow = real but small surviving slice; gap-real = clear unmet need' },
    existingTools: { type: 'string', description: 'which built-ins/plugins/cloud features overlap, and exactly what they do' },
    gapAnalysis: { type: 'string', description: 'the precise slice (if any) existing tools do measurably worse' },
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
  required: ['real', 'reason', 'weakestLink'],
  properties: {
    real: { type: 'boolean', description: 'does this candidate clear the FULL creation bar? Default false when uncertain.' },
    reason: { type: 'string' },
    weakestLink: { type: 'string', description: 'the single weakest part of the case' },
  },
}

// ============================================================
phase('Generate')
const LENSES = [
  { key: 'untouched-domains', focus: 'DOMAINS THE REPO HAS NEVER TOUCHED. Deliberately ignore memory/review. Go into: data & schema/migration work, observability & log triage, dependency & supply-chain hygiene, infra/env/config drift, performance hunting, API/contract evolution, docs/onboarding. Where in ONE of these does a daily pain meet a real baseline gap? Pick the domain first, then the pain.' },
  { key: 'agent-economy', focus: 'THE COST/ECONOMY OF RUNNING THE AGENT ITSELF (a novel axis). Token/context budgeting, model selection per task, context-window management, reusing prompt/spec assets, knowing when an agent run is not worth it. Official tools are blind to their own cost — is there a defensible skill here?' },
  { key: 'artifact-to-action', focus: 'TURNING ARTIFACTS INTO ACTION (a DOING modality, not remembering). A skill that TRANSFORMS something the dev does by hand repeatedly: a stack trace -> a failing repro test; a flaky CI log -> a ranked root-cause hypothesis; a vague ticket -> a scoped contract; an error -> a minimal reproduction. The value is the transform, not stored state.' },
  { key: 'beyond-single-repo', focus: 'BEYOND THE SINGLE LOCAL REPO. Multi-repo / cross-repo state, human<->AI TEAM handoff (not session<->session), tool-agnostic portability across AI clients (Cursor/Codex/etc — the README brags .ai/ is portable; is there an unbuilt skill exploiting that?), shared team context. New axes the official single-session tools structurally cannot serve.' },
  { key: 'doctrine-breaker', focus: 'ADVERSARIAL TO THE STRATEGY ITSELF. strategy.md says "the moat is memory + right-sizing." Treat that as a possible CAGE. Argue for a genuinely new defensible axis the repo has dismissed or never considered, and name exactly why official tools structurally will not do it. Also flag any tempting idea you are NOT proposing because it is mere adjacency.' },
]
const generated = await parallel(LENSES.map(l => () =>
  agent(
    `${CONTEXT}\n\nYOUR LENS: ${l.focus}\n\nPropose 3-5 candidate skills through THIS lens only. ` +
    `For each, be honest in demandEvidence — write "speculative" if you have no real evidence; ` +
    `do not inflate. Prefer fewer, stronger candidates. Avoid anything already judged in strategy.md.`,
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
  `that already carries a verdict in docs/strategy.md's ledger or docs/brainstorm/SHORTLIST.md. ` +
  `ENFORCE THE DIVERGENCE MANDATE: also drop any candidate that is a mode/variant/wrapper/adjacent ` +
  `extension of session-handoff, lessons-learned, PR-reviewer, CLAUDE.md, or the plan/build/review ` +
  `trio — even if its NAME is new. The test: if the pitch could be appended to an existing skill as ` +
  `"...also it can X", drop it and list it as already-judged-adjacency. ` +
  `Return up to 8 fresh candidates, prioritized by GENUINE NOVELTY of domain/axis AND non-speculative ` +
  `demand (not by how well they fit memory/right-sizing). List names you dropped.`,
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
    `Run the BASELINE-GAP TEST. Identify every built-in command, official plugin, and cloud feature ` +
    `that overlaps, and state exactly what each does (use WebSearch if unsure of a tool's current scope). ` +
    `Then decide: is there a slice existing tools do MEASURABLY worse? Be harsh — default toward ` +
    `"duplicative". Only "gap-real" if the unmet need is clear and tied to memory or right-sizing.`,
    { label: `ground:${c.name}`, phase: 'Ground', schema: GROUND_SCHEMA }
  ).then(g => ({ ...c, ground: g })),

  // Stage 2: simulate scenarios (skip if grounding killed it)
  (r) => {
    if (!r || r.ground?.verdict === 'duplicative') return { ...r, sim: null }
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
    if (r.ground?.verdict === 'duplicative') return { ...r, finalVerdict: 'KILL', votes: [], rationale: 'Duplicative of existing tooling (failed baseline-gap test).' }
    const votes = (await parallel([0, 1, 2].map(i => () =>
      agent(
        `${CONTEXT}\n\nYou are SKEPTIC #${i + 1}. Your job is to REFUTE this candidate. Default real=false unless the case is undeniable.\n\n` +
        `CANDIDATE: ${r.name} — ${r.pitch}\nMoat axis: ${r.moatAxis}\nDemand evidence: ${r.demandEvidence}\n` +
        `Grounding: verdict=${r.ground?.verdict}; ${r.ground?.gapAnalysis}\n` +
        `Simulation avgDelta: ${r.sim?.avgDelta ?? 'n/a'}\n\n` +
        `Judge against the FULL creation bar (recurring EVIDENCED demand + proven baseline gap + can ship with ` +
        `should-NOT-trigger evals). Speculative demand alone => real=false. Identify the single weakest link.`,
        { label: `vote${i + 1}:${r.name}`, phase: 'Score', schema: VOTE_SCHEMA }
      )
    ))).filter(Boolean)
    const yes = votes.filter(v => v.real).length
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
