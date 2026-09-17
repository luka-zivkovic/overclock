import {
  answerConfidence,
  answerProbability,
  choice,
  noul,
  score,
  type Answer,
  type ChoiceCriteria,
  type ChoiceQuestion,
  type EntryType,
  type NoulQuestion,
  type Question,
  type ScoreQuestion,
} from "@overclock/judgment-core";

/**
 * Predicates are data: plain JSON objects wrapping one question plus the rule that turns its
 * answer into pass/fail. They serialize, diff, and travel to other packages unchanged.
 */
export interface IsPredicate {
  kind: "is";
  text: string;
  /** Pass when p >= threshold. Default 0.5. */
  threshold: number;
  question: NoulQuestion;
}
export interface NotPredicate {
  kind: "not";
  text: string;
  /** Pass when p <= threshold. Default 0.5. */
  threshold: number;
  question: NoulQuestion;
}
export interface OneOfPredicate {
  kind: "oneOf";
  name: string;
  question: ChoiceQuestion;
  /** Labels that count as a pass. Absent: never fails, only annotates. */
  expect?: string[];
  /** Fail when the answer's confidence is below this. */
  minConfidence?: number;
}
export interface RatedPredicate {
  kind: "rated";
  name: string;
  question: ScoreQuestion;
  /** Inclusive bounds on the expected level (0-based). */
  min?: number;
  max?: number;
}
export type Predicate = IsPredicate | NotPredicate | OneOfPredicate | RatedPredicate;

export interface IsOptions {
  threshold?: number;
  /** Optional descriptions of the yes and no outcomes, forwarded to the question. */
  criteria?: NoulQuestion["criteria"];
}
export interface OneOfOptions {
  expect?: string[];
  minConfidence?: number;
}
export interface RatedOptions {
  min?: number;
  max?: number;
}

function assertUnit(name: string, value: number): void {
  if (!(value >= 0 && value <= 1)) throw new RangeError(`${name} must be between 0 and 1, got ${value}`);
}

export const s = {
  /** The value has this property. */
  is(text: string, options: IsOptions = {}): IsPredicate {
    const threshold = options.threshold ?? 0.5;
    assertUnit("threshold", threshold);
    return { kind: "is", text, threshold, question: noul(text, options.criteria) };
  },
  /** The value does not have this property. Fails when p exceeds the threshold. */
  not(text: string, options: IsOptions = {}): NotPredicate {
    const threshold = options.threshold ?? 0.5;
    assertUnit("threshold", threshold);
    return { kind: "not", text, threshold, question: noul(text, options.criteria) };
  },
  /** Classify into named labels. With `expect`, pass only when the choice is one of them. */
  oneOf(name: string, criteria: ChoiceCriteria, options: OneOfOptions = {}): OneOfPredicate {
    const predicate: OneOfPredicate = { kind: "oneOf", name, question: choice(name, criteria) };
    if (options.expect) {
      for (const label of options.expect) {
        if (!(label in criteria)) throw new RangeError(`expect label "${label}" is not one of ${Object.keys(criteria).join(", ")}`);
      }
      predicate.expect = [...options.expect];
    }
    if (options.minConfidence !== undefined) {
      assertUnit("minConfidence", options.minConfidence);
      predicate.minConfidence = options.minConfidence;
    }
    return predicate;
  },
  /** Rate against ordered levels (index 0 lowest). Pass when the expected level is within [min, max]. */
  rated(name: string, levels: readonly [string, string, ...string[]], options: RatedOptions = {}): RatedPredicate {
    const predicate: RatedPredicate = { kind: "rated", name, question: score(name, levels) };
    const top = levels.length - 1;
    if (options.min !== undefined) {
      if (options.min < 0 || options.min > top) throw new RangeError(`min must be between 0 and ${top}`);
      predicate.min = options.min;
    }
    if (options.max !== undefined) {
      if (options.max < 0 || options.max > top) throw new RangeError(`max must be between 0 and ${top}`);
      predicate.max = options.max;
    }
    return predicate;
  },
};

export type Band = "pass" | "fail" | "review";

export interface Verdict {
  pass: boolean;
  band: Band;
  /** The single-number summary from judgment-core (noul p, chosen-label p, normalized score). */
  p: number;
  confidence?: number;
  /** Signed distance from the decision boundary in probability units; near zero means borderline. */
  distance: number;
  message: string;
}

