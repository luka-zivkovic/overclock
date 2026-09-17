import { choice as choiceQuestion, judgeFromEnv, noul, score, type ChoiceQuestion, type NoulQuestion, type ScoreQuestion } from "@overclock/judgment-core";
import { SemanticEngine, judgmentSlot, textOf, type Judged, type JudgmentSummary, type RunStats } from "./engine.js";

export interface SemanticOptions {
  /** Default: a lazily created engine over `judgeFromEnv()` (replay/record/live by environment). */
  engine?: SemanticEngine;
  allowLargeScan?: boolean;
  budget?: number;
  signal?: AbortSignal;
}

export interface FilterOptions extends SemanticOptions {
  /** Keep rows with p >= threshold. Default 0.5. */
  threshold?: number;
}

export type ScoreSpec = ScoreQuestion | { instructions: string; levels: string[] };

let defaultEngine: SemanticEngine | undefined;

function engineOf(options: SemanticOptions): SemanticEngine {
  if (options.engine) return options.engine;
  defaultEngine ??= new SemanticEngine({ judge: judgeFromEnv() });
  return defaultEngine;
}

function judgeOptions(options: SemanticOptions) {
  const out: { allowLargeScan?: boolean; budget?: number; signal?: AbortSignal } = {};
  if (options.allowLargeScan !== undefined) out.allowLargeScan = options.allowLargeScan;
  if (options.budget !== undefined) out.budget = options.budget;
  if (options.signal !== undefined) out.signal = options.signal;
  return out;
}

export function toScoreQuestion(spec: ScoreSpec): ScoreQuestion {
  if ("type" in spec) return spec;
  const [first, second, ...rest] = spec.levels;
  if (first === undefined || second === undefined) throw new TypeError("score levels need at least two entries");
  return score(spec.instructions, [first, second, ...rest]);
}

/** Attach a judgment to a row under `$judgments[questionHash]`, keeping earlier evidence. */
export function annotate<T>(row: T, summary: JudgmentSummary): Judged<T> {
  const existing = (row as { $judgments?: Record<string, JudgmentSummary> }).$judgments ?? {};
  return { ...row, $judgments: { ...existing, [judgmentSlot(summary.question)]: summary } };
}

/** Judge `question` about `rows[i][column]` for every row and return the annotated rows plus stats. */
export async function judgeRows<T>(
  rows: T[],
  column: keyof T & string,
  question: NoulQuestion | ChoiceQuestion | ScoreQuestion,
  options: SemanticOptions = {},
): Promise<{ rows: Judged<T>[]; stats: RunStats }> {
  const engine = engineOf(options);
  const texts = rows.map((row) => textOf(row[column]));
  const { judgments, stats } = await engine.judgeTexts(texts, question, judgeOptions(options));
  return { rows: rows.map((row, i) => annotate(row, judgments[i]!)), stats };
}

/** Annotate every row with its judgment; no filtering. */
export async function semanticScore<T>(
  rows: T[],
  column: keyof T & string,
  question: NoulQuestion | ChoiceQuestion | ScoreQuestion | string,
  options: SemanticOptions = {},
): Promise<Judged<T>[]> {
  const q = typeof question === "string" ? noul(question) : question;
  return (await judgeRows(rows, column, q, options)).rows;
}

/** Keep rows whose yes-probability for the question is at least `threshold` (default 0.5). */
export async function semanticFilter<T>(
  rows: T[],
  column: keyof T & string,
  question: NoulQuestion | string,
  options: FilterOptions = {},
): Promise<Judged<T>[]> {
  const q = typeof question === "string" ? noul(question) : question;
  const threshold = options.threshold ?? 0.5;
  const slot = judgmentSlot(q);
  const judged = await judgeRows(rows, column, q, options);
  return judged.rows.filter((row) => row.$judgments[slot]!.p >= threshold);
}

/** Stable sort by expected score against an ordered rubric. */
export async function semanticSort<T>(
  rows: T[],
  column: keyof T & string,
  question: ScoreSpec,
  direction: "asc" | "desc" = "desc",
  options: SemanticOptions = {},
): Promise<Judged<T>[]> {
  const q = toScoreQuestion(question);
  const slot = judgmentSlot(q);
  const judged = await judgeRows(rows, column, q, options);
  return sortBySlot(judged.rows, slot, direction);
}

export function sortBySlot<T extends Judged<unknown>>(rows: T[], slot: string, direction: "asc" | "desc"): T[] {
  const sign = direction === "asc" ? 1 : -1;
  return rows
    .map((row, index) => ({ row, index, value: scoreOf(row.$judgments[slot]) }))
    .sort((a, b) => sign * (a.value - b.value) || a.index - b.index)
    .map((item) => item.row);
}

function scoreOf(summary: JudgmentSummary | undefined): number {
  if (!summary) return Number.NEGATIVE_INFINITY;
  return summary.answer.type === "score" ? summary.answer.score : summary.p;
}

/** Group rows by the chosen label of a choice question. Every label is present, possibly empty. */
export async function semanticGroupBy<T>(
  rows: T[],
  column: keyof T & string,
  question: ChoiceQuestion,
  options: SemanticOptions = {},
): Promise<Map<string, Judged<T>[]>> {
  const slot = judgmentSlot(question);
  const judged = await judgeRows(rows, column, question, options);
  const groups = new Map<string, Judged<T>[]>();
  for (const label of Object.keys(question.criteria)) groups.set(label, []);
  for (const row of judged.rows) {
    const answer = row.$judgments[slot]!.answer;
    const label = answer.type === "choice" ? answer.choice : String(answer.type);
    const bucket = groups.get(label);
    if (bucket) bucket.push(row);
    else groups.set(label, [row]);
  }
  return groups;
}

export { choiceQuestion as choice, noul, score };
