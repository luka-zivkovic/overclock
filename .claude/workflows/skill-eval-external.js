export const meta = {
  name: 'skill-eval-external',
  description: 'Run EXISTING published skills (not generated ideas) through Overclock\'s evaluation gauntlet: baseline-gap vs what Overclock already ships, scenario simulation, 3-vote adversarial creation/adoption-bar panel. Writes a verdict log to docs/brainstorm/.',
  whenToUse: 'Evaluate third-party skills for adoption/inspiration. Candidates are passed via args as a JSON array of {name, pitch, source, fullDescription}.',
  phases: [
    { title: 'Ground', detail: 'baseline-gap vs Overclock + the wider ecosystem' },
    { title: 'Simulate', detail: 'skill-in-use vs Overclock-today baseline' },
    { title: 'Score', detail: '3-vote adversarial adoption-bar panel' },
    { title: 'Synthesize', detail: 'write external-eval log + update shortlist' },
  ],
}

const REPO = '.'
const CONTEXT = `
You are evaluating EXISTING, PUBLISHED third-party skills for the Overclock repo at ${REPO}
— a PERSONAL TOOLKIT of Claude Code plugins/skills. NOT a product line, NOT a marketplace entry.

These candidates ALREADY EXIST and ship publicly. The question is NOT "is this defensible" and NOT
"does this beat the ecosystem" — it is simply: IS THIS USEFUL ENOUGH TO ADD TO THE KIT, and if so,
what is the best way to get that utility — install the published skill as-is, build your own tuned
version in Overclock, lift one mechanism into an existing skill, or skip it?

BEFORE judging, read to ground yourself (Read/Bash/Glob) — this is RESEARCH to judge fit and build it
BETTER, not a gate to disqualify on:
- ${REPO}/docs/strategy.md        — operating principles (the usefulness bar, sharpened 2026-06-25)
- ${REPO}/README.md               — what Overclock already ships
- ${REPO}/docs/brainstorm/SHORTLIST.md — prior verdicts
- list ${REPO}/plugins/**/skills/  — the EXISTING KIT (the ONLY redundancy set that matters)
- NOTE overlapping installed tools: /simplify + code-simplifier, /code-review, feature-dev,
  pr-review-toolkit, plan mode, session-memory (lessons-learned/session-handoff), learning-loop,
  natural-writing, discipline-gates (test-discipline/git-archaeologist), and CLAUDE.md.

RULES (from strategy.md, usefulness bar):
1. USEFULNESS IS THE GATE. A skill is worth having if you'd reliably reach for it on real work.
   Reliable triggering of a wanted behavior is REAL value EVEN IF the base model could do it when
   asked, or a published skill already does it — automating a preference you'd otherwise re-type
   every time IS the value. Do NOT disqualify for "no moat", "stateless", "native-LLM-collapse",
   "elicitable by a one-line prompt", or "freely installable elsewhere". None of those are kills.
2. NON-REDUNDANCY IS SCOPED TO THIS KIT. The only redundancy that kills is true duplication of a
   skill ALREADY IN ${REPO}/plugins (would the two fight over the same trigger?). Overlap with the
   wider ecosystem or with the base model's latent ability is NOT redundancy — it's design context.
3. RIGHT-SIZE OR IT'S BLOAT. The one strict discipline: it must fire only when wanted, with real
   anti-triggers / a triage gate. A skill that misfires on trivial work is worse than none.
4. DEMAND: a real reason is enough. A direct request or a concrete named use justifies adding it; a
   shipped benchmark or real usage is strong supporting evidence (credit it, but verify it measures
   what it claims). Only purely speculative "might be nice" candidates that nothing points to wait.

Possible verdicts you are deciding between, per candidate:
- ADOPT-AS-IS: useful, and the published skill fits well enough to just install — no need to rebuild.
- BUILD-IN-OVERCLOCK: useful, but you want your OWN version — tuned to you, adapted to fit, or owned
  and under your control. Wanting your own tuned tool is a legitimate reason; it does NOT require a
  memory/right-sizing "gap" the published version misses.
- INSPIRE: don't adopt whole — lift one specific mechanism into an existing Overclock skill.
- PASS: not useful enough to add, OR it true-duplicates a skill already in the kit (would collide).
Be concrete and honest. ADOPT-AS-IS, BUILD-IN-OVERCLOCK, INSPIRE, and PASS are all common, valid outcomes.
`

