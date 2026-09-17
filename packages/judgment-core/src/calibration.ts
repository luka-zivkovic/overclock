import type { JudgmentClient } from "./client.js";
import type { EntryType, Question } from "./questions.js";

export interface CalibrationItem {
  /** Predicted probability that the label is true. */
  p: number;
  label: boolean;
}

export interface ThresholdRow {
  threshold: number;
  tp: number;
  fp: number;
  tn: number;
  fn: number;
  precision: number;
  recall: number;
  f1: number;
  accuracy: number;
}

export interface ReliabilityBin {
  lo: number;
  hi: number;
  count: number;
  meanP: number;
  /** Fraction of true labels in the bin; NaN when empty. */
  observed: number;
}

export type CalibrationMetric = "f1" | "precision" | "recall" | "accuracy" | { precisionAtRecall: number };

export interface CalibrationReport {
  n: number;
  positives: number;
  /** Mean squared error between p and label; 0 is perfect. */
  brier: number;
  /** Expected calibration error over the reliability bins. */
  ece: number;
  bins: ReliabilityBin[];
  thresholds: ThresholdRow[];
  best: { metric: CalibrationMetric; threshold: number; value: number; row: ThresholdRow };
  /** Accuracy at 0.5, the naive operating point. */
  agreementAtHalf: number;
}

export interface CalibrationOptions {
  /** Reliability bins. Default 10. */
  bins?: number;
  /** Metric the returned threshold maximizes. Default "f1". */
  metric?: CalibrationMetric;
  /** Candidate thresholds. Default: every distinct p plus 0.05 steps. */
  thresholds?: number[];
}

function rowAt(items: CalibrationItem[], threshold: number): ThresholdRow {
  let tp = 0;
  let fp = 0;
  let tn = 0;
  let fn = 0;
  for (const item of items) {
    const predicted = item.p >= threshold;
    if (predicted && item.label) tp += 1;
    else if (predicted && !item.label) fp += 1;
    else if (!predicted && !item.label) tn += 1;
    else fn += 1;
  }
  const precision = tp + fp === 0 ? 0 : tp / (tp + fp);
  const recall = tp + fn === 0 ? 0 : tp / (tp + fn);
  const f1 = precision + recall === 0 ? 0 : (2 * precision * recall) / (precision + recall);
  const accuracy = items.length === 0 ? 0 : (tp + tn) / items.length;
  return { threshold, tp, fp, tn, fn, precision, recall, f1, accuracy };
}

function metricValue(row: ThresholdRow, metric: CalibrationMetric): number {
  if (typeof metric === "string") return row[metric];
  return row.recall >= metric.precisionAtRecall ? row.precision : Number.NEGATIVE_INFINITY;
}

/** Thresholds should come from data. This turns labeled probabilities into an operating point. */
export function calibrate(items: CalibrationItem[], options: CalibrationOptions = {}): CalibrationReport {
  if (items.length === 0) throw new RangeError("calibrate() needs at least one labeled item");
  for (const item of items) {
    if (!(item.p >= 0 && item.p <= 1)) throw new RangeError(`probability out of range: ${item.p}`);
  }
  const binCount = options.bins ?? 10;
  const metric = options.metric ?? "f1";
  const candidates = options.thresholds ?? defaultThresholds(items);
  const positives = items.filter((item) => item.label).length;
  const brier = items.reduce((sum, item) => sum + (item.p - (item.label ? 1 : 0)) ** 2, 0) / items.length;

  const bins: ReliabilityBin[] = [];
  for (let i = 0; i < binCount; i += 1) {
    const lo = i / binCount;
    const hi = (i + 1) / binCount;
    const inBin = items.filter((item) => (i === binCount - 1 ? item.p >= lo && item.p <= hi : item.p >= lo && item.p < hi));
    const count = inBin.length;
    bins.push({
      lo,
      hi,
      count,
      meanP: count ? inBin.reduce((s, item) => s + item.p, 0) / count : Number.NaN,
      observed: count ? inBin.filter((item) => item.label).length / count : Number.NaN,
    });
  }
  const ece = bins.reduce((sum, bin) => (bin.count ? sum + (bin.count / items.length) * Math.abs(bin.observed - bin.meanP) : sum), 0);

  const thresholds = candidates.map((threshold) => rowAt(items, threshold));
  let best = thresholds[0]!;
  let bestValue = metricValue(best, metric);
  for (const row of thresholds) {
    const value = metricValue(row, metric);
    // Prefer the higher threshold on ties: it is the more conservative operating point.
    if (value > bestValue || (value === bestValue && row.threshold > best.threshold)) {
      best = row;
      bestValue = value;
    }
  }
  if (bestValue === Number.NEGATIVE_INFINITY) bestValue = Number.NaN;
  return {
    n: items.length,
    positives,
    brier,
    ece,
    bins,
    thresholds,
    best: { metric, threshold: best.threshold, value: bestValue, row: best },
    agreementAtHalf: rowAt(items, 0.5).accuracy,
  };
}

function defaultThresholds(items: CalibrationItem[]): number[] {
  const set = new Set<number>();
  for (let t = 0; t <= 1.0001; t += 0.05) set.add(Math.round(t * 100) / 100);
  for (const item of items) set.add(Math.round(item.p * 1000) / 1000);
  return [...set].sort((a, b) => a - b);
}

export interface LabeledCase {
  state: EntryType;
  question: Question;
  label: boolean;
}

/** Run labeled cases through a client, then calibrate on the returned probabilities. */
export async function calibrateJudgments(
  client: JudgmentClient,
  cases: LabeledCase[],
  options: CalibrationOptions = {},
): Promise<{ report: CalibrationReport; items: Array<CalibrationItem & { case: LabeledCase }> }> {
  const judgments = await Promise.all(cases.map((c) => client.ask(c.state, c.question)));
  const items = cases.map((c, i) => ({ p: judgments[i]!.p, label: c.label, case: c }));
  return { report: calibrate(items, options), items };
}

/** Plain-text reliability diagram and threshold summary for terminals and READMEs. */
export function renderCalibration(report: CalibrationReport): string {
  const lines: string[] = [];
  lines.push(`n=${report.n} positives=${report.positives} brier=${report.brier.toFixed(3)} ece=${report.ece.toFixed(3)}`);
  const metric = typeof report.best.metric === "string" ? report.best.metric : `precision@recall>=${report.best.metric.precisionAtRecall}`;
  lines.push(
    `best threshold ${report.best.threshold.toFixed(2)} by ${metric}: ${Number.isNaN(report.best.value) ? "unreachable" : report.best.value.toFixed(3)} ` +
      `(precision ${report.best.row.precision.toFixed(2)}, recall ${report.best.row.recall.toFixed(2)}, accuracy ${report.best.row.accuracy.toFixed(2)})`,
  );
  lines.push("reliability (bin: predicted -> observed, count)");
  for (const bin of report.bins) {
    if (!bin.count) {
      lines.push(`  ${bin.lo.toFixed(1)}-${bin.hi.toFixed(1)}  (empty)`);
      continue;
    }
    const bar = "#".repeat(Math.round(bin.observed * 20)).padEnd(20, ".");
    lines.push(`  ${bin.lo.toFixed(1)}-${bin.hi.toFixed(1)}  ${bin.meanP.toFixed(2)} -> ${bin.observed.toFixed(2)}  ${bar}  n=${bin.count}`);
  }
  return lines.join("\n");
}
