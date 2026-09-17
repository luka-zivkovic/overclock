import { questionHash, type Question } from "@overclock/judgment-core";
import { sql, type Kysely } from "kysely";
import { addStats, emptyStats, textOf, type RunStats, type SemanticEngine } from "./engine.js";

export interface MaterializedColumn {
  table: string;
  column: string;
  questionHash: string;
  targetColumn: string;
  question: Question;
  model: string;
}

/** Where the query layer learns that a (table, column, question, model) already lives in a real column. */
export interface MaterializedRegistry {
  lookup(table: string, column: string, questionHash: string, model: string): Promise<MaterializedColumn | undefined>;
  /** Find by the target column, for refresh. */
  lookupTarget(table: string, targetColumn: string): Promise<MaterializedColumn | undefined>;
  register(entry: MaterializedColumn): Promise<void>;
  list(): Promise<MaterializedColumn[]>;
}

/** In-memory registry, for tests and for engines that materialize nothing. */
export class MemoryMaterializedRegistry implements MaterializedRegistry {
  private readonly entries = new Map<string, MaterializedColumn>();
  async lookup(table: string, column: string, hash: string, model: string): Promise<MaterializedColumn | undefined> {
    return this.entries.get(`${table}\n${column}\n${hash}\n${model}`);
  }
  async lookupTarget(table: string, targetColumn: string): Promise<MaterializedColumn | undefined> {
    for (const entry of this.entries.values()) if (entry.table === table && entry.targetColumn === targetColumn) return entry;
    return undefined;
  }
  async register(entry: MaterializedColumn): Promise<void> {
    this.entries.set(`${entry.table}\n${entry.column}\n${entry.questionHash}\n${entry.model}`, entry);
  }
  async list(): Promise<MaterializedColumn[]> {
    return [...this.entries.values()];
  }
}

interface RegistryRow {
  table_name: string;
  column_name: string;
  question_hash: string;
  target_column: string;
  question: Question | string;
  model: string;
}

/**
 * Registry in a Postgres table:
 *
 * ```sql
 * semantic_materialized(table_name text, column_name text, question_hash text, target_column text,
 *                       question jsonb, model text, created_at timestamptz default now(),
 *                       primary key (table_name, column_name, question_hash, model))
 * ```
 */
export class PostgresMaterializedRegistry implements MaterializedRegistry {
  private readonly table: string;
  constructor(
    private readonly db: Kysely<any>,
    options: { table?: string } = {},
  ) {
    this.table = options.table ?? "semantic_materialized";
  }

  async ensureTable(): Promise<void> {
    await sql`
      create table if not exists ${sql.table(this.table)} (
        table_name text not null,
        column_name text not null,
        question_hash text not null,
        target_column text not null,
        question jsonb not null,
        model text not null,
        created_at timestamptz not null default now(),
        primary key (table_name, column_name, question_hash, model)
      )
    `.execute(this.db);
  }

  private base() {
    return this.db.selectFrom(this.table).select(["table_name", "column_name", "question_hash", "target_column", "question", "model"]);
  }

  async lookup(table: string, column: string, hash: string, model: string): Promise<MaterializedColumn | undefined> {
    const row = await this.base()
      .where("table_name", "=", table)
      .where("column_name", "=", column)
      .where("question_hash", "=", hash)
      .where("model", "=", model)
      .executeTakeFirst();
    return row ? fromRow(row as RegistryRow) : undefined;
  }

  async lookupTarget(table: string, targetColumn: string): Promise<MaterializedColumn | undefined> {
    const row = await this.base().where("table_name", "=", table).where("target_column", "=", targetColumn).executeTakeFirst();
    return row ? fromRow(row as RegistryRow) : undefined;
  }

  async register(entry: MaterializedColumn): Promise<void> {
    await this.db
      .insertInto(this.table)
      .values({
        table_name: entry.table,
        column_name: entry.column,
        question_hash: entry.questionHash,
        target_column: entry.targetColumn,
        question: sql`${JSON.stringify(entry.question)}::jsonb`,
        model: entry.model,
      })
      .onConflict((oc) => oc.columns(["table_name", "column_name", "question_hash", "model"]).doUpdateSet({ target_column: entry.targetColumn }))
      .execute();
  }

  async list(): Promise<MaterializedColumn[]> {
    const rows = await this.base().orderBy("table_name").orderBy("target_column").execute();
    return (rows as RegistryRow[]).map(fromRow);
  }
}

function fromRow(row: RegistryRow): MaterializedColumn {
  return {
    table: row.table_name,
    column: row.column_name,
    questionHash: row.question_hash,
    targetColumn: row.target_column,
    question: (typeof row.question === "string" ? JSON.parse(row.question) : row.question) as Question,
    model: row.model,
  };
}

export interface MaterializeOptions {
  table: string;
  column: string;
  question: Question | string;
  /** Target column name; created as nullable `real` when missing. */
  as: string;
  /** Rows judged per batch. Default 500. */
  batchSize?: number;
  /** Ordering / cursor column. Default "id". */
  keyColumn?: string;
  registry?: MaterializedRegistry;
  signal?: AbortSignal;
}

