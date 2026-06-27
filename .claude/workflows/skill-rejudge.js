export const meta = {
  name: 'skill-rejudge',
  description: 'Re-judge previously-KILLed Overclock skill candidates under the CORRECTED bar (usefulness + non-redundancy, NOT a memory/right-sizing moat). Selects candidates that were killed for moat-reasons, re-grounds, re-simulates, re-scores, and reports which verdicts flip.',
  phases: [
    { title: 'Select', detail: 'find candidates killed for "no moat", not genuine redundancy' },
    { title: 'Ground', detail: 'non-redundancy test (corrected bar)' },
    { title: 'Simulate', detail: 'usefulness vs baseline' },
    { title: 'Score', detail: '3-vote usefulness panel' },
    { title: 'Synthesize', detail: 'report flips, update shortlist' },
  ],
}

const REPO = '/Users/makina/startups/overclock'
const CONTEXT = `
You are RE-JUDGING previously-rejected skill candidates for the Overclock repo at ${REPO}.

A correction was made (recorded in .ai/memory/LESSONS.md and docs/strategy.md, 2026-06-22):
THE BAR IS USEFULNESS, not a "memory + right-sizing moat". Many past candidates were KILLed
for "touching neither moat axis" / "stateless persona" / "stateless ceremony" — the WRONG
reason. A plain, stateless, well-designed skill that saves real time every day is a GOOD skill.

BEFORE judging, read: ${REPO}/docs/strategy.md (note the usefulness clarification at the top of
Operating principles), ${REPO}/README.md, ${REPO}/docs/brainstorm/SHORTLIST.md, and the dated
${REPO}/docs/brainstorm/run-*.md logs. Also note what already ships / is installed: /simplify,
code-simplifier, /code-review, /security-review, /verify, /run, feature-dev, pr-review-toolkit,
plan mode, session-memory (lessons-learned, session-handoff), commit-push-pr, CLAUDE.md.

CORRECTED BAR:
1. USEFUL FIRST — genuinely helps everyday dev / working-with-AI, reached for often. Stateless is fine.
2. NON-REDUNDANT — a dev would reach for it over the existing tool. Kill only for true duplication
   (an existing tool does the same job as well/better), NOT for "lacks a moat".
3. WELL-DESIGNED — right-sized, sane anti-triggers, shippable with should-NOT-trigger evals.
Moat (memory/right-sizing) is a BONUS signal, never a requirement.
`

const SELECT_SCHEMA = {
  type: 'object',
  required: ['reconsider', 'leftKilled'],
  properties: {
    reconsider: {
      type: 'array',
      description: 'past KILLed candidates that deserve a fresh look because they were killed mainly for lacking a moat / being stateless / "off-axis" — NOT for genuine redundancy, being a deterministic-CLI job, or being a mode of an existing skill. Up to 8, most useful first.',
      items: {
        type: 'object',
        required: ['name', 'pitch', 'originalKillReason', 'whyReconsider'],
        properties: {
          name: { type: 'string' },
          pitch: { type: 'string', description: 'reconstruct the candidate\'s pitch from the run log' },
          originalKillReason: { type: 'string', description: 'why it was originally KILLed (quote/paraphrase the run log)' },
          whyReconsider: { type: 'string', description: 'why the moat-correction might change the verdict' },
        },
      },
    },
    leftKilled: { type: 'array', items: { type: 'string' }, description: 'candidates NOT reconsidered because they failed for legitimate reasons (true redundancy, deterministic-CLI-owned, adjacency to existing skill) that the correction does not affect' },
  },
}

const GROUND_SCHEMA = {
  type: 'object',
  required: ['name', 'verdict', 'existingTools', 'gapAnalysis'],
  properties: {
    name: { type: 'string' },
    verdict: { type: 'string', enum: ['useful-and-distinct', 'narrow', 'redundant'], description: 'redundant = existing tool does the same job as well/better; narrow = useful only in a thin slice; useful-and-distinct = genuinely useful for daily work AND worth reaching for vs alternatives. Do NOT downgrade for "lacks a moat".' },
    existingTools: { type: 'string' },
    gapAnalysis: { type: 'string', description: 'why a dev would still reach for this over existing tools, OR why it is redundant' },
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
          situation: { type: 'string' },
          baseline: { type: 'string', description: 'what happens TODAY with existing tools only (incl. /simplify, /verify)' },
          withSkill: { type: 'string' },
          deltaScore: { type: 'number', description: '1-10 added everyday value over baseline (1=no real difference)' },
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
    worthBuilding: { type: 'boolean', description: 'worth Overclock building? TRUE if genuinely useful for everyday work AND non-redundant AND can be well-designed. Do NOT require a moat. FALSE only for genuine redundancy, marginal value, or undesign-able sprawl.' },
    reason: { type: 'string' },
    weakestLink: { type: 'string' },
  },
}

