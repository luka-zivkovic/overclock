import type { Answer, Usage } from "./questions.js";

export interface CachedJudgment {
  answer: Answer;
  model: string;
  /** Usage of the request that produced it, for accounting; may be absent. */
  usage?: Usage;
  storedAt: string;
}

/** Pluggable store keyed by judgmentKey(model, state, question). Judgments are idempotent, so caching is safe. */
export interface JudgmentCache {
  get(key: string): Promise<CachedJudgment | undefined>;
  set(key: string, value: CachedJudgment): Promise<void>;
}

/** In-memory LRU. Default capacity 10,000 entries. */
export class MemoryCache implements JudgmentCache {
  private readonly entries = new Map<string, CachedJudgment>();
  constructor(private readonly capacity = 10_000) {
    if (capacity < 1) throw new RangeError("MemoryCache capacity must be at least 1");
  }
  async get(key: string): Promise<CachedJudgment | undefined> {
    const value = this.entries.get(key);
    if (value === undefined) return undefined;
    this.entries.delete(key);
    this.entries.set(key, value);
    return value;
  }
  async set(key: string, value: CachedJudgment): Promise<void> {
    this.entries.delete(key);
    this.entries.set(key, value);
    if (this.entries.size > this.capacity) {
      const oldest = this.entries.keys().next().value;
      if (oldest !== undefined) this.entries.delete(oldest);
    }
  }
  get size(): number {
    return this.entries.size;
  }
  clear(): void {
    this.entries.clear();
  }
}

/** Adapter over any async key/value store (Redis, a Postgres table, a KV namespace). */
export class KeyValueCache implements JudgmentCache {
  constructor(
    private readonly store: {
      get(key: string): Promise<string | null | undefined>;
      set(key: string, value: string): Promise<void>;
    },
    private readonly prefix = "judgment:",
  ) {}
  async get(key: string): Promise<CachedJudgment | undefined> {
    const raw = await this.store.get(this.prefix + key);
    return raw ? (JSON.parse(raw) as CachedJudgment) : undefined;
  }
  async set(key: string, value: CachedJudgment): Promise<void> {
    await this.store.set(this.prefix + key, JSON.stringify(value));
  }
}

/** A cache that never stores anything, for callers that want every judgment fresh. */
export class NoCache implements JudgmentCache {
  async get(): Promise<undefined> {
    return undefined;
  }
  async set(): Promise<void> {}
}
