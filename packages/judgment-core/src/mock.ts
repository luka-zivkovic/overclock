import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { JudgmentError, ZERO_USAGE, addUsage, type Judge, type JudgeOptions, type JudgeRequest, type JudgeResponse } from "./judge.js";
import {
  fixtureKey,
  sha256,
  type Answer,
  type ChoiceAnswer,
  type EntryType,
  type NoulAnswer,
  type Question,
  type ScoreAnswer,
} from "./questions.js";

export interface FixtureEntry {
  answer: Answer;
  /** Kept for readability of the fixture file; not used for lookup. */
  question?: Question;
  statePreview?: string;
  model?: string;
  recordedAt?: string;
}

export interface FixtureStore {
  get(key: string): FixtureEntry | undefined;
  set(key: string, entry: FixtureEntry): void;
  /** Persist pending writes, if the store is durable. */
  save(): void;
  readonly size: number;
}

export class MemoryFixtures implements FixtureStore {
  private readonly entries = new Map<string, FixtureEntry>();
  get(key: string): FixtureEntry | undefined {
    return this.entries.get(key);
  }
  set(key: string, entry: FixtureEntry): void {
    this.entries.set(key, entry);
  }
  save(): void {}
  get size(): number {
    return this.entries.size;
  }
}

interface FixtureFile {
  version: 1;
  entries: Record<string, FixtureEntry>;
}

/** A JSON file of recorded answers keyed by fixtureKey(state, question). Loaded lazily, saved explicitly. */
export class JsonFileFixtures implements FixtureStore {
  private entries: Record<string, FixtureEntry> | undefined;
  private dirty = false;

  constructor(readonly path: string) {}

  private load(): Record<string, FixtureEntry> {
    if (this.entries) return this.entries;
    if (existsSync(this.path)) {
      const parsed = JSON.parse(readFileSync(this.path, "utf8")) as FixtureFile;
      if (parsed.version !== 1 || typeof parsed.entries !== "object") {
        throw new JudgmentError(`unsupported fixture file ${this.path}`);
      }
      this.entries = parsed.entries;
    } else {
      this.entries = {};
    }
    return this.entries;
  }

  get(key: string): FixtureEntry | undefined {
    return this.load()[key];
  }

  set(key: string, entry: FixtureEntry): void {
    this.load()[key] = entry;
    this.dirty = true;
  }

  save(): void {
    if (!this.dirty) return;
    const entries = this.load();
    const sorted: Record<string, FixtureEntry> = {};
    for (const key of Object.keys(entries).sort()) sorted[key] = entries[key]!;
    mkdirSync(dirname(this.path), { recursive: true });
    writeFileSync(this.path, `${JSON.stringify({ version: 1, entries: sorted } satisfies FixtureFile, null, 1)}\n`);
    this.dirty = false;
  }

  get size(): number {
    return Object.keys(this.load()).length;
  }
}

export class MissingFixtureError extends JudgmentError {
  constructor(
    readonly key: string,
    readonly question: Question,
    readonly state: EntryType,
  ) {
    super(
      `no fixture for question ${JSON.stringify(question.instructions)} (key ${key.slice(0, 12)}…). ` +
        "Record it with a live judge (MockJudge { record }) or set onMissing: 'synthesize'.",
    );
    this.name = "MissingFixtureError";
  }
}

/** Hand-written answers for tests: return an Answer to use it, undefined to fall through. */
export type MockRule = (state: EntryType, question: Question, name: string) => Answer | undefined;

export interface MockJudgeOptions {
  fixtures?: FixtureStore;
  /** When set, misses are answered by this judge and recorded into `fixtures`. */
  record?: Judge;
  rules?: MockRule[];
  /** What to do when neither rules nor fixtures nor a recording judge answer. Default: throw. */
  onMissing?: "throw" | "synthesize";
  /** Model name reported on responses and used in cache keys. Default: "mock". */
  model?: string;
  /** Simulated latency per request in ms. Default 0. */
  latencyMs?: number;
}

/**
 * Deterministic judge for tests. Resolution order per question: rules, fixtures, recording
 * judge (answers are stored), then `onMissing`. Requests through this judge are counted so
 * tests can assert on batching (one call per distinct state).
 */
export class MockJudge implements Judge {
  readonly model: string;
  readonly fixtures: FixtureStore;
  readonly calls: JudgeRequest[] = [];
  private readonly record: Judge | undefined;
  private readonly rules: MockRule[];
  private readonly onMissing: "throw" | "synthesize";
  private readonly latencyMs: number;

  constructor(options: MockJudgeOptions = {}) {
    this.fixtures = options.fixtures ?? new MemoryFixtures();
    this.record = options.record;
    this.rules = options.rules ?? [];
    this.onMissing = options.onMissing ?? "throw";
    this.model = options.model ?? (options.record ? options.record.model : "mock");
    this.latencyMs = options.latencyMs ?? 0;
  }

