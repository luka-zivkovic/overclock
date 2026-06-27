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
