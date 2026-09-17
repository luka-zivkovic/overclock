// Stability: the same request repeated. TypeSafe's docs report identical answers across runs;
// this measures it on our inputs, bypassing every cache.
import { noul, type Judge } from "@overclock/judgment-core";
import { messages, predicates, type PredicateName } from "./data/messages.js";
import { fmt, max, mean, stddev, table } from "./lib.js";

export const name = "stability";

const REPEATS = 5;
const SAMPLE = 12;

export interface StabilityData {
  repeats: number;
  items: Array<{ id: string; text: string; predicate: PredicateName; ps: number[] }>;
}

export async function run(judge: Judge): Promise<StabilityData> {
  const names = Object.keys(predicates) as PredicateName[];
  // Every 7th message: spreads the sample across the themes without cherry-picking.
  const sample = messages.filter((_, i) => i % 7 === 0).slice(0, SAMPLE);
  const items: StabilityData["items"] = [];
  for (const m of sample) for (const n of names) items.push({ id: m.id, text: m.text, predicate: n, ps: [] });
  for (let r = 0; r < REPEATS; r += 1) {
    await Promise.all(
      sample.map(async (m) => {
        const response = await judge.judge({ state: m.text, questions: Object.fromEntries(names.map((n) => [n, noul(predicates[n])])) });
        for (const n of names) {
          const answer = response.answers[n];
          const item = items.find((i) => i.id === m.id && i.predicate === n)!;
          item.ps.push(answer && answer.type === "noul" ? answer.noul : Number.NaN);
        }
      }),
    );
  }
  return { repeats: REPEATS, items };
}

export function render(data: StabilityData): string {
  const byPredicate = new Map<string, StabilityData["items"]>();
  for (const item of data.items) byPredicate.set(item.predicate, [...(byPredicate.get(item.predicate) ?? []), item]);
  const rows: Array<Array<string | number>> = [];
  for (const [predicate, items] of byPredicate) {
    const ranges = items.map((i) => max(i.ps) - Math.min(...i.ps));
    const sds = items.map((i) => stddev(i.ps));
    rows.push([predicate, items.length, fmt(mean(sds)), fmt(max(sds)), fmt(max(ranges)), items.filter((_, k) => ranges[k]! > 0.05).length, items.filter((i) => new Set(i.ps.map((p) => p >= 0.5)).size > 1).length]);
  }
  const worst = [...data.items].sort((a, b) => max(b.ps) - Math.min(...b.ps) - (max(a.ps) - Math.min(...a.ps))).slice(0, 5);
  return [
    `${data.items.length / 3} messages × 3 predicates, each request repeated ${data.repeats} times with no cache.`,
    "",
    table(["predicate", "items", "mean sd", "max sd", "max range", "range > 0.05", "verdict flips at 0.5"], rows),
    "",
    "Widest ranges:",
    "",
    table(["id", "predicate", "p per repeat", "text"], worst.map((i) => [i.id, i.predicate, i.ps.map((p) => p.toFixed(2)).join(", "), i.text.slice(0, 90)])),
  ].join("\n");
}
