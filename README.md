# Judgment

Typed, probabilistic judgment for TypeScript, built on [TypeSafe](https://typesafe.ai)'s System One
API (`jev-latest`). One call takes one `state` and many `questions`; the questions run in parallel
and isolated, so adding questions is flat in cost. These packages turn that into things you can
put in a schema, a test, or a query.

| Package | What it is |
| --- | --- |
| [`@overclock/judgment-core`](packages/judgment-core) | `Judge` interface (live SDK wrapper + deterministic mock with record/replay fixtures), batcher, cache, evidence type, calibration harness |
| [`@overclock/semantic-types`](packages/semantic-types) | Zod for meaning: `semantic(schema, { body: [s.is("is polite"), s.not("contains PII")] })`, strict/annotate/review modes, test matchers, contracts, calibrate CLI |
| [`@overclock/semantic-sql`](packages/semantic-sql) | Judgment as a query operator: Kysely layer that pushes structural predicates to SQL, runs semantic predicates as a packed post-pass with a Postgres row cache, plus materialized semantic columns |

```ts
import { z } from "zod";
import { s, semantic } from "@overclock/semantic-types";

const Reply = semantic(z.object({ subject: z.string(), body: z.string() }), {
  body: [s.is("is polite and professional", { threshold: 0.8 }), s.not("contains personally identifiable information", { threshold: 0.2 })],
  $self: [s.is("subject matches the body's content")],
});
const result = await Reply.safeParseAsync(draft); // { success, data, evidence[] } — probabilities kept
```

```ts
import { semantic } from "@overclock/semantic-sql";

const rows = await semantic(db.selectFrom("reviews").selectAll().where("created_at", ">", lastWeek), engine)
  .whereMeaning("body", "mentions a shipping delay", { threshold: 0.75 })
  .orderByScore("body", "urgency", ["none", "mild", "high"], "desc")
  .limit(50)
  .execute();
```

## Develop

```sh
pnpm install
pnpm build          # tsc project references
pnpm test           # deterministic: MockJudge rules and committed fixtures, no network
LIVE=1 pnpm test    # adds the live round trips (needs TYPESAFE_API_KEY)
pnpm showcase       # regenerates examples/SHOWCASE.md from recorded fixtures
pnpm experiments    # re-renders experiments/RESULTS.md from stored raw results
JUDGMENT_FIXTURES=record pnpm showcase   # re-record the showcase against the live API
```

Node 20+. Tests never call the API unless `LIVE=1`; fixture-backed tests re-record with
`JUDGMENT_FIXTURES=record` (or `--update-semantic-fixtures`).

## Showcase

[`examples/SHOWCASE.md`](examples/SHOWCASE.md) is generated from real runs: guarding LLM output,
moderating user content with a review band, semantic contracts on a function boundary, a
calibration report over a labeled set, and five queries over a support-ticket table with
before/after cost numbers. `examples/demos/` holds the runnable sources.

## Experiments

[`experiments/RESULTS.md`](experiments/RESULTS.md) holds four recorded experiments on 80 hand-labeled
support messages and the 22-message politeness set: packing drift versus pack size (with token cost
per row), held-out calibration, request stability, and adversarial input with and without untrusted
framing. `pnpm experiments:live` re-runs them; `pnpm experiments` re-renders from the stored raw
results.

## Status and plan

See [PLAN.md](PLAN.md) for the milestones and what is still open (undocumented request limits and
unpublished pricing are handled by configuration, not assumptions).
