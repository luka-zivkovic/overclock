Design complete. I read `docs/strategy.md`, the 2026-08-17 role-matrix screen result, the role-matrix experiment README, both experimental skill trees (`anticipate-edge-cases`, `pr-kit/review-pr` including its finding contract), and `AGENTS.md`; I did not touch `qa/experiments/review-contract-gaps-phase0`. Consultation was read-only: no files edited, no processes beyond these read tools, no agents invoked.

## Outcome (TLDR)

The screen's own diagnosis says the bottleneck is **candidate generation, not admission or placement**: strict verification worked perfectly (28 byte-exact ties, zero unsupported admissions) but the implementation-blind brief never produced a confirmable root cause, because it anchored on hypothetical implementation shapes while every real defect across all four runs lived in a **pre-existing consumer contract the actual diff violated** (the unreachable option-description hint, raw `dataTableId` workflow consumers, the ResourceLocator probe). So the build-ready pivot is to drop the blind brief as a composition input entirely and build one new implementation-aware, consumer-grounded second-pass skill — **`audit-consumer-contracts`** — that deterministically extracts the diff's touched contract surface, enumerates its *pre-existing* base-tree consumers, verifies each consumer's expectation against the head, and appends only fail-closed-admitted findings to a frozen base review. This changes the artifact and the evidence requirement, not the timing, so it is not another permutation of the risk brief.

## Why this shape