const GROUND_SCHEMA = {
  type: 'object',
  required: ['name', 'verdict', 'overlapsOverclock', 'gapAnalysis', 'benchmarkCheck'],
  properties: {
    name: { type: 'string' },
    verdict: { type: 'string', enum: ['overclock-gap-real', 'narrow', 'duplicative-of-overclock', 'good-but-no-overclock-gap'], description: 'duplicative-of-overclock = true-duplicates a skill ALREADY IN THE KIT (would collide) → lean PASS; good-but-no-overclock-gap = useful and the published skill fits as-is → lean ADOPT-AS-IS; overclock-gap-real = useful and you would want your OWN tuned/owned version → lean BUILD-IN-OVERCLOCK (does NOT require a memory/right-sizing gap)' },
    overlapsOverclock: { type: 'string', description: 'which skills ALREADY IN THE KIT (plugins/) overlap and what they do — ecosystem/base-model overlap is design context, NOT redundancy' },
    gapAnalysis: { type: 'string', description: 'if useful: would the published skill fit as-is, or do you want your own tuned/owned version, or does a skill already in the kit collide with it? usefulness is the gate, not a measurable-gap test' },
    benchmarkCheck: { type: 'string', description: 'if the skill cites a benchmark/usage, does it actually measure what it claims? credit or discount it honestly' },
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
          baseline: { type: 'string', description: 'what happens with OVERCLOCK + built-ins TODAY (incl. /simplify, code-simplifier) — no new skill' },
          withSkill: { type: 'string' },
          deltaScore: { type: 'number', description: '1-10 added value over the Overclock-today baseline (1=no real difference)' },
        },
      },
    },
    avgDelta: { type: 'number' },
  },
}

const VOTE_SCHEMA = {
  type: 'object',
  required: ['recommendation', 'reason', 'weakestLink'],
  properties: {
    recommendation: { type: 'string', enum: ['ADOPT-AS-IS', 'BUILD-IN-OVERCLOCK', 'INSPIRE', 'PASS'], description: 'your independent recommendation' },
    reason: { type: 'string' },
    weakestLink: { type: 'string', description: 'the single weakest part of the case for adding this to the kit' },
  },
}

