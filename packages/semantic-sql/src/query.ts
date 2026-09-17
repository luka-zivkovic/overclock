import { noul, questionHash, type ChoiceQuestion, type NoulQuestion, type ScoreQuestion } from "@overclock/judgment-core";
import { sql, type AliasNode, type CompiledQuery, type SelectQueryBuilder, type TableNode } from "kysely";
import { SemanticEngine, addStats, emptyStats, judgmentSlot, textOf, type Estimate, type Judged, type RunStats } from "./engine.js";
import { annotate, sortBySlot, toScoreQuestion } from "./functions.js";
import type { MaterializedColumn } from "./materialize.js";

export type SemanticOp =
  | { kind: "meaning"; column: string; question: NoulQuestion; threshold: number }
  | { kind: "choice"; column: string; question: ChoiceQuestion; labels: string[] }
  | { kind: "score"; column: string; question: ScoreQuestion; direction: "asc" | "desc" };

export interface SemanticQueryOptions {
  /**
   * Table name for materialized-column routing. When omitted it is read from the builder's
   * first `from` (a plain or aliased table); subqueries and joins leave it undefined and skip
   * routing.
   */
  table?: string;
}

export interface Explain {
  /** The structural query that will run, including any pushed-down semantic predicates. */
  sql: string;
  parameters: readonly unknown[];
  estimate: Estimate;
  /** Ops answered by SQL against a materialized column. */
  pushedDown: Array<{ op: SemanticOp; targetColumn: string }>;
  /** Ops that will run as a batched post-pass. */
  postPass: SemanticOp[];
}

interface State {
  ops: SemanticOp[];
  limit?: number;
  budget?: number;
  allowLargeScan: boolean;
}

type AnyBuilder = SelectQueryBuilder<any, any, any>;

/** Wrap a Kysely select query so semantic predicates can be chained onto it. */
export function semantic<DB, TB extends keyof DB, O>(
  qb: SelectQueryBuilder<DB, TB, O>,
  engine: SemanticEngine,
  options: SemanticQueryOptions = {},
): SemanticQuery<DB, TB, O> {
  const table = options.table ?? tableNameOf(qb);
  return new SemanticQuery(qb, engine, table, { ops: [], allowLargeScan: false });
}

/**
 * Structural predicates stay in the wrapped builder and run in SQL. Semantic predicates run as a
 * batched post-pass in declaration order (each filter only judges the survivors of the previous
 * one), then score ordering, then the limit. Every method returns a new query.
 */
export class SemanticQuery<DB, TB extends keyof DB, O> {
  constructor(
    private readonly qb: SelectQueryBuilder<DB, TB, O>,
    private readonly engine: SemanticEngine,
    private readonly table: string | undefined,
    private readonly state: State,
  ) {}

  private with(patch: Partial<State>): SemanticQuery<DB, TB, O> {
    return new SemanticQuery(this.qb, this.engine, this.table, { ...this.state, ...patch });
  }

  private push(op: SemanticOp): SemanticQuery<DB, TB, O> {
    return this.with({ ops: [...this.state.ops, op] });
  }

  /** Keep rows whose yes-probability for a noul question about `column` is >= threshold (default 0.5). */
  whereMeaning(column: keyof O & string, question: NoulQuestion | string, options: { threshold?: number } = {}): SemanticQuery<DB, TB, O> {
    const q = typeof question === "string" ? noul(question) : question;
    return this.push({ kind: "meaning", column, question: q, threshold: options.threshold ?? 0.5 });
  }

  /** Keep rows whose chosen label is one of `labels`. */
  whereChoice(column: keyof O & string, question: ChoiceQuestion, labels: string[]): SemanticQuery<DB, TB, O> {
    for (const label of labels) {
      if (!(label in question.criteria)) throw new TypeError(`label "${label}" is not one of the choice criteria`);
    }
    return this.push({ kind: "choice", column, question, labels });
  }

  /** Order by expected score against an ordered rubric; `name` is the score question's instructions. */
  orderByScore(column: keyof O & string, name: string, levels: string[], direction: "asc" | "desc" = "desc"): SemanticQuery<DB, TB, O> {
    return this.push({ kind: "score", column, question: toScoreQuestion({ instructions: name, levels }), direction });
  }

  /** Applied after semantic filtering and ordering. */
  limit(n: number): SemanticQuery<DB, TB, O> {
    if (!Number.isInteger(n) || n < 0) throw new RangeError("limit must be a non-negative integer");
    return this.with({ limit: n });
  }

  allowLargeScan(): SemanticQuery<DB, TB, O> {
    return this.with({ allowLargeScan: true });
  }

  budget(n: number): SemanticQuery<DB, TB, O> {
    return this.with({ budget: n });
  }

  /** The plan: pushdown SQL, cost estimate, and which ops go where. Judges nothing. */
  async explain(): Promise<Explain> {
    const plan = await this.plan();
    const compiled = plan.query.compile();
    const rows = await this.countRows(plan.query);
    return {
      sql: compiled.sql,
      parameters: compiled.parameters,
      estimate: this.engine.estimate({ rows, questions: plan.postPass.length }),
      pushedDown: plan.pushedDown,
      postPass: plan.postPass,
    };
  }

