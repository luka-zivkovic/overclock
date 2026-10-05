# Skunk Works skill implementation and evaluation plan

Status: proposal; no candidates implemented or validated by this document

Prepared: 2026-10-05

Repository baseline: `e3fd1f1` on `origin/master`

## Objective and decisions

Develop three independently useful skills: `first-flight`, `vendor-bakeoff`, and
`migration-forecast`. Investigate `verification-map` as a fourth candidate. Each should own a
different task, produce observable evidence, and earn publication independently. There is no
requirement to choose only one or bundle them into a general project-management skill.

The maintainer requested independent Codex and Claude Code suggestions, their comparison, and
this plan. Claude was consulted through Agent Bridge without receiving Codex's candidate list.
Both ranked `first-flight` first and proposed completion forecasting and declared exceptions;
Claude added `vendor-bakeoff` and `lean-crew`, while Codex added `verification-map`. The comparison
narrowed forecasting to migrations and retained exceptions and crew sizing as possible
enhancements. Agreement between agents is design input, not evidence of effectiveness.

This PR adds only a planning document. It does not publish skills, change routing, or replace the
build/no-build authority of [strategy.md](strategy.md). Record adopted candidate decisions there
when implementation begins. [SHORTLIST.md](brainstorm/SHORTLIST.md) remains historical evidence,
not an implementation queue. The direct request supplies a reason to explore these workflows;
novelty, memory, and a marketplace moat are not acceptance requirements.

## Source and interpretation

