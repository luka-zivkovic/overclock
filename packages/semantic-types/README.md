# @overclock/semantic-types

Zod for meaning. Attach semantic predicates to a Zod schema and validate what a value *means*,
not only its shape, with probabilities kept as evidence. Judgments come from TypeSafe's Jev model
through `@overclock/judgment-core`.

```ts
import { z } from "zod";
import { s, semantic } from "@overclock/semantic-types";

const Reply = semantic(
  z.object({ subject: z.string(), body: z.string() }),
  {
    body: [
      s.is("is polite and professional", { threshold: 0.8 }),
      s.not("contains personally identifiable information", { threshold: 0.2 }),
      s.oneOf("primary intent", { answer: null, escalate: null, decline: null }, { expect: ["answer", "escalate"] }),
      s.rated("clarity", ["confusing", "acceptable", "crystal clear"], { min: 1 }),
    ],
    $self: [s.is("subject matches the body's content")],
  },
);

const reply = await Reply.parseAsync(draft);       // throws ZodError (shape) or SemanticError (meaning, with evidence)
const result = await Reply.safeParseAsync(draft);  // { success, data, evidence[], issues[], needsReview[] }
```

## Design decisions

- **One call per value, not per predicate.** All predicates about an object are judged in a single
  request: the whole object is the state and field predicates are phrased as
  `Regarding the field "body": …`. Structural validation runs first, so malformed input costs
  nothing. `fieldScoped: true` sends only the field's value instead (one request per field) for
  privacy or cost.
- **Predicates are data.** `s.is / s.not / s.oneOf / s.rated` return plain JSON objects wrapping one
  question and its pass rule. They serialize, diff, and are reused by `@overclock/semantic-sql`.
- **Evidence is never dropped.** Every result carries the probability, confidence and full answer
  per predicate; `SemanticError.evidence` is what you log.
- **Modes.** `strict` (default) fails on threshold. `annotate` never fails and attaches evidence to
  `data.$meta`. `review` adds a third band: verdicts within `margin` of a boundary land in
  `needsReview` instead of failing.

**Untrusted content.** `untrusted: true` wraps the state as `{ untrusted_input: value }` and tells
the judge, in every question, that instruction-like text inside it is just content. In the recorded
adversarial experiment this framing turned two instruction-injection flips into holds, at the cost
of a sarcasm case; it is a mitigation, not a guarantee.

## More than a validator

- `meaning(value, "…")` returns the probability; `assertMeaning(value, "…")` throws below the
  threshold. For code that is not Zod-shaped.
- `guarded(fn, { pre, post })` wraps a function with semantic contracts over `{ input, output }`.
- `expect(output).toMean("cites at least one source")` and `toMeanNot` for Vitest and Jest:
  `expect.extend(semanticMatchers())`. The default client replays fixtures from
  `.judgment/fixtures.json`, so CI is deterministic; run once with `--update-semantic-fixtures`
  (or `JUDGMENT_FIXTURES=record`) and a `TYPESAFE_API_KEY` to record.
- Property-based checks compose naturally:
  `fc.assert(fc.asyncProperty(arb, async (x) => (await meaning(f(x), "…")) > 0.9))`.
- `semantic-types calibrate ./labeled.jsonl --predicate "is polite"` prints a reliability diagram
  and the threshold that maximizes your chosen metric. Thresholds should come from data.

## Client configuration

`configure({ judge })` sets the default client. Without it, `judgeFromEnv()` from judgment-core
decides: replay fixtures by default, record with `JUDGMENT_FIXTURES=record`, or go live with
`JUDGMENT_FIXTURES=live`. Any `semantic()` schema or helper also accepts an explicit `client`.
