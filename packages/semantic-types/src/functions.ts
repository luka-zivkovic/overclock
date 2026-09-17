import type { JudgmentClient } from "@overclock/judgment-core";
import { getClient } from "./config.js";
import { s, type IsOptions, type Predicate } from "./predicates.js";
import { SemanticError, evaluateSpec, type Evaluation, type Mode } from "./semantic.js";

export interface MeaningOptions extends IsOptions {
  client?: JudgmentClient;
}

/** Probability (0..1) that `value` has the described property. For code that is not Zod-shaped. */
export async function meaning(value: unknown, text: string, options: MeaningOptions = {}): Promise<number> {
  const { client, ...rest } = options;
  const evaluation = await evaluateSpec(value, { $self: [s.is(text, rest)] }, { mode: "annotate", ...(client ? { client } : {}) });
  return evaluation.evidence[0]?.p ?? 0;
}

/** Throw SemanticError unless `value` has the described property at the threshold (default 0.5). */
export async function assertMeaning(value: unknown, text: string, options: MeaningOptions = {}): Promise<void> {
  const { client, ...rest } = options;
  const evaluation = await evaluateSpec(value, { $self: [s.is(text, rest)] }, client ? { client } : {});
  if (!evaluation.ok) throw new SemanticError(evaluation.issues, evaluation.evidence);
}

export interface GuardOptions {
  /** Checked against `{ input }` before the call. */
  pre?: Predicate[];
  /** Checked against `{ input, output }` after the call. */
  post?: Predicate[];
  mode?: Mode;
  client?: JudgmentClient;
}

export class ContractViolation extends SemanticError {
  constructor(
    readonly stage: "pre" | "post",
    evaluation: Evaluation,
  ) {
    super(evaluation.issues, evaluation.evidence);
    this.name = "ContractViolation";
    this.message = `${stage}-condition failed: ${this.message}`;
  }
}

/**
 * Wrap a function with semantic pre- and post-conditions. Predicates see the state
 * `{ input, output }`, so write them as "the output answers the question in the input".
 */
export function guarded<A extends unknown[], R>(fn: (...args: A) => R | Promise<R>, options: GuardOptions): (...args: A) => Promise<R> {
  const evalOptions = { ...(options.mode ? { mode: options.mode } : {}), ...(options.client ? { client: options.client } : {}) };
  return async (...args: A): Promise<R> => {
    const input = args.length === 1 ? args[0] : args;
    if (options.pre?.length) {
      const pre = await evaluateSpec({ input }, { $self: options.pre }, evalOptions);
      if (!pre.ok) throw new ContractViolation("pre", pre);
    }
    const output = await fn(...args);
    if (options.post?.length) {
      const post = await evaluateSpec({ input, output }, { $self: options.post }, evalOptions);
      if (!post.ok) throw new ContractViolation("post", post);
    }
    return output;
  };
}