/** Human-readable label of what a predicate demands. */
export function describePredicate(predicate: Predicate): string {
  switch (predicate.kind) {
    case "is":
      return `${predicate.text} (p >= ${predicate.threshold})`;
    case "not":
      return `not: ${predicate.text} (p <= ${predicate.threshold})`;
    case "oneOf":
      return predicate.expect ? `${predicate.name} in [${predicate.expect.join(", ")}]` : `${predicate.name} (annotate)`;
    case "rated": {
      const bounds = [predicate.min !== undefined ? `>= ${predicate.min}` : "", predicate.max !== undefined ? `<= ${predicate.max}` : ""].filter(Boolean);
      return bounds.length ? `${predicate.name} ${bounds.join(" and ")}` : `${predicate.name} (annotate)`;
    }
  }
}

/** Turn an answer into a verdict. `margin` is the half-width of the review band around the boundary. */
export function judgeAnswer(predicate: Predicate, answer: Answer, margin = 0): Verdict {
  const p = answerProbability(answer, predicate.question);
  const confidence = answerConfidence(answer);
  let distance: number;
  let pass: boolean;
  let message: string;
  switch (predicate.kind) {
    case "is": {
      if (answer.type !== "noul") throw new TypeError("is predicate expects a noul answer");
      distance = p - predicate.threshold;
      pass = distance >= 0;
      message = `${pass ? "is" : "is not"} "${predicate.text}" (p=${p.toFixed(2)}, threshold ${predicate.threshold})`;
      break;
    }
    case "not": {
      if (answer.type !== "noul") throw new TypeError("not predicate expects a noul answer");
      distance = predicate.threshold - p;
      pass = distance >= 0;
      message = `${pass ? "does not" : "does"} "${predicate.text}" (p=${p.toFixed(2)}, limit ${predicate.threshold})`;
      break;
    }
    case "oneOf": {
      if (answer.type !== "choice") throw new TypeError("oneOf predicate expects a choice answer");
      if (predicate.expect) {
        const mass = predicate.expect.reduce((sum, label) => sum + (answer.probabilities[label] ?? 0), 0);
        distance = mass - 0.5;
        pass = predicate.expect.includes(answer.choice);
      } else {
        distance = answer.confidence;
        pass = true;
      }
      if (predicate.minConfidence !== undefined && answer.confidence < predicate.minConfidence) {
        pass = false;
        distance = Math.min(distance, answer.confidence - predicate.minConfidence);
      }
      message = `${predicate.name}: ${answer.choice} (p=${p.toFixed(2)}, confidence ${answer.confidence.toFixed(2)})${predicate.expect ? `, expected one of ${predicate.expect.join("/")}` : ""}`;
      break;
    }
    case "rated": {
      if (answer.type !== "score") throw new TypeError("rated predicate expects a score answer");
      const top = Math.max(1, predicate.question.criteria.length - 1);
      const lower = predicate.min !== undefined ? (answer.score - predicate.min) / top : Number.POSITIVE_INFINITY;
      const upper = predicate.max !== undefined ? (predicate.max - answer.score) / top : Number.POSITIVE_INFINITY;
      distance = Math.min(lower, upper);
      if (!Number.isFinite(distance)) distance = answer.confidence;
      pass = distance >= 0;
      const level = predicate.question.criteria[Math.round(answer.score)];
      message = `${predicate.name}: ${answer.score.toFixed(2)}${level !== undefined ? ` (~${String(level)})` : ""}${predicate.min !== undefined ? `, min ${predicate.min}` : ""}${predicate.max !== undefined ? `, max ${predicate.max}` : ""}`;
      break;
    }
  }
  const band: Band = Math.abs(distance) < margin ? "review" : pass ? "pass" : "fail";
  const verdict: Verdict = { pass, band, p, distance, message };
  if (confidence !== undefined) verdict.confidence = confidence;
  return verdict;
}

/** Rewrite a predicate's question so it refers to one field of a larger state. */
export function scopeToField(question: Question, fieldPath: string): Question {
  const original = typeof question.instructions === "string" ? question.instructions : JSON.stringify(question.instructions ?? "");
  const instructions: EntryType = `Regarding the field "${fieldPath}": ${original}`;
  return { ...question, instructions };
}
