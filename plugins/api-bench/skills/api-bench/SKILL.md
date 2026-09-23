---
name: api-bench
description: "Dry-run how an application would call a model API before writing the app: send a system prompt, seed messages, tool definitions, and stubbed tool results through a bounded, budget-capped tool-use loop against the Claude Messages API or an OpenAI-compatible endpoint, then review the exact transcript. Use when the user wants an actual transcript: to prototype, simulate, dry-run, or bench an API prompt or tool design, see what Claude or another model actually does with a tool set, compare two prompt variants on real runs, or check a request shape before it goes into code. Do not use to delegate work to another coding harness, to evaluate Claude Code skills or sessions, to spawn subagents, to answer API questions that documentation already settles, to predict what a model would do when reasoning about the schemas answers it, or for ordinary code changes that name no model call."
---

# API Bench

Treat the bench as a dry run: the request an application would send, executed once under hard
limits, so the design is judged on a real transcript rather than a guess. The user still owns the
application code; the bench produces evidence, not edits.

The command examples use Claude Code's `${CLAUDE_SKILL_DIR}` variable. On a host that does not
define it, use the installed directory of this `api-bench` skill as an absolute path. Do not scan
user directories or plugin caches to discover it.

## Boundaries

- A live run sends the spec's prompts, tool schemas, and stub results to an external provider and
  spends money. Before the first live request in a conversation, run `validate` and quote its
  `endpoint` and `credential_source` to the user together with the model, request cap, and token
  or dollar cap, then get the user's go-ahead. The host in `endpoint` is where the credential
  goes; a spec the user did not write can point it anywhere. A mock run needs no consent.
- Credentials come only from the environment (`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`,
  `OPENAI_API_KEY`, or the spec's `api_key_env`). Never put a key in a spec, a command argument,
  or a transcript, and never print one. If no credential is present, run with `--mock` or stop.
- A spec that names its own `api_key_env` is asking for a specific secret. The helper refuses to
  read it unless the run command repeats the name as `--credential-env <NAME>`; add that flag only
  after the user has seen which variable and which endpoint are involved.
- Every run needs a `budget.max_requests`; unbounded runs are refused. Keep first runs small:
  one seed conversation, a handful of turns, a low request cap.
- Write run output only to a fresh scratch directory outside version control. Do not commit
  transcripts, and do not edit the user's application code as part of a bench.
- Prefer a mock run for wiring checks, for environments without network, and whenever the
  question is about the loop mechanics rather than model behavior.

## Write the spec

Copy [templates/bench-spec.json](templates/bench-spec.json) and edit it to match the application's
intended request. The field reference is [references/spec-schema.md](references/spec-schema.md).
Put in the spec exactly what the app would send: the real system prompt, real tool names and
schemas, and stub results that look like the app's real tool output. Set `pricing` from the
provider's current price list when the user wants a dollar estimate; the helper ships no prices.

Validate without network:

```text
python3 "${CLAUDE_SKILL_DIR}/scripts/api_bench.py" validate --spec <spec.json>
```

`validate` reports the endpoint, the tools that have no stub, and which environment variable
would supply the credential. Fix `unstubbed_tools` unless a missing stub is the point of the test.

## Run

Mock run, no network and no credential:

```text
python3 "${CLAUDE_SKILL_DIR}/scripts/api_bench.py" run \
  --spec <spec.json> --mock <responses.json> --out <fresh-scratch-dir>
```

A mock file is a list of provider-shaped responses consumed in order; see
[templates/mock-responses.json](templates/mock-responses.json) for the Claude shape.

Live run, after the user's go-ahead:

```text
python3 "${CLAUDE_SKILL_DIR}/scripts/api_bench.py" run \
  --spec <spec.json> --out <fresh-scratch-dir> --max-requests <n>
```

The helper loops until the model ends its turn, a scripted `user_turns` entry is exhausted, or a
limit trips. It returns all parallel tool results in one message, passes assistant content back
unchanged, retries transient HTTP failures at most twice, and exits non-zero with a `status` other
than `completed` at any boundary. A run writes `transcript.jsonl` and `summary.json` into `--out`.

## Review the transcript

Read `summary.json` first, then the events that explain it. Use
[references/transcript-review.md](references/transcript-review.md) for the checklist: tool inputs
that miss the schema, stubs that never matched, `truncated` or `refusal` stops, unexpected tool
order, token and cache figures, and the final text against the app's acceptance criteria. Quote
transcript lines as evidence; do not summarize behavior the transcript does not show.

## Compare variants

Run each variant into its own directory, keeping everything except the change under test fixed,
then:

```text
python3 "${CLAUDE_SKILL_DIR}/scripts/api_bench.py" compare --a <dir-a> --b <dir-b>
```

One run per variant shows a difference, not a trend. Say so, and offer repeated runs before the
user treats a single comparison as a result.

## Report

Give the user: the spec and model used, the run status and why it stopped, request and token
totals with the dollar estimate when pricing was supplied, what the model did with the tools, and
the concrete change to the prompt, tool schema, or stub the evidence supports. Keep application
code changes as a separate, user-authorized step.

## Stop conditions

Stop and report rather than improvise on `invalid_spec`, `missing_credentials`, `budget_exceeded`,
`turn_limit`, `provider_error`, `mock_exhausted`, `request_too_large`, `truncated`, `refusal`, or
`protocol_error`. Never retry a live run in a loop to get past a budget, never raise a cap the
user did not approve, and never write a transcript by hand to stand in for a run that did not
happen.