phase('Select')
const sel = await agent(
  `${CONTEXT}\n\nRead docs/brainstorm/SHORTLIST.md and the run-*.md logs. The ledger holds ~45 KILLed ` +
  `internal candidates plus an external-skills table. Identify the candidates that were KILLed PRIMARILY ` +
  `because they lacked a memory/right-sizing moat, were "stateless", or were "off-axis" — and that, under ` +
  `the corrected usefulness bar, might actually be worth building. EXCLUDE candidates that failed for ` +
  `reasons the correction does NOT change: genuine redundancy with an existing tool, the job being owned ` +
  `by a deterministic CLI, or being a mere mode/variant of an existing skill. Be honest and selective.`,
  { label: 'select', phase: 'Select', schema: SELECT_SCHEMA }
)
const candidates = (sel?.reconsider ?? []).slice(0, 8)
log(`Reconsidering ${candidates.length}; left legitimately killed: ${(sel?.leftKilled ?? []).length}`)
if (candidates.length === 0) {
  return { summary: 'No prior candidates were killed for moat-only reasons — the corrected bar changes nothing in the ledger.', flips: [] }
}

const evaluated = await pipeline(
  candidates,
  (c) => agent(
    `${CONTEXT}\n\nRE-JUDGING CANDIDATE: ${JSON.stringify(c)}\n\n` +
    `Run the NON-REDUNDANCY TEST under the corrected bar. Name every overlapping built-in/plugin/cloud ` +
    `feature and what it does (WebSearch if unsure). Decide: would a dev genuinely reach for THIS over the ` +
    `existing tools for an everyday task? "redundant" only if an existing tool does the same job as well or ` +
    `better; "useful-and-distinct" if it adds real daily value (no moat required).`,
    { label: `ground:${c.name}`, phase: 'Ground', schema: GROUND_SCHEMA }
  ).then(g => ({ ...c, ground: g })),

  (r) => {
    if (!r || r.ground?.verdict === 'redundant') return { ...r, sim: null }
    return agent(
      `${CONTEXT}\n\nCANDIDATE: ${r.name} — ${r.pitch}\nGap: ${r.ground?.gapAnalysis}\n\n` +
      `2 CONCRETE everyday dev/AI scenarios. Honestly: baseline (existing tools today) vs WITH the skill, ` +
      `delta 1-10 (1=no real difference). Don't flatter it.`,
      { label: `sim:${r.name}`, phase: 'Simulate', schema: SIM_SCHEMA }
    ).then(s => ({ ...r, sim: s }))
  },

  async (r) => {
    if (!r) return null
    if (r.ground?.verdict === 'redundant') return { ...r, finalVerdict: 'KILL', votes: [], rationale: 'Still redundant under the corrected bar (existing tool does it as well/better).' }
    const votes = (await parallel([0, 1, 2].map(i => () =>
      agent(
        `${CONTEXT}\n\nYou are REVIEWER #${i + 1}. Bar = usefulness + non-redundancy + design quality, NOT a moat.\n\n` +
        `CANDIDATE: ${r.name} — ${r.pitch}\nOriginal kill reason: ${r.originalKillReason}\n` +
        `Grounding: ${r.ground?.verdict}; ${r.ground?.gapAnalysis}\nSim avgDelta: ${r.sim?.avgDelta ?? 'n/a'}\n\n` +
        `Vote worthBuilding honestly under the corrected bar. Name the weakest link.`,
        { label: `vote${i + 1}:${r.name}`, phase: 'Score', schema: VOTE_SCHEMA }
      )
    ))).filter(Boolean)
    const yes = votes.filter(v => v.worthBuilding).length
    const finalVerdict = yes >= 2 ? 'STRONG' : (yes === 1 ? 'PARKED' : 'KILL')
    return { ...r, votes, finalVerdict, rationale: votes.map(v => v.weakestLink).join(' | ') }
  }
)

const results = evaluated.filter(Boolean)
const flips = results.filter(r => r.finalVerdict !== 'KILL')
log(`Re-judge: ${flips.length} flipped off KILL (${flips.map(f => `${f.name}->${f.finalVerdict}`).join(', ') || 'none'})`)

phase('Synthesize')
const synth = await agent(
  `${CONTEXT}\n\nYou are the SCRIBE. Re-judge results (JSON):\n${JSON.stringify(results, null, 2)}\n\n` +
  `Also list the candidates left legitimately killed: ${JSON.stringify(sel?.leftKilled ?? [])}\n\n` +
  `Write files:\n` +
  `1. Timestamp via Bash: \`date +%Y-%m-%d-%H%M\`.\n` +
  `2. Write ${REPO}/docs/brainstorm/rejudge-<timestamp>.md. Header: these are PRIOR candidates re-judged ` +
  `under the corrected usefulness bar (moat is not a gate). Per candidate: new verdict (STRONG/PARKED/KILL), ` +
  `original kill reason, the corrected grounding + scenarios + votes, and whether the verdict FLIPPED and why. ` +
  `End with a clear list of FLIPS (now worth building) vs unchanged, and the candidates left legitimately killed.\n` +
  `3. Update ${REPO}/docs/brainstorm/SHORTLIST.md: for any candidate whose verdict changed, update its row ` +
  `(new verdict + one-line why + note "re-judged 2026-06-22 under usefulness bar"). Do not delete history.\n` +
  `4. Do NOT modify docs/strategy.md.\n` +
  `Return a 4-6 line summary: which flipped to STRONG/PARKED, and the headline.`,
  { label: 'scribe', phase: 'Synthesize' }
)

return { summary: synth, flips: flips.map(f => ({ name: f.name, verdict: f.finalVerdict })) }