The source is Lockheed Martin's
[Kelly's 14 Rules](https://www.lockheedmartin.com/content/dam/lockheed-martin/aero/photo/skunkworks/kellys-14-rules.pdf).
The proposed workflows are software adaptations, not claims that Kelly prescribed agent behavior.

| Original principle, paraphrased | Proposed application |
|---|---|
| Rule 9: test the product in flight early | Prove consequential integration assumptions with a runnable slice |
| Rule 7: take responsibility for obtaining good vendor bids | Compare components on representative workloads |
| Rule 6: review spent, committed, and projected completion costs | Forecast remaining migration work from comparable observations |
| Rule 8: allocate inspection responsibility and avoid duplication | Map failure modes to verification evidence and uncover gaps |
| Rules 10 and 5: agree specifications and exceptions; record important work | Make accepted exclusions distinguishable from unmet obligations |
| Rules 1, 3, 12, and 13: clear authority, small teams, liaison, controlled access | Give delegated work a purpose, owner, and bounded context |

## Portfolio and repository fit

| Workstream | Deliverable | Initial packaging | Priority |
|---|---|---|---|
| `first-flight` | A working slice and evidence of what it proves | One standalone skill and plugin | 1 |
| `vendor-bakeoff` | Reproducible comparative measurements and a bounded conclusion | One standalone skill and plugin | 2 |
| `migration-forecast` | An inventory, category-specific forecast, and approach options | One standalone skill and plugin | 3 |
| `verification-map` | A source-backed map of failure modes, checks, and gaps | Experiment first; separate skill if useful | Discovery |
| Declared exceptions | Proposed/accepted exclusions and undeclared deviations | Possible `feature-dossier` enhancement | Contingent |
| Crew sizing | Purpose and scope for each delegation | Possible `agent-bridge` reference enhancement | Deferred |

The clean baseline includes `api-bench` and `untangle`, which were absent from the initial local
inventory. Account for them explicitly. `feature-dossier` exists in the maintainer's local work
but is absent from this baseline; do not treat it as a published dependency or include that
unrelated work in these PRs. Recheck its status before implementing the contingent enhancement.

Each new skill must work without another portfolio member. Initially use narrow, model-invoked
descriptions with positive triggers and anti-triggers. For `vendor-bakeoff`, `migration-forecast`,
and `verification-map`, those triggers require a request for the specific experiment, forecast,
or audit; an ordinary recommendation, migration implementation, or test edit is insufficient.
`first-flight` may trigger during qualifying new-feature implementation. Keep explicit invocation
available for every skill. If implicit routing cannot be made selective, evaluate a user-invoked
version with matching policy metadata rather than broadening its ownership.

## 1. First Flight

**Contract:** build the smallest executable path that tests a consequential assumption, then keep
that path working as the requested feature grows. Own the order of implementation, not a second
general planning methodology.

1. Identify the new feature's consequential uncertainty and its observable success condition.
2. Choose the thinnest slice through a real entry point that can test it. Name the real components,
   any stubs, and the exact claim each permits. Do not select a convenient but irrelevant demo.
3. Implement and execute that slice within the user's implementation scope before adding breadth.
4. Record the command, observation, outcome, environment, and unresolved assumptions. Re-execute
   after changes that affect the path; avoid ritual reruns after unrelated edits.
5. Report separately what ran successfully, what failed, what was simulated, and what remains
   untested. Keep the evidence in the response or an already-authorized project artifact.

**Example:** before building a billing interface, exercise sandbox checkout, signature verification,
entitlement persistence, and the access check. A stubbed checkout can establish local wiring, but
cannot establish the payment provider's behavior.

**Routing:** substantial new features/integrations with an executable entry point and a material
uncertainty; exclude ordinary bug fixes, refactors, copy changes, UI polish, already-proven plumbing,
and requests only for a mockup. A small file count alone does not exclude a risky integration.

**Neighbors:** `test-discipline` owns its existing-code test gates; `debugging-discipline` owns
resistant bugs. `api-bench` owns standalone model-request simulations and prompt comparisons.
An application integration using a model can still qualify here, but a model transcript alone
does not prove the application's surrounding path. Respect any installed implementation workflow;
add the early executable milestone rather than replacing its planning and review phases.

**Implementation:** a concise core procedure and a directly linked evidence format. Add a helper
only for a demonstrated deterministic need; do not build a universal application runner.
Missing credentials or an unavailable environment yield an honest blocked observation or a
clearly labelled local simulation, never a fabricated successful flight.

**Acceptance cases:** a CLI with a planted config-path defect; an HTTP integration with a contract
mismatch; a worker with a persistence boundary; a mocked success that does not establish the
chosen assumption; an unavailable service; and trivial-edit/bugfix negatives. Measure whether
the relevant path ran before unrelated implementation expanded, when a material defect was found,
and whether the final feature still meets its requirements. Do not optimize a raw files-written
or tool-call count at the expense of completion quality.

## 2. Vendor Bakeoff

**Contract:** compare two to four executable alternatives against the same acceptance criteria
and representative inputs. Produce measurements that help choose a component; allow ties,
inconclusive results, and no qualifying candidate.

1. Establish the decision, candidates, hard constraints, representative data, and execution budget.
2. Freeze the comparison protocol before examining outcomes: correctness criteria, allowed
   candidate-specific setup, relevant performance/cost measures, and repetition policy.
3. Build a small harness in a task-owned scratch area. Pin versions and record environment and input
   provenance. Apply equivalent workloads; report tuning differences and failed runs.
4. Run within the authorized local/network scope. Preserve raw measurements and enough commands
   to reproduce them; distinguish measured results from documentation claims and estimates.
5. Report hard-constraint failures before tradeoffs. Explain what the sample cannot establish.

**Example:** compare PDF text extractors on scanned documents, tables, and ordinary text pages,
using expected outputs and separately measured runtime. The fastest wrong output cannot win.

**Routing:** explicit requests to benchmark or experimentally compare libraries/services on a
concrete workload. Exclude general recommendations, documentation questions, supply-chain audits,
and comparisons with no feasible measurable outcome. Offer an experiment design when execution
is unavailable, clearly marked as unrun.

**Neighbors:** `critical-thinking` owns broad consequential recommendations; this skill owns the
requested empirical comparison and conclusions supported by that experiment. Pure model-prompt,
tool-schema, and model API transcript comparisons remain with `api-bench`. Do not recreate its
provider loop. Cross-provider coding-harness consultation remains with `agent-bridge`.

**Implementation:** a protocol template and result schema, with a small result validator if needed.
Use native benchmark tools and task-specific adapters; avoid a generic package-installation or
benchmark platform. Results distinguish correctness, performance, cost, setup effort, and unknowns
instead of hiding them inside an arbitrary composite score.

**Acceptance cases:** a fast but incorrect candidate; a failure on one input category; noisy timings;
unequal default configuration; no candidate meeting constraints; and missing credentials/budget.
Routing negatives include a general recommendation and an `api-bench` prompt comparison. Check
reproducibility and the validity of the decision, not merely the presence of a results table.

## 3. Migration Forecast

**Contract:** estimate remaining repetitive engineering work using comparable observations,
separating mechanical cases, exceptions, and unknowns. Remain read-only on the target project.

1. Define the migration unit and completion criteria, including integration and final verification.
2. Inventory completed and remaining units from code, tests, and supplied work records. Deduplicate
   matches and label inference; a grep hit is a candidate unit, not automatically unfinished work.
3. Classify cases by materially different effort. Inspect a representative sample of each category
   and expose selection bias, dependencies, and unobserved categories.
4. Use supplied or measured effort in explicit units. Compute ranges per category and identify the
   work for which no credible estimate exists. Do not use commit timestamps or session counts as
   elapsed engineering time, or convert effort into calendar dates without availability data.
5. Present the current approach alongside evidence-supported alternatives such as a codemod,
   reordered work, or a narrower scope. Do not implement or silently adopt those alternatives.

**Example:** a Jest-to-Vitest migration has straightforward conversions, custom mocks, and
integration suites. Forecast each category separately and include final integration work rather
than extrapolating one average from the easiest completed files.

**Routing:** an explicit forecast/remaining-effort request for a repetitive migration, bulk upgrade,
or comparable refactor. Exclude ordinary migration implementation, general roadmaps, trivial work,
token billing, and requests to preserve session state. Missing effort data can still yield a useful
inventory and sampling plan, but not a fabricated time estimate.

**Neighbors:** `session-handoff` preserves working state; it does not own this forecast. `untangle`
owns whole-repository direction and its checklist; this skill takes a settled migration scope and
does not reopen keep/park/delete decisions. Read an existing plan when supplied; create no competing
roadmap or persistent progress ledger.

**Implementation:** an inspectable inventory and a small deterministic estimator for supplied
category counts and effort bounds, with tests for units, arithmetic, missing data, and impossible
inputs. Repository-specific discovery can use existing search/AST tools without importing another
skill's scripts. Report forecast assumptions and the provenance of every numerical input.

**Acceptance cases:** homogeneous work; easy cases completed first; an unseen difficult category;
missing timing data; partial/reverted conversions; and scope added after the forecast. Use frozen
historical cutoffs without future leakage, then compare with later outcomes. Deterministic arithmetic
tests establish mechanics only; categorical judgment and forecast usefulness require rubric evidence.

## 4. Verification Map discovery

**Contract to investigate:** map important failure modes to their owners, existing checks, and
remaining evidence gaps. Focus on one bounded service/integration/pipeline, not a generic audit
of the entire repository. The report never removes tests or weakens a gate.

Start with one concrete suite supplied during implementation and a synthetic fixture containing
both a missing boundary check and intentional overlapping coverage. Trace each important behavior
to source and actual assertions, including mocks and execution environments. Distinguish absence
of inspected evidence from proof that a check is absent everywhere.

The report should list failure mode, responsible layer, check and source anchor, what it proves,
and the remaining gap. Suggest consolidation only where equivalent protection is established.
Independent checks, defense in depth, and tests at different boundaries are not waste merely
because they have similar names or assertions.

Explicit verification-ownership audits qualify; routine test writing, single-regression diagnosis,
diff review, and generic requests to make CI faster do not. `test-discipline` continues to own its
test gates. Do not revive the parked contract-review experiments or claim PR-review lift: the
output is a bounded verification map, not an automatic second reviewer.

Promote to a standalone candidate only if the report finds actionable, source-valid gaps and
preserves necessary independent coverage. Otherwise narrow or park it with the observed result.
Candidate cases must include a complete suite that should produce no gap, dynamic test discovery,
mocked boundaries, and deliberate duplicate protection. No generic checklist counts as success.

## Smaller enhancements

**Declared exceptions:** after `feature-dossier` lands, inspect its current contract before changing
it. Add only missing support for proposed/accepted exclusions, rationale, consequences, acceptance
provenance, and revisit conditions. Preserve approved requirements until the user adopts a change;
an unexplained omission remains an unmet obligation. Reuse existing decisions/deviations instead
of adding a parallel ledger. Add a live case for an undeclared omission and a negative against
self-approved scope reduction. `groundwork` may carry the same information in its brief if a real
gap exists, but receives no speculative change in this plan.

**Crew sizing:** defer a standalone `lean-crew`. If a delegation enhancement is implemented, require
a distinct reason for every worker: specialization, separable implementation, or independent
checking. Intentional independent review may repeat coverage. Preserve the requested review
intent, provider authorization, ownership, and path boundaries. Do not introduce automatic fan-out,
remove an explicitly requested reviewer, or widen `agent-bridge` into an orchestration engine.

## Evaluation and promotion contract

The recommendations in this document have **subjective** evidence: no measured gain is claimed.
Future behavioral changes use the **rubric** tier, supplemented by **objective** checks for helper
mechanics, file state, arithmetic, provenance, and scope. Follow
[skill-authoring-notes.md](skill-authoring-notes.md#evidence-tiers-for-skill-changes); a command log or
valid JSON alone does not establish behavioral quality.

For each candidate, commit its contract, cases, frozen fixtures, rubric, and numerical acceptance
thresholds before live runs. Use the existing QA harness rather than creating another eval stack.
Suggested initial gate, to freeze in that candidate's experiment record:

- All deterministic checks and authority/scope controls pass; zero fabricated evidence or
  unauthorized writes, external calls, commits, or publication.
- At least ten adjudicated behavioral cases spanning positive, negative, unavailable-input, and
  misleading-evidence scenarios. Use an independent judge and human adjudication for disputed
  outcomes; the authoring context must not grade its own candidate.
- Paired baseline/candidate runs on at least three distinct substantive tasks, under equivalent
  model, effort, tool, and budget conditions. Require useful improvement on at least two tasks,
  no material regression on any task, and no negative-control regressions. Report ties and costs.
  This is an initial pilot gate, not a claim of statistical generalization.
- Routing precision at least 90%, recall at least 80%, and specificity at least 90%, with zero
  selections outside each prompt's declared ownership. Freeze prompt ownership before running.

Every behavioral suite and routing battery needs isolated `skill` evidence. A multi-skill or
hook-bearing owner also needs `plugin` evidence; declared external composition needs `stack`
evidence. Single-skill, hook-free plugins still need target-only evidence. Keep sibling bodies,
hooks, and group descriptions out of isolated packages. Test the relevant ownership boundaries
against installed neighbors and, when available, the other candidates; an absent optional sibling
must have a safe standalone fallback or explicit scope stop.

Commit concise experiment results and limitations. Raw generated material belongs under
`qa/_work/` and stays uncommitted. A failed or unavailable live run is not a pass; record it and
fix the demonstrated problem or retain the candidate as unpublished. Do not relax a frozen gate
after seeing results; a revised hypothesis needs a new record and fresh confirmation cases.

## Implementation sequence and PR boundaries

1. **Candidate PR: First Flight.** Record the proposed decision in `docs/strategy.md`; add the
   standalone draft under `qa/experiments/first-flight/`, contract, cases, fixtures, rubric, and
   routing controls. Run the pilot and commit a result before preparing its publication change.
2. **Candidate PR: Vendor Bakeoff.** Repeat under `qa/experiments/vendor-bakeoff/`, with the
   `api-bench` ownership boundary and a reproducible local comparison. It does not depend on
   First Flight landing.
3. **Candidate PR: Migration Forecast.** Repeat under `qa/experiments/migration-forecast/`,
   beginning with inventory/estimator mechanics and historical-cutoff cases before live forecasts.
4. **Discovery PR: Verification Map.** Put the bounded pilot under
   `qa/experiments/verification-map/`; record promote/narrow/park with evidence. No shipping
   skeleton is needed just to conduct the discovery.
5. **Publication PR per passing candidate.** Move its standalone distribution to
   `plugins/<name>/skills/<name>/`, add the plugin manifest and published eval/battery paths,
   and update strategy with the observed outcome. A candidate may ship while others remain parked.
6. **Enhancement PRs only for demonstrated gaps.** Handle declared exceptions after its owner is
   available; handle crew sizing if the delegation workflow needs it. Keep these independent from
   the new plugins and their acceptance claims.

The order expresses priority, not a requirement for every candidate to wait for every earlier
candidate. This plan does not authorize automatic paid runs or implementation of the skills in
the documentation PR. Choose concrete pilot repositories/fixtures and run budgets in the relevant
candidate PR; no additional speculative demand count is required.

## Distribution, authority, and release checklist

Each published skill carries a focused `SKILL.md`, quoted `agents/openai.yaml` display name and
25–64 character short description, and a one-sentence default prompt naming `$<skill-name>`.
Invocation policy must agree across harnesses. Keep branch detail in directly linked references,
deterministic helpers in scripts, and reusable formats in templates/assets. All runtime dependencies
must resolve inside the installed skill directory. Do not create a shared catchall reference or
new hooks for these candidates.

First Flight inherits only the user's authorized implementation scope. Vendor Bakeoff writes only
its task-owned experiment artifacts; target application changes are separate work. Migration
Forecast and Verification Map inspect the target read-only. Any saved report needs an authorized
path. None commits, pushes, publishes, deploys, or silently changes requirements. External data
sharing and paid operations stay within established conversation authorization and explicit caps;
credentials never enter committed artifacts. Preserve existing files and unrelated work.

Keep candidates outside `plugins/` until their publication PR: any change under a published plugin
is a shipping change. Publication requires the matching manifest and marketplace versions,
synchronized setup capabilities, the consequent `overclock-setup` version bump, relevant changelog
entries, and accurate README evidence counts. Recheck symmetric package conflicts and intentionally
shared files if any affected owner uses them. The present docs-only PR needs no version bump.

Run the full [maintainer validation suite](../AGENTS.md#validation) for every implementation PR:

```bash
for d in plugins/*/skills/*/; do python3 tools/validate_skill.py "$d"; done
python3 tools/audit_skills.py plugins --fail-on fail
python3 tools/check_shared_files.py
python3 tools/check_doc_claims.py
python3 tools/check_setup_catalog.py
python3 -m unittest discover -s qa -p 'test_*.py'
python3 tools/check_version_bump.py --base origin/master
npx casefile@0.2.1 scan . --config casefile.config.json --fail-on warning --no-store
```

Run the casefile scan on a clean tree or archive so generated Python caches are not mistaken for
bundled binaries. When manifests or marketplace metadata change, also run `claude plugin validate .`
and validate every affected plugin directory when the CLI is available. Passing structural checks
does not replace live behavior/routing evidence. Publication is complete only when the candidate's
frozen evidence gates and release checks both pass, with limitations recorded in its PR.
