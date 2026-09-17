import { PGlite } from "@electric-sql/pglite";
import { noul } from "@overclock/judgment-core";
import { Kysely } from "kysely";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { MemoryRowCache, PGliteDialect, PostgresRowCache, SemanticEngine, rowKey, semanticFilter } from "../src/index.js";
import { mockJudge } from "./helpers.js";

let pg: PGlite;
let db: Kysely<any>;

beforeAll(async () => {
  pg = new PGlite();
  db = new Kysely<any>({ dialect: new PGliteDialect(pg) });
});
afterAll(async () => {
  await db.destroy();
  await pg.close();
});

describe("PGliteDialect", () => {
  it("runs queries, transactions and rollbacks", async () => {
    await db.schema.createTable("t").addColumn("id", "serial", (c) => c.primaryKey()).addColumn("name", "text").execute();
    await db.insertInto("t").values({ name: "a" }).execute();
    await db
      .transaction()
      .execute(async (trx) => {
        await trx.insertInto("t").values({ name: "b" }).execute();
        throw new Error("boom");
      })
      .catch(() => undefined);
    await db.transaction().execute((trx) => trx.insertInto("t").values({ name: "c" }).execute());
    const rows = await db.selectFrom("t").select("name").orderBy("id").execute();
    expect(rows.map((r) => r.name)).toEqual(["a", "c"]);
    const deleted = await db.deleteFrom("t").where("name", "=", "a").executeTakeFirst();
    expect(deleted.numDeletedRows).toBe(1n);
    // Concurrent queries queue on the single connection instead of interleaving.
    const results = await Promise.all([1, 2, 3].map((n) => db.selectFrom("t").select(({ fn }) => fn.countAll().as("n")).executeTakeFirst().then(() => n)));
    expect(results).toEqual([1, 2, 3]);
  });
});

describe("PostgresRowCache", () => {
  it("round-trips rows through the semantic_judgments table", async () => {
    const cache = new PostgresRowCache(db);
    await cache.ensureTable();
    await cache.ensureTable();
    const q = noul("mentions a shipping delay");
    const a = rowKey("mock", "late package", q);
    const b = rowKey("mock", "fine", q);
    const missing = rowKey("mock", "never stored", q);
    await cache.setMany([
      { key: a, value: { p: 0.9, confidence: 0.5, answer: { type: "noul", noul: 0.9 }, model: "mock" } },
      { key: b, value: { p: 0.1, answer: { type: "noul", noul: 0.1 }, model: "mock" } },
    ]);
    await cache.setMany([{ key: a, value: { p: 0.2, answer: { type: "noul", noul: 0.2 }, model: "mock" } }]); // conflict: first write wins
    const hits = await cache.getMany([a, b, missing]);
    expect(hits.size).toBe(2);
    expect(hits.get(a.key)).toEqual({ p: expect.closeTo(0.9, 5), confidence: expect.closeTo(0.5, 5), answer: { type: "noul", noul: 0.9 }, model: "mock" });
    expect(hits.get(b.key)).toEqual({ p: expect.closeTo(0.1, 5), answer: { type: "noul", noul: 0.1 }, model: "mock" });
    expect(hits.get(b.key)).not.toHaveProperty("confidence");
    // Same text under a different model is a different row.
    expect((await cache.getMany([rowKey("other", "late package", q)])).size).toBe(0);
    expect(await cache.getMany([])).toEqual(new Map());
  });

  it("makes a second identical query all cache hits with zero api calls", async () => {
    const cache = new PostgresRowCache(db);
    await cache.ensureTable();
    const rows = [
      { id: 1, body: "delivery was late" },
      { id: 2, body: "perfect" },
      { id: 3, body: "delay after delay" },
    ];
    const judge = mockJudge();
    const engine = new SemanticEngine({ judge, rowCache: cache, packSize: 2 });
    const first = await semanticFilter(rows, "body", "mentions a shipping delay", { engine });
    expect(first.map((r) => r.id)).toEqual([1, 3]);
    expect(engine.lastStats()).toMatchObject({ cacheHits: 0, apiCalls: 2 });

    // A fresh engine (fresh memory) over the same table still hits.
    const judge2 = mockJudge();
    const engine2 = new SemanticEngine({ judge: judge2, rowCache: new PostgresRowCache(db), packSize: 2 });
    const second = await semanticFilter(rows, "body", "mentions a shipping delay", { engine: engine2 });
    expect(second.map((r) => r.id)).toEqual([1, 3]);
    expect(judge2.calls).toHaveLength(0);
    expect(engine2.lastStats()).toMatchObject({ judgments: 3, cacheHits: 3, apiCalls: 0, packs: 0 });
    expect(Object.values(second[0]!.$judgments)[0]!.cached).toBe(true);
  });
});

describe("MemoryRowCache", () => {
  it("evicts the least recently used entry", async () => {
    const cache = new MemoryRowCache(2);
    const q = noul("x");
    const [a, b, c] = ["a", "b", "c"].map((t) => rowKey("m", t, q));
    const row = { p: 1, answer: { type: "noul" as const, noul: 1 }, model: "m" };
    await cache.setMany([{ key: a!, value: row }, { key: b!, value: row }]);
    await cache.getMany([a!]);
    await cache.setMany([{ key: c!, value: row }]);
    expect([...(await cache.getMany([a!, b!, c!])).keys()]).toEqual([a!.key, c!.key]);
  });
});
