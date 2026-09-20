# Independent forward-use record

On 2026-09-11, a fresh Codex subagent received the prototype as its only active
skill. It did not receive parent discussion, expected outputs, parent controls or
the proposed QA diff. This was one authoring exercise in the current harness,
not a Claude CLI behavioral evaluation or an implicit-selection test.

Request: use the supplied `session-handoff` contract and repository eval
conventions to add a regression case for a user changing their mind after the
resume brief. Write eval and fixture artifacts only in a fresh scratch copy.

Allowed evidence: the target `SKILL.md`, `qa/eval_contract.py`, `qa/run_evals.sh`,
the existing `session-handoff` suite and `qa/fixtures/additional.py`. No paid calls,
private logs, installed sibling skills, git mutation or remote actions were used.

The author produced a native continuation case: after a real six-line Postgres
brief, the user changes direction to SQLite and authorizes only the local SQL.
Existing case 7 serves as the permitted Postgres-confirmation control. The author
also supplied a copied fixture builder and explicitly described its local preview
as using placeholder anchors, not a live-ready git run.

Parent integration changed the emitted case's ID from 8 to 10, added a separate
deterministic unchanged-handoff expectation and reused the real fixture builder.
The case and builder are committed in the native suite. Parent tests materialize
actual git repositories and verify matching full anchors and initially absent
migration/canary files. No target skill code was changed.

The author reported six synthetic checks for SQLite shape, premature direct
Write/Edit attempts, a denied attempt, missing migration and session discontinuity.
Those scratch-only helpers are **not adopted evidence for native behavior** and
are not part of the shipping runner. They cannot inspect arbitrary Bash effects.
The committed deterministic tests cover the narrower file-state claims directly;
the native judge retains responsibility for chronological tool behavior.

Outcome: one usable authored case was integrated after parent inspection. This
supports feasibility, not measured authoring quality, time saved, standalone
invocation, negative-control success or superiority over an unskilled author.
Those remain unmeasured. No provider cost is fabricated for the existing-harness
exercise.
