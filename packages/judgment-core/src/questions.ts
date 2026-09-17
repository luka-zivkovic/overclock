import { createHash } from "node:crypto";

/** A JSON-compatible value. */
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
/** Text, a JSON object or array, or null: the shapes TypeSafe accepts for state, instructions, and criteria. */
export type EntryType = string | { [key: string]: JsonValue } | JsonValue[] | null;

export interface NoulQuestion {
  type: "noul";
  instructions?: EntryType;
  criteria?: { true?: EntryType; false?: EntryType } | null;
}
export type ChoiceCriteria = { [label: string]: EntryType };
export interface ChoiceQuestion<T extends ChoiceCriteria = ChoiceCriteria> {
  type: "choice";
  instructions?: EntryType;
  criteria: T;
}
export type ScoreCriteria = readonly [EntryType, EntryType, ...EntryType[]];
export interface ScoreQuestion<T extends ScoreCriteria = ScoreCriteria> {
  type: "score";
  instructions?: EntryType;
  criteria: T;
}
/** A question is plain data: serializable, diffable, hashable, reusable across packages. */
export type Question = NoulQuestion | ChoiceQuestion | ScoreQuestion;
export type Questions = Record<string, Question>;

export interface NoulAnswer {
  readonly type: "noul";
  /** Probability of a yes answer, 0..1. */
  readonly noul: number;
}
export interface ChoiceAnswer<T extends ChoiceCriteria = ChoiceCriteria> {
  readonly type: "choice";
  readonly choice: keyof T & string;
  readonly confidence: number;
  readonly probabilities: { readonly [label in keyof T]: number };
}
export interface ScoreAnswer {
  readonly type: "score";
  /** Probability-weighted expected level; may fall between integer levels. */
  readonly score: number;
  readonly confidence: number;
  readonly legend: Readonly<Record<string, EntryType>>;
  readonly probabilities: Readonly<Record<string, number>>;
}
export type Answer = NoulAnswer | ChoiceAnswer | ScoreAnswer;
export type AnswerFor<Q extends Question> = Q extends NoulQuestion
  ? NoulAnswer
  : Q extends ChoiceQuestion<infer C>
    ? ChoiceAnswer<C>
    : Q extends ScoreQuestion
      ? ScoreAnswer
      : never;

export interface Usage {
  readonly input_tokens: number;
  readonly output_tokens: number;
}

/** Create a yes/no question. */
export function noul(instructions: EntryType, criteria?: NoulQuestion["criteria"]): NoulQuestion {
  return criteria === undefined ? { type: "noul", instructions } : { type: "noul", instructions, criteria };
}
/** Create a question that selects one of several named labels. */
export function choice<const T extends ChoiceCriteria>(instructions: EntryType, criteria: T): ChoiceQuestion<T> {
  if (Object.keys(criteria).length < 2) throw new TypeError("choice() needs at least two labels");
  return { type: "choice", instructions, criteria };
}
/** Create a question that rates against an ordered rubric (index 0 is the lowest level). */
export function score<const T extends ScoreCriteria>(instructions: EntryType, criteria: T): ScoreQuestion<T> {
  if (criteria.length < 2) throw new TypeError("score() needs at least two levels");
  return { type: "score", instructions, criteria };
}

/** Number of levels in a score question. */
export function scoreLevels(question: ScoreQuestion): number {
  return question.criteria.length;
}

/**
 * Stable JSON: object keys sorted recursively so equal values hash equally regardless of
 * construction order. `undefined` properties are dropped, as JSON.stringify does.
 */
export function canonicalize(value: unknown): string {
  return JSON.stringify(sortKeys(value));
}

function sortKeys(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(value as Record<string, unknown>).sort()) {
      const item = (value as Record<string, unknown>)[key];
      if (item !== undefined) out[key] = sortKeys(item);
    }
    return out;
  }
  return value;
}

export function sha256(text: string): string {
  return createHash("sha256").update(text).digest("hex");
}

export function stateHash(state: EntryType): string {
  return sha256(canonicalize(state));
}

export function questionHash(question: Question): string {
  return sha256(canonicalize(question));
}

/** Cache key: judgments are idempotent for a fixed (model, state, question). */
export function judgmentKey(model: string, state: EntryType, question: Question): string {
  return sha256(`${model}\n${canonicalize(state)}\n${canonicalize(question)}`);
}

/** Fixture key: model-independent, so a fixture file survives model renames. */
export function fixtureKey(state: EntryType, question: Question): string {
  return sha256(`${canonicalize(state)}\n${canonicalize(question)}`);
}

/** Byte length of the canonical state, used by the request-size guard. */
export function stateBytes(state: EntryType): number {
  return Buffer.byteLength(canonicalize(state), "utf8");
}

/**
 * A single 0..1 number summarizing an answer: the noul probability, the probability of the
 * chosen label, or the expected score normalized by the top level. The full distribution is
 * always kept alongside it; this is for thresholds and calibration.
 */
export function answerProbability(answer: Answer, question?: Question): number {
  switch (answer.type) {
    case "noul":
      return answer.noul;
    case "choice":
      return answer.probabilities[answer.choice] ?? 0;
    case "score": {
      const levels = question && question.type === "score" ? question.criteria.length : Object.keys(answer.legend).length;
      const top = Math.max(1, levels - 1);
      return Math.min(1, Math.max(0, answer.score / top));
    }
  }
}

export function answerConfidence(answer: Answer): number | undefined {
  return answer.type === "noul" ? undefined : answer.confidence;
}
