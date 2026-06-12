# HANDOFF.md template

Fill-in-ready skeleton for `.ai/memory/HANDOFF.md`. Copy the skeleton, replace every `<...>` placeholder with real content from the session, and delete any guidance comments. Keep the section order exactly as shown — the contract requires stable ordering. Target under 150 lines total.

## Skeleton

```markdown
<!-- memory-schema: v1 -->
# Session Handoff
Saved: <ISO-8601 date and time, e.g. 2026-06-10T17:42:00>

## Current goal
<One or two sentences: what we are ultimately trying to achieve and why.>

## Plan
- [x] <Step that is finished>
- [~] <Step in progress — note exactly where work stopped within it>
- [ ] <Step not started>

## Decisions
- <Decision made> — <rationale: why this over the alternatives>

## Failed approaches
- <What was tried> — FAILED because <diagnosed cause>. <What this rules out / do not retry unless X changes.>

## Open questions
- <Unresolved unknown, including anything awaiting a user answer>

## Next steps
1. <Concrete first action a cold session could start with>
2. <Second action>

## Key files
- <path/to/file> — <why it matters to this work>

## Environment anchors
- Branch: <git branch --show-current>
- HEAD: <git rev-parse --short HEAD>
- Dirty files: <git status --porcelain output, or "clean">
- Date: <save date>
<!-- Non-git project: replace Branch/HEAD/Dirty with "Not a git repo" and list key-file mtimes instead. -->
```

## Worked example

```markdown
<!-- memory-schema: v1 -->
# Session Handoff
Saved: 2026-06-10T17:42:00

## Current goal
Add rate limiting to the public API so the free tier is capped at 100 req/min per key, without breaking the existing enterprise bypass header.

## Plan
- [x] Add `rate-limiter-flexible` and a Redis-backed limiter in src/middleware/rateLimit.ts
- [~] Wire the middleware into src/app.ts — done for /api/v1/*, stopped before the /webhooks routes (they must stay unlimited)
- [ ] Add 429 response body matching the error envelope in src/errors.ts
- [ ] Integration tests in test/rateLimit.test.ts

## Decisions
- Redis-backed counters over in-memory — the API runs 3 replicas behind the LB, so per-process counters would triple the effective limit.
- Limit keyed on API key, not IP — corporate NATs would unfairly throttle whole offices.

## Failed approaches
- express-rate-limit with its Redis store — FAILED because its store API drops the millisecond precision our 100/min sliding window needs; counts reset on whole-second boundaries and burst tests flaked. Do not retry; rate-limiter-flexible handles this natively.

## Open questions
- Should the enterprise bypass header (`X-RL-Bypass`) be validated against the keys table, or is the shared secret enough? Asked the user, no answer yet.

## Next steps
1. Exclude /webhooks routes from the limiter in src/app.ts (see the in-progress plan step).
2. Implement the 429 envelope, then run `npm test -- rateLimit`.

## Key files
- src/middleware/rateLimit.ts — the limiter implementation
- src/app.ts — middleware wiring (in progress)
- src/errors.ts — error envelope the 429 body must match

## Environment anchors
- Branch: feat/rate-limiting
- HEAD: 8c41f2a
- Dirty files: M src/app.ts, ?? src/middleware/rateLimit.ts
- Date: 2026-06-10
```
