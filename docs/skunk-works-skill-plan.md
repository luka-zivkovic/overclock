# Skunk Works skill implementation and evaluation plan

Status: proposal; one build candidate (`first-flight`), three parked candidates. Nothing is
implemented or validated by this document.

Prepared: 2026-10-05. Usefulness audit applied: 2026-10-06
([record](brainstorm/skunk-works-audit-2026-10-06.md)).

Repository baseline: `e3fd1f1` on `origin/master`

## Objective and decisions

Build `first-flight` as a standalone skill. Keep `vendor-bakeoff`, `migration-forecast`, and
`verification-map` on record as parked candidates with explicit gates, in the sense
[strategy.md](strategy.md) gives PARKED: real, not now, and here is what changes the answer. Each
candidate owns a different task; none depends on another, and a parked candidate may be built
later without reopening this plan.

The maintainer requested independent Codex and Claude Code suggestions, their comparison, and
this plan. Claude was consulted through Agent Bridge without receiving Codex's candidate list.
Both ranked `first-flight` first and proposed completion forecasting and declared exceptions;
Claude added `vendor-bakeoff` and `lean-crew`, while Codex added `verification-map`. The comparison
narrowed forecasting to migrations and retained exceptions and crew sizing as possible
enhancements. Agreement between agents is design input, not evidence of effectiveness. The
2026-10-06 audit then ran each candidate through the brainstorm gauntlet (in-kit collision,
baseline behaviour, ecosystem grounding, scenario simulation, right-sizing probes) and produced
the verdicts recorded below.

This PR adds only a planning document and its audit record. It does not publish skills, change
routing, or replace the build/no-build authority of [strategy.md](strategy.md). Record adopted
candidate decisions there when implementation begins. [SHORTLIST.md](brainstorm/SHORTLIST.md)
remains historical evidence, not an implementation queue; its rows for these four candidates
point back to the audit record. The direct request supplies a reason to explore these workflows;
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

| Workstream | Verdict (2026-10-06) | Smallest form that delivers the value | Gate |
|---|---|---|---|
| `first-flight` | **STRONG**, build | One standalone model-invoked skill and plugin | Routing battery at the thresholds below; declared seams with `to-tickets`, `prototype`, `tdd`, and `api-bench` |
| `vendor-bakeoff` | PARKED, lean build later | Short model-invoked skill plus protocol and results templates; no runner script | The next real bake-off request, built on that workload; `api-bench` anti-trigger edit in the same PR |
| `migration-forecast` | PARKED | An instruction line or short checklist, not a skill | A real migration surfacing the need twice; the effort estimator is dropped |
| `verification-map` | PARKED, discovery optional | User-invoked skill with a fixed table and advisory anchors | One synthetic-fixture run at roughly ten dollars with the stop signal below |
| Declared exceptions | Contingent, not audited | Possible `feature-dossier` enhancement | `feature-dossier` landing on master |
| Crew sizing | Deferred, not audited | Possible `agent-bridge` reference enhancement | A demonstrated delegation gap |

The clean baseline includes `api-bench` and `untangle`, which were absent from the initial local
inventory. Account for them explicitly. `feature-dossier` exists in the maintainer's local work
but is absent from this baseline; do not treat it as a published dependency or include that
unrelated work in these PRs. Recheck its status before implementing the contingent enhancement.

**Prior verdicts this plan must respect.** [SHORTLIST.md](brainstorm/SHORTLIST.md) already holds
three judged neighbours of `first-flight`, all from the 2026-07-19 external evaluation:
`to-tickets` (BUILD-IN-OVERCLOCK, gated on demand) decomposes a spec into tracer-bullet
vertical-slice tickets across sessions; `prototype` (ADOPT-AS-IS) writes throwaway code that
answers one question and is then discarded; `tdd (seam-disciplined)` (BUILD-IN-OVERCLOCK) is
test-first feature work with pre-agreed seams. `first-flight` is distinct from each: its slice is
kept and grows into the feature, it chooses which slice executes first inside one feature and
what that run proves, and it owns execution order rather than red/green per unit. Those seams
must appear in its description and its routing negatives. If `to-tickets` or `tdd` ships later,
the three descriptions must be re-read together.

`first-flight` uses a narrow, model-invoked description with positive triggers and anti-triggers
and keeps explicit invocation available. If implicit routing cannot be made selective, evaluate a
user-invoked version with matching policy metadata rather than broadening its ownership.

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

**Why it clears the bar.** The audit found the baseline failure real and recurrent: on an
integration-shaped feature a strong agent goes breadth-first (models, wrapper, routes, webhook,
UI, mocked tests, "done"), nothing reaches the real boundary, and the mocks encode the agent's own
guess about the service. The model applies the tracer-bullet pattern when told to and rarely
unprompted, and almost never with the two distinguishing moves here: naming the consequential
assumption, and reporting ran, simulated, and untested separately. Published tracer-bullet skills
are generic "touch every layer first" ceremony with no anti-triggers; `feature-dev` has no
executable milestone; Ultraplan plans only. No shipped skill owns implementation order.

