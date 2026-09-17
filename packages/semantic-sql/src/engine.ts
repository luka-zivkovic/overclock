import {
  JudgmentError,
  answerConfidence,
  answerProbability,
  createLimiter,
  questionHash,
  type Answer,
  type EntryType,
  type Judge,
  type JudgeResponse,
  type Question,
} from "@overclock/judgment-core";
import { MemoryRowCache, rowKey, type CachedRow, type RowCache, type RowCacheEntry, type RowCacheKey } from "./cache.js";
import type { MaterializedRegistry } from "./materialize.js";

/** Why a row matched: the probability, the full answer, and the question that produced it. */
export interface JudgmentSummary {
  p: number;
  confidence?: number;
  answer: Answer;
  question: Question;
  cached: boolean;
}

/** Rows returned by every semantic operator carry their evidence under `$judgments[questionHash]`. */
export type Judged<T> = T & { $judgments: Record<string, JudgmentSummary> };

export interface RunStats {
  /** Rows that entered the semantic pass (after structural pushdown). */
  rowsScanned: number;
  /** Row judgments requested, including cache hits and deduplicated identical texts. */
  judgments: number;
  cacheHits: number;
  apiCalls: number;
  packs: number;
  /** Semantic operators answered by SQL against a materialized column. */
  pushedDown: number;
  tokens: { input: number; output: number };
  /** Only present when `pricing` is configured; computed from returned usage. */
  estimatedCostUsd?: number;
  durationMs: number;
}

export interface Estimate {
  rows: number;
  questions: number;
  /** rows * questions: the worst case before cache hits. */
  judgments: number;
  packs: number;
}

export interface Pricing {
  inputPerMillion?: number;
  outputPerMillion?: number;
}

export interface SemanticEngineOptions {
  judge: Judge;
  /** Default: MemoryRowCache(). Pass NoRowCache to disable. */
  rowCache?: RowCache;
  /** Rows per judge call. Default 100. */
  packSize?: number;
  /** Upper bound on canonical state bytes per pack. Default 64 KiB. */
  maxPackBytes?: number;
  /** Concurrent judge calls. Default 4. */
  concurrency?: number;
  /** USD per million tokens; when absent no cost is reported. */
  pricing?: Pricing;
  /** Max judgments per query before ScanBudgetExceededError. Default 5000. */
  budget?: number;
  /** Where the query layer looks up materialized semantic columns. */
  materialized?: MaterializedRegistry;
}

export interface JudgeTextsOptions {
  signal?: AbortSignal;
  /** Skip the budget check for this call. */
  allowLargeScan?: boolean;
  /** Override the engine budget for this call. */
  budget?: number;
  /** Set to false when a compound run will call `record()` with merged stats itself. Default true. */
  record?: boolean;
}

export class ScanBudgetExceededError extends JudgmentError {
  constructor(
    readonly estimate: Estimate,
    readonly budget: number,
  ) {
    super(
      `query would need up to ${estimate.judgments} judgments (${estimate.rows} rows x ${estimate.questions} questions, ` +
        `~${estimate.packs} calls); budget is ${budget}. Narrow the structural query, raise budget, or pass allowLargeScan: true.`,
    );
    this.name = "ScanBudgetExceededError";
  }
}

export const ROW_PREFIX = "Regarding row";

export function emptyStats(): RunStats {
  return { rowsScanned: 0, judgments: 0, cacheHits: 0, apiCalls: 0, packs: 0, pushedDown: 0, tokens: { input: 0, output: 0 }, durationMs: 0 };
}

export function addStats(a: RunStats, b: RunStats): RunStats {
  const out: RunStats = {
    rowsScanned: a.rowsScanned + b.rowsScanned,
    judgments: a.judgments + b.judgments,
    cacheHits: a.cacheHits + b.cacheHits,
    apiCalls: a.apiCalls + b.apiCalls,
    packs: a.packs + b.packs,
    pushedDown: a.pushedDown + b.pushedDown,
    tokens: { input: a.tokens.input + b.tokens.input, output: a.tokens.output + b.tokens.output },
    durationMs: a.durationMs + b.durationMs,
  };
  if (a.estimatedCostUsd !== undefined || b.estimatedCostUsd !== undefined) {
    out.estimatedCostUsd = (a.estimatedCostUsd ?? 0) + (b.estimatedCostUsd ?? 0);
  }
  return out;
}

