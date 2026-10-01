# Long runs

Read this when the budget spans more than one sitting, when subagents will work on the attempt, or
when resuming after the conversation was compacted. Long attempts fail in predictable ways: the
try log disappears with the context, parallel lines duplicate each other, and a subagent's
success claim is taken on its word.

## Keep the state outside the context

- Keep one notes file for the attempt: the frame, the candidate pool, the try log, the current best
  line, and every verified result with the evidence behind it. Put it in a scratch location the
  user can see. Ask once before creating it inside tracked source, and never commit it.
- Update it each time a try reaches a verdict, not at the end. A resumed attempt reads the notes
  file before doing anything else, and treats its logged dead ends as closed.

## Parallel lines

- When subagents are available and the budget pays for them, try genuinely different candidates in
  parallel rather than several copies of the same idea.
- Give each subagent the goal, the fixed check, exactly one candidate with what would have to be
  true for it to work, the dead ends it must not repeat, its share of the budget, and a return
  format: measured result, verdict, evidence, lesson.
- Have subagents write bulky output to files and return the path with a short verdict, so the
  coordinating context stays small.
- The same limits bind every subagent: the check stays fixed, guardrails are not obstacles, and
  nothing is committed.

## Referees

- A referee is a fresh subagent whose only job is to break a claimed result. Give it the claim, the
  evidence, and the check, and ask for a counterexample, a gap, or a failed rerun. Do not give it
  the reasoning that produced the confidence.
- A claim that survives two independent referees is much stronger than one that survives none. A
  claim a referee breaks goes back into the try log as a lesson.
- For a proof, have a referee re-derive each key step independently, and formalize it with a proof
  assistant when one is available in the environment.

## Checkpoints and keep-going loops

- At each checkpoint, give the report block from the skill and the next shot, then continue if the
  budget allows.
- A user can re-invoke the skill on a schedule, for example with a host loop command, to keep a
  long attempt moving the way a person would by saying "keep going". Each invocation resumes from
  the notes file. Once a stop rule is met, say which one and end the loop if the host allows it.
