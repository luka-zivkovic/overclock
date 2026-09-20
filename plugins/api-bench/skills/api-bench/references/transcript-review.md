# Reviewing a bench transcript

Read `summary.json` first. Its `status` and `detail` say why the run stopped; everything else is
context for that. Then open `transcript.jsonl` and quote the lines that support each finding.

## Checklist

1. **Did the run finish for the right reason?** `completed` means the model ended its turn.
   `turn_limit` or `budget_exceeded` on a task that should take two tool calls points at a loop
   (repeated identical calls, tool results the model cannot use). `truncated` means `max_tokens`
   is too low for the output the prompt asks for, or the prompt invites an essay where the app
   wants a sentence.
2. **Tool inputs against the schema.** For every `tool_call` event compare `input` with the tool's
   `input_schema`: missing required keys, extra keys, wrong types, or values the app would reject
   (dates in the wrong format, ids the prompt never gave). Each mismatch is a description or
   schema fix, not a stub fix.
3. **Stub coverage.** `missing_stubs` in the summary lists tools the model called without a stub;
   `"stub": "default"` on a case-based stub means no `when` matched. Decide whether the model
   asked for something the app's real tool would answer, or whether the stub is incomplete.
4. **Tool order and parallelism.** `tool_sequence` shows the order; a `response` event with
   several `tool_use` blocks shows a parallel call. Check that dependencies hold (lookup before
   list) and that the app's loop can honor parallel calls in one message.
5. **Refusals and stop details.** A `refusal` status records `stop_details` on the `response`
   event. Report the category verbatim. Tell the user before any prompt change that would route
   around a safety decision, and let them decide whether to make it.
6. **Usage.** Compare `usage.input_tokens` across turns: a growing prefix is expected, but a jump
   after a tool result means a large stub. `cache_read_input_tokens` of zero across a multi-turn
   live run means nothing is being cached yet; that is a design note for the app, not a bench
   failure.
7. **Final text against acceptance criteria.** Read `final_text` as the app's user would see it.
   Check the format the system prompt demanded (length, structure, language) and whether the
   answer used the tool results or ignored them.

## Writing up

For each finding give: the transcript line (event kind and turn), what it shows, and the single
smallest change that addresses it. Separate what the transcript proves from what you infer. A
mock run proves the loop mechanics and the request shape; it says nothing about model behavior,
so label it as such. One live run is one sample; recommend repeated runs before calling a
difference between variants a result.