/** Convert any column value to the text the judge sees. */
export function textOf(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "";
  if (value instanceof Date) return value.toISOString();
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

/** The question asked about one packed row: the original, addressed to that row id. */
export function packedQuestion(question: Question, id: string): Question {
  const original = question.instructions;
  const instructions: EntryType =
    typeof original === "string" || original === undefined
      ? `${ROW_PREFIX} "${id}": ${original ?? ""}`
      : { regarding_row: id, instructions: original };
  return { ...question, instructions } as Question;
}

interface PackItem {
  id: string;
  text: string;
  index: number;
}

/**
 * Runs one question over many texts: row-level cache first, then packs of `packSize` rows per
 * judge call, bounded by `concurrency`. The state of a pack is `{ rows: [{ id, text }, ...] }`
 * and each row gets its own copy of the question, named by its id (`r0`, `r1`, ...).
 */
export class SemanticEngine {
  readonly judge: Judge;
  readonly rowCache: RowCache;
  readonly packSize: number;
  readonly maxPackBytes: number;
  readonly budget: number;
  readonly pricing: Pricing | undefined;
  readonly materialized: MaterializedRegistry | undefined;
  private readonly limit: <T>(task: () => Promise<T>) => Promise<T>;
  private last: RunStats = emptyStats();
  private total: RunStats = emptyStats();

  constructor(options: SemanticEngineOptions) {
    this.judge = options.judge;
    this.rowCache = options.rowCache ?? new MemoryRowCache();
    this.packSize = options.packSize ?? 100;
    this.maxPackBytes = options.maxPackBytes ?? 64 * 1024;
    this.budget = options.budget ?? 5000;
    this.pricing = options.pricing;
    this.materialized = options.materialized;
    if (!Number.isInteger(this.packSize) || this.packSize < 1) throw new RangeError("packSize must be a positive integer");
    this.limit = createLimiter(options.concurrency ?? 4);
  }

  get model(): string {
    return this.judge.model;
  }

  /** Worst-case work for a query, before cache hits. */
  estimate(input: { rows: number; questions: number }): Estimate {
    const packs = Math.ceil(input.rows / this.packSize) * input.questions;
    return { rows: input.rows, questions: input.questions, judgments: input.rows * input.questions, packs };
  }

  /** Throw ScanBudgetExceededError when an estimate exceeds the budget, unless allowLargeScan. */
  checkBudget(estimate: Estimate, options: { allowLargeScan?: boolean; budget?: number } = {}): void {
    if (options.allowLargeScan) return;
    const budget = options.budget ?? this.budget;
    if (estimate.judgments > budget) throw new ScanBudgetExceededError(estimate, budget);
  }

  lastStats(): RunStats {
    return cloneStats(this.last);
  }

  totals(): RunStats {
    return cloneStats(this.total);
  }

  /** Record a run's stats as the last run and add them to the totals. */
  record(stats: RunStats): void {
    this.last = cloneStats(stats);
    this.total = addStats(this.total, stats);
  }

  /** Price token usage with the configured rates; undefined when no pricing is configured. */
  cost(usage: { input: number; output: number }): number | undefined {
    if (!this.pricing) return undefined;
    const input = ((this.pricing.inputPerMillion ?? 0) * usage.input) / 1_000_000;
    const output = ((this.pricing.outputPerMillion ?? 0) * usage.output) / 1_000_000;
    return input + output;
  }

  /** Judge one question over many texts. `judgments[i]` is the answer for `texts[i]`. */
  async judgeTexts(
    texts: string[],
    question: Question,
    options: JudgeTextsOptions = {},
  ): Promise<{ judgments: JudgmentSummary[]; stats: RunStats }> {
    const started = performance.now();
    const stats = emptyStats();
    stats.rowsScanned = texts.length;
    stats.judgments = texts.length;
    this.checkBudget(this.estimate({ rows: texts.length, questions: 1 }), options);

    // Identical texts share one judgment.
    const uniqueTexts: string[] = [];
    const uniqueIndex = new Map<string, number>();
    const textToUnique: number[] = texts.map((text) => {
      let index = uniqueIndex.get(text);
      if (index === undefined) {
        index = uniqueTexts.length;
        uniqueIndex.set(text, index);
        uniqueTexts.push(text);
      }
      return index;
    });

    const keys: RowCacheKey[] = uniqueTexts.map((text) => rowKey(this.model, text, question));
    const cached = await this.rowCache.getMany(keys);
    const results: Array<CachedRow | undefined> = keys.map((key) => cached.get(key.key));
    stats.cacheHits = textToUnique.filter((u) => results[u] !== undefined).length;

    const misses: PackItem[] = [];
    uniqueTexts.forEach((text, index) => {
      if (results[index] === undefined) misses.push({ id: "", text, index });
    });

    if (misses.length > 0) {
      const packs = this.pack(misses);
      stats.packs = packs.length;
      const responses = await Promise.all(packs.map((pack) => this.limit(() => this.judgePack(pack, question, options.signal))));
      const entries: RowCacheEntry[] = [];
      for (let i = 0; i < packs.length; i += 1) {
        const pack = packs[i]!;
        const response = responses[i]!;
        stats.apiCalls += 1;
        stats.tokens.input += response.usage.input_tokens;
        stats.tokens.output += response.usage.output_tokens;
        for (const item of pack) {
          const answer = response.answers[item.id];
          if (!answer) throw new JudgmentError(`judge returned no answer for packed row ${item.id}`);
          const row: CachedRow = { p: answerProbability(answer, question), answer, model: response.model };
          const confidence = answerConfidence(answer);
          if (confidence !== undefined) row.confidence = confidence;
          results[item.index] = row;
          entries.push({ key: keys[item.index]!, value: row });
        }
      }
      await this.rowCache.setMany(entries);
    }

    const judgments: JudgmentSummary[] = textToUnique.map((u) => {
      const row = results[u]!;
      const summary: JudgmentSummary = { p: row.p, answer: row.answer, question, cached: cached.has(keys[u]!.key) };
      if (row.confidence !== undefined) summary.confidence = row.confidence;
      return summary;
    });

    const cost = this.cost(stats.tokens);
    if (cost !== undefined) stats.estimatedCostUsd = cost;
    stats.durationMs = Math.round(performance.now() - started);
    if (options.record !== false) this.record(stats);
    return { judgments, stats };
  }

  /** Group misses into packs of at most packSize rows and maxPackBytes of canonical state. */
  private pack(items: PackItem[]): PackItem[][] {
    const packs: PackItem[][] = [];
    let current: PackItem[] = [];
    let bytes = PACK_OVERHEAD;
    const flush = () => {
      if (current.length > 0) packs.push(current);
      current = [];
      bytes = PACK_OVERHEAD;
    };
    for (const item of items) {
      const size = rowBytes(item.text) + 1;
      if (size + PACK_OVERHEAD > this.maxPackBytes) {
        // A single oversized text gets its own call.
        flush();
        packs.push([{ ...item, id: "r0" }]);
        continue;
      }
      if (current.length >= this.packSize || bytes + size > this.maxPackBytes) flush();
      current.push({ ...item, id: `r${current.length}` });
      bytes += size;
    }
    flush();
    return packs;
  }

  private async judgePack(pack: PackItem[], question: Question, signal: AbortSignal | undefined): Promise<JudgeResponse> {
    const state = { rows: pack.map(({ id, text }) => ({ id, text })) };
    const questions: Record<string, Question> = {};
    for (const item of pack) questions[item.id] = packedQuestion(question, item.id);
    return this.judge.judge({ state, questions }, signal ? { signal } : {});
  }
}

/** Bytes of `{"rows":[]}` plus slack for separators. */
const PACK_OVERHEAD = 12;

function rowBytes(text: string): number {
  // {"id":"r99","text":<json>}
  return 24 + Buffer.byteLength(JSON.stringify(text), "utf8");
}

function cloneStats(stats: RunStats): RunStats {
  return { ...stats, tokens: { ...stats.tokens } };
}

/** Key under which a question's evidence is stored on a row. */
export function judgmentSlot(question: Question): string {
  return questionHash(question);
}

