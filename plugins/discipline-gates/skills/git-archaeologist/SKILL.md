---
name: git-archaeologist
description: "Always use before deleting, bypassing, or weakening a structural defensive construct in existing committed code: a guard clause or early return that rejects invalid/unsafe state, retry/backoff, protective sleep/delay, lock/mutex, a caller-input clamp/bounds check, or a check commented 'redundant'/'defensive'/'shouldn't happen'. Recover why it exists with git blame, the introducing commit, and linked PR/issue evidence, then warn before removal. Trigger only when the requested change weakens one of those constructs. Do NOT use for behavior-preserving control-flow rewrites where the construct remains effective, ordinary early returns, typo/copy fixes, config/version/dependency bumps, pure renames/signature changes, formatting, generated/vendored/lockfile hunks, new features, pure additions, or uncommitted code."
---

# Git Archaeologist

Chesterton's fence, mechanized. Defensive code usually exists because something broke once —
and the reason lives in git history, a real artifact, not in intuition. Before a change
deletes or weakens such a construct, this skill recovers the original intent and puts the
evidence in front of the decision. It warns; it does not block.

## Trigger — a structural pattern list, never a vibe

Fires when the change at hand would **delete or weaken** one of these in existing committed
code:

- a guard clause or early return that rejects invalid, unsafe, or unexpected state
- a retry / backoff loop
- a protective `sleep` / delay / debounce used for ordering, backpressure, or race avoidance
- a lock, mutex, or synchronization primitive
- a clamp, bounds check, or limit
- any check commented as "redundant", "defensive", "just in case", or "shouldn't happen"

"Weaken" includes relaxing a limit, shortening a timeout, narrowing a guard condition, and
demoting an error to a warning. The trigger is this action-class list — never "this code
looks surprising or load-bearing", which asks the agent to notice exactly what it is about
to miss.

## Triage first — silent no-op

Read `references/right-sizing.md` and `references/anti-triggers.md`. Stay silent on trivial
changes, renames that keep behavior, formatting, new feature work, and pure additions. Two
mode-specific silences: uncommitted or brand-new code has no history to recover, and a rename
of a defensive construct's variable is not a weakening.

## Procedure

1. **Pin the exact lines** being removed or weakened.
2. **Recover the line history**: `git log -L<start>,<end>:<file>` for the range's history, and
   `git blame -w -C <file>` (whitespace-insensitive, follows copies) when the range is fuzzy.
   Identify the commit(s) that INTRODUCED the construct, not just the last touch.
3. **Read the introducing commit** with `git show <sha>` — the full message and the diff
   context. Check the line history for a remove-and-reintroduce pattern: a construct that was
   deleted once and came back is the strongest possible keep signal.
4. **Follow linked references.** Extract issue/PR numbers and URLs from the message
   (`#123`, `Fixes …`). If the repo has a remote and `gh` is available, pull the discussion:
   `gh pr list --search <sha> --state merged`, `gh issue view <n>`, `gh pr view <n>`.
5. **Degrade honestly.** No remote, no `gh`, squashed or uninformative history ("wip",
   "fixes") → state exactly what could not be recovered and say the intent is unknown.
   **Never invent intent.** An unfollowable `#42` is reported as unfollowable, not paraphrased
   from imagination. The same rule covers background knowledge: a CVE, advisory, or issue you
   remember about this code but did not retrieve in this session is NOT evidence — either
   retrieve it (and cite the command that returned it) or present it as an explicitly
   unverified recollection ("I believe a related advisory exists; I could not verify it
   here"), never as fact.

## Output — the Chesterton's-fence report

Present, before the removal proceeds:

- **Evidence**: introducing commit sha, its message (quoted), the relevant diff context, and
  any linked issue/PR content actually retrieved.
- **The risk**: the concrete regression the construct was added to prevent, which its removal
  reopens.
- **A verdict**:
  - `safe-to-remove` — intent recovered and demonstrably obsolete (the failure mode can no
    longer occur), with the reasoning;
  - `remove-only-with-replacement` — the protected failure mode is real; name the safeguard
    or regression test that should land with the removal;
  - `stop-and-confirm` — intent unrecoverable or actively load-bearing; the user decides with
    the evidence in view.

This is a warning gate, not a blocker: if the user confirms, proceed with the removal.

## Handoff

If the evidence shows the construct guards real behavior and the removal proceeds anyway,
recommend running the `test-discipline` skill first (characterize mode) to pin the behavior
the construct protected — a red pin later beats a silent regression.

## Boundaries

- `/code-review` and `/simplify` run post-diff; this gate runs before the deletion lands. A
  "simplify this function" request that would strip a retry or clamp is exactly when it fires.
- New feature work belongs to feature-dev; pure additions have no history and are out of scope.
- `/verify` and `/run` confirm behavior after a change — downstream of this gate.

## Reference files

- `references/anti-triggers.md` — the shared should-NOT-fire surface. Read during triage.
- `references/right-sizing.md` — the one-question triage rule. Read during triage.
