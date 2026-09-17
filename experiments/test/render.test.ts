// The stored raw results and the renderers must stay in sync: RESULTS.md is regenerated from
// experiments/results/*.json in CI, and this test fails early if a renderer no longer fits its data.
import { describe, expect, it } from "vitest";
import * as adversarial from "../adversarial.js";
import * as heldout from "../heldout.js";
import { loadResult } from "../lib.js";
import * as packing from "../packing.js";
import * as stability from "../stability.js";

describe("experiment renderers", () => {
  it("render every stored result without throwing", () => {
    for (const experiment of [packing, heldout, stability, adversarial]) {
      const stored = loadResult<never>(experiment.name);
      expect(stored, `stored result for ${experiment.name}`).toBeDefined();
      const text = experiment.render(stored!.data);
      expect(text.length).toBeGreaterThan(200);
      expect(text).not.toContain("NaN");
      expect(text).not.toContain("n/a");
    }
  });

  it("packing data covers every message at every pack size", () => {
    const stored = loadResult<packing.PackingData>("packing")!;
    for (const entry of stored.data.predicates) {
      for (const size of stored.data.packSizes) {
        expect(Object.keys(entry.p[String(size)]!)).toHaveLength(80);
      }
    }
  });
});
