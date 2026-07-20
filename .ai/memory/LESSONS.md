<!-- memory-schema: v1 -->
# Lessons

## Judge new skills on usefulness, not the "memory + right-sizing moat"
- **When:** brainstorming, scoring, or evaluating candidate skills for Overclock (the skill-brainstorm / skill-eval-external workflows, or any "should we build this skill?" judgment)
- **Wrong:** treating the "memory + right-sizing moat" from docs/strategy.md as a prescriptive gate — KILLing/PASSing candidates for "touches neither moat axis", "stateless persona", or "no right-sizing", as if a skill must be stateful or adaptive to be worth building
- **Right:** judge against the user's actual bar — is the skill genuinely USEFUL for everyday dev / working-with-AI, and non-redundant vs existing alternatives? The moat is DESCRIPTIVE (it explains why already-built skills like session-memory are stateful — the user needed memory), not a requirement for future skills. Memory/right-sizing is a bonus signal that a skill is especially defensible, never a gate. The baseline-gap test survives but reframed: "is this worth reaching for vs the built-in?" not "does it have a moat?"
- **Evidence:** 2026-06-22 user: "i didn't say that when starting this brainstorming session. They don't have to be stateful or adaptive. They need to be useful, that's the core principle. The first skills we created are that, because i needed them to be, others we create don't have to be that." The original ask (session start) was skills that "help in everyday development and working with ai" — usefulness, never a moat gate. The mis-framing caused ~45 KILLs and 5/6 external PASSes to reject candidates partly for the wrong reason.
- **Count:** 1
- **Last reinforced:** 2026-06-22

## When the user directly asks for a simple useful skill, build that — don't inflate it into a moat-shaped candidate
- **When:** the user makes a direct, concrete request for a skill ("I just want a skill that does X"), especially for their own everyday use rather than for the Overclock marketplace
- **Wrong:** bolting on moat machinery the user never asked for (e.g. "personalization memory" + "precedence hierarchy") to make it clear the build-for-marketplace bar, then running the full skill-eval-external / brainstorm gauntlet and reporting an INSPIRE/PASS verdict — answering "should Overclock ship this for the moat?" when the user asked "give me a useful skill." Also: routing a prose/writing need into lessons-learned (which is for coding corrections) just because it is the nearest memory skill.
- **Right:** separate the two questions. The gauntlet answers "should Overclock BUILD/ADOPT this as a defensible product." A direct user request answers "is this useful to ME" — and a stateless, no-moat skill that saves the user real time is a valid YES under the usefulness bar. Build the simple thing (one tight SKILL.md, right-sized, real anti-triggers), keep it lightweight, skip the ceremony.
- **Evidence:** 2026-06-25 — user asked for a natural-writing skill for blog posts; agent ran it through skill-eval-external as an "Overclock-adapted" candidate with invented voice-memory/precedence differentiators, got INSPIRE, then kept folding it into lessons-learned. User: "you're confusing lessons learned with plain writing. I just want a skill that will help me write in a more natural language ... so i can use ai without overcorrecting." Fix: built plugins/natural-writing as a plain stateless skill.
- **Count:** 1
- **Last reinforced:** 2026-06-25

## Verify eval-fixture mechanics with the skill's own oracle before running live evals
- **When:** authoring or editing qa/ fixtures and eval cases that will run through run_evals.sh (each case costs paid runner + judge model sessions)
- **Wrong:** assuming a planted mechanic behaves as imagined — e.g. assuming `Math.floor(12.34*100)` yields 1233 (it's 1234: `12.34*100 === 1234.0000000000002`, so the planted "bug" never reproduced), or that `node --test tests/` accepts a bare directory (node 22 throws MODULE_NOT_FOUND)
- **Right:** before any live run, prove every fixture mechanic with a cheap deterministic check using the same oracle the skill will use: `node -e` the buggy value and assert it, run the vacuous test and confirm it stays green under mutation, `git log -L` the fixture history and confirm the introducing commit surfaces. Only then spend model sessions.
- **Evidence:** 2026-07-03 discipline-gates build: the $12.34 float bug didn't reproduce and the `node --test tests/` invocation failed — both caught by the pre-eval sanity chain, fixed by switching to $4.35 (floor 434 vs round 435) and `node --test` default discovery. Zero live-eval money spent on broken fixtures.
- **Count:** 1
- **Last reinforced:** 2026-07-03

## Workflow args can arrive stringified — coerce and fail loudly instead of silently falling back
- **When:** invoking any `.claude/workflows/*.js` that takes candidates/config via `args` (skill-eval-external, skill-brainstorm, skill-rejudge), or authoring a new workflow with an `args` fallback
- **Wrong:** trusting `Array.isArray(args)` alone with a silent `DEFAULT_CANDIDATES` fallback — the harness can deliver `args` as a JSON-encoded STRING, so the check fails and the workflow silently evaluates the wrong (default) candidate set, burning the full agent budget
- **Right:** in the script, coerce `typeof args === 'string' ? JSON.parse(args) : args` before the array check, and `log()` which candidate source was chosen so a fallback is visible in the first progress line; when launching, check the first log line names the expected candidate count before letting the run proceed
- **Evidence:** 2026-07-19 external-eval run of 14 mattpocock/compound-engineering candidates: args arrived stringified, script fell back to the 6 inlined ponytail-era defaults, spent 30 agents / ~680k tokens re-judging already-judged skills, and appended 6 duplicate SHORTLIST rows (reverted). Fixed by coercion + explicit source log in skill-eval-external.js.
- **Count:** 1
- **Last reinforced:** 2026-07-19

## Give history/artifact-oracle skills at least one pinned real-repo eval case
- **When:** designing an eval suite for a skill whose mechanism operates on real-world artifacts — git history (git-archaeologist), PRs/issues, advisories — rather than on files the fixture fabricates
- **Wrong:** synthetic-only fixtures. They cannot produce layered real history (a blame tip buried under lint/style commits) and never tempt the model with real background knowledge, so fabrication failure modes stay invisible: all 4 synthetic git-archaeologist cases passed while the skill could still assert remembered CVEs as fact.
- **Right:** add a SHA-pinned clone of a real open-source repo as a fixture (cache it across runs — evals already need network for the model API; restore the GitHub origin URL so gh works). Write expectations that grade the honesty path permissively (retrieved-and-cited OR explicitly-disclaimed both pass).
- **Evidence:** 2026-07-03 user: "Can you maybe use some real world open source project pr-s ... Just to have it as an eval case". The pinned npm/node-semver case (MAX_LENGTH ReDoS guard, true intent 2 style-commits deep) failed 4/5 on its FIRST run — the session asserted CVE-2022-25883 from memory without retrieval — exposing a SKILL.md gap fixed with the retrieve-or-disclaim rule.
- **Count:** 1
- **Last reinforced:** 2026-07-03
