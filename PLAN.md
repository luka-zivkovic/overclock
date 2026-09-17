# Build plan: judgment-core, semantic-types, semantic-sql

One monorepo with a shared core so the second package is cheap once the first exists. Two things
shape everything: the API is one `state` + many `questions` per call (questions run in parallel
and isolated, so cost is flat as you add questions), and request limits and pricing are not yet
published, so the harness is config-driven and every test runs against a mock with record/replay
fixtures.

API surface (from the TypeSafe docs and SDK 0.6): `npm i @typesafe-ai/sdk`, Node 20+,
`client.systemOne({ state, questions })` with `noul()`, `choice()`, `score()` helpers, model
`jev-latest`. Answers: noul → `{ noul: 0..1 }`; choice → `{ choice, probabilities, confidence }`;
score → `{ score, probabilities, legend, confidence }`. Choice questions cap at 255 labels.

## Shared foundation: `@overclock/judgment-core`

| # | Item | Status |
| --- | --- | --- |
| 1 | `Judge` interface with `TypeSafeJudge` (SDK wrapper; SDK defaults retry 408/429/5xx with backoff and honor Retry-After) and `MockJudge` (rules → fixtures → recording judge → throw/synthesize) | done |
| 2 | Batcher: `JudgmentClient.ask()` groups by identical state within a tick, one request per distinct state, bounded concurrency, `maxQuestionsPerCall` split, state-size guard, in-flight dedupe | done |
| 3 | Cache: `sha256(model, canonical(state), canonical(question)) → answer`; in-memory LRU, `KeyValueCache` adapter, `NoCache` | done |
| 4 | Calibration: agreement, Brier, ECE, reliability bins, best threshold for f1 / precision / recall / accuracy / precision-at-recall; text reliability diagram | done |
| 5 | Evidence type `{ answer, p, confidence?, question, stateHash, key, cached, model, usage? }` | done |
| M | Unit tests on `MockJudge`; one `live` test gated by `LIVE=1` + `TYPESAFE_API_KEY` | done (14 unit, 1 live) |

## Package 1: `@overclock/semantic-types`

| # | Item | Status |
| --- | --- | --- |
| 1 | `semantic(zodSchema, spec)` with one request per value: whole object as state, field predicates phrased `Regarding the field "x": …`, issues mapped back to paths; `fieldScoped` option | done |
| 2 | Predicates as data: `s.is / s.not / s.oneOf / s.rated` | done |
| 3 | Evidence never dropped: `safeParseAsync` returns issues and the full probability per predicate; `SemanticError.evidence` | done |
| 4 | Modes: `strict`, `annotate` (`data.$meta`), `review` (pass / fail / `needsReview` within `margin`) | done |
| 5 | Nested paths, absent optional fields skipped, embeddable `.schema` with custom Zod issues, `.with()` variants | done |
| 6 | `assertMeaning`, `meaning`, `guarded(fn, { pre, post })` | done |
| 7 | Vitest/Jest matchers `toMean` / `toMeanNot` with fixture replay and `--update-semantic-fixtures` recording | done |
| 8 | Property-based usage documented (fast-check) and demonstrated over sampled inputs in the showcase | done |
| 9 | `semantic-types calibrate ./labeled.jsonl --predicate "…"` prints threshold + reliability diagram | done |
| 10 | Docs with three demos: guarding LLM output, validating user content, semantic contract tests | done (examples/SHOWCASE.md) |

## Package 2: `@overclock/semantic-sql`

| # | Item | Status |
| --- | --- | --- |
| 1 | `semanticFilter` / `semanticSort` / `semanticGroupBy` over arrays with packing (state = `{ rows: [{ id, text }] }`, one question per row, fallback to one row per call for long texts) and a row-level cache | done |
| 2 | Kysely layer `semantic(qb, engine)` with `.whereMeaning / .whereChoice / .orderByScore / .limit / .allowLargeScan / .budget / .explain`; pushdown split and cost planner | done |
| 3 | Postgres cache table `semantic_judgments` and explain-style stats (rows scanned, cache hits, API calls, packs, tokens) | done |
| 4 | Materialized semantic columns: `semantic-sql materialize table.column "…" --as col`, registry, batch backfill, `refresh` / `watch` polling worker, planner routing to plain SQL | done |
| 5 | Demo: support-ticket table, five queries, before/after cost numbers | done (examples/SHOWCASE.md) |
| M | 33 deterministic tests on PGlite (in-process Postgres) with MockJudge; no network | done |
| S | Stretch: Postgres function `jev_noul(text, text)` via pg_net / plv8; DuckDB scalar UDF | not started |

## Open questions tracked as configuration

- State size and questions-per-request limits are undocumented: `maxStateBytes`,
  `maxQuestionsPerCall`, `packSize`, `maxPackBytes` and `concurrency` are options with
  conservative defaults, never constants.
- Rate limits are undocumented: the SDK's retry policy is exposed unchanged through `TypeSafeJudge`.
- Pricing is unpublished: cost is only reported when a rate is configured, always computed from the
  `usage` the API returns.
- Fixtures are keyed without the model name so a fixture file survives model
  renames; the cache key includes it so a model change invalidates cached judgments.
