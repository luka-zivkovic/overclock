# Judging seams and grading

The helper decides everything a rule can decide. These are the two questions it hands to you,
and the table that turns findings into grades.

## Routing pairs

Each pair lists two model-invoked skills in one harness whose positive triggers share terms. A
shared vocabulary is not a collision. Confirm a collision only when all three hold:

1. You can write one realistic user request, in the user's words, that matches the positive
   trigger of both descriptions.
2. Neither description's anti-trigger excludes that request.
3. The skills would do materially different things with it (different output, different writes,
   or different stopping points). Two names for the same behavior is still a collision: the
   model picks one at random.

Record a confirmed collision as `judged/routing-collision`, severity **medium**, area
coherence, with the request you wrote and both skill paths. Use **low** when one skill is
clearly narrower and the overlap is a corner case. Reject the pair silently when you cannot
write the request. Never report more than five confirmed collisions; keep the strongest.

The fix is a description change, not a deletion: add the missing anti-trigger to one skill
(naming the other), or disable one source when the two are true duplicates.

## Contradictions

`instruction_directives` holds rule-like lines from every instruction file the detected
harnesses load, each with `path:line`. `instruction_pairs` names files that should agree but
are maintained separately.

A contradiction is two lines that cannot both be followed in the same situation: `npm` versus
`pnpm` for installs, "commit after each step" versus "never commit", "tests in `test/`" versus
"tests next to the code". Different wording, emphasis, or scope is not a contradiction. A
project rule that narrows a user rule is precedence working as intended, not a conflict, unless
the user rule is phrased as absolute.

Record a confirmed contradiction as `judged/contradiction`, severity **medium**, area coherence,
citing both locations. The fix names which file should own the rule and the exact line to
change or remove.

## Grades

The helper grades safety, coherence, and hygiene from its own findings with this table, applied
to each area's counts. Add confirmed judged findings to the coherence counts and apply the same
table again. The other areas never change by judgment.

| Grade | Rule |
| --- | --- |
| F | any critical finding |
| D | two or more high |
| C | one high, or three or more medium |
| B | one or two medium |
| A | nothing above low |

Context is graded from the estimated tokens of instruction files plus model-invoked skill
descriptions that load in every session of the heaviest harness: A under 6,000, B under 12,000,
C under 20,000, D above. MCP tool definitions are not counted because servers are never started;
say so when the grade matters.

Overall is the worst of safety, coherence, and hygiene. Context is reported beside it, not
folded in, because a large but intentional setup is a cost, not a defect.

## What not to report

- Generic advice with no evidence path ("consider adding tests", "document your setup").
- Usage frequency or never-invoked skills: `/skill-doctor` measures that.
- Install health, broken binaries, or measured hook latency: `/doctor` measures that.
- Style preferences inside a single skill: `casefile` and the skill's own author own that.
