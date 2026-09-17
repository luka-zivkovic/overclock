import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  JsonFileFixtures,
  JudgmentClient,
  MemoryCache,
  MissingFixtureError,
  MockJudge,
  NoCache,
  StateTooLargeError,
  answerProbability,
  calibrate,
  calibrateJudgments,
  canonicalize,
  choice,
  createLimiter,
  fixtureKey,
  judgmentKey,
  noul,
  renderCalibration,
  rules,
  score,
  synthesizeAnswer,
  type Judge,
  type JudgeRequest,
} from "../src/index.js";

describe("questions", () => {
  it("builds plain data questions", () => {
    expect(noul("Is it polite?")).toEqual({ type: "noul", instructions: "Is it polite?" });
    expect(choice("Intent?", { a: null, b: "the b case" })).toEqual({ type: "choice", instructions: "Intent?", criteria: { a: null, b: "the b case" } });
    expect(score("Clarity", ["bad", "ok", "great"]).criteria).toHaveLength(3);
    expect(() => choice("x", { only: null })).toThrow(TypeError);
  });

  it("canonicalizes key order so equal values hash equally", () => {
    expect(canonicalize({ b: 1, a: [{ d: 2, c: 3 }] })).toBe('{"a":[{"c":3,"d":2}],"b":1}');
    const q = noul("x");
    expect(judgmentKey("m", { a: 1, b: 2 }, q)).toBe(judgmentKey("m", { b: 2, a: 1 }, q));
    expect(judgmentKey("m", "s", q)).not.toBe(judgmentKey("other", "s", q));
    expect(fixtureKey("s", q)).toBe(fixtureKey("s", { ...q }));
  });

  it("summarizes answers as one probability without losing the distribution", () => {
    expect(answerProbability({ type: "noul", noul: 0.42 })).toBe(0.42);
    expect(answerProbability({ type: "choice", choice: "b", confidence: 0.7, probabilities: { a: 0.3, b: 0.7 } })).toBe(0.7);
    const q = score("clarity", ["bad", "ok", "great"]);
    expect(answerProbability({ type: "score", score: 1.5, confidence: 0.5, legend: {}, probabilities: {} }, q)).toBe(0.75);
  });
});

describe("MockJudge", () => {
  it("answers from rules, then fixtures, then throws on a miss", async () => {
    const judge = new MockJudge({ rules: [rules.noul("polite", 0.9)] });
    const ok = await judge.judge({ state: "hi", questions: { a: noul("Is it polite?") } });
    expect(ok.answers.a).toEqual({ type: "noul", noul: 0.9 });
    await expect(judge.judge({ state: "hi", questions: { b: noul("Is it rude?") } })).rejects.toBeInstanceOf(MissingFixtureError);
  });

  it("synthesizes stable answers when asked", async () => {
    const judge = new MockJudge({ onMissing: "synthesize" });
    const q = { s: score("Clarity", ["bad", "ok", "great"]), c: choice("Intent", { a: null, b: null }), n: noul("Polite?") };
    const first = await judge.judge({ state: "text", questions: q });
    const second = await judge.judge({ state: "text", questions: q });
    expect(first.answers).toEqual(second.answers);
    const s = first.answers.s;
    expect(s?.type).toBe("score");
    if (s?.type === "score") {
      const total = Object.values(s.probabilities).reduce((a, b) => a + b, 0);
      expect(total).toBeCloseTo(1, 2);
      expect(Object.keys(s.legend)).toEqual(["0", "1", "2"]);
    }
    expect(synthesizeAnswer("x", noul("y"))).toEqual(synthesizeAnswer("x", noul("y")));
  });

  it("records misses through a live judge into a fixture file and replays them", async () => {
    const dir = mkdtempSync(join(tmpdir(), "judgment-"));
    const path = join(dir, "nested", "fixtures.json");
    let liveCalls = 0;
    const live: Judge = {
      model: "jev-test",
      async judge(request: JudgeRequest) {
        liveCalls += 1;
        const answers = Object.fromEntries(Object.keys(request.questions).map((name) => [name, { type: "noul" as const, noul: 0.66 }]));
        return { model: "jev-test", answers, usage: { input_tokens: 10, output_tokens: 2 } };
      },
    };
    const recorder = new MockJudge({ fixtures: new JsonFileFixtures(path), record: live });
    const response = await recorder.judge({ state: "s", questions: { a: noul("A?"), b: noul("B?") } });
    expect(response.model).toBe("jev-test");
    expect(response.usage.input_tokens).toBe(10);
    expect(liveCalls).toBe(1);
    const file = JSON.parse(readFileSync(path, "utf8")) as { version: number; entries: Record<string, { answer: { noul: number }; model: string }> };
    expect(file.version).toBe(1);
    expect(Object.keys(file.entries)).toHaveLength(2);

    const replay = new MockJudge({ fixtures: new JsonFileFixtures(path) });
    const again = await replay.judge({ state: "s", questions: { x: noul("B?") } });
    expect(again.answers.x).toEqual({ type: "noul", noul: 0.66 });
    expect(again.usage.input_tokens).toBe(0);
    expect(liveCalls).toBe(1);
    rmSync(dir, { recursive: true, force: true });
  });
});

