#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { JudgmentClient, calibrate, judgeFromEnv, noul, renderCalibration, type CalibrationMetric } from "@overclock/judgment-core";
import { scopeToField } from "./predicates.js";

const HELP = `semantic-types calibrate <labeled.jsonl> --predicate "<text>" [options]

Each line: {"value": <any JSON>, "label": true|false}  (or "state" instead of "value")
Options:
  --predicate <text>   the s.is(...) text to calibrate (required)
  --field <path>       judge a field of each value instead of the whole value
  --metric <name>      f1 | precision | recall | accuracy | precision@<recall>   (default f1)
  --bins <n>           reliability bins (default 10)
  --fixtures <path>    fixture file for replay/record (default .judgment/fixtures.json)
  --json               print the full report as JSON
Environment: JUDGMENT_FIXTURES=replay|record|live (default replay), TYPESAFE_API_KEY for record/live.`;

function parseArgs(argv: string[]): { command: string | undefined; positional: string[]; flags: Record<string, string | true> } {
  const [command, ...rest] = argv;
  const positional: string[] = [];
  const flags: Record<string, string | true> = {};
  for (let i = 0; i < rest.length; i += 1) {
    const arg = rest[i]!;
    if (arg.startsWith("--")) {
      const name = arg.slice(2);
      const next = rest[i + 1];
      if (next !== undefined && !next.startsWith("--")) {
        flags[name] = next;
        i += 1;
      } else flags[name] = true;
    } else positional.push(arg);
  }
  return { command, positional, flags };
}

function parseMetric(raw: string | true | undefined): CalibrationMetric {
  if (raw === undefined || raw === true) return "f1";
  const at = /^precision@(\d*\.?\d+)$/.exec(raw);
  if (at) return { precisionAtRecall: Number(at[1]) };
  if (raw === "f1" || raw === "precision" || raw === "recall" || raw === "accuracy") return raw;
  throw new Error(`unknown metric ${raw}`);
}

export async function main(argv: string[] = process.argv.slice(2)): Promise<number> {
  const { command, positional, flags } = parseArgs(argv);
  if (command !== "calibrate" || positional.length !== 1 || typeof flags.predicate !== "string") {
    console.error(HELP);
    return 2;
  }
  const lines = readFileSync(positional[0]!, "utf8").split("\n").filter((line) => line.trim());
  const cases = lines.map((line, index) => {
    const row = JSON.parse(line) as { value?: unknown; state?: unknown; label?: unknown };
    if (typeof row.label !== "boolean") throw new Error(`line ${index + 1}: label must be a boolean`);
    return { value: row.value !== undefined ? row.value : row.state, label: row.label };
  });
  const judge = judgeFromEnv(typeof flags.fixtures === "string" ? { fixtures: flags.fixtures } : {});
  const client = new JudgmentClient({ judge });
  const field = typeof flags.field === "string" ? flags.field : undefined;
  const question = field ? scopeToField(noul(flags.predicate), field) : noul(flags.predicate);
  const judgments = await Promise.all(cases.map((c) => client.ask(c.value as never, question)));
  const items = cases.map((c, i) => ({ p: judgments[i]!.p, label: c.label }));
  const report = calibrate(items, { metric: parseMetric(flags.metric), ...(typeof flags.bins === "string" ? { bins: Number(flags.bins) } : {}) });
  if (flags.json) {
    console.log(JSON.stringify({ predicate: flags.predicate, field, report, usage: client.usage() }, null, 1));
  } else {
    console.log(`predicate: ${flags.predicate}${field ? ` (field ${field})` : ""}`);
    console.log(renderCalibration(report));
    console.log(`recommended: s.is(${JSON.stringify(flags.predicate)}, { threshold: ${report.best.threshold.toFixed(2)} })`);
    const usage = client.usage();
    console.log(`judge: ${judge.model}; requests ${usage.requests}, cache hits ${usage.cacheHits}, tokens ${usage.inputTokens}/${usage.outputTokens}`);
  }
  return 0;
}

const invokedDirectly = process.argv[1] && /cli\.(js|ts)$/.test(process.argv[1]);
if (invokedDirectly) {
  main().then(
    (code) => process.exit(code),
    (error) => {
      console.error(error instanceof Error ? error.message : error);
      process.exit(1);
    },
  );
}