- The only three confirmed-or-near-confirmed contributions in the whole program were consumer-contract violations discoverable by searching the base tree for consumers of identifiers the diff touched. The blind pass can't know which identifiers the diff touches; a full reviewer touches them but doesn't systematically enumerate out-of-diff consumers (pr-kit's base review missed the unreachable-description bug that built-in caught, and vice-versa reviewers missed `dataTableId`).
- The implementation-blind router failed (routed all four no-lift blocks). Replace it with a **deterministic, auditable gate**: the model pass runs only when the surface extractor finds ≥1 changed identifier with external base consumers. Zero consumers ⇒ compact no-op at script cost, no model spend.
- All existing safety machinery is reusable: the screen proved `assemble_review.py`-style admission and byte-preserving assembly are sound. Keep them; feed them better candidates.

## Product boundary

One independently installable experimental skill, unpublished, at
`qa/experiments/consumer-contract-audit-phase0/candidate/consumer-contract-audit/skills/audit-consumer-contracts/` (own `.claude-plugin/plugin.json`, `agents/openai.yaml` per AGENTS.md invariants). It is **not** a reviewer, not part of pr-kit, and not a revival of the blind brief: read-only, report-only, explicit-invocation, no posting/fixing/committing, no fetch, current source outranks any supplied artifact. Composition with a base review is optional input (a frozen review file/text), never a sibling dependency; standalone it returns its own findings-only report.

## Trigger / anti-trigger intent (draft frontmatter description)

`disable-model-invocation: true` (matching both siblings; `allow_implicit_invocation: false` in openai.yaml), with the description still carrying real anti-triggers:

> "Audit whether a committed change breaks pre-existing consumers of the identifiers, options, keys, schemas, routes, or emitted values it touches. Use only when the user explicitly invokes it on an exact base/head pair or PR, either standalone or as a strict append-only second pass over a supplied frozen review. Enumerates base-tree consumers outside the diff, verifies each expectation against the exact head, and reports only confirmed changed-line-anchored findings; when no touched identifier has external consumers, returns a compact no-op. Do not use for general code review, pre-implementation risk brainstorming, style or wording changes, debugging observed failures, fixing/applying findings, or posting comments."

Anti-trigger routing intent: generic "review this PR" → review-pr/built-in; pre-diff "what could go wrong" → anticipate-edge-cases; this skill fires only on explicit consumer/contract-impact requests or explicit second-pass composition.

## Core execution workflow

1. **Pin endpoints** — exact 40-char base/head SHAs (PR metadata or user refs), same immutable-target and one-line-helper-call rules as review-pr; never fetch, never read the working tree as evidence.
2. **Deterministic surface extraction** — `scripts/extract_surface.py` parses the exact diff and emits `contract-surface.json`: changed/removed/renamed identifiers (exported symbols, property/option names, string keys, config/schema fields, event/route names, displayed-text keys), each with base-tree consumer hits **outside the changed files** (path:line @ base SHA), plus a changed-line allowlist (port of `collect_changed_lines.py`). If zero surface entries have external consumers: emit the two-line no-op and stop — no model exploration.
3. **Per-consumer verification (model)** — for each surfaced contract with consumers, in priority order under an inspection budget: state the consumer's expectation from base evidence; verify at the head whether it still holds (reachability/precedence/display conditions, persisted raw values vs re-resolved keys, version gates, aliasing/migration); actively search for the defeating guard and record guards checked. Persisted/user-authored state (workflows, configs, DB rows) counts as a consumer — this is the lens that found `dataTableId`.
4. **Fail-closed admission and assembly** — serialize candidates to the schema, run `scripts/admit_findings.py`; when a frozen base review is supplied, append admitted findings only, otherwise emit standalone report. Empty admission with a supplied review ⇒ base bytes returned exactly.
5. **Report** — findings first (finding-contract anatomy), then a consumer-coverage ledger: surfaced contracts, consumers verified vs skipped under budget, guards checked, blind spots. `No admitted findings` is a success state.

## Bundled deterministic helpers and schemas

- `scripts/extract_surface.py` — diff → identifier surface → external-consumer map; fail-closed on missing objects, ambiguous refs, dirty state; bounded output (`--limit/--prefix`).
- `scripts/inspect_pair.py` — the read-only git/GitHub wrapper (adapt review-pr's `inspect_review.py`: status/diff/show/search/log/pr-metadata; no `git`/`gh` direct calls).
- `scripts/admit_findings.py` — merges `validate_findings.py` + `assemble_review.py` semantics (below).
- `references/contract-surface-schema.json`, `references/candidate-schema.json` (extends the role-matrix candidate contract with required consumer-evidence fields), `references/consumer-lenses.md` (reachability, persisted-identity, precedence/shadowing, versioned-gating, event/route propagation).

## Strict admission and base-review retention rules

A candidate is admitted only when **all** hold, mechanically checked where possible:

1. Anchored to a line in the exact changed-line allowlist (correct diff side).
2. Cites ≥1 **pre-existing** consumer at `path:line @ base-sha` located **outside the changed files**, whose expectation the diff violates — extractor-listed or verifier-discovered-then-mechanically-confirmed to exist at base.
3. Cites head evidence (`path:line @ head-sha`) of the violated expectation; both citations verified against repository content.
4. Reachable concrete input/state/event sequence; `guards_checked` non-empty; no defeating guard found.
5. Change causality: introduced or newly exposed by this diff (pre-existing defects rejected).
6. Not a duplicate of a base-review root cause (root-cause dedup against a review index); one root cause admitted once.
7. Confidence high/medium per the existing finding contract; any reference to a PR/issue not present in supplied metadata is rejected outright (blocks the unsupported-assertion failure the judges flagged).

Retention: append-only by construction — the frozen review is never rewritten, reordered, or summarized; empty admission returns base bytes byte-for-byte (assemble-style hash check); no empty appendix. Fail closed on stale digests, unknown surface IDs, malformed paths, unsupported priorities.

## Evaluation plan (small, behavioral + routing)

**Behavioral (target-only skill evidence, deterministic-first):**
1. Positive control A — synthetic repo where an added hint is shadowed by an existing description consumer (the agent-guardrails defect class): expect exactly one admitted finding citing the out-of-diff consumer.
2. Positive control B — key rename with a persisted raw-identity consumer (the `dataTableId` class): expect one admitted finding; also assert the extractor alone surfaces the consumer (validates the deterministic layer independently).
3. Negative control — same change shapes but with a version gate/alias that defeats them: expect byte-identical base review plus a guards-checked ledger; any admitted finding fails the eval.
4. No-surface control — doc/wording-only diff: expect the deterministic no-op with zero model exploration.
5. Unit tests for `extract_surface.py` and `admit_findings.py`: allowlist enforcement, external-consumer requirement, dedup, byte preservation, fail-closed paths (pattern of `qa/test_pr_kit_candidate.py`).

**Routing battery:** positive prompts (explicit consumer-impact/second-pass requests) must select this skill; negatives (generic review, pre-implementation brainstorming, style-only, fix requests) must not; reuse the ≥90% precision / ≥80% recall / ≥90% specificity gate from agent-bridge.

**Composition screen:** two **fresh** merged PRs (the four prior heads are calibration-only, per the role-matrix rule — use them solely to verify mechanically, without model runs, that the extractor fires on agent-guardrails and stays quiet where appropriate), both reviewer families, sealed frozen base reviews, blind matched-pair judging with the existing `judge-rubric.md`/`judge-output-schema.json`. Promotion gates: zero mutation/posting, zero unsupported additions, 100% base-finding retention, ≥1 matched win or material new contribution, `wins − losses ≥ 0` per reviewer family, plus a **deterministic-gate efficiency check**: model spend occurred only on cases the extractor gated in, with avoided cost recorded. Metric is confirmed distinct root causes per dollar, never output length.

## Blockers and residual risks

- I could not write the plan file: my toolset in this consultation has no write capability (Read/Grep/Glob only), consistent with the read-only contract; this message is the deliverable.
- Main design risk: identifier extraction on TypeScript/Vue monorepos is heuristic; a noisy surface map wastes budget. Mitigate by ranking consumers (persisted/user-authored state and display-precedence consumers first) and hard-capping verified consumers per run.
- Second risk: this skill's lift may overlap what a strong reviewer already finds (built-in caught the description bug unaided). The dedup rule makes that a tie, not a loss — the screen must show it converts at least one *cross-reviewer miss* into an admitted finding, or the candidate parks like its predecessors.
- Verification actually run: reads of the six files/trees named above only; no tests executed, nothing changed, and the dirty checkout was left untouched.
