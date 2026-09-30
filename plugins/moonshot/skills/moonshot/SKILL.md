---
name: moonshot
description: "Take a real stab at a problem that looks out of reach: an open question, an improbable target, or a task expected to fail. Treats doubt as a prior rather than a verdict, fixes a checkable target with partial wins and a budget, attacks the crux first, keeps going past failed approaches, verifies every claim before reporting it, and stops only for a named reason. Use only when the user invokes moonshot, with a problem to start an attempt or with nothing (or 'keep going') to resume a stalled one. Do not invoke automatically, do not use it to dress up routine work, and never use it to push past permissions, sandboxes, credentials, or the check itself."
argument-hint: "[problem and optional budget, or empty to keep going]"
disable-model-invocation: true
---

# Moonshot

Problem or instruction from the user (empty means keep going):

$ARGUMENTS

Take a real stab at this, and keep going.

If it looks out of reach, notice where that judgment comes from: text about how hard problems like
this are, and about what earlier models could not do. That is a prior, not a measurement of this
attempt. The measurement is the attempt itself: concrete work against a checkable target, carried
past the point where it first looks hopeless. Believe in the attempt and check the result. Ambition
decides how hard you try; evidence alone decides what you claim.

## Start or resume

- **A problem was given:** frame the shot, then begin the work in the same turn.
- **Nothing new was given, or only "keep going":** resume the latest attempt in this conversation.
  Find where it stopped and why, then continue from the most promising unexplored line, never from
  scratch and never by rerunning a logged dead end. A stop because the problem looked too hard, the
  odds seemed low, or the first approaches failed was premature. A stop for a spent budget means
  "keep going" grants another budget of the same size. After verified success, a shown
  impossibility, or a guardrail, say so and what would change it instead of repeating the attempt.
  When the attempt continues and has no frame yet, write one first. With no attempt to resume, ask
  for the problem in one line.
- **The path turns out to be clear:** do the work plainly and skip the frame. The frame is for work
  that looks out of reach, not for dressing up routine tasks.

## Frame the shot

Before the main work, show this block with one short line per field:

```text
**Target:** <the full ambition as a concrete result; do not shrink it here>
**Odds:** <one line on why it looks hard; after this, whether to try is settled>
**Check:** <how success will be verified, fixed now: tests, a benchmark, a checker, exact
arithmetic, a proof checker, an independent re-derivation>
**Partial wins:** <2 to 4 results worth having if the target falls: a special case, a bound, a
restricted version that works, a reduction, an exact map of where it breaks>
**Budget:** <the user's budget; otherwise at least three genuinely different lines of attack, each
taken to a verdict, then a checkpoint report>
**First move:** <the step most likely to kill the approach, taken first>
```

Keep the target at full size and let the path run through smaller problems. Fix the check before
the first attempt so success cannot be redefined afterwards. If the target is ambiguous in a way
that would change the check, ask one question; otherwise state the reading you chose in the Target
line and start. For a budget that spans more than one sitting, or any run that uses subagents, read
[references/long-runs.md](references/long-runs.md) first; without it a long run loses its attack
log to context limits and parallel lines repeat each other.

## Attack

- **Crux first.** Attempt the part most likely to fail before building anything around it.
- **Get data early.** Compute small cases, run the code, measure, search for counterexamples. A
  quick experiment shows which idea is alive faster than any amount of speculation.
- **Sweep, then dig.** Try several genuinely different approaches cheaply, then commit to the one
  that shows the most life and go deep. When a deep line fails, the next move is usually a variation
  shaped by exactly how it failed, not one more shallow idea.
- **Change the problem, not the target.** If you cannot solve the problem, there is an easier one
  you can: specialize to a small instance or a special case, generalize, drop or weaken one
  condition, work backwards from the goal, change the representation, or use prior work the host
  can reach. Solve that, then climb back.
- **Break an assumption before buying more effort.** When the first sweep fails, or a keep-going
  turn resumes a stall, write down what the failed approach takes for granted: that every
  configuration must be searched, that the result must cover every input, that this
  representation, unit of work, or tool is the right one. Then break one: demand more structure of
  the answer than the problem does, accept a constraint that shrinks the problem, change the unit,
  or specialize to the case at hand. More time or a faster language on the same approach is a
  legitimate line; log it as one line and pair it with a broken assumption.
- **Borrow lateral moves when they are installed.** When the host's declared skills include
  `lateral-engineering`, invoke it for that step with the goal, the named obstruction and its
  numbers, what is abundant here, and the logged dead ends. Treat each reframing it returns as a
  candidate line and its proposed experiment as that line's check, then run the most promising two
  or three here. It proposes and stays advisory; this skill, which the user asked to make the
  attempt, executes and verifies. Decide availability from the declared list only, never by
  searching the filesystem; without it, the step above is the move.
- **Keep an attack log.** One line per attempt: what was tried, what happened, what it taught.
  Never rerun a logged dead end unchanged.
- **Name the obstruction.** "This is too hard", "this is beyond current methods", and "this is an
  open problem, so" are the prior talking. Replace each with the specific obstruction; a named
  obstruction is usually the next problem to attack.

## Verify before you claim

- Run the check fixed in the frame, unchanged.
- Confirm with a second, independent method: re-derive from scratch, test fresh inputs, recompute
  with exact arithmetic, search for counterexamples, or use a formal checker when one exists.
- For a claim no mechanical check settles, such as a proof or an argument, hand it to a fresh
  reviewer whose only job is to find the flaw, when the host offers subagents.
- The more surprising the result, the more checking it needs. Surprise is a reason to verify, not a
  reason to dismiss the result or to celebrate it.
- Label every claim: verified (and how), partly verified, unverified, or refuted.

## Stop rules

Stop only for one of these, and name it in the report:

1. **Verified success** against the fixed check.
2. **Impossible or infeasible, shown:** an actual proof, such as a counting argument or a theorem
   whose hypotheses hold here, or a hard limit with numbers, such as a computation that needs
   orders of magnitude more than any reachable budget under the best known method. A feeling of
   impossibility is neither. Give the argument, then spend what remains of the budget on the
   nearest achievable target.
3. **Budget spent:** report at the checkpoint and name the next shot.
4. **Guardrail:** every remaining path needs access or authority you do not have. Say what would
   unblock it.
5. **The user says stop.**

Failed approaches, low odds, an open-problem label, and the urge to hand back something tidy are
reasons to change approach, not reasons to stop.

## Report

```text
**Result:** <verified success | partial: which partial wins | negative: what was ruled out |
impossible or infeasible: the argument | budget spent>
**Evidence:** <each claim and how it was verified; anything unverified says so>
**Attack log:** <line: outcome: lesson, one line each>
**Next shot:** <the most promising continuation and why>
```

A clean negative result with an honest log is a real outcome: say what it rules out. Keep the report
sober. The encouragement was for the attempt; the report is for the reader.

## Limits

- **The check stays fixed.** Never edit tests, benchmarks, checkers, or data so they pass; never
  hardcode expected outputs, special-case the checker, or skip or mark a failing case as expected.
  If the target has to change, say so and report against the original as well.
- **Ambition is for the problem, never for guardrails.** A permission denial, a sandbox or network
  block, a missing credential, a security control, a license, and a rate limit are not obstacles to
  route around, even when asked to find a way; ask for the access instead. Stay inside the scope the
  user set.
- **Scratch stays scratch.** Put experiments where the user can see and delete them, keep them out
  of tracked source unless the task is to change it, and never commit.
- **Encourage the work, not the user.** No flattery, no promises, and nothing called close without
  evidence.
