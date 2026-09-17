// Runs the experiments and writes RESULTS.md.
//
//   pnpm experiments                      # re-render from experiments/results/*.json (no key)
//   pnpm experiments:live                 # run every experiment against TypeSafe and store raw results
//   pnpm experiments:live -- packing      # only the named experiments
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Judge } from "@overclock/judgment-core";
import * as adversarial from "./adversarial.js";
import * as heldout from "./heldout.js";
import { here, liveJudge, mode, recorded } from "./lib.js";
import * as packing from "./packing.js";
import * as stability from "./stability.js";

interface Experiment<T> {
  name: string;
  title: string;
  question: string;
  run(judge: Judge): Promise<T>;
  render(data: T): string;
}

const experiments: Array<Experiment<any>> = [
  { ...packing, title: "Packing: does judging many rows per request change the answers?", question: "semantic-sql packs up to K rows into one request. If probabilities drift with K, the cost saving is not free." },
  { ...heldout, title: "Held-out calibration: how good is a threshold picked on one fold when applied to another?", question: "The showcase's perfect separation was measured on the set that chose the threshold." },
  { ...stability, title: "Stability: does the same request return the same probability?", question: "The docs claim identical answers across runs; deterministic tests depend on it." },
  { ...adversarial, title: "Adversarial input: can text inside the message move the verdict?", question: "Predicates over user content meet injection, self-labeling, sarcasm, padding, and obfuscation." },
];

async function main(): Promise<void> {
  const selected = process.argv.slice(2).filter((arg) => !arg.startsWith("-"));
  const chosen = selected.length ? experiments.filter((e) => selected.includes(e.name)) : experiments;
  if (!chosen.length) throw new Error(`no experiment named ${selected.join(", ")}; known: ${experiments.map((e) => e.name).join(", ")}`);
  const judge = mode === "live" ? liveJudge() : undefined;
  const parts: string[] = ["# Experiments: recorded results", ""];
  parts.push("Raw results live in `experiments/results/*.json`; this file is rendered from them by `pnpm experiments`. `pnpm experiments:live` re-runs against TypeSafe (`jev-latest`) and overwrites the raw results. Every number below is from a real run on the inputs in `experiments/data/` and the experiment sources.");
  parts.push("");
  for (const experiment of experiments) {
    const active = chosen.includes(experiment);
    let result: { recordedAt: string; data: unknown };
    try {
      result = active && judge ? await recorded(experiment.name, () => experiment.run(judge)) : await recorded(experiment.name, () => Promise.reject(new Error("not selected")));
    } catch (error) {
      parts.push(`## ${experiment.title}`, "", `_No stored result yet (${error instanceof Error ? error.message : String(error)})._`, "");
      continue;
    }
    parts.push(`## ${experiment.title}`, "", `**Question.** ${experiment.question}`, "", `Recorded ${result.recordedAt.slice(0, 16).replace("T", " ")} UTC.`, "", experiment.render(result.data), "");
    console.log(`${experiment.name}: ${active && judge ? "ran live" : "rendered from stored results"}`);
  }
  const output = join(here, "RESULTS.md");
  writeFileSync(output, `${parts.join("\n")}\n`);
  console.log(`wrote ${output}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
