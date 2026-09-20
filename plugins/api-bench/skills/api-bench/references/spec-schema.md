# Bench spec reference

A spec is one JSON object. Unknown top-level fields are rejected so a typo cannot silently drop a
limit. Paths in this document are relative to the skill directory.

## Identity and provider

| Field | Required | Meaning |
|---|---|---|
| `name` | no | Short identifier used in summaries and `compare` output. Default `bench`. |
| `provider` | no | `anthropic` (default) or `openai-compatible`. |
| `model` | yes | Model identifier sent verbatim. Use the exact current ID from the provider's model list. |
| `base_url` | anthropic: no; openai-compatible: yes | Absolute URL. Must be `https` unless the host is loopback (`localhost`, `127.0.0.1`, `::1`) for a local server. No query or fragment. For `anthropic` it defaults to `https://api.anthropic.com` and the helper posts to `/v1/messages`; for `openai-compatible` the helper posts to `<base_url>/chat/completions`, so include any `/v1` prefix the server expects. |
| `api_key_env` | no | Name of the environment variable holding the credential, when it is not the default. Anthropic defaults to `ANTHROPIC_API_KEY`, then `ANTHROPIC_AUTH_TOKEN` (sent as a plain bearer token, for gateways that accept one). OpenAI-compatible defaults to `OPENAI_API_KEY`. A live `run` honors a non-default name only when the command repeats it as `--credential-env <NAME>`; otherwise it stops with `missing_credentials`. This keeps a spec from quietly choosing which secret is sent to its `base_url`. |

## Conversation

| Field | Required | Meaning |
|---|---|---|
| `system` | no | System prompt string, sent as the top-level `system` field (Anthropic) or the first `system` message (OpenAI-compatible). |
| `messages` | yes | Seed conversation. Must start and end with a `user` turn. Content is a string or, for Anthropic, a list of content blocks. |
| `user_turns` | no | Scripted follow-up user messages. After each `end_turn` the next one is appended and the loop continues. Unused entries are listed in the summary. |

## Tools and stubs

| Field | Required | Meaning |
|---|---|---|
| `tools` | no | List of `{name, description, input_schema}`; `input_schema` must be an object schema. An optional `strict: true` on a tool is forwarded to the Anthropic API. |
| `tool_results` | no | Map from tool name to a stub. `"*"` is a catch-all. A tool call with no stub receives an `is_error` tool result naming the gap, and the tool is listed under `missing_stubs`. |
| `tool_choice` | no | Forwarded verbatim to the Anthropic API. Note that some models reject forced choices (`any`, `tool`); prefer `auto` plus a prompt instruction. |

A stub is either a constant (string or JSON, returned for every call) or an object using only
these keys:

```json
{
  "cases": [
    {"when": {"email": "ada@example.com"}, "result": {"customer_id": "cus_123"}},
    {"when": {"email": "bad@example.com"}, "error": "customer suspended"}
  ],
  "result": "fallback result when no case matches",
  "error": "fallback error when no case matches",
  "default": "same as result; kept for readability"
}
```

`when` matches when every listed key equals the tool input's value. Cases are tried in order.
`error` values are returned with `is_error: true`, which is how the app would report a failed
tool. Stub results longer than 64 KB are truncated with a marker.

## Generation parameters

| Field | Default | Meaning |
|---|---|---|
| `max_turns` | 8 | Assistant turns per run, hard ceiling 50. |
| `max_tokens` | 4096 | Per-response output cap; a response that hits it ends the run with `truncated`. |
| `thinking` | none | Forwarded verbatim, for example `{"type": "adaptive"}`. Omit on models where thinking is always on. |
| `effort` | none | `low`, `medium`, `high`, `xhigh`, or `max`; sent as `output_config.effort` (Anthropic only). |
| `temperature` | none | 0 to 2. Rejected by current Claude models; mainly for OpenAI-compatible servers. |

## Limits and pricing

`budget` is required and may contain only:

| Field | Meaning |
|---|---|
| `max_requests` | Required, 1 to 500. Counts every HTTP request including retries' final attempt and mock responses. |
| `max_total_tokens` | Optional. Input plus output tokens across the run. |
| `max_usd` | Optional. Requires `pricing`. Compared against the running estimate after each response. |

`pricing` is optional and holds USD per million tokens: `input_per_mtok` and `output_per_mtok`
are required together; `cache_read_per_mtok` and `cache_write_per_mtok` default to the input
price. Neither the helper nor the bundled template ships a price; copy current prices from the
provider on the day of the run, for example
`"pricing": {"input_per_mtok": 3, "output_per_mtok": 15, "cache_read_per_mtok": 0.3}`, and say
in the report that `estimated_usd` is an estimate from those numbers.

`notes` is free text for the reader and is never sent to the provider.

## Output files

`run` writes two files into `--out`, which must be a fresh or empty directory unless `--force`
is passed:

- `transcript.jsonl`: one event per line. Event kinds are `run_start`, `request` (the exact
  body sent), `response` (raw content, stop reason, usage, latency), `tool_call` (name, input,
  which stub answered, the result, `is_error`), `user_turn`, `pause_turn`, `error`, and `run_end`.
  Headers are never recorded, and any occurrence of the credential value is replaced with
  `[redacted-credential]`.
- `summary.json`: status, stop detail, turns, requests, usage totals, `estimated_usd`, tool call
  counts and order, missing stubs, unused scripted turns, final text, and the spec's SHA-256.

## Run statuses

| Status | Exit code | Meaning |
|---|---|---|
| `completed` | 0 | The model ended its turn with no scripted user turns left. |
| `turn_limit` | 2 | `max_turns` reached. |
| `budget_exceeded` | 2 | A `budget` cap tripped. |
| `truncated` | 2 | A response stopped at `max_tokens`. |
| `refusal` | 2 | The provider declined; `stop_details` is in the transcript. |
| `provider_error` | 2 | HTTP error after retries, transport failure, or an unparseable response. |
| `mock_exhausted` | 2 | The mock file ran out of responses. |
| `protocol_error` | 2 | An unrecognized stop reason or a malformed tool-use turn. |
| `request_too_large` | 2 | A request body exceeded 4 MB. |
| `invalid_spec`, `invalid_mock`, `invalid_output`, `missing_credentials` | 1 | The run never started. |
