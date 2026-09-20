# Apply mode contract

Apply works the checklist in `UNTANGLE.md` one item at a time. The user may not be a developer,
so every step is visible, verified, and reversible.

## Preconditions

- The plan exists, passes `plan check`, and has no `pending` decisions.
- The working tree is clean apart from the plan file itself. `plan next` enforces this and
  returns exit 2 with the dirty paths otherwise. Tell the user which files are uncommitted and
  stop. Do not stash, reset, or commit for them.
- The project is a git repository. Without git there is no way to revert a step, so apply stops.

## One item per pass

1. Run `plan next`. It returns the first unchecked item with its `paths` and `verify` text.
2. Show the item in plain language and confirm before touching anything.
3. Make the change. Touch only the listed paths. A "park" item moves the thread to the plan's
   named archive location; a "delete" item removes exactly the listed paths; a hygiene item
   edits exactly the listed files. If the change needs a path the item does not name, stop and
   propose a plan edit instead of improvising.
4. Run the item's verification and show the output. A failed verification means the item is
   not done: revert what you changed with `git checkout -- <paths>` or by removing new files,
   report it, and stop.
5. Tick the item with `plan tick`, recording what changed and what proved it.
6. Print the commit command for this item, for example:

   ```text
   git add -A && git commit -m "untangle C2: delete the AI summarizer experiment"
   ```

   Do not run it. Stop until the user says to continue. If they ask you to keep going without
   committing, warn once that the next preflight will refuse a dirty tree, then stop.

## Items that need a partner

- An item that deletes or weakens a guard, retry, lock, or bounds check inside kept code should
  first go through git-archaeologist when it is installed. Without it, say the history was not
  checked and let the user decide.
- The final "review the spine" item hands off to the host's code review tool. Without one, mark
  the item as a scope stop and leave it unchecked.

## Never

- `git commit`, `git push`, `git reset`, `git stash`, branch changes, or history rewrites.
- Deleting or moving anything outside the item's paths.
- Ticking an item whose verification did not run or did not pass.
- Editing the plan by hand during apply beyond what `plan tick` writes. Decision changes go
  back through survey.
