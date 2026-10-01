---
name: moonshot
description: "Take a real stab at a problem that looks out of reach or stuck on the usual answer: an open question, an improbable target, a task expected to fail, or a way of working worth rethinking. Treats doubt as a prior rather than a verdict, fixes a checkable goal and budget, generates out-of-pocket candidates before judging any, gives the best bet and the wildest a real, measured try against the usual way, keeps going past failures, verifies every claim, and stops only for a named reason. Use only when the user invokes moonshot, with a problem to start or with nothing (or 'keep going') to resume. Do not invoke automatically or for routine work, and never use it to push past permissions, sandboxes, credentials, policies, or the check itself."
argument-hint: "[problem and optional budget, or empty to keep going]"
disable-model-invocation: true
---

# Moonshot

Problem or instruction from the user (empty means keep going):

$ARGUMENTS

Take a real stab at this, and keep going.

If it looks out of reach, notice where that judgment comes from: text about how hard problems like
this are, and about what earlier models could not do. That is a prior, not a measurement of this
attempt; so is the sense that an idea is unrealistic because nobody does it that way. The
measurement is the attempt itself: candidates generated wide, the promising and the improbable
alike tried against a checkable goal, and the work carried past the point where it first looks
hopeless. Believe in the attempt and check the result. Ambition decides how hard and how wide you
try; evidence alone decides what you claim.

## Start or resume

- **A problem was given:** frame it, then begin the work in the same turn.
- **Nothing new, or only "keep going":** resume the latest attempt here from its most promising
  untested candidate or unexplored line, never from scratch. A stop because the problem looked too
  hard or the first tries failed was premature; after a spent budget, "keep going" grants another
  of the same size. After verified success, a shown impossibility, or a guardrail, say so and what
  would change it instead of repeating the attempt. Write the frame and the pool first if they are
  missing. With no attempt to resume, ask for the problem in one line.
- **The path turns out to be clear:** do the work plainly and skip the frame; it is for work that
  looks out of reach or stuck on the usual answer, not for routine tasks.

## Frame

Before the main work, show this block with one short line per field:

```text
**Goal:** <the outcome that matters, at full size, without naming a mechanism>
**Wall:** <what stops the usual answer, with a number>
**Inventory:** abundant: <idle or newly cheap> · fixed: <known ahead, so precomputable> ·
habits: <conventions or old estimates a measurement could revisit> · negotiable: <freedoms to trade>
**Check:** <how success will be verified, fixed now>
**Partial wins:** <2 to 4 results worth having if the goal falls>
**Budget:** <the user's; otherwise at least three candidates tried to a verdict, then a checkpoint>
```

Take the wall's number from the user or the data, or mark it assumed. The inventory is where
unexpected answers come from; permissions, quotas, rate limits, licenses, terms, and security
controls set by others are guardrails, never habits. Fix the check before the first try so success
cannot be redefined later, and state your reading of an ambiguous goal in the Goal line. For a
budget beyond one sitting, or any run with subagents, read
[references/long-runs.md](references/long-runs.md) first.

## Diverge before you judge

The usual answer arrives first and crowds out the rest, so set it aside on purpose.

1. **Name the baseline:** the usual answer in a line or two. It is the control every candidate must
   beat on the check, not the plan.
2. **List what it takes for granted:** the unit of work, who does it, when, where, what must be
   exact, which tool or layer owns it, and whether the measure of success is negotiable. The user's
   hard requirements stay.
3. **Generate at least eight candidates that differ in kind before judging any.** Show each in one
   line: its name, its move, and what would have to be true for it to work. That condition, not how
   novel or familiar the idea feels, is what its try tests. The moves:
   - **Repurpose** a technology, format, or system at hand for a job it was not built for; name the
     property that would do the work.
   - **Remove** a step, layer, or handoff assumed mandatory.
   - **Relocate** the work to another actor, time, or place.
   - **Invert** push and pull, before and after, exact and approximate, or who owns the truth.
   - **Import** a mechanism from an unrelated field, with what maps to what.
   - **Change the unit** of work, delivery, or measurement.
   - **Accept a constraint** that makes the wall disappear, and state its cost.
   - **Embrace the failure:** assume the bad thing happens often and design for it.
   - **Change the practice:** a different order, owner, cadence, or rule, when the wall lives in how
     people work.

   Keep at least two that look unrealistic: that look is a prior, and a try is the measurement. One
   idea under different tool names counts once.
