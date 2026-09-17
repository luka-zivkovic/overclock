# @overclock/judgment-core

The shared foundation for typed, probabilistic judgment on top of [TypeSafe](https://typesafe.ai)'s
System One API (model `jev-latest`). One call takes one `state` and many named `questions`; the
questions run in parallel and isolated, so cost is flat as you add questions. This package makes
that cheap to use correctly: a `Judge` interface with a live and a mock implementation, a batcher,
a cache, record/replay fixtures, and a calibration harness. Everything above it only sees `Judge`.

```ts
import { JudgmentClient, TypeSafeJudge, noul, choice, score } from "@overclock/judgment-core";

const client = new JudgmentClient({ judge: new TypeSafeJudge() }); // reads TYPESAFE_API_KEY

const draft = "Thanks for reaching out! I have refunded your order; expect it within 3 days.";
const [polite, intent, clarity] = await Promise.all([
  client.ask(draft, noul("Is the message polite and professional?")),
  client.ask(draft, choice("What is the primary intent?", { answer: null, escalate: null, decline: null })),
  client.ask(draft, score("Rate the clarity", ["confusing", "acceptable", "crystal clear"])),
]);
// One HTTP request: all three questions share the same state.
polite.p;                 // 0.95
intent.answer.choice;     // "answer", with intent.answer.probabilities and intent.confidence
clarity.answer.score;     // 1.93 on a 0..2 rubric; clarity.p is the normalized 0.97
client.usage();           // { requests: 1, questions: 3, cacheHits: 0, inputTokens, outputTokens, ... }
```

## What it provides

**Questions are data.** `noul(text)`, `choice(text, labels)` and `score(text, levels)` build plain
JSON objects matching the wire format. Hash them, store them, diff them.

**`Judge`.** `TypeSafeJudge` wraps the official SDK (`@typesafe-ai/sdk`), whose defaults already
retry 408, 429 and 5xx with jittered backoff and honor `Retry-After`. `MockJudge` answers from
hand-written rules, a fixture store, or a recording judge, in that order; a miss throws so CI stays
deterministic, or `onMissing: "synthesize"` returns stable hash-derived answers for plumbing tests.
`judgeFromEnv()` picks replay, record or live from `JUDGMENT_FIXTURES` (or
`--update-semantic-fixtures` on argv).

**Batcher.** `JudgmentClient.ask(state, question)` collects everything queued in one tick, groups
by identical state (canonical JSON hash), and sends one request per distinct state. Concurrency is
bounded, batches are split at `maxQuestionsPerCall`, and a request-size guard rejects states above
`maxStateBytes`. Identical in-flight questions share one answer.

**Cache.** `sha256(model, canonical(state), canonical(question)) -> answer`. In-memory LRU by
default, `KeyValueCache` for any async KV store, `NoCache` to opt out. Judgments are idempotent,
so repeated queries cost nothing.

**Evidence.** Every `Judgment` carries `{ answer, p, confidence?, question, stateHash, key, cached, model, usage? }`.
`p` is one 0..1 number (noul probability, chosen-label probability, or expected score normalized by
the top level); the full distribution is always on `answer`.

**Calibration.** `calibrate([{ p, label }])` returns Brier score, expected calibration error,
reliability bins, a threshold table, and the threshold that maximizes `f1`, `precision`,
`recall`, `accuracy` or `{ precisionAtRecall }`. `calibrateJudgments(client, cases)` runs the
cases first. `renderCalibration(report)` prints a text reliability diagram.

## Testing

Unit tests use `MockJudge` and never touch the network. One test tagged live runs only with
`LIVE=1` and `TYPESAFE_API_KEY`:

```sh
pnpm test                 # deterministic
LIVE=1 pnpm test          # adds the live round trip
```

## Limits worth knowing

Request size, questions per request and rate limits are not documented by TypeSafe yet, so the
batcher's `maxQuestionsPerCall`, `maxStateBytes` and `concurrency` are configuration, not
constants. Choice questions are capped at 255 labels per the docs' line-search cookbook. Pricing is
not published; count tokens from `usage()` rather than assuming a rate.
