import { MemoryCache, type JudgmentCache } from "./cache.js";
import { JudgmentError, ZERO_USAGE, addUsage, type Judge, type JudgeRequest, type JudgeResponse } from "./judge.js";
import {
  answerConfidence,
  answerProbability,
  judgmentKey,
  stateBytes,
  stateHash,
  type Answer,
  type AnswerFor,
  type EntryType,
  type Question,
  type Usage,
} from "./questions.js";

/** Every judgment keeps its probability and the question that produced it. Nothing is thrown away. */
export interface Judgment<A extends Answer = Answer> {
  answer: A;
  /** Single 0..1 summary: noul probability, chosen-label probability, or normalized expected score. */
  p: number;
  /** Distribution concentration for choice and score answers; undefined for noul. */
  confidence?: number;
  question: Question;
  state: EntryType;
  stateHash: string;
  /** judgmentKey(model, state, question): the cache key. */
  key: string;
  cached: boolean;
  model: string;
  /** Token usage of the request this answer came from, shared with its batch mates; absent on cache hits. */
  usage?: Usage;
}

export interface UsageTotals {
  /** Requests actually sent to the judge. */
  requests: number;
  /** Questions asked through ask(), including cache hits. */
  questions: number;
  cacheHits: number;
  /** Questions deduplicated against an identical in-flight question. */
  inFlightHits: number;
  inputTokens: number;
  outputTokens: number;
}

export interface JudgmentClientOptions {
  judge: Judge;
  /** Default: MemoryCache(10000). Pass NoCache to disable. */
  cache?: JudgmentCache;
  /** Concurrent requests to the judge. Default 4. */
  concurrency?: number;
  /** Upper bound on questions packed into one request for the same state. Default 64. */
  maxQuestionsPerCall?: number;
  /** Reject states whose canonical JSON exceeds this many bytes. Default 262144 (256 KiB). */
  maxStateBytes?: number;
  /** Collection window for batching. Default 0 (next macrotask), which still merges everything queued synchronously. */
  batchWindowMs?: number;
}

export class StateTooLargeError extends JudgmentError {
  constructor(
    readonly bytes: number,
    readonly limit: number,
  ) {
    super(`state is ${bytes} bytes; the request-size guard allows ${limit}. Split the state or raise maxStateBytes.`);
    this.name = "StateTooLargeError";
  }
}

interface Pending {
  question: Question;
  key: string;
  resolve: (judgment: Judgment) => void;
  reject: (error: unknown) => void;
}

interface Group {
  state: EntryType;
  hash: string;
  items: Pending[];
}

/** Bounded concurrency without a dependency. */
export function createLimiter(concurrency: number): <T>(task: () => Promise<T>) => Promise<T> {
  if (!Number.isInteger(concurrency) || concurrency < 1) throw new RangeError("concurrency must be a positive integer");
  let active = 0;
  const queue: Array<() => void> = [];
  const next = () => {
    active -= 1;
    const run = queue.shift();
    if (run) run();
  };
  return <T>(task: () => Promise<T>) =>
    new Promise<T>((resolve, reject) => {
      const run = () => {
        active += 1;
        task().then(resolve, reject).finally(next);
      };
      if (active < concurrency) run();
      else queue.push(run);
    });
}

/**
 * Batches (state, question) pairs: everything queued within one tick is grouped by identical
 * state and sent as one request per distinct state, so adding questions is flat in cost.
 * Cache hits resolve without a request; identical in-flight questions share one answer.
 */
export class JudgmentClient {
  readonly judge: Judge;
  readonly cache: JudgmentCache;
  private readonly limit: <T>(task: () => Promise<T>) => Promise<T>;
  private readonly maxQuestionsPerCall: number;
  private readonly maxStateBytes: number;
  private readonly batchWindowMs: number;
  private readonly groups = new Map<string, Group>();
  private readonly inFlight = new Map<string, Promise<Judgment>>();
  private timer: ReturnType<typeof setTimeout> | undefined;
  private flushing: Promise<void> = Promise.resolve();
  private readonly totals: UsageTotals = { requests: 0, questions: 0, cacheHits: 0, inFlightHits: 0, inputTokens: 0, outputTokens: 0 };

  constructor(options: JudgmentClientOptions) {
    this.judge = options.judge;
    this.cache = options.cache ?? new MemoryCache();
    this.limit = createLimiter(options.concurrency ?? 4);
    this.maxQuestionsPerCall = options.maxQuestionsPerCall ?? 64;
    this.maxStateBytes = options.maxStateBytes ?? 256 * 1024;
    this.batchWindowMs = options.batchWindowMs ?? 0;
  }