4. **Borrow lateral moves when they are installed.** When the host's declared skills include
   `lateral-engineering`, invoke it here with the goal, wall, inventory, and baseline, and add its
   reframings to the pool with their proposed experiments as tries. It proposes and stays advisory;
   this skill runs and verifies the tries. Decide availability from the declared list only, never
   by searching the filesystem; without it, the moves above are the step.

## Try

- **Try at least three:** the best bet, the wildest candidate whose condition can be tested here,
  and one between. Measure the baseline on the same check when that is cheap, so "better" means
  better than the usual way.
- **Each try is the cheapest experiment that could prove its condition false:** a prototype, a
  benchmark, a calculation with real numbers, a simulation on the user's data, or a dry run on a
  copy. State the pass and fail signals first, and record the measured number.
- **Drop a candidate only on a failed try or a hard limit with numbers.** "Unusual", "nobody does
  this", "sounds unrealistic", and a guess about the outcome are not results.
- **Let each failure shape the next try,** and when a whole round fails, return to the pool before
  buying more effort on one idea; more time or a faster language for the same approach is one
  line, not a plan.
- **Dig into what passes:** crux first, data early. If the full goal will not fall, change the
  problem, not the goal: specialize, generalize, drop a condition, work backwards, or change the
  representation, then climb back.
- **Keep a try log,** one line per try as in the report, and never rerun a logged dead end
  unchanged.
- **Name the obstruction.** "Too hard", "beyond current methods", and "nobody would do it that way"
  are the prior talking; replace each with the specific obstruction, usually the next problem to
  attack.

## Verify before you claim

- Run the fixed check, unchanged, and confirm with an independent second method: a re-derivation,
  fresh inputs, exact recomputation, a counterexample search, or a formal checker.
- A claim that a candidate beats the usual way needs both measured on the same check and data.
  Label a simulation or an estimate as one, never as an observed result.
- For a claim no mechanical check settles, such as a proof, have a fresh reviewer try to break it
  when the host offers subagents.
- The more surprising the result, the more checking it needs; surprise is a reason to verify, not
  to dismiss or celebrate.
- Label every claim: verified (and how), partly verified, unverified, or refuted.

## Stop rules

Stop only for one of these, and name it in the report:

1. **Verified success** against the fixed check.
2. **Impossible or infeasible, shown:** a proof, such as a counting argument or a theorem whose
   hypotheses hold here, or a hard limit with numbers, such as a computation orders of magnitude
   beyond any reachable budget under the best known method. A feeling of impossibility is neither.
   Give the argument, then spend the rest of the budget on the nearest achievable goal.
3. **Budget spent:** report at the checkpoint and name the next shot.
4. **Guardrail:** every remaining path needs access or authority you do not have; say what would
   unblock it.
5. **The user says stop.**

Failed tries, low odds, an open-problem label, and the urge to hand back something tidy are reasons
to change approach, not to stop.

## Report

```text
**Result:** <verified success | partial: which partial wins | negative: what was ruled out |
impossible or infeasible: the argument | budget spent>
**Tried:** <candidate: test: measured result: verdict, one line each, baseline included>
**Evidence:** <each claim and how it was verified; anything unverified or simulated says so>
**Untested:** <candidates left in the pool, each with its cheapest next experiment>
**Next shot:** <the most promising continuation and why>
```

A clean negative result with an honest log is a real outcome: say what it rules out. Keep the report
sober; the encouragement was for the attempt, and the report is for the reader.

## Limits

- **The check stays fixed.** Never edit tests, benchmarks, checkers, or data to pass; never
  hardcode outputs, special-case the checker, or skip or mark a failing case as expected. If the
  goal must change, say so and report against the original too.
- **Unconventional is not unauthorized.** An out-of-pocket idea changes how the goal is reached,
  never who may do what. Permission denials, sandbox or network blocks, missing credentials,
  security controls, licenses, quotas, rate limits, terms of service, and other people's accounts
  are not obstacles to route around, even when asked to find a way; ask for the access instead,
  and stay inside the scope the user set.
- **Try changes on copies.** A new way of working is a proposal until its owners adopt it: try it on
  data, in a simulation, or on a copy, never by changing shared settings, pipelines, schedules,
  ownership rules, or production systems.
- **Scratch stays scratch.** Experiments go where the user can see and delete them, outside tracked
  source unless the task is to change it; one that needs its own repository or service gets a
  throwaway one in scratch. Never commit the user's work.
- **Encourage the work, not the user.** No flattery, no promises, nothing called close without
  evidence, and no idea sold as better than the usual way before a try shows it.
