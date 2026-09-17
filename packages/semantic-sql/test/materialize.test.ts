import { PGlite } from "@electric-sql/pglite";
import { noul } from "@overclock/judgment-core";
import { Kysely, sql } from "kysely";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { PGliteDialect, PostgresMaterializedRegistry, PostgresRowCache, SemanticEngine, materialize, refresh, semantic, watch } from "../src/index.js";
import { mockJudge } from "./helpers.js";

let pg: PGlite;
let db: Kysely<any>;
let registry: PostgresMaterializedRegistry;

beforeAll(async () => {
  pg = new PGlite();
  db = new Kysely<any>({ dialect: new PGliteDialect(pg) });
  await pg.exec("create table reviews (id serial primary key, body text not null, created_at timestamptz not null default now())");
  const bodies = ["Shipping delay!!", "All good", "Late delivery", "Fine", "Delay again!", "Perfect", "late", "ok", "shipping slow", "great", "delayed", "meh"];
  await db.insertInto("reviews").values(bodies.map((body) => ({ body }))).execute();
  registry = new PostgresMaterializedRegistry(db);
});
afterAll(async () => {
  await db.destroy();
  await pg.close();
});

const question = noul("mentions a shipping delay");

describe("materialize", () => {
  it("adds the column, registers it, and backfills every row in batches", async () => {
    const judge = mockJudge();
    const engine = new SemanticEngine({ judge, packSize: 4, materialized: registry });
    const result = await materialize(db, engine, { table: "reviews", column: "body", question, as: "delay_p", batchSize: 5 });
    expect(result).toMatchObject({ table: "reviews", column: "body", targetColumn: "delay_p", judged: 12, batches: 3 });
    // Batches of 5, 5, 2 rows packed 4 at a time: 2 + 2 + 1 calls.
    expect(result.stats).toMatchObject({ judgments: 12, apiCalls: 5, packs: 5 });

    const columns = await db.introspection.getTables();
    const reviews = columns.find((t) => t.name === "reviews")!;
    expect(reviews.columns.find((c) => c.name === "delay_p")).toMatchObject({ dataType: "float4", isNullable: true });

    const entry = await registry.lookupTarget("reviews", "delay_p");
    expect(entry).toMatchObject({ table: "reviews", column: "body", targetColumn: "delay_p", question, model: "mock" });
    expect(await registry.list()).toHaveLength(1);

    const rows = await db.selectFrom("reviews").select(["body", "delay_p"]).orderBy("id").execute();
    expect(rows.every((r) => r.delay_p !== null)).toBe(true);
    expect(rows.filter((r) => Number(r.delay_p) > 0.5).map((r) => r.body)).toEqual(["Shipping delay!!", "Late delivery", "Delay again!", "late", "shipping slow", "delayed"]);
  });

  it("is idempotent: a second materialize judges nothing", async () => {
    const judge = mockJudge();
    const engine = new SemanticEngine({ judge, materialized: registry });
    const again = await materialize(db, engine, { table: "reviews", column: "body", question, as: "delay_p" });
    expect(again.judged).toBe(0);
    expect(judge.calls).toHaveLength(0);
  });

  it("routes whereMeaning on the same (column, question) to SQL", async () => {
    const judge = mockJudge();
    const engine = new SemanticEngine({ judge, materialized: registry });
    const query = semantic(db.selectFrom("reviews").selectAll(), engine).whereMeaning("body", question, { threshold: 0.75 }).limit(3);
    const plan = await query.explain();
    expect(plan.sql).toBe('select * from "reviews" where "delay_p" >= $1 limit $2');
    expect(plan.pushedDown).toHaveLength(1);
    expect(plan.estimate.judgments).toBe(0);

    const { rows, stats } = await query.executeWithStats();
    expect(rows.map((r) => r.body)).toEqual(["Shipping delay!!", "Late delivery", "Delay again!"]);
    expect(judge.calls).toHaveLength(0);
    expect(stats.pushedDown).toBe(1);
    expect(stats.apiCalls).toBe(0);

    // A different threshold or model is not the same column: different question -> post-pass.
    const other = new SemanticEngine({ judge: mockJudge(), materialized: registry });
    const post = await semantic(db.selectFrom("reviews").selectAll(), other).whereMeaning("body", "something else").explain();
    expect(post.pushedDown).toEqual([]);
  });

  it("materializes a score question and routes orderByScore to SQL", async () => {
    const judge = mockJudge();
    const engine = new SemanticEngine({ judge, materialized: registry });
    const levels = ["none", "mild", "high"];
    await materialize(db, engine, { table: "reviews", column: "body", question: { type: "score", instructions: "urgency", criteria: ["none", "mild", "high"] }, as: "urgency_s" });
    const calls = judge.calls.length;
    const { rows, stats } = await semantic(db.selectFrom("reviews").selectAll(), engine).orderByScore("body", "urgency", levels, "desc").limit(2).executeWithStats();
    expect(judge.calls).toHaveLength(calls);
    expect(stats.pushedDown).toBe(1);
    expect(rows.map((r) => r.body)).toEqual(["Shipping delay!!", "Delay again!"]);
  });

  it("refresh judges only rows whose target is NULL", async () => {
    await db.insertInto("reviews").values([{ body: "new: delay" }, { body: "new: fine" }]).execute();
    const judge = mockJudge();
    const engine = new SemanticEngine({ judge, materialized: registry, rowCache: new PostgresRowCache(db) });
    await (engine.rowCache as PostgresRowCache).ensureTable();
    const result = await refresh(db, engine, { table: "reviews", as: "delay_p" });
    expect(result.judged).toBe(2);
    expect(judge.calls).toHaveLength(1);
    expect(Object.keys(judge.calls[0]!.questions)).toEqual(["r0", "r1"]);
    const rows = await db.selectFrom("reviews").select(["body", "delay_p"]).where("body", "like", "new:%").orderBy("id").execute();
    expect(rows.map((r) => [r.body, Number(r.delay_p) > 0.5])).toEqual([
      ["new: delay", true],
      ["new: fine", false],
    ]);
    await expect(refresh(db, engine, { table: "reviews", as: "nope" })).rejects.toThrow(/no materialized column/);
  });

  it("watch polls refresh until aborted", async () => {
    const judge = mockJudge();
    const engine = new SemanticEngine({ judge, materialized: registry });
    const controller = new AbortController();
    const seen: number[] = [];
    const done = watch(db, engine, {
      table: "reviews",
      as: "delay_p",
      intervalMs: 10,
      signal: controller.signal,
      onRefresh: (r) => {
        seen.push(r.judged);
        if (seen.length === 1) void sql`insert into reviews (body) values ('watched delay')`.execute(db);
        if (seen.length >= 4) controller.abort();
      },
    });
    const totals = await done;
    expect(totals.refreshes).toBeGreaterThanOrEqual(4);
    expect(totals.judged).toBe(1);
    const row = await db.selectFrom("reviews").select("delay_p").where("body", "=", "watched delay").executeTakeFirstOrThrow();
    expect(Number(row.delay_p)).toBeGreaterThan(0.5);
  });
});
