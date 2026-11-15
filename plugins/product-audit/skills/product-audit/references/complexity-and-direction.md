# Complexity and direction

Both checks are about the product as a whole. Both stay structural: they rest on counts and
paths the code shows, not on how a screen feels.

## Filling the Snapshot

Take the numbers before writing any finding, so the next audit can compare like with like.
Each is a whole number, or `n/a` when it cannot be measured for this kind of product. Write
`0` when the scan could have found the thing and found none.

| Measure | What to count |
|---|---|
| Screens, Endpoints, Commands, Data models, Packages | The scan's totals, corrected for anything you found by reading. Endpoints count one per method, as the scan lists them. |
| Settings and flags | Settings on settings screens (`settings`, which leaves out buttons), plus flag-like variables, preference keys, and command options a user is expected to set. |
| Integrations | Services in the scan's list. Note in the evidence any that no file imports. |
| Top-level destinations | Entries in the primary navigation: sidebar, tab bar, top menu, the first level of commands, or the main list a user picks from. |
| Steps to the core action | See below. |

Prefer the scan's number when the scan measures the right thing, so the next audit can
compare; count by hand when it does not. Either way the `Measured:` line under the table says
which numbers were translated or hand-counted, and how. For a collection of packages, the
destinations are the units a user chooses between, and first-time installation is not a step
to the core action unless every use repeats it.

**Steps to the core action.** The core action is the thing the promise says a returning user
does, not one-time setup: checking off a habit, not creating one. The first screen after
opening the product, signed in and past first run, is step 0. Each move to another screen is
one step. Completing the action on its screen (filling the form and submitting it) is one
step, however many fields it has. Opening on a home page, going to Today, then ticking and
saving is 2. Cite the files you walked.

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
- Surface the owner maintains that no user is offered: a second packaging, a parallel
  configuration, a compatibility layer nothing documents.

## What does not count

- Colour, spacing, typography, icons, wording, accessibility, performance.
- Code structure, naming, or duplication, except as evidence that one feature exists twice.
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

A finding has no decision column. The owner accepts it by leaving its move in Next moves, or
declines it; then end the Finding cell with `(declined by owner)` and do not raise it again
unless the evidence changes.

If none qualifies, write `None.` A product whose front door is short and whose menu matches
its promise has no findings.

## Direction verdicts

| Verdict | It holds when |
|---|---|
| `focused` | Core and supporting features are most of the product, recent work went mainly into them, and the purpose sources agree. |
| `drifting` | The promise is clear, but recent work or most new surface went into adjacent or off-promise features while the core stood still or stayed unfinished. |
| `split` | Two clusters of features each have their own core, their own data, and their own user or job, so one promise cannot cover both; or the purpose sources describe two products. |
| `undefined` | No source states a promise and the features do not point to one, or the only honest promise is a list of features. |

When two verdicts fit, give the one whose options the owner could act on, name the other, and
say what evidence would tip it. If two honest wordings of the promise would class a feature
differently, say which features depend on the wording.

Any verdict other than `focused` cites at least two of:

- **Class shares** from the Features table.
- **Recent effort**: the scan's `recent_commits`, each mapped to the feature its paths belong
  to ("5 of the last 7 commits went to the recipe planner"). `areas` gives the same picture by
  directory, but a commit touching several directories counts in each.
- **Growth**: what kind of surface arrived in the latest quarters.
- **Purpose sources** that disagree with each other or with the code.
- **Direction documents** promising something the code went away from.
- **An unfinished core** beside finished extras.
- **The owner's usage**, once they answer: the feature in daily use is not the core.

Work on plumbing is not drift: upgrades, refactors, sign-in, and deployment serve every
feature. A menu file edited only to add entries for new features is those features' work, not
plumbing. "Recent" ends at the newest commit, so give that date, and say so when it is months
old. When the history is shallow or missing, say that the effort evidence is partial.

## The choice

Unless the verdict is `focused`, give two or three options. Each is a path the owner could
really take, stated as what the product becomes and what follows from it:

- narrow to the promise, and park or cut the rest;
- change the promise to match what is used, and demote the old core;
- split into two products;
- for `undefined`: pick one user and one job, write the promise, and audit again.

Mark exactly one `(recommended)` and follow it with a one-line reason tied to the evidence.
With a `focused` verdict, write `None.` under The choice.

If critical-thinking is installed, the owner may hand the recommended option to it for a stress
test. If it is not, the recommendation stands as the audit's own reasoning.

## Ordering the next moves

Next is the single move that is right whichever option the owner picks. Finishing a core
feature users can reach unfinished usually qualifies; so does removing a dead placeholder. If
no move survives every option, Next is choosing the option. After that:

1. Settle the direction when it is not `focused`.
2. Park or cut the heaviest features that do not earn their keep.
3. Shorten the front door.
4. Gaps from the outside view, last.

A move may cite several ids, as `(F1, F2, X1)`. With nothing evidenced, write "Nothing
obvious; next is whatever you decide to build."