// Candidates: from args (JSON array) if provided, else the inlined default set below.
const DEFAULT_CANDIDATES = [
  { name: 'ponytail', source: 'https://github.com/DietrichGebert/ponytail', pitch: "Persistent 'lazy senior dev' persona that forces the simplest solution that works (YAGNI, stdlib-first, no unrequested abstractions); active every response with lite/full/ultra modes.", fullDescription: "A persistent behavioral skill. A 'ladder' reflex: does this need to exist (YAGNI) -> stdlib -> native platform feature -> already-installed dep -> one line -> minimum code. Rules against unrequested abstractions/boilerplate, deletion over addition, marks deliberate simplifications with `ponytail:` comments naming the ceiling+upgrade path. Ships a real AGENTIC benchmark: headless Claude Code editing tiangolo's full-stack-fastapi-template, 12 feature tickets, n=4, Haiku 4.5 -- -54% LOC mean (up to -94% on over-build traps), -22% tokens, -20% cost, -27% time, 100% safety retained (a bare 'write one-liners' prompt drops a safety guard; ponytail keeps it). Works across 14 agents." },
  { name: 'ponytail-review-and-audit', source: 'https://github.com/DietrichGebert/ponytail', pitch: "One-shot over-engineering review of a diff (ponytail-review) or whole repo (ponytail-audit): ranked findings tagged delete/stdlib/native/yagni/shrink, one line each, ends with 'net: -N lines possible'.", fullDescription: "Reviews specifically for unnecessary complexity (NOT correctness/security/perf -- explicitly out of scope, routed elsewhere). Terse tagged findings with concrete replacements (e.g. 'L4: native: moment.js for one format call. Intl.DateTimeFormat, 0 deps.'). Lists findings, applies nothing, one-shot." },
  { name: 'ponytail-debt', source: 'https://github.com/DietrichGebert/ponytail', pitch: 'Harvest every `ponytail:` shortcut comment in the repo into one debt ledger (ceiling + upgrade trigger per row), flagging ones with no trigger as silent-rot risk.', fullDescription: "Greps repo for `(#|//) ?ponytail:` markers, one ledger row per hit grouped by file, pulls ceiling+trigger from the comment convention, flags 'no-trigger' rows. Reads/reports only; can persist to PONYTAIL-DEBT.md if asked. Depends on the ponytail comment convention existing in the codebase." },
  { name: 'ponytail-gain', source: 'https://github.com/DietrichGebert/ponytail', pitch: "Display a scoreboard of ponytail's published benchmark medians (less code/cost, more speed) as ASCII bars; explicitly refuses to invent per-repo savings numbers.", fullDescription: 'One-shot display of benchmark medians. Honesty boundary: NEVER prints a per-repo savings number because the unbuilt version was never written; points to /ponytail-debt for real counted figures instead.' },
  { name: 'karpathy-guidelines', source: 'https://github.com/multica-ai/andrej-karpathy-skills', pitch: 'Behavioral guidelines to reduce common LLM coding mistakes: think-before-coding (surface assumptions), simplicity-first, surgical changes (touch only what is needed), goal-driven execution (define verifiable success criteria, loop until verified).', fullDescription: "Four behavioral guidelines derived from Karpathy's observations on LLM coding pitfalls. Biases toward caution over speed; says 'for trivial tasks, use judgment'. Overlaps conceptually with ponytail (simplicity) and with plan/verify workflows (goal-driven execution, write-a-failing-test-first)." },
  { name: 'what-did-i-get-done', source: 'https://github.com/cursor/plugins/blob/3347cbab/cursor-team-kit/skills/what-did-i-get-done/SKILL.md', pitch: 'Generate a concise, high-signal work summary from git commits in a time range, filtered to the current user excluding merges, with the resolved date range and optional 2-5 bullets.', fullDescription: "Converts time references to dates, runs git log filtered by current user excluding merges over that range, distills substantial (non-cosmetic) changes into a status update. Output: brief status-report summary + actual date range + optional bullets. Functional descriptions, doesn't infer reasoning." },
]
// args may arrive as a JSON-encoded string depending on the harness — coerce before use.
let candidateArgs = args
if (typeof candidateArgs === 'string') {
  try { candidateArgs = JSON.parse(candidateArgs) } catch { candidateArgs = null }
}
const candidates = Array.isArray(candidateArgs) && candidateArgs.length ? candidateArgs : DEFAULT_CANDIDATES
log(candidates === DEFAULT_CANDIDATES
  ? `No usable args — falling back to the ${candidates.length} inlined DEFAULT_CANDIDATES`
  : `Evaluating ${candidates.length} published skills from args against Overclock's surface`)

