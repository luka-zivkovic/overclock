import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import { main } from "../src/cli.js";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const data = join(root, "examples", "data", "polite.jsonl");
const fixtures = join(root, "examples", "fixtures", "calibrate.json");

describe("semantic-types calibrate", () => {
  afterEach(() => vi.restoreAllMocks());

  it("prints usage on bad arguments", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(await main(["calibrate"])).toBe(2);
    expect(error.mock.calls[0]?.[0]).toContain("semantic-types calibrate");
  });

  it("replays the recorded fixture and recommends a threshold", async () => {
    const lines: string[] = [];
    vi.spyOn(console, "log").mockImplementation((line: string) => {
      lines.push(String(line));
    });
    const code = await main(["calibrate", data, "--predicate", "is polite and professional", "--fixtures", fixtures]);
    expect(code).toBe(0);
    const text = lines.join("\n");
    expect(text).toContain("n=22 positives=11");
    expect(text).toMatch(/best threshold 0\.\d\d by f1/);
    expect(text).toContain('recommended: s.is("is polite and professional", { threshold:');
    expect(text).toContain("requests 22, cache hits 0, tokens 0/0");
  });

  it("emits JSON with a precision-at-recall operating point", async () => {
    const lines: string[] = [];
    vi.spyOn(console, "log").mockImplementation((line: string) => {
      lines.push(String(line));
    });
    const code = await main(["calibrate", data, "--predicate", "is polite and professional", "--fixtures", fixtures, "--metric", "precision@0.9", "--json"]);
    expect(code).toBe(0);
    const parsed = JSON.parse(lines.join("\n")) as { report: { best: { metric: unknown; row: { recall: number } } } };
    expect(parsed.report.best.metric).toEqual({ precisionAtRecall: 0.9 });
    expect(parsed.report.best.row.recall).toBeGreaterThanOrEqual(0.9);
  });
});
