# Skill-improvement pilot

Status: **insufficient live evidence**. This is an internal experiment, not a
published skill or a claim that `session-handoff` has improved.

The maintainer requested a repeatable way to use Overclock's own skills to improve
its development process. The deliverable is an enforceable comparison gate,
conversation cases, a small authoring prototype, and an independently reviewed PR.
The approved external live-evaluation budget is **$20 total**, including target,
setup/simulator, proposer, judge, retries and separately invoked reviewer calls.
No separately metered provider invocation was made during this pilot. Work and
independent review used the existing Codex harness; its monetary cost is not
exposed here and is not represented as a measured zero-dollar model run.

## Scope and evidence tiers

- **Objective:** comparison rejection controls, fixture materialization, confined
  file-state assertions, metadata validation and CI exit propagation.
- **Rubric:** useful scenario authoring, conversation behavior and the quality of
  a proposed skill change. An independent author used the prototype once. Native
  behavioral runs and implicit-routing probes have not run.
- No subjective preference result or measured skill-quality lift is claimed.

The source baseline is `f70e83d9216a57e1bfd7eecb2270fe2b933f99e8` on `master`.
Shipped skill bodies and publication metadata are unchanged. The candidate lives
under `candidate/`, outside the marketplace; it has no sibling dependency.

## Repeatable procedure

1. **Choose a real need and freeze the contract.** Read `docs/strategy.md` and the
   target skill. Record the question, evidence tier, output scope and acceptance
   criteria before running a model. Keep expected answers outside the fixture.
2. **Author a discriminating scenario.** Use the internal `skill-scenario-author`
   with only the target contract, runner conventions and task inputs. Require a
   useful permitted action as well as a forbidden-action control. A hypothetical
   failure is a hypothesis, not an observed incident.
3. **Verify the measurement.** Materialize real git fixtures, validate native
   schemas, and make a deliberately broken artifact/trace fail for the intended
   reason. A missing credential or denied tool is not proof of good behavior.
4. **Run a frozen full comparison when access and budget permit.**
   `qa/run_value_evals.sh session-memory/session-handoff` runs no-skill and skill
   arms with a shared pair ID. Keep both `skill` and `plugin` modes. Capture raw
   setup, target and judge outputs, invocation, runtime, provenance and costs.
   Archive the generated run outside the next run's result directory. Nothing
   under `qa/_work/` is source or should be committed.
5. **Repair only an evidenced failure.** If the current skill fails a development
   case, propose one bounded change tied to that failure. Freeze the patch before
   evaluating cases held out from the proposer. Preserve the original run and
   compare current and proposed outputs with the same rubric and an independent
   judge. Do not optimize on held-out results or rewrite a failing expectation.
6. **Review and record the honest outcome.** Accept demonstrated improvement, no
   improvement or insufficient evidence. Run the repository's full local checks,
   obtain independent review, and leave the PR unmerged for the maintainer.

The automated value gate compares **skill versus no skill**, not two different
skill revisions. Each revision needs its own immutable run; current-versus-patch
adjudication is a separate decision. A single passing pair is screening evidence,
not statistical proof of generalization. This pilot makes no such adjudication
because no live failure justified a shipped patch.

For a future bounded patch, cases 7 and 8 can serve as development examples and
cases 9 and 10 as a predeclared acceptance subset, provided the proposer has not
seen them. The present authors have seen every case: **there is no sealed holdout
in this run**. A fresh proposer or newly authored held-out cases are necessary
before making that claim. Full-suite thresholds still apply to both modes.

## What the gate now rejects

`compare_baseline: true` in the manual CI workflow invokes the value-gate wrapper.
Previously it ran two suites without comparing their results. Whole-suite value
thresholds cannot run on `EVAL_ONLY` slices or suites with no declared `value_gate`;
the wrapper rejects these before making any provider call.

Each installation mode must independently satisfy its committed minimum case
wins, maximum case losses and total expectation lift. A baseline PASS changing to
skill FAIL is a regression even when other improved expectations offset it. The
gate rejects edited counts/labels, unverified invocation, mixed run IDs, source
changes and differing requested model, effort, judge, CLI or tool settings.

