// Held-out calibration: pick the threshold on one fold, measure on the other.
// The showcase's perfect score was on the same set the threshold came from; this is the honest number.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { JudgmentClient, NoCache, calibrate, noul, type Judge } from "@overclock/judgment-core";
import { messages, predicates, type PredicateName } from "./data/messages.js";
import { binaryMetrics, fmt, here, pct, splitByHash, table } from "./lib.js";

export const name = "heldout";

interface Scored {
  id: string;
  p: number;
  label: boolean;
}

export interface HeldOutData {
  sets: Array<{
    predicate: string;
    instructions: string;
    calibration: Scored[];
    heldOut: Scored[];
  }>;
  usage: { requests: number; inputTokens: number; outputTokens: number };
}

export async function run(judge: Judge): Promise<HeldOutData> {
  const client = new JudgmentClient({ judge, cache: new NoCache(), concurrency: 6 });
  const sets: HeldOutData["sets"] = [];

  // Customer messages: all three questions about one message share a single request.
  const names = Object.keys(predicates) as PredicateName[];
  const judged = await Promise.all(
    messages.map(async (m) => {
      const out = await client.askAll(m.text, Object.fromEntries(names.map((n) => [n, noul(predicates[n])])));
      return { id: m.id, p: Object.fromEntries(names.map((n) => [n, out[n]!.p])) as Record<PredicateName, number> };
    }),
  );
  for (const n of names) {
    const scored: Scored[] = messages.map((m, i) => ({ id: m.id, p: judged[i]!.p[n], label: m[n] }));
    const { calibration, heldOut } = splitByHash(scored, 0.6);
    sets.push({ predicate: n, instructions: predicates[n], calibration, heldOut });
  }

  // Agent replies: the politeness set from the showcase.
  const polite = readFileSync(join(here, "..", "examples", "data", "polite.jsonl"), "utf8")
    .split("\n")
    .filter(Boolean)
    .map((line, i) => ({ id: `p${String(i + 1).padStart(3, "0")}`, ...(JSON.parse(line) as { value: string; label: boolean }) }));
  const politeQuestion = noul("is polite and professional");
  const politeJudged = await Promise.all(polite.map((c) => client.ask(c.value, politeQuestion)));
  const politeScored: Scored[] = polite.map((c, i) => ({ id: c.id, p: politeJudged[i]!.p, label: c.label }));
  const politeSplit = splitByHash(politeScored, 0.6);
  sets.push({ predicate: "polite (agent replies)", instructions: "is polite and professional", calibration: politeSplit.calibration, heldOut: politeSplit.heldOut });

  const usage = client.usage();
  return { sets, usage: { requests: usage.requests, inputTokens: usage.inputTokens, outputTokens: usage.outputTokens } };
}

export function render(data: HeldOutData): string {
  const rows: Array<Array<string | number>> = [];
  const details: string[] = [];
  for (const set of data.sets) {
    const report = calibrate(set.calibration, { metric: "f1" });
    const threshold = report.best.threshold;
    const naive = binaryMetrics(set.heldOut, 0.5);
    const tuned = binaryMetrics(set.heldOut, threshold);
    const heldOutReport = calibrate(set.heldOut, { thresholds: [threshold] });
    rows.push([
      set.predicate,
      `${set.calibration.length} / ${set.heldOut.length}`,
      fmt(threshold, 2),
      pct(naive.accuracy),
      pct(tuned.accuracy),
      fmt(tuned.precision, 2),
      fmt(tuned.recall, 2),
      fmt(tuned.f1, 2),
      fmt(tuned.brier),
      fmt(heldOutReport.ece),
    ]);
    const misses = set.heldOut.filter((s) => (s.p >= threshold) !== s.label);
    if (misses.length) {
      const lookup = new Map(messages.map((m) => [m.id, m.text]));
      details.push(
        `**${set.predicate}** misses on the held-out fold at threshold ${fmt(threshold, 2)}:\n\n` +
          table(
            ["id", "label", "p", "text"],
            misses.map((s) => [s.id, s.label ? "yes" : "no", pct(s.p), (lookup.get(s.id) ?? "(agent reply)").slice(0, 110)]),
          ),
      );
    }
  }
  return [
    "Threshold chosen on a 60% calibration fold by F1, then applied to the untouched 40% fold. `naive` is accuracy at 0.5 on the same held-out fold.",
    "",
    table(["predicate", "cal / held-out", "threshold", "naive acc", "acc", "precision", "recall", "F1", "Brier", "ECE"], rows),
    "",
    ...details,
    "",
    `Usage: ${data.usage.requests} requests, ${data.usage.inputTokens} input / ${data.usage.outputTokens} output tokens.`,
  ].join("\n");
}
