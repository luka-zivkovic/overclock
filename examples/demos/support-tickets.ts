import { PGlite } from "@electric-sql/pglite";
import type { JudgmentClient } from "@overclock/judgment-core";
import { PGliteDialect, PostgresMaterializedRegistry, PostgresRowCache, SemanticEngine, choice, materialize, semantic } from "@overclock/semantic-sql";
import { Kysely, sql, type Generated } from "kysely";
import { code, pct, table, type DemoReport } from "./types.js";

interface DB {
  tickets: { id: Generated<number>; customer: string; body: string; created_at: Date; mentions_delay?: number | null };
}

const tickets: Array<{ customer: string; body: string; daysAgo: number }> = [
  { customer: "acme", body: "Order #4471 was supposed to arrive Tuesday and the tracking page still says 'label created'. It's Friday.", daysAgo: 1 },
  { customer: "acme", body: "Can I change the billing email on our account to finance@acme.example?", daysAgo: 2 },
  { customer: "globex", body: "Your courier left the parcel at the wrong building and now it's gone. I need this resolved today.", daysAgo: 1 },
  { customer: "globex", body: "Love the new dashboard, just wanted to say thanks.", daysAgo: 3 },
  { customer: "initech", body: "Third week waiting on the replacement unit. Every update says 'shipping soon'. What is going on?", daysAgo: 2 },
  { customer: "initech", body: "How do I export last quarter's invoices as CSV?", daysAgo: 4 },
  { customer: "umbrella", body: "The package arrived but the box was crushed and two of the five units are cracked.", daysAgo: 1 },
  { customer: "umbrella", body: "Shipment delayed again? The ETA moved from the 3rd to the 9th with no explanation. We have a launch on the 8th.", daysAgo: 0 },
  { customer: "hooli", body: "Please cancel my subscription at the end of this billing cycle.", daysAgo: 5 },
  { customer: "hooli", body: "Password reset emails never arrive. Checked spam.", daysAgo: 2 },
  { customer: "stark", body: "Delivery was one day late but everything is fine. No action needed, just FYI.", daysAgo: 6 },
  { customer: "stark", body: "Can we get a quote for 500 units with delivery before the end of the month?", daysAgo: 1 },
  { customer: "wayne", body: "Where is my order? It's been two weeks since the confirmation email and nothing since.", daysAgo: 0 },
  { customer: "wayne", body: "Requesting the SOC 2 report for our vendor review.", daysAgo: 9 },
];