**Routing:** substantial new features/integrations with an executable entry point and a material
uncertainty; exclude ordinary bug fixes, refactors, copy changes, UI polish, already-proven plumbing,
and requests only for a mockup. The discriminator is a *new external or runtime boundary with
unproven behaviour*, not file count: a Sentry initialisation in three files qualifies; a CRUD page
on an existing table does not. Expect recall and specificity to fight on exactly that small-but-
risky case; the battery must hold it.

**Neighbors:** `test-discipline` owns its existing-code test gates; `debugging-discipline` owns
resistant bugs; both anti-trigger on new-feature work. `api-bench` owns standalone model-request
simulations and prompt comparisons. An application integration using a model can still qualify
here, but a model transcript alone does not prove the application's surrounding path; "prototype
our model integration" is the ambiguous prompt and needs a routing negative pair. Respect any
installed implementation workflow; add the early executable milestone rather than replacing its
planning and review phases. See the prior-verdicts paragraph above for `to-tickets`, `prototype`,
and `tdd`.

**Implementation:** a concise core procedure and a directly linked evidence format. Add a helper
only for a demonstrated deterministic need; do not build a universal application runner.
Missing credentials or an unavailable environment yield an honest blocked observation or a
clearly labelled local simulation, never a fabricated successful flight. A CLAUDE.md line ("run
the riskiest path first") delivers a fraction of the value and cannot carry slice selection or the
evidence format; the maintainer will not type `$first-flight` at the moment breadth-first drift
begins, which is why the skill is model-invoked.

**Acceptance cases:** a CLI with a planted config-path defect; an HTTP integration with a contract
mismatch; a worker with a persistence boundary; a mocked success that does not establish the
chosen assumption; an unavailable service; and trivial-edit/bugfix negatives. Measure whether
the relevant path ran before unrelated implementation expanded, when a material defect was found,
and whether the final feature still meets its requirements. Do not optimize a raw files-written
or tool-call count at the expense of completion quality.

**Biggest risk:** trigger drift into "every feature". A fire rate that approaches `feature-dev`'s
turns the skill into ceremony and is worse than no skill.

## Parked candidates

Each entry keeps enough of the contract to rebuild the case without re-grounding. Full reasoning,
scenarios, and right-sizing probes are in the [audit record](brainstorm/skunk-works-audit-2026-10-06.md).

### Vendor Bakeoff — PARKED, lean build on the next real request

Contract: compare two to four executable alternatives against the same acceptance criteria and
representative inputs; freeze the protocol (correctness criteria, inputs, repetition policy)
before observing outcomes; pin versions; run with repetitions; report hard-constraint failures
before tradeoffs; allow ties, inconclusive results, and no qualifying candidate; never present
unrun numbers as results.

Why parked rather than built now: the baseline failure is predictable and costly (one run,
fastest-wrong wins, unequal default configs, unpinned versions, documentation claims or invented
numbers when the run fails, criteria chosen after seeing results), but the moment is episodic, a
few bake-offs a year. Build it on the first real workload rather than a synthetic one.

Design notes to carry forward: a short `SKILL.md` plus `templates/protocol.md` and
`templates/results.md`; no runner script and no validator unless a run demonstrates the need.
`critical-thinking` owns the decision after the measurements; the report stops at measured results
and constraint failures. One real in-kit seam: "compare GPT-4o vs Claude on our 30 samples" fires
both `api-bench` and this; `vendor-bakeoff` owns protocol and scoring and may call `api-bench` as
the adapter for model candidates, and `api-bench` gains an anti-trigger for multi-candidate
bake-offs with correctness criteria (an `api-bench` version bump in the same PR). Add "external
components, not two in-repo implementations" to the anti-triggers.

### Migration Forecast — PARKED, demoted to an instruction line

Contract as proposed: on an explicit remaining-effort request for a repetitive migration,
inventory done versus remaining units, classify by effort category, sample each category, give
ranges per category, name unknowns, present codemod, reorder, and scope-cut alternatives, stay
read-only, refuse calendar dates without availability data.

Why parked: with the agent doing the conversion, engineering hours is not the quantity the
maintainer decides on. The decision-changing output is the categorized inventory, the hard-tail
list, blockers needing a human decision, and whether a codemod clears the homogeneous bulk. The
plan's heaviest component, a deterministic effort estimator with tests, targeted the least
valuable part and is dropped. The inventory step is already handled adequately by the baseline;
the classification discipline is the only gap, and it fits in a few lines. `codemod-from-exemplar`
was already KILLed as "prefer ast-grep", one CLAUDE.md line. Right-sizing is the main hazard: "how
many Jest files are left" wants a grep count, not a ceremony.

Smallest form: an instruction line or short checklist. On remaining-work questions for a
migration: inventory by grep, classify remaining units by effort class, sample the hard class,
count setup, CI, and final-green as units, propose a codemod for the homogeneous bulk, never
extrapolate from the completed-easy average, never give hours without supplied timing. Revisit as
a skill only if a real migration surfaces the need twice.

### Verification Map — PARKED, bounded discovery optional

Contract to investigate: for one bounded service, integration, or pipeline, map important
failure modes to the responsible layer, the existing check with a source anchor, what it proves,
and the remaining gap. Suggest consolidation only where equivalent protection is established.
Never remove a test or weaken a gate. Explicit verification-ownership audits only.

Why parked: the remainder beyond coverage and mutation tools is real (semantic failure-mode
enumeration, mock blindness, layer ownership), and the baseline fails the way the plan predicts
(lists test files by name, calls a mocked signature check "covered", never names idempotency,
proposes deleting unit plus integration "duplicates"). But the value lives entirely in the step
the parked contract-review experiments (`anticipate-edge-cases` through codex V2–V5 in
[strategy.md](strategy.md)) could not make reliable: tracing to actual assertions with anchors.
Trigger, scope, and output differ from that line; the mechanics are dangerously close. The closest
in-kit neighbour is `independent-research`, not `test-discipline`, so the description must name
verification ownership and failure-mode mapping as the discriminator.

Discovery, if run: one synthetic fixture containing a mocked boundary, an unguarded idempotency
gap, and deliberate overlapping coverage, plus a complete suite that must yield zero gaps. Budget
about ten dollars. Advisory `file:line` anchors the user verifies, never a materialized ledger.
Stop signal, decided before running: if the candidate needs a deterministic anchor helper to pass,
it is the V2–V5 experiment again; park it with that result. `test-discipline` keeps its gates;
do not claim PR-review lift.

## Smaller enhancements

Neither was audited; both are contingent on owners that are not in this baseline.

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
  For `first-flight` the battery must include the small-but-risky integration, the
  `api-bench` model-integration pair, and the `prototype` and `to-tickets` seams.

Every behavioral suite and routing battery needs isolated `skill` evidence. A multi-skill or
hook-bearing owner also needs `plugin` evidence; declared external composition needs `stack`
evidence. Single-skill, hook-free plugins still need target-only evidence. Keep sibling bodies,
hooks, and group descriptions out of isolated packages. Test the relevant ownership boundaries
against installed neighbors; an absent optional sibling must have a safe standalone fallback or
explicit scope stop.

Commit concise experiment results and limitations. Raw generated material belongs under
`qa/_work/` and stays uncommitted. A failed or unavailable live run is not a pass; record it and
fix the demonstrated problem or retain the candidate as unpublished. Do not relax a frozen gate
after seeing results; a revised hypothesis needs a new record and fresh confirmation cases.

## Implementation sequence and PR boundaries

1. **Candidate PR: First Flight.** Record the proposed decision in `docs/strategy.md`; add the
   standalone draft under `qa/experiments/first-flight/`, contract, cases, fixtures, rubric, and
   routing controls. Run the pilot and commit a result before preparing its publication change.
2. **Publication PR for First Flight** once the frozen gate passes. Move the distribution to
   `plugins/first-flight/skills/first-flight/`, add the plugin manifest and published eval/battery
   paths, and update strategy with the observed outcome.
3. **Parked candidates** re-enter only through their gates above. `vendor-bakeoff` starts as a
   candidate PR on the first real bake-off workload; `verification-map` starts, if at all, as a
   discovery record under `qa/experiments/verification-map/` with its stop signal written first;
   `migration-forecast` needs no PR beyond the instruction line, recorded where the maintainer
   keeps standing instructions.
4. **Enhancement PRs only for demonstrated gaps.** Handle declared exceptions after its owner is
   available; handle crew sizing if the delegation workflow needs it. Keep these independent from
   the new plugin and its acceptance claims.

This plan does not authorize automatic paid runs or implementation of the skills in the
documentation PR. Choose concrete pilot repositories/fixtures and run budgets in the relevant
candidate PR.

## Distribution, authority, and release checklist

A published skill carries a focused `SKILL.md`, quoted `agents/openai.yaml` display name and
25–64 character short description, and a one-sentence default prompt naming `$<skill-name>`.
Invocation policy must agree across harnesses. Keep branch detail in directly linked references,
deterministic helpers in scripts, and reusable formats in templates/assets. All runtime dependencies
must resolve inside the installed skill directory. Do not create a shared catchall reference or
new hooks for these candidates.

First Flight inherits only the user's authorized implementation scope. Vendor Bakeoff, if built,
writes only its task-owned experiment artifacts; target application changes are separate work.
Verification Map inspects the target read-only. Any saved report needs an authorized path. None
commits, pushes, publishes, deploys, or silently changes requirements. External data sharing and
paid operations stay within established conversation authorization and explicit caps; credentials
never enter committed artifacts. Preserve existing files and unrelated work.

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
