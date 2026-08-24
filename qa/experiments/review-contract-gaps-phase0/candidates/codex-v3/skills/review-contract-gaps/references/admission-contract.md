# V3 admission contract

The model owns semantic reasoning. The bundled helper owns clerical evidence.

## Discovery claim

Return one claim only for a source-supported contract violation on a reachable path. Each claim
contains a stable `C1`, `C2`, ... id, normalized root-cause key, changed decision, contract,
producer, consumers, guards checked, counterexample scenario, and finding prose.

Evidence hints contain:

- safe repository-relative `path`;
- approximate positive `line_hint`;
- a one- or multi-line source `snippet`, optionally abbreviating surrounding text with `...`, and
  preserving at least one concrete source line without a line-number prefix;
- symbolic `ref` (`base` or `head`) for non-changed evidence; and
- semantic `role`.

The contract must use `base`. A changed hint uses `side` (`LEFT` or `RIGHT`) instead of a ref. The
helper resolves `base` to the unique merge base and chooses the nearest uniquely matching normalized
source line from the concrete snippet fragments. Standalone ellipses and punctuation-only fragments
are never evidence. Resolution is restricted to real changed lines for the changed hint, and an
approximate line number is never accepted without lexical overlap with a concrete fragment.

Do not include review-coverage judgments during discovery. Do not author SHAs, exact line text,
review hashes, coverage arithmetic, or a second copy of the changed anchor in finding prose.

## Per-claim admission

The helper admits a claim only when:

- the id and root-cause key are unique;
- every evidence hint resolves unambiguously at its symbolic ref;
- the changed hint resolves to a real changed line on the requested side;
- the contract resolves at the merge base;
- at least one producer, one consumer, and one checked guard exist;
- scenario and material finding fields are non-empty; and
- priority is `P0`–`P2` and confidence is `high` or `medium`.

An invalid claim is recorded with deterministic rejection reasons and dropped without invalidating
other claims. No repair session is allowed.

## Coverage subtraction

Coverage is a separate semantic decision over materialized cards and a frozen review. Exactly one
decision per materialized claim is expected. Only `uncovered` is admitted. `covered`, `unclear`,
missing, duplicate, and invalid decisions fail closed for that claim. Unknown claim ids never add a
finding.

Standalone mode skips subtraction and clearly labels that limitation.
