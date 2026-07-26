# SOLUTIONS.md template

Fill-in-ready skeleton for `.ai/memory/SOLUTIONS.md`. Copy the skeleton, replace every `<...>`
placeholder with real content, and keep the field order exactly as shown — the contract requires
stable ordering. Target under 250 lines total; entries lead with Symptoms because retrieval
matches on that line.

## Skeleton

```markdown
<!-- memory-schema: v1 -->
# Solutions

## <short problem-shaped title>
- **Symptoms:** <observable failure — exact error text or wrong behavior>
- **Context:** <module, stack, and situation where this applies>
- **What didn't work:** <attempted fixes that failed, each with why when diagnosed>
- **Solution:** <what actually fixed it, concretely>
- **Why it works:** <the root cause the fix addresses>
- **Verified:** <[agent-observed] or [user-reported] plus the test or observed behavior>
- **Date:** <ISO-8601 date>
```

## Worked example

```markdown
<!-- memory-schema: v1 -->
# Solutions

## Webhook retries duplicate orders under concurrent delivery
- **Symptoms:** duplicate rows in `orders` with identical `external_id`; provider dashboard shows the same webhook delivered 2-3 times within ~5s; began after enabling provider-side retries.
- **Context:** src/webhooks/orders.ts handler + Postgres; any endpoint the provider retries on timeout.
- **What didn't work:** in-memory dedup Set — FAILED, three replicas behind the LB each keep their own set; raising the handler timeout — FAILED, retries come from provider-side 5s cap, not our latency.
- **Solution:** unique index on `orders.external_id` plus `ON CONFLICT DO NOTHING`, returning 200 for the duplicate delivery.
- **Why it works:** dedup moves to the one shared layer (the database); retries become idempotent no-ops regardless of which replica handles them.
- **Verified:** [agent-observed] test/webhooks/dedup.test.ts fires the same payload 3x concurrently and asserts one row; ran red before the index, green after.
- **Date:** 2026-07-20
```