export interface RefreshOptions {
  table: string;
  as: string;
  batchSize?: number;
  keyColumn?: string;
  registry?: MaterializedRegistry;
  signal?: AbortSignal;
}

export interface MaterializeResult {
  table: string;
  column: string;
  targetColumn: string;
  questionHash: string;
  /** Rows judged and written in this call. */
  judged: number;
  batches: number;
  stats: RunStats;
}

/**
 * Add a real column holding the judgment probability (noul) or expected score (score) for
 * `question` over `column`, register it so `semantic()` queries route to SQL, and backfill
 * every row whose target is NULL.
 */
export async function materialize(db: Kysely<any>, engine: SemanticEngine, options: MaterializeOptions): Promise<MaterializeResult> {
  const question: Question = typeof options.question === "string" ? { type: "noul", instructions: options.question } : options.question;
  const registry = options.registry ?? engine.materialized ?? new PostgresMaterializedRegistry(db);
  if (registry instanceof PostgresMaterializedRegistry) await registry.ensureTable();
  await sql`alter table ${sql.table(options.table)} add column if not exists ${sql.ref(options.as)} real`.execute(db);
  const entry: MaterializedColumn = {
    table: options.table,
    column: options.column,
    questionHash: questionHash(question),
    targetColumn: options.as,
    question,
    model: engine.model,
  };
  await registry.register(entry);
  return backfill(db, engine, entry, options);
}

/** Judge only rows whose target column is NULL (new inserts): the polling-cursor worker step. */
export async function refresh(db: Kysely<any>, engine: SemanticEngine, options: RefreshOptions): Promise<MaterializeResult> {
  const registry = options.registry ?? engine.materialized ?? new PostgresMaterializedRegistry(db);
  const entry = await registry.lookupTarget(options.table, options.as);
  if (!entry) throw new Error(`no materialized column ${options.table}.${options.as}; run materialize() first`);
  return backfill(db, engine, entry, options);
}

export interface WatchOptions extends RefreshOptions {
  /** Poll interval. Default 5000 ms. */
  intervalMs?: number;
  signal: AbortSignal;
  onRefresh?: (result: MaterializeResult) => void;
}

/** Poll `refresh` until the signal aborts. Resolves with the totals. */
export async function watch(db: Kysely<any>, engine: SemanticEngine, options: WatchOptions): Promise<{ judged: number; refreshes: number }> {
  const intervalMs = options.intervalMs ?? 5000;
  let judged = 0;
  let refreshes = 0;
  while (!options.signal.aborted) {
    const result = await refresh(db, engine, options);
    judged += result.judged;
    refreshes += 1;
    options.onRefresh?.(result);
    await sleep(intervalMs, options.signal);
  }
  return { judged, refreshes };
}

async function backfill(
  db: Kysely<any>,
  engine: SemanticEngine,
  entry: MaterializedColumn,
  options: { batchSize?: number; keyColumn?: string; signal?: AbortSignal },
): Promise<MaterializeResult> {
  const batchSize = options.batchSize ?? 500;
  const keyColumn = options.keyColumn ?? "id";
  let judged = 0;
  let batches = 0;
  let stats = emptyStats();
  let cursor: unknown = undefined;
  for (;;) {
    if (options.signal?.aborted) break;
    let query = db
      .selectFrom(entry.table)
      .select([sql.ref(keyColumn).as("key"), sql.ref(entry.column).as("text")])
      .where(sql.ref(entry.targetColumn), "is", null)
      .orderBy(sql.ref(keyColumn))
      .limit(batchSize);
    if (cursor !== undefined) query = query.where(sql.ref(keyColumn), ">", cursor);
    const rows = (await query.execute()) as Array<{ key: unknown; text: unknown }>;
    if (rows.length === 0) break;
    const texts = rows.map((row) => textOf(row.text));
    const signal = options.signal;
    const run = await engine.judgeTexts(texts, entry.question, { allowLargeScan: true, record: false, ...(signal ? { signal } : {}) });
    stats = addStats(stats, run.stats);
    for (let i = 0; i < rows.length; i += 1) {
      const summary = run.judgments[i]!;
      const value = summary.answer.type === "score" ? summary.answer.score : summary.p;
      await db
        .updateTable(entry.table)
        .set({ [entry.targetColumn]: value })
        .where(sql.ref(keyColumn), "=", rows[i]!.key)
        .execute();
    }
    judged += rows.length;
    batches += 1;
    cursor = rows[rows.length - 1]!.key;
    if (rows.length < batchSize) break;
  }
  engine.record(stats);
  return { table: entry.table, column: entry.column, targetColumn: entry.targetColumn, questionHash: entry.questionHash, judged, batches, stats };
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) return resolve();
    const timer = setTimeout(done, ms);
    function done() {
      clearTimeout(timer);
      signal.removeEventListener("abort", done);
      resolve();
    }
    signal.addEventListener("abort", done, { once: true });
  });
}
