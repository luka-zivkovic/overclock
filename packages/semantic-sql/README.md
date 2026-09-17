# @overclock/semantic-sql

Judgment as a query operator. The same question objects as
[`@overclock/judgment-core`](../judgment-core) (`noul`, `choice`, `score`) become `WHERE`,
`ORDER BY` and `GROUP BY` over arrays and over Kysely queries, with packed batching, a row-level
cache, a cost planner, and materialized semantic columns for the hot paths.

```ts
import { Kysely } from "kysely";
import { SemanticEngine, semantic } from "@overclock/semantic-sql";
import { judgeFromEnv } from "@overclock/judgment-core";

const engine = new SemanticEngine({ judge: judgeFromEnv() });

const rows = await semantic(
  db.selectFrom("reviews").selectAll().where("created_at", ">", since),   // structural: SQL
  engine,
)
  .whereMeaning("body", "mentions a shipping delay", { threshold: 0.75 })  // semantic: batched post-pass
  .orderByScore("body", "urgency", ["none", "mild", "high"], "desc")
  .limit(5)
  .execute();

rows[0].$judgments; // { [questionHash]: { p, confidence?, answer, question, cached } }
```

## Three layers

1. **Pushdown.** Structural predicates stay in the Kysely builder and run as SQL. When a
   semantic predicate has been materialized (see below), it is rewritten to SQL as well:
   `whereMeaning` becomes `where target_column >= threshold`, `orderByScore` becomes
   `order by target_column`, and the limit is pushed down when nothing is left to judge.
2. **Batched post-pass.** Everything else runs after the structural query, in declaration
   order: each filter only judges the rows that survived the previous one, then score
   ordering, then the limit. Rows are packed `packSize` at a time into one judge call whose
   state is `{ rows: [{ id: "r0", text }, ...] }` and whose questions are the original
   question addressed to each row (`Regarding row "r0": ...`, criteria kept). Identical texts
   are judged once. Every judgment is cached per (model, text, question), so the same query
   tomorrow costs nothing.
3. **Materialize.** For a predicate you query constantly, write the judgment into a real
   column once, register it, and keep it fresh with a polling worker. Queries on the same
   (column, question, model) route to SQL automatically.

## Plain functions

```ts
import { semanticFilter, semanticSort, semanticGroupBy, semanticScore, choice } from "@overclock/semantic-sql";

const late = await semanticFilter(reviews, "body", "mentions a shipping delay", { threshold: 0.75, engine });
const byUrgency = await semanticSort(reviews, "body", { instructions: "urgency", levels: ["none", "mild", "high"] }, "desc", { engine });
const groups = await semanticGroupBy(reviews, "body", choice("Topic?", { shipping: null, refund: null, product: null }), { engine });
const annotated = await semanticScore(reviews, "body", "mentions a shipping delay", { engine }); // no filtering
```

All of them return rows with `$judgments` attached. Without `engine`, a default engine over
`judgeFromEnv()` is created lazily (replay / record / live by environment).

## Engine

```ts
const engine = new SemanticEngine({
  judge,                       // any judgment-core Judge (TypeSafeJudge, MockJudge, judgeFromEnv())
  rowCache: new PostgresRowCache(db),   // default MemoryRowCache(); NoRowCache to disable
  packSize: 100,               // rows per judge call
  maxPackBytes: 64 * 1024,     // canonical state per call; larger texts get a call of their own
  concurrency: 4,
  budget: 5000,                // max judgments per query
  pricing: { inputPerMillion: 0.5, outputPerMillion: 1.5 },  // optional; USD per million tokens
  materialized: new PostgresMaterializedRegistry(db),        // optional; enables SQL routing
});
```

`PostgresRowCache` stores rows in `semantic_judgments(state_hash, question_hash, model, p,
confidence, answer jsonb, created_at)`; call `ensureTable()` once or create it in a migration.

### Cost planner and explain

`engine.estimate({ rows, questions })` returns `{ rows, questions, judgments, packs }`. A query
whose worst case exceeds `budget` throws `ScanBudgetExceededError` (carrying the estimate)
before any judge call, unless you pass `allowLargeScan` or raise `.budget(n)`. The query layer
counts the structural result first (`select count(*)` of the pushdown query) so the check is
real, not a guess.

```ts
const plan = await query.explain();
// { sql, parameters, estimate, pushedDown: [...], postPass: [...] }  (judges nothing)

const { rows, stats } = await query.executeWithStats();
// stats: { rowsScanned, judgments, cacheHits, apiCalls, packs, pushedDown,
//          tokens: { input, output }, estimatedCostUsd?, durationMs }
engine.lastStats(); engine.totals();
```

`estimatedCostUsd` is present only when `pricing` is configured and is computed from the
usage the judge returned; no rate is ever assumed.

## Materialized semantic columns

```ts
import { materialize, refresh, watch } from "@overclock/semantic-sql";

await materialize(db, engine, { table: "reviews", column: "body", question: "mentions a shipping delay", as: "delay_p" });
// ALTER TABLE reviews ADD COLUMN IF NOT EXISTS delay_p real; registers it in semantic_materialized;
// backfills rows where delay_p IS NULL in batches of 500 ordered by `id` (keyColumn).

await refresh(db, engine, { table: "reviews", as: "delay_p" });        // judges only NULL rows (new inserts)
await watch(db, engine, { table: "reviews", as: "delay_p", intervalMs: 5000, signal });  // refresh in a loop
```

The column holds the yes-probability for a noul question or the expected level for a score
question. Routing matches on (table, column, question hash, model); a different question text or a
different model runs as a post-pass (the threshold is not part of the key). Rows whose target column is
still NULL are excluded by a pushed-down `whereMeaning` until the next refresh. The table name
is read from the builder's first `from` (plain or aliased); pass `semantic(qb, engine, { table })`
for subqueries or joins.

CLI (needs the optional `pg` package and `DATABASE_URL` or `--database-url`; the judge comes
from `judgeFromEnv()`):

```
semantic-sql materialize reviews.body "mentions a shipping delay" --as delay_p [--batch 500] [--key id]
semantic-sql refresh reviews --as delay_p
semantic-sql watch reviews --as delay_p --interval 5000
```

## Postgres in-process

`PGliteDialect` is a small Kysely dialect over [PGlite](https://pglite.dev) (a devDependency
here; pass any object with `query(sql, params)`), so tests and demos run real Postgres without
a server:

```ts
import { PGlite } from "@electric-sql/pglite";
const db = new Kysely<DB>({ dialect: new PGliteDialect(new PGlite()) });
```

## Limits

- Choice questions cap at 255 labels (TypeSafe documentation).
- Pack size and concurrency are configuration, not tuned defaults: request limits are not
  documented, so start with `packSize: 100`, `concurrency: 4`, and adjust to observed errors.
- Pricing is not published. Cost is computed from returned usage only when you configure a
  rate; otherwise `estimatedCostUsd` is absent.
- `whereChoice` is never pushed down (materialized columns are numeric).
- Materialized columns are refreshed by polling (`refresh` / `watch`); there is no
  LISTEN/NOTIFY.