export async function supportTickets(client: JudgmentClient): Promise<DemoReport> {
  const pg = new PGlite();
  const db = new Kysely<DB>({ dialect: new PGliteDialect(pg) });
  await sql`create table tickets (id serial primary key, customer text not null, body text not null, created_at timestamptz not null)`.execute(db);
  const now = Date.now();
  await db
    .insertInto("tickets")
    .values(tickets.map((t) => ({ customer: t.customer, body: t.body, created_at: new Date(now - t.daysAgo * 86_400_000) })))
    .execute();

  const cache = new PostgresRowCache(db);
  await cache.ensureTable();
  const registry = new PostgresMaterializedRegistry(db);
  await registry.ensureTable();
  const engine = new SemanticEngine({ judge: client.judge, rowCache: cache, materialized: registry, packSize: 8 });
  const lastWeek = new Date(now - 7 * 86_400_000);

  const sections: DemoReport["sections"] = [];
  const structural = db.selectFrom("tickets").selectAll().where("created_at", ">", lastWeek);

  // Query 1: semantic filter + score ordering with a limit.
  const q1 = semantic(structural, engine)
    .whereMeaning("body", "mentions a shipping delay", { threshold: 0.75 })
    .orderByScore("body", "urgency", ["none", "mild", "high"], "desc")
    .limit(5);
  const first = await q1.executeWithStats();
  sections.push({
    heading: "Query 1: delayed shipments, most urgent first",
    body:
      code(`const rows = await semantic(db.selectFrom("tickets").selectAll().where("created_at", ">", lastWeek), engine)
  .whereMeaning("body", "mentions a shipping delay", { threshold: 0.75 })   // batched post-pass
  .orderByScore("body", "urgency", ["none", "mild", "high"], "desc")          // batched post-pass
  .limit(5)
  .executeWithStats();`) +
      "\n\n" +
      table(
        ["customer", "ticket", "p(delay)", "urgency"],
        first.rows.map((row) => {
          const judgments = Object.values(row.$judgments);
          const delay = judgments.find((j) => j.answer.type === "noul");
          const urgency = judgments.find((j) => j.answer.type === "score");
          return [row.customer, row.body.slice(0, 70) + (row.body.length > 70 ? "…" : ""), delay ? pct(delay.p) : "—", urgency && urgency.answer.type === "score" ? urgency.answer.score.toFixed(2) : "—"];
        }),
      ) +
      "\n\n" +
      `Stats: ${first.stats.rowsScanned} rows scanned after SQL pushdown, ${first.stats.judgments} judgments, ${first.stats.apiCalls} API calls in ${first.stats.packs} packs, ${first.stats.cacheHits} cache hits, ${first.stats.tokens.input} / ${first.stats.tokens.output} tokens.`,
  });

  // Query 2: identical query, served from the Postgres row cache.
  const second = await q1.executeWithStats();
  sections.push({
    heading: "Query 2: the same query again",
    body: `Stats: ${second.stats.rowsScanned} rows scanned, ${second.stats.judgments} judgments, ${second.stats.apiCalls} API calls, ${second.stats.cacheHits} cache hits. The second run is a lookup in the \`semantic_judgments\` table.`,
  });

  // Query 3: the cost planner refuses an unbounded scan.
  let refused = "not refused";
  try {
    await semantic(db.selectFrom("tickets").selectAll(), engine).whereMeaning("body", "is about billing").budget(5).execute();
  } catch (error) {
    refused = error instanceof Error ? error.message : String(error);
  }
  const explained = await semantic(db.selectFrom("tickets").selectAll(), engine).whereMeaning("body", "is about billing").explain();
  sections.push({
    heading: "Query 3: the cost planner",
    body:
      code(`await semantic(db.selectFrom("tickets").selectAll(), engine)
  .whereMeaning("body", "is about billing")
  .budget(5)          // max judgments for this query
  .execute();         // throws ScanBudgetExceededError with the estimate`) +
      "\n\n" +
      `Refused: \`${refused}\`\n\n\`explain()\` for the unbudgeted version: ${JSON.stringify(explained.estimate)} over SQL \`${explained.sql}\`.`,
  });

  // Query 4: materialize the predicate into a column, then the planner pushes it into SQL.
  const materialized = await materialize(db, engine, { table: "tickets", column: "body", question: "mentions a shipping delay", as: "mentions_delay" });
  const pushed = await semantic(db.selectFrom("tickets").selectAll(), engine).whereMeaning("body", "mentions a shipping delay", { threshold: 0.75 }).executeWithStats();
  sections.push({
    heading: "Query 4: materialize, then it is just SQL",
    body:
      code(`semantic-sql materialize tickets.body "mentions a shipping delay" --as mentions_delay
# adds a nullable real column, backfills in batches, registers the mapping`) +
      "\n\n" +
      `Backfilled ${materialized.judged} rows in ${materialized.batches} batch${materialized.batches === 1 ? "" : "es"}. The next \`whereMeaning\` on the same column and question compiled to \`where mentions_delay >= 0.75\`: ${pushed.stats.pushedDown} predicate pushed down, ${pushed.stats.apiCalls} API calls, ${pushed.rows.length} rows.\n\n` +
      table(["customer", "mentions_delay"], pushed.rows.map((row) => [row.customer, ((row as { mentions_delay?: number | null }).mentions_delay ?? 0).toFixed(2)])),
  });

  // Query 5: group by choice.
  const grouped = await semantic(db.selectFrom("tickets").selectAll(), engine)
    .whereChoice("body", choice("What kind of request is this?", { shipping: null, billing: null, account: null, feedback: null, sales: null }), ["shipping", "billing", "account", "feedback", "sales"])
    .executeWithStats();
  const counts = new Map<string, number>();
  for (const row of grouped.rows) {
    const choiceJudgment = Object.values(row.$judgments).find((j) => j.answer.type === "choice");
    const label = choiceJudgment && choiceJudgment.answer.type === "choice" ? choiceJudgment.answer.choice : "?";
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  sections.push({
    heading: "Query 5: classify every ticket in one pass",
    body:
      code(`await semantic(db.selectFrom("tickets").selectAll(), engine)
  .whereChoice("body", choice("What kind of request is this?", { shipping: null, billing: null, account: null, feedback: null, sales: null }), [...allLabels])
  .executeWithStats();`) +
      "\n\n" +
      table(["kind", "tickets"], [...counts.entries()].sort((a, b) => b[1] - a[1])) +
      `\n\nStats: ${grouped.stats.judgments} judgments in ${grouped.stats.apiCalls} API calls (${grouped.stats.packs} packs of up to 8 rows).`,
  });

  const totals = engine.totals();
  sections.push({
    heading: "Totals for the five queries",
    body: `${totals.judgments} judgments, ${totals.apiCalls} API calls, ${totals.cacheHits} cache hits, ${totals.tokens.input} input and ${totals.tokens.output} output tokens.`,
  });

  await db.destroy();
  await pg.close();
  return {
    id: "support-tickets",
    title: "Judgment as a query operator",
    summary: "Fourteen support tickets in an in-process Postgres (PGlite). Structural predicates run in SQL; semantic predicates run as a packed post-pass with a row cache in Postgres; a materialized column turns a predicate into an ordinary indexed WHERE.",
    sections,
    usage: { requests: totals.apiCalls, questions: totals.judgments, cacheHits: totals.cacheHits, inputTokens: totals.tokens.input, outputTokens: totals.tokens.output },
  };
}