const evaluated = await pipeline(
  candidates,
  // Stage 1: baseline-gap grounding (web allowed to verify benchmarks / overlap)
  (c) => agent(
    `${CONTEXT}\n\nPUBLISHED SKILL UNDER EVALUATION:\n${JSON.stringify(c, null, 2)}\n\n` +
    `Run the BASELINE-GAP TEST against Overclock's existing surface AND against the skill being ` +
    `installable as-is. Use WebSearch/WebFetch if you need to verify its benchmark or adoption. ` +
    `Decide the grounding verdict honestly — "good-but-no-overclock-gap" (lean adopt) is a common ` +
    `and valid outcome for a genuinely good skill that Overclock has no special reason to rebuild.`,
    { label: `ground:${c.name}`, phase: 'Ground', schema: GROUND_SCHEMA }
  ).then(g => ({ ...c, ground: g })),

  // Stage 2: simulate vs Overclock-today (skip only if flatly duplicative)
  (r) => {
    if (!r || r.ground?.verdict === 'duplicative-of-overclock') return { ...r, sim: null }
    return agent(
      `${CONTEXT}\n\nSKILL: ${r.name} — ${r.pitch}\nGrounding gap: ${r.ground?.gapAnalysis}\n\n` +
      `Construct 2 CONCRETE dev/AI scenarios where this skill would fire. Play out honestly what ` +
      `happens with OVERCLOCK + built-ins TODAY (baseline — remember /simplify and code-simplifier ` +
      `already exist) vs WITH this skill, and score the delta 1-10. Do not flatter the skill.`,
      { label: `sim:${r.name}`, phase: 'Simulate', schema: SIM_SCHEMA }
    ).then(s => ({ ...r, sim: s }))
  },

  // Stage 3: 3-vote adversarial adoption-bar panel
  async (r) => {
    if (!r) return null
    const votes = (await parallel([0, 1, 2].map(i => () =>
      agent(
        `${CONTEXT}\n\nYou are REVIEWER #${i + 1}, independently deciding what to do with this PUBLISHED ` +
        `skill for the kit. Judge USEFULNESS first — would you reach for it on real work? (reliable ` +
        `triggering counts even if the base model could do it when asked, or it's installable elsewhere). ` +
        `Then pick the best way to get that utility. PASS only if it is not useful enough OR it ` +
        `true-duplicates a skill ALREADY IN THE KIT. Do NOT default against a tuned BUILD just because ` +
        `the published version is installable or it "lacks a moat".\n\n` +
        `SKILL: ${r.name} — ${r.pitch}\nSource: ${r.source}\n` +
        `Grounding: verdict=${r.ground?.verdict}; ${r.ground?.gapAnalysis}\nBenchmark check: ${r.ground?.benchmarkCheck}\n` +
        `Simulation avgDelta vs Overclock-today: ${r.sim?.avgDelta ?? 'n/a (skipped — duplicative)'}\n\n` +
        `Pick ONE recommendation (ADOPT-AS-IS / BUILD-IN-OVERCLOCK / INSPIRE / PASS) and name the weakest link.`,
        { label: `vote${i + 1}:${r.name}`, phase: 'Score', schema: VOTE_SCHEMA }
      )
    ))).filter(Boolean)
    // majority recommendation
    const tally = {}
    for (const v of votes) tally[v.recommendation] = (tally[v.recommendation] ?? 0) + 1
    const finalVerdict = Object.entries(tally).sort((a, b) => b[1] - a[1])[0]?.[0] ?? 'PASS'
    return { ...r, votes, tally, finalVerdict }
  }
)

const results = evaluated.filter(Boolean)
const summary = results.map(r => `${r.name}: ${r.finalVerdict} (${JSON.stringify(r.tally)})`).join('; ')
log(`Verdicts — ${summary}`)

phase('Synthesize')
const synth = await agent(
  `${CONTEXT}\n\nYou are the SCRIBE. Full structured result of an external-skill evaluation run (JSON):\n` +
  `${JSON.stringify(results, null, 2)}\n\n` +
  `Write files with the Write tool:\n` +
  `1. Get a timestamp: \`date +%Y-%m-%d-%H%M\` via Bash.\n` +
  `2. Write ${REPO}/docs/brainstorm/external-eval-<timestamp>.md. Header explains these are EXISTING ` +
  `   published skills evaluated for adoption (not generated ideas). Per skill: source URL, the final ` +
  `   verdict (ADOPT-AS-IS / BUILD-IN-OVERCLOCK / INSPIRE / PASS), the vote tally, the baseline-gap ` +
  `   finding (incl. overlap with Overclock's /simplify, code-simplifier, etc.), the benchmark check, ` +
  `   the simulated scenarios + deltas where they ran, and the decisive reason. Concise, honest.\n` +
  `3. Update (create if missing) ${REPO}/docs/brainstorm/SHORTLIST.md: add a clearly-labeled ` +
  `   "External skills evaluated" section/table (name | source | verdict | one-line why | date) so these ` +
  `   don't get confused with internally-generated candidates. Do not alter existing rows.\n` +
  `4. Do NOT modify docs/strategy.md.\n` +
  `Return a 4-6 line plain-text summary with the per-skill verdicts and the single headline takeaway.`,
  { label: 'scribe', phase: 'Synthesize' }
)

return { summary: synth, verdicts: results.map(r => ({ name: r.name, verdict: r.finalVerdict, tally: r.tally })) }
