import { TypeSafeClient, type RetryPolicy, type TypeSafeClientConfig } from "@typesafe-ai/sdk";
import type { Answer, EntryType, Question, Questions, Usage } from "./questions.js";

export interface JudgeRequest {
  state: EntryType;
  /** Non-empty. Questions run in parallel and isolated; answers never depend on each other. */
  questions: Questions;
}
export interface JudgeResponse {
  model: string;
  answers: Record<string, Answer>;
  usage: Usage;
}
export interface JudgeOptions {
  signal?: AbortSignal;
}

/** The only thing higher layers see. Implemented by TypeSafeJudge and MockJudge. */
export interface Judge {
  /** Model name used for cache keys. */
  readonly model: string;
  judge(request: JudgeRequest, options?: JudgeOptions): Promise<JudgeResponse>;
}

export class JudgmentError extends Error {
  constructor(message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "JudgmentError";
  }
}

export interface TypeSafeJudgeOptions {
  /** An existing SDK client; when omitted one is built from the other options and TYPESAFE_API_KEY. */
  client?: TypeSafeClient;
  apiKey?: string;
  baseURL?: string;
  /** Defaults to jev-latest via the SDK. Fixed at construction so cache keys are stable. */
  model?: string;
  /** Per-attempt timeout in ms (SDK default 10000). */
  timeout?: number;
  /** SDK retry overrides. By default the SDK retries 408, 429 and 5xx (529 included) with jittered backoff and honors Retry-After. */
  retry?: Partial<RetryPolicy>;
}

/** Wraps the official SDK. Retries on 429/529 are the SDK's; nothing is added on top. */
export class TypeSafeJudge implements Judge {
  readonly model: string;
  private readonly client: TypeSafeClient;

  constructor(options: TypeSafeJudgeOptions = {}) {
    if (options.client) {
      this.client = options.client;
    } else {
      const config: TypeSafeClientConfig = {};
      if (options.apiKey !== undefined) config.apiKey = options.apiKey;
      if (options.baseURL !== undefined) config.baseURL = options.baseURL;
      if (options.model !== undefined) config.defaultModel = options.model;
      if (options.timeout !== undefined) config.timeout = options.timeout;
      if (options.retry !== undefined) config.retry = options.retry;
      this.client = new TypeSafeClient(config);
    }
    this.model = options.model ?? this.client.defaultModel;
  }

  async judge(request: JudgeRequest, options: JudgeOptions = {}): Promise<JudgeResponse> {
    if (Object.keys(request.questions).length === 0) throw new JudgmentError("judge() needs at least one question");
    const call = options.signal ? { signal: options.signal } : {};
    const result = await this.client.systemOne(
      { state: request.state, questions: request.questions as Questions, model: this.model },
      call,
    );
    return {
      model: result.model,
      answers: result.answers as unknown as Record<string, Answer>,
      usage: { input_tokens: result.usage.input_tokens, output_tokens: result.usage.output_tokens },
    };
  }
}

/** Sum token usage across responses. */
export function addUsage(a: Usage, b: Usage): Usage {
  return { input_tokens: a.input_tokens + b.input_tokens, output_tokens: a.output_tokens + b.output_tokens };
}

export const ZERO_USAGE: Usage = { input_tokens: 0, output_tokens: 0 };

export type { Question, EntryType };
