export { s, describePredicate, judgeAnswer, scopeToField } from "./predicates.js";
export type {
  Band,
  IsOptions,
  IsPredicate,
  NotPredicate,
  OneOfOptions,
  OneOfPredicate,
  Predicate,
  RatedOptions,
  RatedPredicate,
  Verdict,
} from "./predicates.js";
export { SemanticError, SemanticSchema, evaluateSpec, semantic } from "./semantic.js";
export type {
  Evaluation,
  Evidence,
  Mode,
  SemanticFailure,
  SemanticIssue,
  SemanticOptions,
  SemanticResult,
  SemanticSuccess,
  Spec,
  WithMeta,
} from "./semantic.js";
export { ContractViolation, assertMeaning, guarded, meaning } from "./functions.js";
export type { GuardOptions, MeaningOptions } from "./functions.js";
export { configure, getClient, resetClient } from "./config.js";
export type { ConfigureOptions } from "./config.js";
export { semanticMatchers } from "./matchers.js";
export type { MatcherOptions, SemanticMatchers } from "./matchers.js";
