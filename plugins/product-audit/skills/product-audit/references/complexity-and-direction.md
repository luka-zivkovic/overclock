# Complexity and direction

Both checks are about the product as a whole. Both stay structural: they rest on counts and
paths the code shows, not on how a screen feels.

## Three measures first

Take these before writing any finding. They go in the Snapshot, so the next audit can compare.

- **Steps to the core action.** From opening the product, signed in and past first run, to
  finishing the main thing the promise names. Each screen change, required form, or required
  choice is one step. Cite the files you walked. Use `n/a` when the path cannot be traced
  from code.
- **Top-level destinations.** Entries in the primary navigation: sidebar, tab bar, top menu,
  or the first level of commands.
- **Settings and flags.** User-facing settings, flag-like variables, and command options.

## What counts as a complexity finding

- The core action sits behind more steps than an adjacent feature, or behind a screen it does
  not need.
- Navigation gives adjacent or off-promise features the same rank as the core.
- There are more top-level destinations than the core and supporting features need.
- Settings nobody would change from the default, settings that stand in for a decision the
  product avoided, or settings for features that are parked or cut.
- Two ways to do one thing: two entry points, two editors, two export paths.
- Modes or roles that multiply every screen.
- A concept a user must learn that exists for one feature only.
- Surface a user can reach that does nothing yet: a "coming soon" page, a placeholder, a
  permanently disabled control.
- One screen with far more controls than the rest, mixing controls from several features.

## What does not count

- Colour, spacing, typography, icons, wording, accessibility, performance.
- Code structure, naming, or duplication.
- "It feels cluttered" with no count behind it.
- Anything that needs the rendered screen, unless the owner supplied a screenshot; then cite
  the screenshot.

Those belong to a design or code review. Say so once in the chat report if they seem to
matter; do not review them here.

## Writing a finding

At most five, ranked by how much of the core path each one touches. Each row needs:

- **Finding**: one plain sentence.
- **Evidence**: the paths and the count that support it.
- **Simpler**: the smaller shape, stated as what is removed, merged, or demoted, and what the
  user gives up, if anything.

If none qualifies, write `None.` A product whose front door is short and whose menu matches
its promise has no findings.

## Direction verdicts

| Verdict | It holds when |
|---|---|
| `focused` | Core and supporting features are most of the product, recent work went mainly into them, and the purpose sources agree. |
| `drifting` | The promise is clear, but recent work or most new surface went into adjacent or off-promise features while the core stood still or stayed unfinished. |
| `split` | Two clusters of features each have their own core, their own data, and their own user or job, so one promise cannot cover both; or the purpose sources describe two products. |
| `undefined` | No source states a promise and the features do not point to one, or the only honest promise is a list of features. |

Any verdict other than `focused` cites at least two of:

- **Class shares** from the Features table.
- **Recent effort**: commits inside the recent window, by `areas`, mapped to the features that
  live there ("31 of the last 40 commits touched the recipe planner").
- **Growth**: what kind of surface arrived in the latest quarters.
- **Purpose sources** that disagree with each other or with the code.
- **Direction documents** promising something the code went away from.
- **An unfinished core** beside finished extras.
- **The owner's usage**, once they answer: the feature in daily use is not the core.

Work on plumbing is not drift: upgrades, refactors, sign-in, and deployment serve every
feature. When the history is shallow or missing, say that the effort evidence is partial.

## The choice

Unless the verdict is `focused`, give two or three options. Each is a path the owner could
really take, stated as what the product becomes and what follows from it:

- narrow to the promise, and park or cut the rest;
- change the promise to match what is used, and demote the old core;
- split into two products;
- for `undefined`: pick one user and one job, write the promise, and audit again.

Mark exactly one `(recommended)` with a one-line reason tied to the evidence. With a `focused`
verdict, write `None.` under The choice.

If critical-thinking is installed, the owner may hand the recommended option to it for a stress
test. If it is not, the recommendation stands as the audit's own reasoning.

## Ordering the next moves

1. Finish a core feature that users can reach unfinished.
2. Settle the direction when it is not `focused`; every later move depends on it.
3. Park or cut the heaviest features that do not earn their keep.
4. Shorten the front door.
5. Gaps from the outside view, last.

Next holds the single move that removes the most weight or risk and needs no further
decision. With nothing evidenced, write "Nothing obvious; next is whatever you decide to
build."
