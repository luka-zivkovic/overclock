// Packing: judge every message singly, then packed K rows per request, and compare probabilities.
// semantic-sql's cost model depends on packing being answer-neutral; this measures how neutral.
import { noul, type Judge } from "@overclock/judgment-core";
import { NoRowCache, SemanticEngine } from "@overclock/semantic-sql";
import { messages, predicates, type PredicateName } from "./data/messages.js";
import { binaryMetrics, fmt, max, mean, pct, table } from "./lib.js";

export const name = "packing";

const PACK_SIZES = [1, 4, 8, 16, 32];

export interface PackingData {
  packSizes: number[];
  predicates: Array<{
    predicate: PredicateName;
    /** p per message id, per pack size. */
    p: Record<string, Record<string, number>>;
    usage: Record<string, { calls: number; input: number; output: number }>;
  }>;
}

export async function run(judge: Judge): Promise<PackingData> {
  const names = Object.keys(predicates) as PredicateName[];
  const texts = messages.map((m) => m.text);
  const out: PackingData["predicates"] = [];
  for (const n of names) {
    const p: Record<string, Record<string, number>> = {};
    const usage: PackingData["predicates"][number]["usage"] = {};
    for (const size of PACK_SIZES) {
      const engine = new SemanticEngine({ judge, rowCache: new NoRowCache(), packSize: size, maxPackBytes: 512 * 1024, concurrency: 4, budget: 100_000 });
      const { judgments, stats } = await engine.judgeTexts(texts, noul(predicates[n]));
      p[String(size)] = Object.fromEntries(messages.map((m, i) => [m.id, judgments[i]!.p]));
      usage[String(size)] = { calls: stats.apiCalls, input: stats.tokens.input, output: stats.tokens.output };
    }
    out.push({ predicate: n, p, usage });
  }
  return { packSizes: PACK_SIZES, predicates: out };
}

export function render(data: PackingData): string {
  const sections: string[] = [];
  const summary: Array<Array<string | number>> = [];
  for (const entry of data.predicates) {
    const single = entry.p["1"]!;
    const labels = new Map(messages.map((m) => [m.id, m[entry.predicate]]));
    for (const size of data.packSizes) {
      const packed = entry.p[String(size)]!;
      const ids = Object.keys(single);
      const deltas = ids.map((id) => Math.abs(packed[id]! - single[id]!));
      const flipsHalf = ids.filter((id) => packed[id]! >= 0.5 !== single[id]! >= 0.5).length;
      const flipsHigh = ids.filter((id) => packed[id]! >= 0.75 !== single[id]! >= 0.75).length;
      const metrics = binaryMetrics(ids.map((id) => ({ p: packed[id]!, label: labels.get(id)! })), 0.5);
      const usage = entry.usage[String(size)]!;
      summary.push([
        entry.predicate,
        size,
        usage.calls,
        (usage.input / ids.length).toFixed(0),
        size === 1 ? "—" : fmt(mean(deltas)),
        size === 1 ? "—" : fmt(max(deltas)),
        size === 1 ? "—" : flipsHalf,
        size === 1 ? "—" : flipsHigh,
        pct(metrics.accuracy),
        fmt(metrics.f1, 2),
      ]);
    }
    // Worst drifts at the largest pack size, to show what kind of message moves.
    const largest = entry.p[String(data.packSizes[data.packSizes.length - 1])]!;
    const worst = Object.keys(single)
      .map((id) => ({ id, single: single[id]!, packed: largest[id]!, delta: Math.abs(largest[id]! - single[id]!) }))
      .sort((a, b) => b.delta - a.delta)
      .slice(0, 4);
    const lookup = new Map(messages.map((m) => [m.id, m.text]));
    sections.push(
      `Largest drifts for **${entry.predicate}** at pack size ${data.packSizes[data.packSizes.length - 1]}:\n\n` +
        table(["id", "single", "packed", "label", "text"], worst.map((w) => [w.id, pct(w.single), pct(w.packed), labels.get(w.id) ? "yes" : "no", (lookup.get(w.id) ?? "").slice(0, 90)])),
    );
  }
  return [
    `${messages.length} messages × ${data.predicates.length} predicates, each judged at pack sizes ${data.packSizes.join(", ")} with the cache disabled. Δp compares each packed probability with the single-row probability for the same message. Flips count verdicts that change side of 0.5 or 0.75. Accuracy and F1 are against the hand labels at 0.5.`,
    "",
    table(["predicate", "pack", "calls", "input tokens / row", "mean |Δp|", "max |Δp|", "flips @0.5", "flips @0.75", "accuracy", "F1"], summary),
    "",
    ...sections.flatMap((section) => [section, ""]),
  ].join("\n");
}
