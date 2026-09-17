import { MockJudge, noul } from "@overclock/judgment-core";
import { describe, expect, it } from "vitest";
import { NoRowCache, ScanBudgetExceededError, SemanticEngine, semanticScore } from "../src/index.js";
import { mockJudge } from "./helpers.js";

const rows = Array.from({ length: 10 }, (_, i) => ({ id: i, body: `text ${i}` }));

describe("cost planner", () => {
  it("estimates judgments and packs", () => {
    const engine = new SemanticEngine({ judge: mockJudge(), packSize: 4 });
    expect(engine.estimate({ rows: 10, questions: 2 })).toEqual({ rows: 10, questions: 2, judgments: 20, packs: 6 });
  });

  it("throws ScanBudgetExceededError with the estimate when over budget", async () => {
    const judge = mockJudge();
    const engine = new SemanticEngine({ judge, budget: 5 });
    const error = await semanticScore(rows, "body", "anything", { engine }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ScanBudgetExceededError);
    expect((error as ScanBudgetExceededError).estimate).toEqual({ rows: 10, questions: 1, judgments: 10, packs: 1 });
    expect((error as ScanBudgetExceededError).budget).toBe(5);
    expect(judge.calls).toHaveLength(0);
  });

  it("allowLargeScan and a per-call budget bypass the check", async () => {
    const engine = new SemanticEngine({ judge: mockJudge(), budget: 5 });
    await expect(semanticScore(rows, "body", "anything", { engine, allowLargeScan: true })).resolves.toHaveLength(10);
    await expect(semanticScore(rows, "body", "anything", { engine, budget: 10 })).resolves.toHaveLength(10);
  });
});

describe("stats", () => {
  it("counts rows, judgments, cache hits, calls, packs and tokens", async () => {
    const judge = new MockJudge({ rules: [], onMissing: "synthesize" });
    const usageJudge = {
      model: judge.model,
      async judge(request: Parameters<MockJudge["judge"]>[0]) {
        const response = await judge.judge(request);
        return { ...response, usage: { input_tokens: 100, output_tokens: 7 } };
      },
    };
    const engine = new SemanticEngine({ judge: usageJudge, packSize: 4, pricing: { inputPerMillion: 1, outputPerMillion: 10 } });
    const { stats } = await engine.judgeTexts(rows.map((r) => r.body), noul("anything"));
    expect(stats).toMatchObject({ rowsScanned: 10, judgments: 10, cacheHits: 0, apiCalls: 3, packs: 3, pushedDown: 0, tokens: { input: 300, output: 21 } });
    expect(stats.estimatedCostUsd).toBeCloseTo(300 / 1e6 + 210 / 1e6, 12);
    expect(stats.durationMs).toBeGreaterThanOrEqual(0);

    const second = await engine.judgeTexts([...rows.map((r) => r.body), "fresh"], noul("anything"));
    expect(second.stats).toMatchObject({ rowsScanned: 11, judgments: 11, cacheHits: 10, apiCalls: 1, packs: 1, tokens: { input: 100, output: 7 } });
    expect(engine.lastStats()).toEqual(second.stats);
    expect(engine.totals()).toMatchObject({ judgments: 21, cacheHits: 10, apiCalls: 4, tokens: { input: 400, output: 28 } });
  });

  it("omits estimatedCostUsd without pricing and honors NoRowCache", async () => {
    const judge = mockJudge();
    const engine = new SemanticEngine({ judge, rowCache: new NoRowCache() });
    const { stats } = await engine.judgeTexts(["a", "b"], noul("anything"));
    expect(stats.estimatedCostUsd).toBeUndefined();
    await engine.judgeTexts(["a", "b"], noul("anything"));
    expect(judge.calls).toHaveLength(2);
    expect(engine.lastStats().cacheHits).toBe(0);
  });

  it("bounds concurrency", async () => {
    let active = 0;
    let peak = 0;
    const inner = mockJudge();
    const judge = {
      model: "mock",
      async judge(request: Parameters<MockJudge["judge"]>[0]) {
        active += 1;
        peak = Math.max(peak, active);
        await new Promise((r) => setTimeout(r, 5));
        active -= 1;
        return inner.judge(request);
      },
    };
    const engine = new SemanticEngine({ judge, packSize: 1, concurrency: 2 });
    await engine.judgeTexts(rows.map((r) => r.body), noul("anything"));
    expect(peak).toBe(2);
    expect(inner.calls).toHaveLength(10);
  });
});
