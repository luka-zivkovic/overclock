# Skunk Works candidates — usefulness audit (2026-10-06)

Scope: the four candidates in PR #39 ([`../skunk-works-skill-plan.md`](../skunk-works-skill-plan.md)), judged under the
[`../strategy.md`](../strategy.md) bar (usefulness + right-sizing + no in-kit collision; "exists elsewhere" and
"base model can do it" are not kill reasons). Method mirrors the `skill-brainstorm` gauntlet:
in-kit collision check, baseline behaviour, ecosystem grounding (web), two scenario simulations,
right-sizing probes, adversarial verdict. Declared-exceptions and crew-sizing enhancements were not
audited: they are contingent on `feature-dossier`, which does not exist on master.

| Candidate | Verdict | Smallest form that delivers the value | Gate before build |
|---|---|---|---|
| first-flight | **STRONG** | model-invoked skill | routing battery ≥90% precision; declare seams with to-tickets, prototype, api-bench |
| vendor-bakeoff | **PARKED (lean build)** | short model-invoked skill + protocol/results templates, no runner script | first real bake-off request; api-bench anti-trigger edit in the same PR |
| migration-forecast | **PARKED** | an instruction line or a reference checklist, not a skill | a real migration surfacing the need twice; drop the hours estimator |
| verification-map | **PARKED (run the discovery)** | user-invoked skill with a fixed table and advisory file:line anchors | one ~$10 fixture run; stop if it needs a deterministic anchor helper |

## first-flight — STRONG

- **Baseline gap is real and recurrent.** On "implement Stripe billing" a strong agent goes
  breadth-first (models → wrapper → routes → webhook → UI → mocked tests → "done"). Nothing hits
  the sandbox; mocks encode the agent's own guess about the API. The model knows the tracer-bullet
  pattern and applies it when told, rarely unprompted, and almost never with the distinguishing
  moves: name the consequential assumption, report ran / simulated / untested separately.
- **No in-kit owner of implementation order.** test-discipline and debugging-discipline both
  anti-trigger on new-feature work. groundwork is explicit-elicitation only. untangle is manual.
- **Prior verdicts the plan does not reconcile.** SHORTLIST already holds `to-tickets`
  (BUILD-IN-OVERCLOCK: spec → tracer-bullet vertical-slice tickets, gated on demand) and
  `prototype` (ADOPT-AS-IS: throwaway code that answers a question). first-flight is distinct from
  both — prototype code is discarded, a first-flight slice is kept and grows into the feature;
  to-tickets decomposes across sessions, first-flight picks which slice executes first inside one
  feature — but the plan must say so, and `tdd (seam-disciplined)` sits on the same surface too.
- **Ecosystem.** bullet-tracer, tyevans/tracer, tracer-bullets (×2), mattpocock/tdd all do generic
  "touch every layer first". None pick the slice by uncertainty, none have anti-triggers, none
  separate proved from simulated. feature-dev has no executable milestone; Ultraplan plans only.
- **Scenarios.** Stripe subscriptions: skill finds the raw-body-before-constructEvent defect in
  minute 20 instead of after "done"; handoff carries an honest untested list. Pagination fix +
  padding: must stay silent, and the planned anti-triggers cover it.
- **Right-sizing.** The discriminator must be *new external/runtime boundary with unproven
  behaviour*, not file count. Probes: `--json` flag → no; Sentry init → fire (small, risky); CRUD
  page on existing table → no; nightly Salesforce sync → fire; Storybook scaffold → no. ~4/5
  with a good description; the Sentry case is where recall and specificity fight.
- **Biggest risk.** Trigger drift into "every feature" turns it into ceremony. The api-bench seam
  on model integrations needs explicit negative pairs.
- **Form.** Model-invoked. A CLAUDE.md line ("run the riskiest path first") gives ~30% of the
  value; the maintainer will not type `$first-flight` at the moment breadth-first drift begins.

## vendor-bakeoff — PARKED (lean build)

- **Baseline failure modes are predictable and costly:** one run, no repetitions; correctness
  eyeballed so fastest-wrong wins; unequal default configs; unpinned versions; documentation
  claims or invented numbers when the run fails; criteria chosen after seeing results.
- **Demand is episodic:** 2–6 real bake-offs a year for a solo maintainer (parsers, OCR,
  embedding/vector stores, queue clients, LLM provider for a fixed task). Each is 1–3 hours
  where the default confidently produces a wrong answer. The plan names one concrete use.
- **One real in-kit seam.** "Compare GPT-4o vs Claude on our 30 samples" fires both api-bench
  ("compare two prompt variants on real runs") and this. Fix: vendor-bakeoff owns protocol and
  scoring and may call api-bench as the adapter for model candidates; api-bench gains an
  anti-trigger for multi-candidate bake-offs with correctness criteria (api-bench bump).
  critical-thinking owns the post-bake-off decision; the report should stop at measured results.
