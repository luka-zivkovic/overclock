import { defineConfig } from "vitest/config";

// Unit tests run against MockJudge fixtures and never touch the network.
// Tests tagged live (describe.skipIf(!LIVE)) run only with LIVE=1 and TYPESAFE_API_KEY.
export default defineConfig({
  test: {
    environment: "node",
    include: ["packages/*/test/**/*.test.ts", "examples/test/**/*.test.ts"],
    exclude: ["**/node_modules/**", "**/dist/**"],
    testTimeout: 30_000,
  },
});