describe("JudgmentClient batching", () => {
  it("issues one request per distinct state and keys answers back correctly", async () => {
    const judge = new MockJudge({ rules: [rules.noul("A", 0.9), rules.noul("B", 0.1), rules.choice("intent", "escalate")] });
    const client = new JudgmentClient({ judge });
    const [a, b, c, d] = await Promise.all([
      client.ask("state one", noul("A?")),
      client.ask("state one", noul("B?")),
      client.ask("state one", choice("intent", { answer: null, escalate: null })),
      client.ask("state two", noul("A?")),
    ]);
    expect(judge.calls).toHaveLength(2);
    expect(Object.keys(judge.calls[0]!.questions)).toEqual(["q0", "q1", "q2"]);
    expect(a.p).toBe(0.9);
    expect(b.p).toBe(0.1);
    expect(c.answer.type).toBe("choice");
    expect(c.p).toBe(0.9);
    expect(c.confidence).toBe(0.9);
    expect(a.confidence).toBeUndefined();
    expect(d.stateHash).not.toBe(a.stateHash);
    expect(a.cached).toBe(false);
    expect(client.usage()).toMatchObject({ requests: 2, questions: 4, cacheHits: 0 });
  });

  it("serves repeats from the cache and dedupes identical in-flight questions", async () => {
    const judge = new MockJudge({ rules: [rules.noul("A", 0.5)] });
    const cache = new MemoryCache(2);
    const client = new JudgmentClient({ judge, cache });
    const [first, twin] = await Promise.all([client.ask("s", noul("A?")), client.ask("s", noul("A?"))]);
    expect(judge.calls).toHaveLength(1);
    expect(Object.keys(judge.calls[0]!.questions)).toHaveLength(1);
    expect(twin).toBe(first);
    const hit = await client.ask("s", noul("A?"));
    expect(hit.cached).toBe(true);
    expect(hit.p).toBe(0.5);
    expect(judge.calls).toHaveLength(1);
    expect(client.usage()).toMatchObject({ cacheHits: 1, inFlightHits: 1, requests: 1 });
    await client.ask("t", noul("A?"));
    await client.ask("u", noul("A?"));
    expect(cache.size).toBe(2);
  });

  it("splits oversized batches and guards state size", async () => {
    const judge = new MockJudge({ onMissing: "synthesize" });
    const client = new JudgmentClient({ judge, maxQuestionsPerCall: 2, cache: new NoCache(), maxStateBytes: 64 });
    await Promise.all([1, 2, 3, 4, 5].map((i) => client.ask("same", noul(`Q${i}?`))));
    expect(judge.calls.map((call) => Object.keys(call.questions).length)).toEqual([2, 2, 1]);
    await expect(client.ask("x".repeat(100), noul("big?"))).rejects.toBeInstanceOf(StateTooLargeError);
  });

  it("rejects every question in a failed request and keeps others working", async () => {
    const failing: Judge = {
      model: "flaky",
      async judge(request) {
        if (request.state === "bad") throw new Error("boom");
        return { model: "flaky", answers: { q0: { type: "noul", noul: 1 } }, usage: { input_tokens: 1, output_tokens: 1 } };
      },
    };
    const client = new JudgmentClient({ judge: failing });
    const results = await Promise.allSettled([client.ask("bad", noul("?")), client.ask("good", noul("?"))]);
    expect(results[0]?.status).toBe("rejected");
    expect(results[1]?.status).toBe("fulfilled");
  });

  it("askAll returns named judgments from one request", async () => {
    const judge = new MockJudge({ onMissing: "synthesize" });
    const client = new JudgmentClient({ judge });
    const out = await client.askAll({ body: "hello" }, { polite: noul("polite?"), intent: choice("intent", { a: null, b: null }) });
    expect(judge.calls).toHaveLength(1);
    expect(out.polite.answer.type).toBe("noul");
    expect(out.intent.answer.type).toBe("choice");
  });

  it("bounds concurrency", async () => {
    const limit = createLimiter(2);
    let active = 0;
    let peak = 0;
    await Promise.all(
      Array.from({ length: 6 }, () =>
        limit(async () => {
          active += 1;
          peak = Math.max(peak, active);
          await new Promise((resolve) => setTimeout(resolve, 5));
          active -= 1;
        }),
      ),
    );
    expect(peak).toBe(2);
  });
});

