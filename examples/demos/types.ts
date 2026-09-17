import type { JudgmentClient } from "@overclock/judgment-core";

export interface DemoSection {
  heading: string;
  /** Markdown body. */
  body: string;
}

export interface DemoUsage {
  requests: number;
  questions: number;
  cacheHits: number;
  inputTokens: number;
  outputTokens: number;
}

export interface DemoReport {
  id: string;
  title: string;
  summary: string;
  sections: DemoSection[];
  /** Demos that bypass the JudgmentClient (semantic-sql's engine) report their own usage. */
  usage?: DemoUsage;
}

export type Demo = (client: JudgmentClient) => Promise<DemoReport>;

export function table(headers: string[], rows: Array<Array<string | number>>): string {
  const line = (cells: Array<string | number>) => `| ${cells.map((c) => String(c).replace(/\|/g, "\\|")).join(" | ")} |`;
  return [line(headers), `| ${headers.map(() => "---").join(" | ")} |`, ...rows.map(line)].join("\n");
}

export function pct(p: number): string {
  return `${(p * 100).toFixed(0)}%`;
}

export function code(text: string, lang = "ts"): string {
  return `\`\`\`${lang}\n${text.trim()}\n\`\`\``;
}
