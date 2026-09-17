import { PGlite } from "@electric-sql/pglite";
import { choice, questionHash } from "@overclock/judgment-core";
import { Kysely, type Generated } from "kysely";
import { afterAll, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { PGliteDialect, ScanBudgetExceededError, SemanticEngine, semantic, tableNameOf } from "../src/index.js";
import { mockJudge } from "./helpers.js";

interface DB {
  reviews: { id: Generated<number>; body: string; created_at: string };
}

let pg: PGlite;
let db: Kysely<DB>;

const OLD = "2023-01-01T00:00:00Z";
const NEW = "2024-06-01T00:00:00Z";
const bodies: Array<[string, string]> = [
  ["Shipping delay of two weeks!!", NEW],
  ["Lovely, no complaints", NEW],
  ["Late again! Delay after delay!!", NEW],
  ["Arrived late", NEW],
  ["Shipping was slow but fine", NEW],
  ["Broken on arrival!!!", NEW],
  ["Old review about a delay", OLD],
  ["Old review, happy", OLD],
  ["Delay!!! Unacceptable", NEW],
  ["Great colour", NEW],
  ["Refund requested, shipping never happened", NEW],
  ["Old and late", OLD],
];

beforeAll(async () => {
  pg = new PGlite();
  db = new Kysely<DB>({ dialect: new PGliteDialect(pg) });
  await pg.exec("create table reviews (id serial primary key, body text not null, created_at timestamptz not null)");
  await db
    .insertInto("reviews")
    .values(bodies.map(([body, created_at]) => ({ body, created_at })))
    .execute();
});
afterAll(async () => {
  await db.destroy();
  await pg.close();
});

const recent = () => db.selectFrom("reviews").selectAll().where("created_at", ">", "2024-01-01");

let judge: ReturnType<typeof mockJudge>;
let engine: SemanticEngine;
beforeEach(() => {
  judge = mockJudge();
  engine = new SemanticEngine({ judge, packSize: 4 });
});

describe("semantic()", () => {
  it("pushes structural predicates to SQL, filters and orders semantically, then limits", async () => {
    const { rows, stats } = await semantic(recent(), engine)
      .whereMeaning("body", "mentions a shipping delay", { threshold: 0.75 })
      .orderByScore("body", "urgency", ["none", "mild", "high"], "desc")
      .limit(5)
      .executeWithStats();

    // Old rows never reach the judge.
    const judgedTexts = new Set(judge.calls.flatMap((c) => (c.state as { rows: Array<{ text: string }> }).rows.map((r) => r.text)));
    expect([...judgedTexts].some((t) => t.startsWith("Old"))).toBe(false);
    expect(stats.rowsScanned).toBe(9);

    // Matched: rows mentioning delay/late/shipping among the 9 recent ones -> 6; ordered by "!" count
    // (capped at the top level, so the first three tie) desc, stable by id; limit 5 drops the sixth.
    expect(rows.map((r) => r.body)).toEqual([
      "Shipping delay of two weeks!!",
      "Late again! Delay after delay!!",
      "Delay!!! Unacceptable",
      "Arrived late",
      "Shipping was slow but fine",
    ]);
    expect(rows).toHaveLength(5);
    for (const row of rows) expect(Object.keys(row.$judgments)).toHaveLength(2);

    // 9 noul judgments (3 packs of 4) + 6 score judgments (2 packs).
    expect(stats).toMatchObject({ judgments: 15, cacheHits: 0, apiCalls: 5, packs: 5, pushedDown: 0 });
    expect(stats.tokens).toEqual({ input: 0, output: 0 });
    expect(engine.lastStats()).toEqual(stats);
  });

  it("only judges survivors of earlier filters", async () => {
    const q = choice("Topic", { product: null, shipping: null, refund: null });
    const rows = await semantic(recent(), engine)
      .whereMeaning("body", "mentions a shipping delay")
      .whereChoice("body", q, ["shipping"])
      .execute();
    expect(rows.map((r) => r.body)).toEqual(["Shipping delay of two weeks!!", "Shipping was slow but fine", "Refund requested, shipping never happened"]);
    const choiceCalls = judge.calls.filter((c) => Object.values(c.questions)[0]!.type === "choice");
    expect(choiceCalls.reduce((n, c) => n + Object.keys(c.questions).length, 0)).toBe(6);
    expect(rows[0]!.$judgments[questionHash(q)]!.answer).toMatchObject({ type: "choice", choice: "shipping" });
  });

  it("is immutable and validates labels", () => {
    const base = semantic(recent(), engine);
    const withFilter = base.whereMeaning("body", "x");
    expect(withFilter).not.toBe(base);
    expect(() => base.whereChoice("body", choice("t", { a: null, b: null }), ["c"])).toThrow(TypeError);
    expect(() => base.limit(-1)).toThrow(RangeError);
  });

  it("explain() returns the structural SQL and the estimate without judging", async () => {
    const plan = await semantic(recent(), engine).whereMeaning("body", "mentions a shipping delay").orderByScore("body", "urgency", ["a", "b"]).limit(3).explain();
    expect(plan.sql).toMatch(/^select \* from "reviews" where "created_at" > \$1$/);
    expect(plan.parameters).toEqual(["2024-01-01"]);
    expect(plan.estimate).toEqual({ rows: 9, questions: 2, judgments: 18, packs: 6 });
    expect(plan.pushedDown).toEqual([]);
    expect(plan.postPass.map((op) => op.kind)).toEqual(["meaning", "score"]);
    expect(judge.calls).toHaveLength(0);
  });

  it("enforces the budget from the count query and honors allowLargeScan / budget", async () => {
    const q = semantic(recent(), engine).whereMeaning("body", "x").orderByScore("body", "y", ["a", "b"]).budget(10);
    await expect(q.execute()).rejects.toBeInstanceOf(ScanBudgetExceededError);
    expect(judge.calls).toHaveLength(0);
    await expect(q.budget(18).execute()).resolves.toBeInstanceOf(Array);
    await expect(q.allowLargeScan().execute()).resolves.toBeInstanceOf(Array);
  });

  it("returns every structural row when there are no semantic ops", async () => {
    const { rows, stats } = await semantic(recent(), engine).limit(2).executeWithStats();
    expect(rows).toHaveLength(2);
    expect(rows[0]!.$judgments).toEqual({});
    expect(stats).toMatchObject({ rowsScanned: 2, judgments: 0, apiCalls: 0 });
  });

  it("reads the table name from the builder", () => {
    expect(tableNameOf(db.selectFrom("reviews").selectAll())).toBe("reviews");
    expect(tableNameOf(db.selectFrom("reviews as r").selectAll())).toBe("reviews");
    expect(tableNameOf(db.selectFrom(db.selectFrom("reviews").select("id").as("sub")).selectAll())).toBeUndefined();
  });
});
