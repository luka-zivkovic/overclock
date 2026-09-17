import type { JudgmentClient } from "@overclock/judgment-core";
import { getClient } from "./config.js";
import { s } from "./predicates.js";
import { evaluateSpec } from "./semantic.js";

export interface MatcherOptions {
  threshold?: number;
}

interface MatcherResult {
  pass: boolean;
  message: () => string;
  actual?: unknown;
  expected?: unknown;
}

/**
 * `expect(value).toMean("cites at least one source")` and `toMeanNot`. Async: always `await` them.
 * Backed by the default client, which replays fixtures in CI and records with
 * `--update-semantic-fixtures` (or JUDGMENT_FIXTURES=record).
 */
export function semanticMatchers(client?: JudgmentClient): {
  toMean(received: unknown, text: string, options?: MatcherOptions): Promise<MatcherResult>;
  toMeanNot(received: unknown, text: string, options?: MatcherOptions): Promise<MatcherResult>;
} {
  const resolve = () => getClient(client);
  return {
    async toMean(received, text, options = {}) {
      const evaluation = await evaluateSpec(received, { $self: [s.is(text, options)] }, { client: resolve() });
      const item = evaluation.evidence[0]!;
      return {
        pass: item.pass,
        actual: item.p,
        expected: `p >= ${item.predicate.kind === "is" ? item.predicate.threshold : 0.5}`,
        message: () => `expected value ${item.pass ? "not " : ""}to mean "${text}"; judged p=${item.p.toFixed(3)} (${item.message})`,
      };
    },
    async toMeanNot(received, text, options = {}) {
      const evaluation = await evaluateSpec(received, { $self: [s.not(text, options)] }, { client: resolve() });
      const item = evaluation.evidence[0]!;
      return {
        pass: item.pass,
        actual: item.p,
        expected: `p <= ${item.predicate.kind === "not" ? item.predicate.threshold : 0.5}`,
        message: () => `expected value ${item.pass ? "" : "not "}to mean "${text}"; judged p=${item.p.toFixed(3)} (${item.message})`,
      };
    },
  };
}

/** Types for `expect.extend(semanticMatchers())` in Vitest and Jest. */
export interface SemanticMatchers {
  toMean(text: string, options?: MatcherOptions): Promise<void>;
  toMeanNot(text: string, options?: MatcherOptions): Promise<void>;
}
