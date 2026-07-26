# Publication handoff

Prepare a plan only after a new user message approves exact action IDs, reply bodies, resolve flags,
and a new output path. Preparation does not authorize sealing or remote mutation.

## Eligibility

Require all of the following in the new message:

- an exact subset of the displayed action IDs;
- approval of each exact reply body and resolve flag in that subset;
- a request to prepare publication; and
- a new output path below the repository root.

If an item, wording, resolve flag, or output path is ambiguous, ask for the missing detail and do
not write. Never infer approval from the original request to address feedback.

## Request contract

The temporary UTF-8 request has exactly these fields:

```json
{
  "schema_version": 1,
  "host": "github.com",
  "owner": "acme",
  "repo": "widgets",
  "pr_number": 42,
  "actions": [
    {
      "action_id": "null-guard-thread",
      "surface": "review-thread",
      "source_id": "PRRC_kwDO...",
      "thread_id": "PRRT_kwDO...",
      "verdict": "fixed",
      "reply_body": "> Please guard the null order.\n\nFixed in src/orders.js.",
      "resolve": true
    }
  ]
}
```

Copy only actions the user approved, byte-for-byte at the JSON string level after decoding. The
request deliberately omits `pr_node_id`, `head_oid`, and `plan_digest`: the helper obtains fresh PR
identity and head values itself, while sealing remains a later publisher operation.

## Procedure

1. Build a schema-v1 request containing only the approved actions. Write it to a fresh temporary
   regular JSON file below the repository root; never overwrite a path.
2. Resolve this installed skill's absolute directory from host context and run only its helper:
   ```bash
   /absolute/installed/skill/root/scripts/prepare_publish_plan.py \
     --root /absolute/repository/root \
     --request /absolute/repository/root/path/to/fresh-request.json \
     --output /absolute/repository/root/user-named-draft.json
   ```
   The helper re-pins the open PR node and full remote head OID, verifies that every selected source
   belongs to that PR, validates the unsealed contract, refuses linked or changed inputs, and uses
   no-overwrite output semantics.
3. Remove only the temporary request file from step 1.
4. Summarize the exact output actions, fresh head OID, and output path, then stop. Do not seal the
   plan or perform a remote mutation.
5. If `$publish-pr-feedback` is installed, state that the next separate action is
   `$publish-pr-feedback seal DRAFT NEW_SEALED_PATH`; publishing still requires another invocation
   containing the resulting sealed path and digest. If it is unavailable, report the exact draft
   path and that this standalone resolver cannot seal or publish it. Do not search for, install, or
   emulate the missing publisher.

## Output and standalone boundary

The output uses the unsealed form of the publisher contract. It adds `pr_node_id` and `head_oid`,
has no `plan_digest`, and is created with mode 0600 at the user-named root-confined path. Existing,
linked, hardlinked, escaped, invalid, closed-PR, stale-source, and mismatched-source cases fail
without an output.

Preparation is standalone: `scripts/prepare_publish_plan.py` imports only the resolver's local
`scripts/plan_contract.py` and does not discover or load a sibling skill. The publisher ships its
own byte-identical copy of the unsealed contract and independently validates the exact sealed
schema and digest before any publication preflight.
