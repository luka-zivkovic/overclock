import { TypeSafeJudge } from "./judge.js";
import type { Judge } from "./judge.js";
import { JsonFileFixtures, MockJudge } from "./mock.js";

export interface JudgeFromEnvOptions {
  /** Fixture file for replay/record. Default: `.judgment/fixtures.json` under cwd. */
  fixtures?: string;
  /** Force a mode instead of reading JUDGMENT_FIXTURES. */
  mode?: "replay" | "record" | "live";
  model?: string;
}

/**
 * The judge a test suite or CLI should use, decided by environment:
 *
 * - `JUDGMENT_FIXTURES=record` (or `--update-semantic-fixtures` on argv): replay fixtures, answer
 *   misses live with TYPESAFE_API_KEY, and write them to the fixture file.
 * - `JUDGMENT_FIXTURES=live`: no fixtures, every question goes to the API.
 * - otherwise: replay only. A miss throws MissingFixtureError, so CI stays deterministic.
 */
export function judgeFromEnv(options: JudgeFromEnvOptions = {}): Judge {
  const argvUpdate = process.argv.includes("--update-semantic-fixtures");
  const mode = options.mode ?? (argvUpdate ? "record" : (process.env.JUDGMENT_FIXTURES as JudgeFromEnvOptions["mode"]) ?? "replay");
  const path = options.fixtures ?? process.env.JUDGMENT_FIXTURES_FILE ?? ".judgment/fixtures.json";
  const model = options.model;
  if (mode === "live") return new TypeSafeJudge(model ? { model } : {});
  const fixtures = new JsonFileFixtures(path);
  if (mode === "record") {
    const live = new TypeSafeJudge(model ? { model } : {});
    return new MockJudge({ fixtures, record: live, model: live.model });
  }
  return new MockJudge({ fixtures, ...(model ? { model } : {}) });
}
