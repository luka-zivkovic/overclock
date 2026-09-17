import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { TypeSafeJudge, type Judge } from "@overclock/judgment-core";

export const here = dirname(fileURLToPath(import.meta.url));
export const resultsDir = join(here, "results");

/** Experiments run live and persist raw results; replay re-renders from the stored JSON. */
export const mode: "live" | "replay" = process.env.JUDGMENT_FIXTURES === "live" || process.env.JUDGMENT_FIXTURES === "record" ? "live" : "replay";

export function liveJudge(): Judge {
  if (!process.env.TYPESAFE_API_KEY) throw new Error("live experiments need TYPESAFE_API_KEY (or run in replay mode with stored results)");
  return new TypeSafeJudge();
}

export function resultPath(name: string): string {
  return join(resultsDir, `${name}.json`);
}

export function saveResult<T>(name: string, data: T): void {
  mkdirSync(resultsDir, { recursive: true });
  writeFileSync(resultPath(name), `${JSON.stringify({ recordedAt: new Date().toISOString(), data }, null, 1)}\n`);
}

export function loadResult<T>(name: string): { recordedAt: string; data: T } | undefined {
  const path = resultPath(name);
  if (!existsSync(path)) return undefined;
  return JSON.parse(readFileSync(path, "utf8")) as { recordedAt: string; data: T };
}

/** Run live and store, or load the stored run. */
export async function recorded<T>(name: string, run: () => Promise<T>): Promise<{ recordedAt: string; data: T }> {
  if (mode === "live") {
    const data = await run();
    saveResult(name, data);
    return { recordedAt: new Date().toISOString(), data };
  }
  const stored = loadResult<T>(name);
  if (!stored) throw new Error(`no stored result for ${name}; run with JUDGMENT_FIXTURES=live`);
  return stored;
}

export function table(headers: string[], rows: Array<Array<string | number>>): string {
  const line = (cells: Array<string | number>) => `| ${cells.map((c) => String(c).replace(/\|/g, "\\|")).join(" | ")} |`;
  return [line(headers), `| ${headers.map(() => "---").join(" | ")} |`, ...rows.map(line)].join("\n");
}

export function mean(values: number[]): number {
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : Number.NaN;
}

export function max(values: number[]): number {
  return values.length ? Math.max(...values) : Number.NaN;
}

export function stddev(values: number[]): number {
  if (values.length < 2) return 0;
  const m = mean(values);
  return Math.sqrt(values.reduce((s, v) => s + (v - m) ** 2, 0) / (values.length - 1));
}

export function fmt(value: number, digits = 3): string {
  return Number.isFinite(value) ? value.toFixed(digits) : "n/a";
}

export function pct(value: number): string {
  return Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "n/a";
}

/** Deterministic split by id hash so the same messages land in the same fold every run. */
export function splitByHash<T extends { id: string }>(items: T[], calibrationShare: number): { calibration: T[]; heldOut: T[] } {
  const calibration: T[] = [];
  const heldOut: T[] = [];
  for (const item of items) {
    let hash = 0;
    for (const ch of item.id) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
    (hash % 100 < calibrationShare * 100 ? calibration : heldOut).push(item);
  }
  return { calibration, heldOut };
}

export function binaryMetrics(pairs: Array<{ p: number; label: boolean }>, threshold: number): { accuracy: number; precision: number; recall: number; f1: number; brier: number; n: number } {
  let tp = 0;
  let fp = 0;
  let tn = 0;
  let fn = 0;
  let brier = 0;
  for (const { p, label } of pairs) {
    const predicted = p >= threshold;
    if (predicted && label) tp += 1;
    else if (predicted) fp += 1;
    else if (label) fn += 1;
    else tn += 1;
    brier += (p - (label ? 1 : 0)) ** 2;
  }
  const precision = tp + fp ? tp / (tp + fp) : 0;
  const recall = tp + fn ? tp / (tp + fn) : 0;
  return {
    n: pairs.length,
    accuracy: pairs.length ? (tp + tn) / pairs.length : 0,
    precision,
    recall,
    f1: precision + recall ? (2 * precision * recall) / (precision + recall) : 0,
    brier: pairs.length ? brier / pairs.length : 0,
  };
}
