import { choice, noul, questionHash } from "@overclock/judgment-core";
import { describe, expect, it } from "vitest";
import { ROW_PREFIX, SemanticEngine, semanticFilter, semanticGroupBy, semanticScore, semanticSort } from "../src/index.js";
import { mockJudge } from "./helpers.js";

const reviews = [
  { id: 1, body: "Package arrived late, very annoying" },
  { id: 2, body: "Great product, works as described" },
  { id: 3, body: "Shipping took three weeks!!" },
  { id: 4, body: "Refund please, the item is broken!!!" },
  { id: 5, body: "Nice colour" },
];

describe("semanticFilter", () => {
  it("keeps rows whose p meets the threshold and attaches $judgments", async () => {
    const judge = mockJudge();
    const engine = new SemanticEngine({ judge });
    const q = noul("mentions a shipping delay");
    const kept = await semanticFilter(reviews, "body", q, { engine, threshold: 0.75 });
    expect(kept.map((r) => r.id)).toEqual([1, 3]);
    const evidence = kept[0]!.$judgments[questionHash(q)]!;
    expect(evidence.p).toBe(0.9);
    expect(evidence.answer).toEqual({ type: "noul", noul: 0.9 });
    expect(evidence.question).toEqual(q);
    expect(evidence.cached).toBe(false);
  });

  it("wraps a string question as noul", async () => {
    const engine = new SemanticEngine({ judge: mockJudge() });
    const kept = await semanticFilter(reviews, "body", "mentions a shipping delay", { engine });
    expect(kept.map((r) => r.id)).toEqual([1, 3]);
    expect(Object.values(kept[0]!.$judgments)[0]!.question).toEqual(noul("mentions a shipping delay"));
  });
});

describe("packing", () => {
  it("sends one call per pack of packSize rows, addressed by row id", async () => {
    const judge = mockJudge();
    const engine = new SemanticEngine({ judge, packSize: 3 });
    await semanticScore(reviews, "body", "mentions a shipping delay", { engine });
    expect(judge.calls).toHaveLength(2);
    const first = judge.calls[0]!;
    expect(Object.keys(first.questions)).toEqual(["r0", "r1", "r2"]);
    expect(first.state).toEqual({
      rows: [
        { id: "r0", text: reviews[0]!.body },
        { id: "r1", text: reviews[1]!.body },
        { id: "r2", text: reviews[2]!.body },
      ],
    });
    expect(first.questions.r1!.instructions).toBe(`${ROW_PREFIX} "r1": mentions a shipping delay`);
    expect(Object.keys(judge.calls[1]!.questions)).toEqual(["r0", "r1"]);
    expect(engine.lastStats()).toMatchObject({ rowsScanned: 5, judgments: 5, cacheHits: 0, apiCalls: 2, packs: 2 });
  });

  it("keeps criteria on packed questions", async () => {
    const judge = mockJudge();
    const engine = new SemanticEngine({ judge, packSize: 10 });
    await semanticFilter(reviews, "body", noul("mentions a shipping delay", { true: "any delay", false: "no delay" }), { engine });
    expect(judge.calls[0]!.questions.r0).toMatchObject({ type: "noul", criteria: { true: "any delay", false: "no delay" } });
  });

  it("falls back to a single-row call for a text larger than maxPackBytes", async () => {
    const judge = mockJudge();
    const engine = new SemanticEngine({ judge, packSize: 10, maxPackBytes: 200 });
    const rows = [
      { id: 1, body: "short one" },
      { id: 2, body: "x".repeat(400) },
      { id: 3, body: "short two" },
    ];
    await semanticScore(rows, "body", "mentions a shipping delay", { engine });
    const shapes = judge.calls.map((c) => Object.keys(c.questions));
    expect(shapes).toEqual([["r0"], ["r0"], ["r0"]]);
    const big = judge.calls.find((c) => (c.state as { rows: Array<{ text: string }> }).rows[0]!.text.length === 400);
    expect(big).toBeDefined();
    expect(engine.lastStats().packs).toBe(3);
  });

  it("splits packs when the byte budget would overflow", async () => {
    const judge = mockJudge();
    const engine = new SemanticEngine({ judge, packSize: 10, maxPackBytes: 160 });
    const rows = Array.from({ length: 6 }, (_, i) => ({ id: i, body: `review number ${i} ${"y".repeat(40)}` }));
    await semanticScore(rows, "body", "anything", { engine });
    expect(judge.calls.length).toBeGreaterThan(1);
    for (const call of judge.calls) expect(Buffer.byteLength(JSON.stringify(call.state))).toBeLessThanOrEqual(160);
    expect(judge.calls.reduce((n, c) => n + Object.keys(c.questions).length, 0)).toBe(6);
  });
});

describe("row cache", () => {
  it("answers a repeated query with zero judge calls", async () => {
    const judge = mockJudge();
    const engine = new SemanticEngine({ judge, packSize: 2 });
    const first = await semanticFilter(reviews, "body", "mentions a shipping delay", { engine });
    const calls = judge.calls.length;
    expect(calls).toBe(3);
    const second = await semanticFilter(reviews, "body", "mentions a shipping delay", { engine });
    expect(judge.calls).toHaveLength(calls);
    expect(second.map((r) => r.id)).toEqual(first.map((r) => r.id));
    expect(Object.values(second[0]!.$judgments)[0]!.cached).toBe(true);
    expect(engine.lastStats()).toMatchObject({ judgments: 5, cacheHits: 5, apiCalls: 0, packs: 0 });
  });

  it("judges identical texts once", async () => {
    const judge = mockJudge();
    const engine = new SemanticEngine({ judge, packSize: 10 });
    const rows = [{ body: "same" }, { body: "same" }, { body: "other" }];
    const out = await semanticScore(rows, "body", "anything", { engine });
    expect(Object.keys(judge.calls[0]!.questions)).toEqual(["r0", "r1"]);
    expect(out).toHaveLength(3);
  });
});

describe("semanticSort", () => {
  it("sorts by expected score, stable", async () => {
    const engine = new SemanticEngine({ judge: mockJudge() });
    const sorted = await semanticSort(reviews, "body", { instructions: "urgency", levels: ["none", "mild", "high"] }, "desc", { engine });
    expect(sorted.map((r) => r.id)).toEqual([3, 4, 1, 2, 5]);
    const asc = await semanticSort(reviews, "body", { instructions: "urgency", levels: ["none", "mild", "high"] }, "asc", { engine });
    expect(asc.map((r) => r.id)).toEqual([1, 2, 5, 3, 4]);
    expect(Object.values(sorted[0]!.$judgments)[0]!.answer.type).toBe("score");
  });
});

describe("semanticGroupBy", () => {
  it("groups rows by the chosen label with every label present", async () => {
    const engine = new SemanticEngine({ judge: mockJudge() });
    // The mock picks the first label named in the text and falls back to the first label.
    const q = choice("What is it about?", { product: null, shipping: null, refund: null, spam: null });
    const groups = await semanticGroupBy(reviews, "body", q, { engine });
    expect([...groups.keys()]).toEqual(["product", "shipping", "refund", "spam"]);
    expect(groups.get("shipping")!.map((r) => r.id)).toEqual([3]);
    expect(groups.get("refund")!.map((r) => r.id)).toEqual([4]);
    expect(groups.get("product")!.map((r) => r.id)).toEqual([1, 2, 5]);
    expect(groups.get("spam")).toEqual([]);
  });
});