  async execute(): Promise<Judged<O>[]> {
    return (await this.executeWithStats()).rows;
  }

  async executeWithStats(): Promise<{ rows: Judged<O>[]; stats: RunStats }> {
    const started = performance.now();
    const plan = await this.plan();
    let stats = emptyStats();
    stats.pushedDown = plan.pushedDown.length;

    const budgetOptions = { allowLargeScan: this.state.allowLargeScan, ...(this.state.budget !== undefined ? { budget: this.state.budget } : {}) };
    if (plan.postPass.length > 0 && !this.state.allowLargeScan) {
      const count = await this.countRows(plan.query);
      this.engine.checkBudget(this.engine.estimate({ rows: count, questions: plan.postPass.length }), budgetOptions);
    }

    let rows = (await plan.query.execute()) as Judged<O>[];
    const rowsScanned = rows.length;

    const filters = plan.postPass.filter((op) => op.kind !== "score");
    const sorts = plan.postPass.filter((op): op is Extract<SemanticOp, { kind: "score" }> => op.kind === "score");

    for (const op of filters) {
      const run = await this.judge(rows, op);
      stats = addStats(stats, run.stats);
      const slot = judgmentSlot(op.question);
      rows = run.rows.filter((row) => {
        const summary = row.$judgments[slot]!;
        if (op.kind === "meaning") return summary.p >= op.threshold;
        return summary.answer.type === "choice" && op.labels.includes(summary.answer.choice);
      });
    }
    for (const op of sorts) {
      const run = await this.judge(rows, op);
      stats = addStats(stats, run.stats);
      rows = run.rows;
    }
    // Later sort keys are applied first so the first declared key wins (stable sort).
    for (const op of [...sorts].reverse()) rows = sortBySlot(rows, judgmentSlot(op.question), op.direction);
    if (this.state.limit !== undefined && !plan.limitPushedDown) rows = rows.slice(0, this.state.limit);

    // Each post-pass run counts its own input; the query's scan is the structural result.
    stats.rowsScanned = rowsScanned;
    const cost = this.engine.cost(stats.tokens);
    if (cost !== undefined) stats.estimatedCostUsd = cost;
    stats.durationMs = Math.round(performance.now() - started);
    this.engine.record(stats);
    return { rows: rows.map((row) => ({ ...row, $judgments: row.$judgments ?? {} })), stats };
  }

  private async judge(rows: Judged<O>[], op: SemanticOp): Promise<{ rows: Judged<O>[]; stats: RunStats }> {
    const texts = rows.map((row) => textOf((row as Record<string, unknown>)[op.column]));
    const run = await this.engine.judgeTexts(texts, op.question, { allowLargeScan: true, record: false });
    return { rows: rows.map((row, i) => annotate(row, run.judgments[i]!)), stats: run.stats };
  }

  /** Split ops into SQL pushdown (materialized) and post-pass, and build the structural query. */
  private async plan(): Promise<{ query: AnyBuilder; pushedDown: Explain["pushedDown"]; postPass: SemanticOp[]; limitPushedDown: boolean }> {
    let query = this.qb as AnyBuilder;
    const pushedDown: Explain["pushedDown"] = [];
    const postPass: SemanticOp[] = [];
    for (const op of this.state.ops) {
      const materialized = await this.materializedFor(op);
      if (!materialized) {
        postPass.push(op);
        continue;
      }
      const target = sql.ref(materialized.targetColumn);
      if (op.kind === "meaning") query = query.where(target, ">=", op.threshold);
      else if (op.kind === "score") query = query.orderBy(sql`${target} ${sql.raw(op.direction)} nulls last`);
      pushedDown.push({ op, targetColumn: materialized.targetColumn });
    }
    const limitPushedDown = postPass.length === 0 && this.state.limit !== undefined;
    if (limitPushedDown) query = query.limit(this.state.limit!);
    return { query, pushedDown, postPass, limitPushedDown };
  }

  private async materializedFor(op: SemanticOp): Promise<MaterializedColumn | undefined> {
    const registry = this.engine.materialized;
    if (!registry || this.table === undefined || op.kind === "choice") return undefined;
    return registry.lookup(this.table, op.column, questionHash(op.question), this.engine.model);
  }

  private async countRows(query: AnyBuilder): Promise<number> {
    const row = await query
      .clearSelect()
      .clearOrderBy()
      .clearLimit()
      .clearOffset()
      .select((eb) => eb.fn.countAll<string | number | bigint>().as("count"))
      .executeTakeFirst();
    return Number(row?.count ?? 0);
  }

  /** The structural query that would run, for logging. */
  compile(): Promise<CompiledQuery> {
    return this.plan().then((plan) => plan.query.compile());
  }
}

/** Read the first `from` table of a select builder: `from users` or `from users as u`. */
export function tableNameOf(qb: SelectQueryBuilder<any, any, any>): string | undefined {
  const node = qb.toOperationNode();
  const first = node.from?.froms[0];
  if (!first) return undefined;
  const table = first.kind === "AliasNode" ? (first as AliasNode).node : first;
  if (table.kind !== "TableNode") return undefined;
  return (table as TableNode).table.identifier.name;
}
