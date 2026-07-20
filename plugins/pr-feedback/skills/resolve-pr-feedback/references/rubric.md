# Verdict rubric

Adapted from EveryInc/compound-engineering-plugin (MIT), `ce-resolve-pr-feedback` — reworked
for Overclock's judge-and-draft contract (no autonomous commit/push/post).

The orchestrator applies this to decide each item's verdict **before** any fix is applied.
This is the legitimacy gate: judgment happens in the one context that holds every thread at
once — not inside an isolated fixer that has lost the author's design intent. Read the actual
code when a verdict turns on it; never decide validity from the comment text alone.

Verdicts sort every item into three lists:

- **fix-list** — `fixed` / `fixed-differently` (a better approach than the one suggested);
  applied to the working tree.
- **reply-list** — `replied` / `not-addressing` / `declined`; reply text composed now, no
  code change.
- **human-list** — `needs-human`; `decision_context` composed now, thread stays open.

## Default to fixing

Most review feedback — nitpicks included — is correct and worth fixing. Work the list:
verdict `fixed`, or `fixed-differently` when a better approach is the right call. The checks
below are tripwires, not a per-item deliberation. When nothing trips, mark it to fix and move
on. "I'm uneasy" is not a tripwire; "I read the callers and this breaks X" is.

## How deep to read

- **Clear nit or clearly-valid finding** (typo, a bug the diff shows, naming, a missing
  guard the comment pinpoints) → the comment plus the diff line is enough. Mark to fix.
- **Contestable finding, or code that looks deliberate** → deep-read before accepting: open
  the file, read the callers, check for the invariant or test that would make the reviewer
  wrong. This is where a confidently-wrong reviewer gets caught.
- **Recover the author's intent before overriding deliberate-looking code**: `git log` /
  `git blame` the lines, read the PR description. Weigh intent against the finding rather
  than assuming the reviewer saw more.
- **Dedup reads by file.** Multiple threads on one file: read it once, judge them together.

## Cross-item reasoning

You hold every thread at once — use that:

- **Cluster by root assumption.** If one source (often a bot) makes the same kind of claim
  across several threads and it doesn't hold in one place, scrutinize the siblings: a
  systematically-wrong premise produces a cluster of plausible-but-wrong findings.
- **Converging requests are a strong fix signal.** The same change asked for by independent
  reviewers rarely warrants a divert.
- **Fix the class, not one instance — bounded.** When you accept a finding, check whether
  this PR also introduced other sites governed by the same invariant admitting the same fix
  with no site-specific judgment; fold those into one class fix. Bound it strictly: only
  behavior this PR changed, never every pre-existing occurrence; exclude any site whose
  invariant or treatment differs. If equivalence is itself a judgment call, keep the items
  separate — a false "class complete" is worse than one more round.
- **Non-convergence (treadmill).** Several nits sharing one root — the approach itself is
  the problem ("your regex misses case X", repeated for X after X), or a bot posting fresh
  nits every push without end — become **one** approach-level `needs-human` about the root
  decision, not another round of instance fixes. This fires only on a demonstrated shared
  root; a normal batch of unrelated valid nits is simply fixed.

## Diverts (per item, on concrete signal only)

- **The finding doesn't hold** — the code shows the issue doesn't exist or is already
  handled → `not-addressing`, with evidence.
- **No longer relevant** — the code at that location changed since the review → see
  outdated handling below → usually `not-addressing`.
- **The fix would make the code worse** — violates active project conventions, adds dead
  defensive code, suppresses errors that should propagate, premature abstraction, restates
  code in comments → `declined`, citing the specific harm. Never simplify away a safety
  check to satisfy a nit.
- **Buys nothing real** — cosmetic preference with no benefit to correctness, clarity, or
  maintainability → `replied`, briefly saying why. Small *real* improvements still get
  fixed; the skip bar is "no benefit", not "minor".
- **Risky and unboundable** — touches a hot path, a boundary other code relies on, or
  thinly-tested code, and the benefit doesn't justify it. First de-risk by reading the
  callers (adding a test is a legitimate fix step). Material risk remaining → `needs-human`.
- **Would undo a deliberate design choice (evidence-gated, rare)** — fires only when BOTH
  hold and you can name them: (1) a concrete artifact shows the behavior is a choice (a
  comment/docstring stating it, a test asserting it, a commit/PR rationale) — "the code
  currently does X" is not evidence; and (2) a competent reviewer could reasonably choose
  either way. Both hold → `needs-human` with the intent artifact quoted. Otherwise it is an
  ordinary fix; uncertainty resolves to fixing, not escalating.
- **A question, not a change request** — answerable from the code → `replied`; hinges on a
  product/business call → `needs-human`.

## Outdated threads (`isOutdated: true`)

The diff hunk shifted; the reported line may no longer be where the concern lives, and
`line` may be null. Start at whichever location resolves, preferring `line`, `startLine`,
`originalLine`, `originalStartLine`. If none matches the reviewer's description, extract an
anchor (symbol, identifier, distinctive phrase) and search **the same file** once:

- Anchor found → re-evaluate at that location.
- Not found, comment describes concrete in-place code → `not-addressing` with evidence
  ("searched <file> for <anchor>, not present").
- Not found, code apparently moved to another file → `needs-human`; picking the new location
  is the user's call. Do not grep the whole repo.

## Escalate sparingly

`needs-human` also covers: architectural changes affecting other systems, security-sensitive
decisions, ambiguous business logic, conflicting reviewer feedback. Do the investigation
before escalating — the user should be able to read the `decision_context` and decide in
under 30 seconds.

## Drafted reply formats

Compose these at judgment time — the evidence is in hand. Quote the specific sentence being
addressed, not a long comment wholesale. Replies are drafts until the user approves posting.

`fixed` / `fixed-differently`:
```markdown
> [relevant part of the reviewer's comment]

Fixed in [file] — [one line on what changed; for fixed-differently, why this approach].
```

`replied` / `not-addressing` / `declined`:
```markdown
> [relevant part of the reviewer's comment]

[Direct answer] / Not addressing: [evidence] / Declined: [specific harm cited].
```

`needs-human` — the reply is written as the PR author would write it (no "flagging for human
review" boilerplate):
```markdown
> [relevant part of the reviewer's comment]

[Natural acknowledgment, e.g. "Good question — this trades X against Y; thinking it through
before making a call."]
```

The `decision_context` (shown to the user, never posted):
```markdown
## What the reviewer said
## What I found
## Why this needs your decision
## Options
(a) … — [tradeoff]  (b) … — [tradeoff]
## My lean
```
