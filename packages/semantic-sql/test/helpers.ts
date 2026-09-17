import { MockJudge, type Answer, type EntryType, type MockRule, type Question } from "@overclock/judgment-core";

/** The text of the packed row a question is addressed to (or the plain state). */
export function rowText(state: EntryType, name: string): string {
  if (state && typeof state === "object" && !Array.isArray(state) && Array.isArray(state.rows)) {
    for (const row of state.rows as Array<{ id: string; text: string }>) if (row.id === name) return row.text;
  }
  return typeof state === "string" ? state : JSON.stringify(state);
}

/** A rule that answers per row text. */
export function byText(fn: (text: string, question: Question) => Answer | undefined): MockRule {
  return (state, question, name) => fn(rowText(state, name), question);
}

/** noul: p = 0.9 when the text contains any needle, 0.1 otherwise. */
export function noulContains(...needles: string[]): MockRule {
  return byText((text, question) =>
    question.type === "noul" ? { type: "noul", noul: needles.some((n) => text.toLowerCase().includes(n)) ? 0.9 : 0.1 } : undefined,
  );
}

/** choice: first label whose name appears in the text, else the first label. */
export function choiceByKeyword(): MockRule {
  return byText((text, question) => {
    if (question.type !== "choice") return undefined;
    const labels = Object.keys(question.criteria);
    const choice = labels.find((label) => text.toLowerCase().includes(label)) ?? labels[0]!;
    const probabilities: Record<string, number> = {};
    for (const label of labels) probabilities[label] = label === choice ? 0.8 : 0.2 / (labels.length - 1);
    return { type: "choice", choice, confidence: 0.8, probabilities };
  });
}

/** score: expected level = number of "!" in the text, capped at the top level. */
export function scoreByBangs(): MockRule {
  return byText((text, question) => {
    if (question.type !== "score") return undefined;
    const levels = question.criteria.length;
    const level = Math.min(levels - 1, (text.match(/!/g) ?? []).length);
    const probabilities: Record<string, number> = {};
    const legend: Record<string, EntryType> = {};
    for (let i = 0; i < levels; i += 1) {
      probabilities[String(i)] = i === level ? 1 : 0;
      legend[String(i)] = question.criteria[i] ?? null;
    }
    return { type: "score", score: level, confidence: 1, legend, probabilities };
  });
}

export function mockJudge(extra: MockRule[] = []): MockJudge {
  return new MockJudge({ rules: [...extra, noulContains("delay", "late", "shipping"), choiceByKeyword(), scoreByBangs()], onMissing: "synthesize" });
}
