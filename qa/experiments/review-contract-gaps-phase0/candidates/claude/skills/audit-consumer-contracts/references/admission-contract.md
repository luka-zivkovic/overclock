# Consumer-contract admission contract

Each verifier decision records:

- `surface_id` from the extractor;
- `disposition`: `confirmed-new-finding`, `already-covered`, `defeated`, `unreachable`, or
  `unresolved`;
- `root_cause_key` and a concise reason;
- an exact external base endpoint, its `producer` or `consumer` direction, and head evidence;
- concrete reachable sequence and guards checked; and
- one finding object only for `confirmed-new-finding`.

An anchor contains a safe repository-relative `path`, positive `line`, exact 40-character `ref`, and
exact `line_text`. The `external_endpoint` adds `direction` and a behavioral `expectation`; it must
match an extractor-listed base match and remain outside all changed files. The finding uses the
surface's exact changed-line anchor.

Findings contain `priority` (`P0`, `P1`, `P2`), `confidence` (`high`, `medium`), `title`, changed
location, `failure_path`, `impact`, at least four evidence statements, and a concise draft comment.
Duplicate root causes fail closed. Findings may not cite unsupplied PRs or issues.

When a frozen review is supplied, include its SHA-256 in the payload. This artifact is an append-only
delta; the base review is never part of the candidate text.