describe("calibration", () => {
  it("computes brier, ece, reliability bins and the best threshold", () => {
    const items = [
      { p: 0.95, label: true },
      { p: 0.9, label: true },
      { p: 0.8, label: true },
      { p: 0.7, label: false },
      { p: 0.6, label: true },
      { p: 0.4, label: false },
      { p: 0.2, label: false },
      { p: 0.1, label: false },
    ];
    const report = calibrate(items, { metric: "f1" });
    expect(report.n).toBe(8);
    expect(report.positives).toBe(4);
    expect(report.brier).toBeCloseTo(0.9125 / 8, 6);
    expect(report.bins).toHaveLength(10);
    // At 0.6: tp=4 fp=1 fn=0 -> f1 0.889; at 0.8: tp=3 fp=0 fn=1 -> f1 0.857.
    expect(report.best.threshold).toBeCloseTo(0.6, 5);
    expect(report.best.value).toBeCloseTo(0.889, 2);
    const strict = calibrate(items, { metric: { precisionAtRecall: 0.75 } });
    expect(strict.best.threshold).toBeCloseTo(0.8, 5);
    expect(strict.best.row.precision).toBe(1);
    const unreachable = calibrate([{ p: 0.2, label: true }], { metric: { precisionAtRecall: 1 }, thresholds: [0.5] });
    expect(Number.isNaN(unreachable.best.value)).toBe(true);
    const text = renderCalibration(report);
    expect(text).toContain("best threshold 0.60 by f1");
    expect(text).toContain("reliability");
    expect(() => calibrate([{ p: 1.2, label: true }])).toThrow(RangeError);
  });

  it("runs labeled cases through a client", async () => {
    const judge = new MockJudge({ rules: [rules.noul("yes", 0.9), rules.noul("no", 0.2)] });
    const client = new JudgmentClient({ judge });
    const { report, items } = await calibrateJudgments(client, [
      { state: "a", question: noul("yes?"), label: true },
      { state: "b", question: noul("no?"), label: false },
    ]);
    expect(items.map((i) => i.p)).toEqual([0.9, 0.2]);
    expect(report.agreementAtHalf).toBe(1);
  });
});

describe("live", () => {
  const live = process.env.LIVE === "1" && Boolean(process.env.TYPESAFE_API_KEY);
  afterEach(() => {});
  it.skipIf(!live)("answers three question types in one request", async () => {
    const { TypeSafeJudge } = await import("../src/index.js");
    const client = new JudgmentClient({ judge: new TypeSafeJudge() });
    const out = await client.askAll("Thanks for reaching out! I have refunded your order; expect it within 3 days.", {
      polite: noul("Is the message polite and professional?"),
      intent: choice("What is the primary intent?", { answer: null, escalate: null, decline: null }),
      clarity: score("Rate the clarity", ["confusing", "acceptable", "crystal clear"]),
    });
    expect(out.polite.p).toBeGreaterThan(0.5);
    expect(out.intent.answer.type === "choice" && out.intent.answer.choice).toBe("answer");
    expect(out.clarity.p).toBeGreaterThan(0.5);
    expect(client.usage().requests).toBe(1);
    expect(client.usage().inputTokens).toBeGreaterThan(0);
  });
});
