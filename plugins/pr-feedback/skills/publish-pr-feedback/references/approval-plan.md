# Approval plan contract

The UTF-8 JSON object has exactly these top-level fields:

```json
{
  "schema_version": 1,
  "host": "github.com",
  "owner": "acme",
  "repo": "widgets",
  "pr_number": 42,
  "pr_node_id": "PR_kwDO...",
  "head_oid": "40 lowercase hexadecimal characters",
  "actions": [
    {
      "action_id": "null-guard-thread",
      "surface": "review-thread",
      "source_id": "PRRC_kwDO...",
      "thread_id": "PRRT_kwDO...",
      "verdict": "fixed",
      "reply_body": "> Please guard the null order.\\n\\nFixed in src/orders.js.",
      "resolve": true
    },
    {
      "action_id": "architecture-question",
      "surface": "review-body",
      "source_id": "PRR_kwDO...",
      "verdict": "needs-human",
      "reply_body": "We are keeping this open while we choose between the two designs.",
      "resolve": false
    }
  ],
  "plan_digest": "64 lowercase hexadecimal characters"
}
```

`surface` is `review-thread`, `pr-comment`, or `review-body`. Only a review-thread action has
`thread_id`, and only such an action may set `resolve` to true. A `needs-human` action can never
resolve.

The seal operation rejects unknown fields, empty or duplicate actions, invalid IDs, oversized
replies, and more than 100 actions. It computes `plan_digest` as SHA-256 over canonical UTF-8 JSON
with sorted keys, compact separators, and the `plan_digest` field omitted.

Publishing appends a hidden marker derived from the approved digest and `action_id`. Before any
mutation, the helper verifies that every source belongs to the planned PR and fully paginates
existing comments while searching for those markers. Marker lookup is independent of comment
author, so a serialized retry may use a different authenticated account. After all pagination, the
helper re-pins the open PR and approved head immediately before its first mutation.

The marker provides sequential retry deduplication after a partial failure; it does not alter the
visible reply text. Marker discovery and comment creation are separate GitHub operations, and this
plan does not authorize an extra remote lock mutation. Therefore the helper cannot guarantee
idempotency for concurrent publishers: two overlapping processes can both observe no marker and
post duplicate replies. Run exactly one publisher at a time, wait for it to exit before retrying,
and pass `--confirm-no-concurrent-publisher` only under that condition.

Seal the plan only after the approved code state is present on the remote PR. Publication requires
the remote head OID to match `head_oid` exactly; a push invalidates an older plan.
