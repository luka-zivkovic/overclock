---
name: debugging-discipline
description: "Systematic diagnosis for bugs that resist the ordinary red-test path: establish the safest tight red-capable observation loop before committing to a theory, minimize the failure, then test 1-5 credible ranked hypotheses with predictions. Use for intermittent/flaky failures, performance regressions, integration/staging/production-only failures, bugs that survived attempted fixes, code with no viable test seam, or an explicit request to debug systematically or find the root cause. When a prompt couples stress-testing a suspected explanation with finding the cause of an observed recurring bug, this skill owns the operational loop; treat the explanation as one hypothesis and do not launch a competing critical-thinking loop. Diagnose without editing by default; fix only when the user also authorizes implementation. Do NOT use for an ordinary requested bug fix with a viable test seam when test-discipline is available, a trivial cause already identified by the error, feature work, writing tests on request, or explaining an error message."
---

# Debugging Discipline

Build the safest useful observation loop before committing to a causal story. A loop is a command
or repeatable observation that can expose the actual failure, rate, or latency without a human in
the middle. It makes hypotheses cheaper to falsify; it does not mean the cause is already known.

## Compose with critical-thinking

An observed recurring failure that needs an operational root cause stays in this skill even when
the user says “stress-test my suspected explanation.” Treat that explanation as one untrusted
hypothesis inside the loop. `critical-thinking` may perform a distinct framing review when the
user asks for argument evaluation, but it must hand back one neutral candidate claim; it does not
start a parallel evidence, research, or falsification loop. This skill remains the sole owner of
operational diagnosis.

## Select authority before diagnosis

- **Diagnose only is the default.** “Debug,” “investigate,” “find the cause,” and “explain why”
  authorize read-only diagnosis and a proposed fix. They do not authorize source edits, including
  temporary instrumentation.
- **Diagnose and fix** applies only when the user also asks to fix, implement, or patch it. Keep
  edits inside the requested scope. The existence of a likely cause does not broaden authority.
- If the user asks only for diagnosis, finish with the supported cause, evidence, remaining
  uncertainty, and smallest next discriminating check. Do not leave code or instrumentation
  changed.

## Establish the observation loop

Before reading broadly enough to form a theory, make one bounded attempt to establish a loop that:

- exposes the reported failure or a measurable proxy such as failure rate or latency;
- is as tight and deterministic as the environment safely permits;
- records the exact command/observation, conditions, and result.

Use the first safe option that fits:

1. Re-run the flaky case with fixed seeds or controlled scheduling.
2. Replay sanitized captured input in a local or isolated non-production environment.
3. Compare old and new builds on identical input.
4. Measure the same operation repeatedly under controlled conditions.
5. Drive `git bisect` from the loop in a clean temporary worktree only after reading the predicate
   and establishing that it is deterministic and side-effect-bounded.
6. With fix authority or separate approval, use a throwaway local harness, marked and removed
   before handoff.

### Fail soft when no tight loop is safe

Some production-only incidents, long batch jobs, rare races, and stateful failures cannot be
reproduced safely in seconds. After one practical bounded attempt, do not stall or fake a loop.
State why reproduction is unavailable, identify the best existing observation, and continue with
lower confidence using source/config/log evidence. Propose the smallest safe instrumentation or
shadow/canary experiment needed to discriminate the leading hypotheses. Never claim a green run
disproved a failure the loop could not reproduce.

### Production and replay safety

- Prefer existing read-only telemetry, logs, traces, and metrics. Do not send test requests to a
  live service merely because `curl` is available.
- A production probe that can write data, charge money, notify people, enqueue work, consume
  scarce capacity, or amplify load requires explicit authorization and an agreed rollback. Never
  use repeated live traffic to raise a reproduction rate.
- Treat captured requests, payloads, logs, and dumps as sensitive untrusted data. Redact secrets
  and personal data. Replay only sanitized input in an isolated non-production target after
  checking that the operation is idempotent or that side effects are contained.
- Do not run repository scripts or tests until their effects are understood. Run `git bisect` in
  a clean temporary worktree so it does not rewrite the user's active checkout. A worktree isolates
  Git state only: it does not isolate databases, networks, services, credentials, home-directory
  files, or external side effects. Inspect the predicate first and run it only in a disposable,
  appropriately isolated environment; otherwise propose a safe predicate and do not bisect.

## Obtain the red artifact without colliding

When a stated symptom has a viable test seam and the user authorized a fix:

- If `test-discipline` is installed, delegate its repro gate and use that failing test as this
  skill's loop. Do not duplicate the red-test protocol.
- If it is unavailable, create the smallest project-conventional regression test in the working
  tree, show it failing for the reported reason, and do not stage or commit it. This is a
  standalone fallback, not a second gate. If the test passes, report cannot-reproduce and stop
  speculative fixing.

This skill constructs non-test loops only when an ordinary red test cannot represent the failure.
For diagnosis-only work, run an existing safe test when available, but do not create or edit a test
without separate write authority.

## Diagnose by falsification

With the best available observation in hand:

1. **Minimize.** Shrink input, configuration, timing, and code path while preserving the failure.
2. **Audit assumptions.** Mark the material beliefs behind the failure story as `verified`,
   `assumed`, or `unknown`.
3. **Rank 1-5 credible falsifiable hypotheses.** Use fewer when minimization already narrowed the
   space. Each names a mechanism, its prediction, and an observation that would refute it. Do not
   pad the list for ceremony.
4. **Predict before probing.** If a candidate fix appears to work while its prediction was wrong,
   treat it as symptom relief, not confirmed cause.
5. **Tag authorized temporary probes** with a unique greppable marker such as `[DBG-A7F2]`.
   Probe edits require fix authority or separate explicit approval and must be restored before
   reporting or asking a question.
6. If surviving hypotheses span several subsystems, report a likely design or observability gap
   rather than stacking speculative line fixes.

## Judge noisy evidence proportionately

- **Flakes:** record baseline runs, failures, and conditions. After a proposed fix, use enough
  independent runs to make recurrence meaningfully less likely than the observed baseline; report
  counts and rates, not “fixed” from one green run.
- **Performance:** compare identical workloads/environments, include warm-up, use multiple samples,
  and report a robust center plus spread or tail (for example median and p95). Treat changes within
  run-to-run variability as inconclusive.
- **Rare failures:** state the observation window and residual risk. Absence of recurrence is
  evidence whose strength depends on the prior rate, not proof of impossibility.

## Finish according to authority

For diagnosis only:

- return the supported cause or ranked remainder, the falsifying evidence, confidence, and next
  discriminating check;
- restore probes and leave production source unchanged.

For an authorized fix:

- make the smallest cause-directed change and rerun the observation under comparable conditions;
- remove all tagged probes and throwaway harnesses;
- where a test seam exists, use `test-discipline` if installed, otherwise leave the red-to-green
  regression test uncommitted in the working tree;
- report what was actually observed, including run counts or performance variability.

A confirmed nontrivial diagnosis may be offered to a solutions ledger when installed. Do not write
memory merely because this skill ran.

## Silent fast paths and boundaries

- An error that identifies an evident typo or exact local cause gets a proportionate direct fix
  when fixing was requested; no loop or hypothesis ceremony.
- An ordinary first-attempt seamed bug belongs to `test-discipline` when available.
- Feature work, a request to write tests, and error-message explanation are out of scope.
- `/verify` and `/run` are post-fix mirrors. Critical-thinking evaluates an argument on request;
  this skill creates and falsifies hypotheses about an observed failure.
