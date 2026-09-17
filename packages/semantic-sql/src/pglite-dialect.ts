import {
  CompiledQuery,
  PostgresAdapter,
  PostgresIntrospector,
  PostgresQueryCompiler,
  type DatabaseConnection,
  type DatabaseIntrospector,
  type Dialect,
  type DialectAdapter,
  type Driver,
  type Kysely,
  type QueryCompiler,
  type QueryResult,
  type TransactionSettings,
} from "kysely";

/**
 * The slice of a PGlite instance the dialect needs. Structural so this package does not
 * depend on `@electric-sql/pglite` at runtime; pass `new PGlite()` (or a `PGlite` from
 * `@electric-sql/pglite`) and it just works.
 */
export interface PGliteLike {
  query<T>(sql: string, params?: unknown[]): Promise<{ rows: T[]; affectedRows?: number }>;
}

/**
 * A Kysely dialect for PGlite (Postgres in-process, WASM). PGlite is a single connection, so
 * the driver hands out one connection at a time and queues other requests; transactions use
 * plain `begin` / `commit` / `rollback`.
 */
export class PGliteDialect implements Dialect {
  constructor(private readonly pglite: PGliteLike) {}

  createDriver(): Driver {
    return new PGliteDriver(this.pglite);
  }
  createQueryCompiler(): QueryCompiler {
    return new PostgresQueryCompiler();
  }
  createAdapter(): DialectAdapter {
    return new PostgresAdapter();
  }
  createIntrospector(db: Kysely<unknown>): DatabaseIntrospector {
    return new PostgresIntrospector(db);
  }
}

class PGliteConnection implements DatabaseConnection {
  constructor(private readonly pglite: PGliteLike) {}

  async executeQuery<R>(compiledQuery: CompiledQuery): Promise<QueryResult<R>> {
    const result = await this.pglite.query<R>(compiledQuery.sql, [...compiledQuery.parameters]);
    return result.affectedRows === undefined
      ? { rows: result.rows }
      : { rows: result.rows, numAffectedRows: BigInt(result.affectedRows) };
  }

  async *streamQuery<R>(compiledQuery: CompiledQuery): AsyncIterableIterator<QueryResult<R>> {
    // PGlite has no cursor API; stream the whole result as one chunk.
    yield await this.executeQuery<R>(compiledQuery);
  }
}

class PGliteDriver implements Driver {
  private readonly connection: PGliteConnection;
  private busy = false;
  private readonly waiting: Array<() => void> = [];

  constructor(pglite: PGliteLike) {
    this.connection = new PGliteConnection(pglite);
  }

  async init(): Promise<void> {}

  async acquireConnection(): Promise<DatabaseConnection> {
    if (this.busy) await new Promise<void>((resolve) => this.waiting.push(resolve));
    this.busy = true;
    return this.connection;
  }

  async releaseConnection(): Promise<void> {
    const next = this.waiting.shift();
    if (next) next();
    else this.busy = false;
  }

  async beginTransaction(connection: DatabaseConnection, settings: TransactionSettings): Promise<void> {
    let statement = "begin";
    if (settings.isolationLevel || settings.accessMode) {
      statement = "start transaction";
      if (settings.isolationLevel) statement += ` isolation level ${settings.isolationLevel}`;
      if (settings.accessMode) statement += ` ${settings.accessMode}`;
    }
    await connection.executeQuery(CompiledQuery.raw(statement));
  }

  async commitTransaction(connection: DatabaseConnection): Promise<void> {
    await connection.executeQuery(CompiledQuery.raw("commit"));
  }

  async rollbackTransaction(connection: DatabaseConnection): Promise<void> {
    await connection.executeQuery(CompiledQuery.raw("rollback"));
  }

  async destroy(): Promise<void> {}
}