  async judge(request: JudgeRequest, options: JudgeOptions = {}): Promise<JudgeResponse> {
    this.calls.push(request);
    if (this.latencyMs > 0) await new Promise((resolve) => setTimeout(resolve, this.latencyMs));
    const answers: Record<string, Answer> = {};
    const missing: Record<string, Question> = {};
    for (const [name, question] of Object.entries(request.questions)) {
      const ruled = this.applyRules(request.state, question, name);
      if (ruled) {
        answers[name] = ruled;
        continue;
      }
      const entry = this.fixtures.get(fixtureKey(request.state, question));
      if (entry) {
        answers[name] = entry.answer;
        continue;
      }
      missing[name] = question;
    }
    let usage = ZERO_USAGE;
    let model = this.model;
    if (Object.keys(missing).length > 0) {
      if (this.record) {
        const recorded = await this.record.judge({ state: request.state, questions: missing }, options);
        usage = addUsage(usage, recorded.usage);
        model = recorded.model;
        const recordedAt = new Date().toISOString();
        for (const [name, question] of Object.entries(missing)) {
          const answer = recorded.answers[name];
          if (!answer) throw new JudgmentError(`recording judge returned no answer for ${name}`);
          answers[name] = answer;
          this.fixtures.set(fixtureKey(request.state, question), {
            answer,
            question,
            statePreview: preview(request.state),
            model: recorded.model,
            recordedAt,
          });
        }
        this.fixtures.save();
      } else if (this.onMissing === "synthesize") {
        for (const [name, question] of Object.entries(missing)) {
          answers[name] = synthesizeAnswer(request.state, question);
        }
      } else {
        const [name, question] = Object.entries(missing)[0]!;
        throw new MissingFixtureError(fixtureKey(request.state, question), question, request.state);
      }
    }
    return { model, answers, usage };
  }

  private applyRules(state: EntryType, question: Question, name: string): Answer | undefined {
    for (const rule of this.rules) {
      const answer = rule(state, question, name);
      if (answer) return answer;
    }
    return undefined;
  }
}

function preview(state: EntryType): string {
  const text = typeof state === "string" ? state : JSON.stringify(state);
  return text.length > 120 ? `${text.slice(0, 117)}…` : text;
}

/** Deterministic pseudo-probability in (0,1) derived from a hash. */
function unit(seed: string): number {
  const hex = sha256(seed).slice(0, 12);
  return (Number.parseInt(hex, 16) % 10_000) / 10_000;
}

/** A stable but meaningless answer, for tests that only exercise plumbing. */
export function synthesizeAnswer(state: EntryType, question: Question): Answer {
  const key = fixtureKey(state, question);
  switch (question.type) {
    case "noul":
      return { type: "noul", noul: round(unit(key)) } satisfies NoulAnswer;
    case "choice": {
      const labels = Object.keys(question.criteria);
      const raw = labels.map((label) => unit(`${key}:${label}`) + 0.01);
      const total = raw.reduce((a, b) => a + b, 0);
      const probabilities: Record<string, number> = {};
      labels.forEach((label, i) => (probabilities[label] = round(raw[i]! / total)));
      const choice = labels.reduce((best, label) => (probabilities[label]! > probabilities[best]! ? label : best), labels[0]!);
      return { type: "choice", choice, confidence: round(probabilities[choice]!), probabilities } satisfies ChoiceAnswer;
    }
    case "score": {
      const levels = question.criteria.length;
      const raw = question.criteria.map((_, i) => unit(`${key}:${i}`) + 0.01);
      const total = raw.reduce((a, b) => a + b, 0);
      const probabilities: Record<string, number> = {};
      const legend: Record<string, EntryType> = {};
      let expected = 0;
      for (let i = 0; i < levels; i += 1) {
        const p = raw[i]! / total;
        probabilities[String(i)] = round(p);
        legend[String(i)] = question.criteria[i] ?? null;
        expected += i * p;
      }
      const confidence = Math.max(...Object.values(probabilities));
      return { type: "score", score: round(expected), confidence: round(confidence), legend, probabilities } satisfies ScoreAnswer;
    }
  }
}

function round(value: number): number {
  return Math.round(value * 1000) / 1000;
}

/** Convenience rules for tests. */
export const rules = {
  /** Answer every noul whose instructions contain `needle`. */
  noul(needle: string, p: number): MockRule {
    return (_state, question) =>
      question.type === "noul" && instructionsText(question).includes(needle) ? { type: "noul", noul: p } : undefined;
  },
  /** Answer every choice whose instructions contain `needle` with a fixed label. */
  choice(needle: string, label: string, p = 0.9): MockRule {
    return (_state, question) => {
      if (question.type !== "choice" || !instructionsText(question).includes(needle)) return undefined;
      const labels = Object.keys(question.criteria);
      const rest = labels.length > 1 ? (1 - p) / (labels.length - 1) : 0;
      const probabilities: Record<string, number> = {};
      for (const l of labels) probabilities[l] = l === label ? p : rest;
      return { type: "choice", choice: label, confidence: p, probabilities };
    };
  },
  /** Answer every score whose instructions contain `needle` with a fixed level. */
  score(needle: string, level: number, p = 0.9): MockRule {
    return (_state, question) => {
      if (question.type !== "score" || !instructionsText(question).includes(needle)) return undefined;
      const levels = question.criteria.length;
      const rest = levels > 1 ? (1 - p) / (levels - 1) : 0;
      const probabilities: Record<string, number> = {};
      const legend: Record<string, EntryType> = {};
      let expected = 0;
      for (let i = 0; i < levels; i += 1) {
        const prob = i === level ? p : rest;
        probabilities[String(i)] = prob;
        legend[String(i)] = question.criteria[i] ?? null;
        expected += i * prob;
      }
      return { type: "score", score: expected, confidence: p, legend, probabilities };
    };
  },
};

export function instructionsText(question: Question): string {
  const value = question.instructions;
  return typeof value === "string" ? value : JSON.stringify(value ?? "");
}
