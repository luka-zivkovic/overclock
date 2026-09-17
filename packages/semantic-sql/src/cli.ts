#!/usr/bin/env node
import { judgeFromEnv } from "@overclock/judgment-core";
import { Kysely, PostgresDialect } from "kysely";
import { parseArgs } from "node:util";
import { SemanticEngine } from "./engine.js";
import { PostgresRowCache } from "./cache.js";
import { PostgresMaterializedRegistry, materialize, refresh, watch } from "./materialize.js";

const USAGE = `semantic-sql: materialized semantic columns

  semantic-sql materialize <table.column> "<question text>" --as <col> [--batch 500] [--key id]
  semantic-sql refresh <table> --as <col> [--batch 500] [--key id]
  semantic-sql watch <table> --as <col> [--interval 5000] [--batch 500] [--key id]

Options:
  --database-url <url>   Postgres connection string (or DATABASE_URL). Requires the optional "pg" package.
  --as <col>             Target column holding the probability / expected score.
  --batch <n>            Rows per judge batch (default 500).
  --key <col>            Cursor column (default id).
  --interval <ms>        Poll interval for watch (default 5000).

The judge comes from judgeFromEnv(): JUDGMENT_FIXTURES=live|record|replay and TYPESAFE_API_KEY.
`;

async function openDatabase(url: string | undefined): Promise<Kysely<any>> {
  const connectionString = url ?? process.env.DATABASE_URL;
  if (!connectionString) throw new Error("no database: pass --database-url or set DATABASE_URL");
  let pg: { Pool: new (config: { connectionString: string }) => unknown };
  try {
    pg = (await import("pg")) as unknown as typeof pg;
  } catch {
    throw new Error('the "pg" package is required for --database-url; install it with `npm install pg`');
  }
  const pool = new pg.Pool({ connectionString }) as ConstructorParameters<typeof PostgresDialect>[0]["pool"];
  return new Kysely<any>({ dialect: new PostgresDialect({ pool }) });
}

export async function main(argv = process.argv.slice(2)): Promise<number> {
  const { values, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: {
      as: { type: "string" },
      "database-url": { type: "string" },
      batch: { type: "string" },
      key: { type: "string" },
      interval: { type: "string" },
      help: { type: "boolean", short: "h" },
    },
  });
  const [command, target, questionText] = positionals;
  if (values.help || !command) {
    process.stdout.write(USAGE);
    return command ? 0 : 1;
  }
  if (!values.as) throw new Error("--as <col> is required");
  const batchSize = values.batch ? Number(values.batch) : 500;
  const keyColumn = values.key ?? "id";

  const db = await openDatabase(values["database-url"]);
  try {
    const rowCache = new PostgresRowCache(db);
    await rowCache.ensureTable();
    const registry = new PostgresMaterializedRegistry(db);
    await registry.ensureTable();
    const engine = new SemanticEngine({ judge: judgeFromEnv(), rowCache, materialized: registry });

    switch (command) {
      case "materialize": {
        const [table, column] = (target ?? "").split(".");
        if (!table || !column || !questionText) throw new Error('usage: materialize <table.column> "<question>" --as <col>');
        const result = await materialize(db, engine, { table, column, question: questionText, as: values.as, batchSize, keyColumn, registry });
        process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
        return 0;
      }
      case "refresh": {
        if (!target) throw new Error("usage: refresh <table> --as <col>");
        const result = await refresh(db, engine, { table: target, as: values.as, batchSize, keyColumn, registry });
        process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
        return 0;
      }
      case "watch": {
        if (!target) throw new Error("usage: watch <table> --as <col>");
        const controller = new AbortController();
        process.once("SIGINT", () => controller.abort());
        process.once("SIGTERM", () => controller.abort());
        const intervalMs = values.interval ? Number(values.interval) : 5000;
        const totals = await watch(db, engine, {
          table: target,
          as: values.as,
          batchSize,
          keyColumn,
          registry,
          intervalMs,
          signal: controller.signal,
          onRefresh: (r) => {
            if (r.judged > 0) process.stdout.write(`${new Date().toISOString()} judged ${r.judged} rows (${r.stats.apiCalls} calls)\n`);
          },
        });
        process.stdout.write(`${JSON.stringify(totals)}\n`);
        return 0;
      }
      default:
        process.stderr.write(`unknown command ${command}\n${USAGE}`);
        return 1;
    }
  } finally {
    await db.destroy();
  }
}

const invokedDirectly = process.argv[1] !== undefined && /[\\/]cli\.js$/.test(process.argv[1]);
if (invokedDirectly) {
  main().then(
    (code) => process.exit(code),
    (error: unknown) => {
      process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
      process.exit(1);
    },
  );
}