  get model(): string {
    return this.judge.model;
  }

  /** Ask one question about one state. Resolves with the full evidence. */
  async ask<Q extends Question>(state: EntryType, question: Q): Promise<Judgment<AnswerFor<Q>>> {
    this.totals.questions += 1;
    const bytes = stateBytes(state);
    if (bytes > this.maxStateBytes) throw new StateTooLargeError(bytes, this.maxStateBytes);
    const key = judgmentKey(this.model, state, question);
    const hit = await this.cache.get(key);
    if (hit) {
      this.totals.cacheHits += 1;
      return this.toJudgment(state, question, key, hit.answer, hit.model, true) as Judgment<AnswerFor<Q>>;
    }
    const flying = this.inFlight.get(key);
    if (flying) {
      this.totals.inFlightHits += 1;
      return flying as Promise<Judgment<AnswerFor<Q>>>;
    }
    const promise = new Promise<Judgment>((resolve, reject) => {
      const hash = stateHash(state);
      let group = this.groups.get(hash);
      if (!group) {
        group = { state, hash, items: [] };
        this.groups.set(hash, group);
      }
      group.items.push({ question, key, resolve, reject });
      this.schedule();
    }).finally(() => this.inFlight.delete(key));
    this.inFlight.set(key, promise);
    return promise as Promise<Judgment<AnswerFor<Q>>>;
  }

  /** Ask several named questions about one state; they always share a single request. */
  async askAll<Q extends Record<string, Question>>(
    state: EntryType,
    questions: Q,
  ): Promise<{ [K in keyof Q]: Judgment<AnswerFor<Q[K]>> }> {
    const entries = Object.entries(questions);
    const results = await Promise.all(entries.map(([, question]) => this.ask(state, question)));
    const out: Record<string, Judgment> = {};
    entries.forEach(([name], i) => (out[name] = results[i]!));
    return out as { [K in keyof Q]: Judgment<AnswerFor<Q[K]>> };
  }

  /** Send everything queued now and wait for it. */
  async flush(): Promise<void> {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = undefined;
    }
    this.dispatch();
    await this.flushing;
  }

  usage(): UsageTotals {
    return { ...this.totals };
  }

  private schedule(): void {
    if (this.timer) return;
    this.timer = setTimeout(() => {
      this.timer = undefined;
      this.dispatch();
    }, this.batchWindowMs);
  }

  private dispatch(): void {
    const groups = [...this.groups.values()];
    this.groups.clear();
    const sends: Promise<void>[] = [];
    for (const group of groups) {
      for (let i = 0; i < group.items.length; i += this.maxQuestionsPerCall) {
        sends.push(this.send(group.state, group.items.slice(i, i + this.maxQuestionsPerCall)));
      }
    }
    const batch = Promise.all(sends).then(() => undefined);
    this.flushing = this.flushing.then(() => batch);
  }

  private async send(state: EntryType, items: Pending[]): Promise<void> {
    const questions: Record<string, Question> = {};
    items.forEach((item, i) => (questions[`q${i}`] = item.question));
    const request: JudgeRequest = { state, questions };
    let response: JudgeResponse;
    try {
      response = await this.limit(() => this.judge.judge(request));
    } catch (error) {
      for (const item of items) item.reject(error);
      return;
    }
    this.totals.requests += 1;
    this.totals.inputTokens += response.usage.input_tokens;
    this.totals.outputTokens += response.usage.output_tokens;
    const storedAt = new Date().toISOString();
    await Promise.all(
      items.map(async (item, i) => {
        const answer = response.answers[`q${i}`];
        if (!answer) {
          item.reject(new JudgmentError(`judge returned no answer for question ${i}`));
          return;
        }
        try {
          await this.cache.set(item.key, { answer, model: response.model, usage: response.usage, storedAt });
        } catch (error) {
          item.reject(error);
          return;
        }
        item.resolve(this.toJudgment(state, item.question, item.key, answer, response.model, false, response.usage));
      }),
    );
  }

  private toJudgment(
    state: EntryType,
    question: Question,
    key: string,
    answer: Answer,
    model: string,
    cached: boolean,
    usage?: Usage,
  ): Judgment {
    const confidence = answerConfidence(answer);
    const judgment: Judgment = {
      answer,
      p: answerProbability(answer, question),
      question,
      state,
      stateHash: stateHash(state),
      key,
      cached,
      model,
    };
    if (confidence !== undefined) judgment.confidence = confidence;
    if (usage) judgment.usage = usage;
    return judgment;
  }
}

export { ZERO_USAGE, addUsage };
