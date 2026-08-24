# Contract-gap admission contract

Use this schema as an internal evidence ledger. Return only its validated findings to the user.

## Row fields

Each row contains:

- `id`: stable `C1`, `C2`, ... identifier.
- `decision`: the implementation mechanism actually present.
- `changed_anchor`: `path`, `line`, `side`, and exact `line_text`.
- `contract`: base `path`, `line`, exact `ref`, `line_text`, and behavioral `statement`.
- `producer`: reachable evidence anchor and role.
- `consumers`: one or more reachable evidence anchors and roles.
- `guards_checked`: non-empty evidence statements naming the inspected guard, default, type,
  version gate, feature flag, or test and its result.
- `scenario`: concrete `precondition`, `action`, and `observable_failure`.
- `review_coverage`: `covered`, `uncovered`, or `unclear`, plus a root-cause comparison.
- `disposition`: `confirmed-gap`, `handled`, `covered`, `unreachable`, or `unresolved`.
- `root_cause_key`: a concise normalized causal identity used for deduplication.
- `reason`: why the evidence supports the disposition.

Every evidence anchor contains `path`, positive `line`, exact base/head `ref`, and exact `line_text`.
The contract anchor must use the resolved merge base. Changed anchors must be actual changed lines.

## Finding fields

Each proposed finding contains:

- `row_id`, `priority` (`P0`, `P1`, or `P2`), `confidence` (`high` or `medium`);
- `title`, `file`, `line`, `side`, and exact `changed_line`;
- `failure_path`, `impact`, at least four concrete `evidence` statements; and
- one concise `suggested_comment` suitable for a human to post.

Only `confirmed-gap` rows with `review_coverage.status: uncovered` may produce findings. A finding's
changed anchor must equal its row's changed anchor. Duplicate `root_cause_key` values fail closed.

## Coverage fields

Record non-negative counts for `changed_decisions`, `rows`, `confirmed_gaps`, `handled`, `covered`,
`unreachable`, and `unresolved`, plus arrays of `inspected_surfaces` and `blind_spots`. Counts must
match the rows.

## Non-finding examples

- The brief expected an option to be removed, but the implementation leaves it present and disables
  it: `handled` or `unresolved`, never a finding about a missing option.
- Another package contains the same code pattern but no producer reaches it in the affected runtime:
  `unreachable`.
- The base review already reports the same null/default mismatch at another changed line: `covered`.
- A realistic producer always supplies a non-null description, making a newly added `??` fallback
  unreachable: potentially `confirmed-gap` when the resulting user-facing behavior contradicts the
  change intent and the base review omits it.