- **Ecosystem.** ln-34-benchmark-comparator is a near-equivalent (oracle-first). Informs design.
- **Right-sizing probes.** pandas vs polars on a parquet → fire; Redis vs Memcached → no;
  pytest-xdist vs plain → fire, acceptable; model vs model → both (seam); "compare the two PR
  implementations" → must not fire, needs an "external components, not in-repo A/B" anti-trigger.
- **Form.** Short SKILL.md + `templates/protocol.md` + `templates/results.md`. No runner, no
  validator (the plan's "small result validator if needed" should be dropped unless demonstrated).

## migration-forecast — PARKED

- **The plan aims at the wrong quantity.** With the agent doing the conversion, engineering hours
  is not what the maintainer decides on. The decision-changing output is: remaining units by
  effort class, the hard-tail list (custom mocks, `requireActual`, serializers, timers), blockers
  needing a human decision, and whether a codemod clears the homogeneous bulk. Steps 2, 3 and 5
  of the plan target that; step 4 (effort ranges, deterministic estimator with tests) is the
  heaviest component and the least valuable.
- **Baseline is half-decent already.** The agent greps and counts well; it does fall into the
  "extrapolate from the easy files done first" trap and gives round hour figures without
  provenance. The inventory part is not a gap; the classification discipline is.
- **Decision moment is rare:** stop/continue when the hard tail appears, codemod vs hand-convert,
  scope-cut. Roughly once per migration, a few migrations a year.
- **No in-kit collision.** untangle is manual and repo-wide; session-handoff anti-triggers status
  reports. `codemod-from-exemplar` was KILLed as "prefer ast-grep" = one CLAUDE.md line, which
  already judges the codemod prong a one-liner.
- **Right-sizing risk is the main problem.** "How many Jest files are left?" wants a grep count,
  not a ceremony. "Is it worth finishing?" overlaps critical-thinking. "Estimate the React 19
  upgrade" (not started) would fire though the plan excludes roadmaps.
- **Form.** An instruction line or short checklist: inventory by grep, classify remaining units by
  effort class, sample the hard class, count setup/CI/final-green as units, propose a codemod for
  the homogeneous bulk, never extrapolate from the completed-easy average or give hours without
  supplied timing. Revisit as a skill only if a real migration surfaces the need twice.

## verification-map — PARKED, run the bounded discovery

- **The remainder beyond coverage and mutation tools is real.** Line/branch coverage says nothing
  about assertion strength or mocks. Mutation testing is blind to un-enumerated failure modes
  (no code for idempotency → no mutant), to mock-hidden boundaries, and to layer ownership.
  Semantic failure-mode enumeration, mock blindness and ownership are the whole product.
- **Baseline fails in the way the plan predicts:** lists test files by name, calls a mocked
  signature check "covered", never names idempotency, proposes deleting unit + integration
  "duplicates", and does not distinguish "no check found" from "no check exists".
- **Not a relabel of the parked contract-review line, but dangerously close in mechanics.**
  Trigger (explicit only), scope (one service, not a diff) and output (table, not review comments)
  differ. The load-bearing step — trace to actual assertions with anchors — is exactly the
  anchor-materialization problem that sank V2–V5 (40–80% materialized, $79+ per arm). If anchors
  are advisory file:line the user verifies, it is new; if it needs a deterministic anchor helper
  to pass, it is the same experiment in a new coat. That is the stop signal for the discovery.
- **Closest in-kit neighbour is independent-research** ("independently inspect this local
  repo/CI"), not test-discipline (pre-edit gate, opposite polarity). The description must name
  verification ownership / failure-mode mapping as the discriminator.
- **Demand:** before a risky money/auth release, after an incident, when inheriting a service,
  before deleting "redundant" tests. A few times a year. Passes principle 4 weakly.
- **Form.** User-invoked (`disable-model-invocation`), fixed table template, advisory anchors.
  Keep the discovery at ~$10 and one synthetic fixture with the plan's own three gates
  (complete suite → zero gaps; mocked boundary found; deliberate duplicate preserved).

## Implications for PR #39

1. The plan's priority order (first-flight, then vendor-bakeoff, then migration-forecast,
   verification-map as discovery) survives the audit. Only first-flight is STRONG today.
2. Add a short "prior verdicts" paragraph reconciling first-flight with `to-tickets`,
   `prototype` and `tdd (seam-disciplined)` in SHORTLIST, as AGENTS.md's "read strategy and
   shortlist first" rule intends.
3. Rewrite migration-forecast §3 step 4 and its implementation paragraph: drop the deterministic
   estimator; make the deliverable a categorized inventory + blockers + codemod decision. Consider
   demoting it from a candidate PR to an instruction line.
4. Add the api-bench anti-trigger edit to vendor-bakeoff's publication step, and "external
   components, not in-repo A/B" to its anti-triggers.
5. Add the verification-map stop signal (needs a deterministic anchor helper → stop) to §4.
6. Fix the PR body: the untangle test failure does not reproduce on master locally or in CI.
