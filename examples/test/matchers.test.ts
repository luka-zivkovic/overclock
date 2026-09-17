// Semantic matchers backed by a committed fixture file. CI replays; re-record with
//   JUDGMENT_FIXTURES=record TYPESAFE_API_KEY=... pnpm test   (or: vitest run --update-semantic-fixtures)
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { JudgmentClient, judgeFromEnv } from "@overclock/judgment-core";
import { semanticMatchers, type MatcherOptions } from "@overclock/semantic-types";
import { describe, expect, it } from "vitest";

// Vitest 5 types assertions as Assertion<R, T>; older versions use Assertion<T>. Match your version.
declare module "vitest" {
  interface Assertion<R, T> {
    toMean(text: string, options?: MatcherOptions): Promise<R>;
    toMeanNot(text: string, options?: MatcherOptions): Promise<R>;
  }
}

const fixtures = join(dirname(fileURLToPath(import.meta.url)), "..", "fixtures", "tests.json");
const client = new JudgmentClient({ judge: judgeFromEnv({ fixtures }) });
expect.extend(semanticMatchers(client));

describe("semantic matchers", () => {
  it("checks meaning, not wording", async () => {
    await expect("Smith et al. (2024) report a 12% lift; see https://example.org/paper for the full method.").toMean("cites at least one source");
    await expect("Everyone knows this works. Trust me.").toMeanNot("cites at least one source");
    await expect("Thanks for the report! I've filed it and will update you tomorrow.").toMean("is polite and professional", { threshold: 0.8 });
    await expect("Read the docs before wasting my time.").toMeanNot("is polite and professional");
  });
});
