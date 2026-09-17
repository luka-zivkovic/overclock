import { canonicalize, sha256, stateHash, type Answer, type Question } from "@overclock/judgment-core";
import { sql, type Kysely } from "kysely";

/** What the row cache stores for one (model, text, question). */
export interface CachedRow {
  p: number;
  confidence?: number;
  answer: Answer;
  model: string;
}

/**
 * A row cache key. `key` is the lookup handle (`sha256(model + "\n" + text + "\n" + canonicalize(question))`);
 * the parts are kept alongside so table-backed caches can index them as columns.
 */
export interface RowCacheKey {
  key: string;
  stateHash: string;
  questionHash: string;
  model: string;
}

export interface RowCacheEntry {
  key: RowCacheKey;
  value: CachedRow;
}

/**
 * Per-row judgment cache. The core cache keys by the whole packed state, which never repeats
 * across packs, so the engine caches each (model, text, question) on its own.
 */
export interface RowCache {
  getMany(keys: RowCacheKey[]): Promise<Map<string, CachedRow>>;
  setMany(entries: RowCacheEntry[]): Promise<void>;
}

/** Build the row cache key for a text and the original (unprefixed) question. */
export function rowKey(model: string, text: string, question: Question): RowCacheKey {
  const canonicalQuestion = canonicalize(question);
  return {
    key: sha256(`${model}\n${text}\n${canonicalQuestion}`),
    stateHash: stateHash(text),
    questionHash: sha256(canonicalQuestion),
    model,
  };
}

/** In-memory LRU row cache. Default capacity 50,000 rows. */
export class MemoryRowCache implements RowCache {
  private readonly entries = new Map<string, CachedRow>();
  constructor(private readonly capacity = 50_000) {
    if (capacity < 1) throw new RangeError("MemoryRowCache capacity must be at least 1");
  }
  async getMany(keys: RowCacheKey[]): Promise<Map<string, CachedRow>> {
    const out = new Map<string, CachedRow>();
    for (const { key } of keys) {
      const value = this.entries.get(key);
      if (value === undefined) continue;
      this.entries.delete(key);
      this.entries.set(key, value);
      out.set(key, value);
    }
    return out;
  }
  async setMany(entries: RowCacheEntry[]): Promise<void> {
    for (const { key, value } of entries) {
      this.entries.delete(key.key);
      this.entries.set(key.key, value);
    }
    while (this.entries.size > this.capacity) {
      const oldest = this.entries.keys().next().value;
      if (oldest === undefined) break;
      this.entries.delete(oldest);
    }
  }
  get size(): number {
    return this.entries.size;
  }
  clear(): void {
    this.entries.clear();
  }
}

/** A cache that never stores anything. */
export class NoRowCache implements RowCache {
  async getMany(): Promise<Map<string, CachedRow>> {
    return new Map();
  }
  async setMany(): Promise<void> {}
}

export interface SemanticJudgmentsTable {
  state_hash: string;
  question_hash: string;
  model: string;
  p: number;
  confidence: number | null;
  answer: Answer;
  created_at: Date | string;
}

/**
 * Row cache in a Postgres table:
 *
 * ```sql
 * semantic_judgments(state_hash text, question_hash text, model text, p real, confidence real null,
 *                    answer jsonb, created_at timestamptz default now(),
 *                    primary key (state_hash, question_hash, model))
 * ```
 *
 * Call `ensureTable()` once (idempotent) or create the table in a migration.
 */
export class PostgresRowCache implements RowCache {
  private readonly table: string;
  private readonly chunkSize: number;

  constructor(
    private readonly db: Kysely<any>,
    options: { table?: string; chunkSize?: number } = {},
  ) {
    this.table = options.table ?? "semantic_judgments";
    this.chunkSize = options.chunkSize ?? 500;
  }

  async ensureTable(): Promise<void> {
    await sql`
      create table if not exists ${sql.table(this.table)} (
        state_hash text not null,
        question_hash text not null,
        model text not null,
        p real not null,
        confidence real null,
        answer jsonb not null,
        created_at timestamptz not null default now(),
        primary key (state_hash, question_hash, model)
      )
    `.execute(this.db);
  }

  async getMany(keys: RowCacheKey[]): Promise<Map<string, CachedRow>> {
    const out = new Map<string, CachedRow>();
    if (keys.length === 0) return out;
    const byTriple = new Map<string, RowCacheKey>();
    for (const key of keys) byTriple.set(`${key.stateHash}\n${key.questionHash}\n${key.model}`, key);
    const all = [...byTriple.values()];
    for (let i = 0; i < all.length; i += this.chunkSize) {
      const chunk = all.slice(i, i + this.chunkSize);
      const rows = await this.db
        .selectFrom(this.table)
        .select(["state_hash", "question_hash", "model", "p", "confidence", "answer"])
        .where("state_hash", "in", unique(chunk.map((k) => k.stateHash)))
        .where("question_hash", "in", unique(chunk.map((k) => k.questionHash)))
        .where("model", "in", unique(chunk.map((k) => k.model)))
        .execute();
      for (const row of rows as SemanticJudgmentsTable[]) {
        const key = byTriple.get(`${row.state_hash}\n${row.question_hash}\n${row.model}`);
        if (!key) continue;
        const value: CachedRow = { p: Number(row.p), answer: parseAnswer(row.answer), model: row.model };
        if (row.confidence !== null && row.confidence !== undefined) value.confidence = Number(row.confidence);
        out.set(key.key, value);
      }
    }
    return out;
  }

  async setMany(entries: RowCacheEntry[]): Promise<void> {
    if (entries.length === 0) return;
    for (let i = 0; i < entries.length; i += this.chunkSize) {
      const chunk = entries.slice(i, i + this.chunkSize);
      await this.db
        .insertInto(this.table)
        .values(
          chunk.map(({ key, value }) => ({
            state_hash: key.stateHash,
            question_hash: key.questionHash,
            model: key.model,
            p: value.p,
            confidence: value.confidence ?? null,
            answer: sql`${JSON.stringify(value.answer)}::jsonb`,
          })),
        )
        .onConflict((oc) => oc.columns(["state_hash", "question_hash", "model"]).doNothing())
        .execute();
    }
  }
}

function unique(values: string[]): string[] {
  return [...new Set(values)];
}

function parseAnswer(value: unknown): Answer {
  return (typeof value === "string" ? JSON.parse(value) : value) as Answer;
}