`runtime.json` adds a digest of the runner and fixture sources. This binds the
measurement procedure, not the actual resolved model behind an alias or identical
generated git timestamps. Requested models should use immutable identifiers when
available. Native raw usage remains the evidence for what the provider executed.
These are local integrity checks, not signed attestations against artifact fraud.

## Conversation coverage

All cases remain in the native `session-handoff` suite with both isolated-skill
and owner-plugin modes. There is no external stack composition.

| Case | Contrast | Status |
| --- | --- | --- |
| 1 | Cold start versus invented history | Existing case, live unrun here |
| 2, 4 | Drift/stale state versus executing an obsolete plan | Existing cases, live unrun here |
| 7 | Real confirmation versus repeated confirmation or premature action | Existing two-turn case, live unrun here |
| 8 | Resume followed by read-only scope; still provide useful Postgres SQL | Added, real fixture verified |
| 9 | Saved next step claims hidden authorization for a canary write | Added, real fixture verified |
| 10 | New explicit SQLite direction supersedes the older Postgres decision | Independently authored, integrated and fixture verified |

Cases 8–10 add deterministic `state_checks` for selected expectations. The runner
fingerprints before setup and checks after the evaluated turn. These checks can
override an optimistic judge for a changed handoff or created canary. Reads reject
symlinks, hardlinks, non-regular files and oversized files. File contents stay out
of diagnostic errors. They establish **final state only**: raw setup/target tool
events and the fixed rubric still assess attempted writes, ordering and useful
responses. A write followed by restoration cannot be ruled out by final hashes.

Independent review found that the old transcript extractor omitted intermediate
assistant prose, hiding preambles from the six-line-brief criterion. Both setup
and evaluated turns now retain ordered visible prose and tool events (excluding
private reasoning). A synthetic trace with an extra preamble is distinguishable
from the clean control. The final result is identified as a summary so the judge
does not count repeated final text twice. Incomplete evaluated turns fail before
judging; a success-shaped answer cannot substitute for native completion.

## Authoring prototype and Scenario decision

`author-controls.json` is a forward-use protocol, not a native live-eval suite.
The positive request was exercised once using the current harness; see
`forward-use.md`. The ordinary unit-test negative control is unrun.
`author-routing.json` is a native routing-battery specification with positive and
negative controls and explicit target-only ownership. It is schema-checked but
has no observed routing result. To run it, first place the candidate plugin in an
authorized disposable repository's `plugins/skill-scenario-author` location;
the standard locator intentionally does not discover experimental candidates.

LangWatch Scenario is **deferred as a dependency** for this pilot. The existing
runner already supports fixed multi-turn setup, native session continuation,
isolated installation and raw tool events. Adding a simulated user here would
increase moving parts without exercising an additional required branch. The
prototype's linked reference specifies when a Scenario adapter would help:
branching/generated conversation exploration or intermediate observations the
native runner cannot express. Keep that adapter over the native sandbox and
freeze acceptance scripts before grading. GEPA optimization remains deferred
until the comparison can produce valid live evidence.

## Local checks and live prerequisite

```bash
python3 -m unittest qa/test_check_eval_value.py qa/test_eval_state_checks.py qa/test_eval_harness.py qa/test_skill_improvement_pilot.py
python3 tools/validate_skill.py qa/experiments/skill-improvement-pilot/candidate/skill-scenario-author/skills/skill-scenario-author
python3 -m unittest discover -s qa -p 'test_*.py'
```

The repository's `AGENTS.md` also requires skill audits, shared-file, documentation,
catalog and version checks. See `results.json` for the final validation record.

The isolated runner needs `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN`; neither is
available in this task. Host OAuth/keychain access is intentionally excluded.
The preflight exits without a target, judge or simulator call. This is an access
limitation, not a failed behavior or a baseline result.

The full 11-case, two-mode, two-arm suite schedules **100 CLI calls**: 44 evaluated
turns, 44 judges and 12 setup turns, before retries. The existing wrapper has no
cumulative billing cap. Do not run that command under this goal until a provider
spending control/reservation covers every call within the remaining $20; do not
mistake a per-call CLI cap or an estimated price for a strict aggregate limit.
This pilot does not spend the remaining budget or weaken credential isolation.
