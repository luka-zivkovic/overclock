# The keep test

A feature earns its keep when what it adds to the promise is worth the surface it costs. Judge
each feature on three things, each from a short fixed scale, then read the verdict off the
table. Fixed anchors keep two audits of the same product comparable.

## Class: how it relates to the promise

Take the feature away in your head and read the promise again.

| Class | The test |
|---|---|
| `core` | The promise becomes false without it. |
| `supporting` | The promise still reads true, but a core feature stops working or cannot be reached: sign-in, sync, a setting the core reads, billing in a product that is sold. |
| `adjacent` | Same subject, same person, but the promise holds without it and no core feature depends on it. |
| `off-promise` | It serves a different job or a different person than the promise names. |

A promise needs few things to be true. If more than half the rows come out `core`, the rows
are being graded kindly: run the removal test again.

## Cost: what the feature alone carries

Count the signals the feature owns by itself:

1. its own top-level navigation entry, command group, or installable package;
2. three or more screens or commands;
3. its own data model, or a file it keeps in the user's project;
4. its own third-party integration or outside tool;
5. five or more settings, options, or flags a user is expected to set;
6. upkeep of its own that the files show: a bundled helper of several hundred lines, its own
   test or evaluation suite, or a release history that is mostly maintenance.

A signal every feature in the product has tells them apart no better than none: leave it out.
In a collection where each feature is its own package, signal 1 does not count.

| Cost | Anchor |
|---|---|
| `heavy` | two or more signals |
| `moderate` | exactly one signal |
| `light` | none; it lives inside surface that exists anyway |

Cost is a count, not a criticism. A heavy core is normal; cost only matters where the class
and usage leave the verdict open.

## Usage: who actually uses it

| Label | Meaning |
|---|---|
| `measured: <numbers and period>` | The owner reported analytics, row counts, or logs. |
| `owner: regular` / `owner: rare` / `owner: never` | The owner's statement about use, theirs or their users'. |
| `unknown` | Nobody has said. This is the label until the owner answers. |

When the owner is the only user, their own use is the whole picture. Usage is never inferred
from code age, commit counts, or how finished a feature looks. A dated trace of use found in
the repository, such as a ledger the feature writes or a recorded run, is a lead and not a
label: keep `unknown`, cite the trace, and put it in the question so the owner can confirm.

The audit does not gather usage itself. When the owner has no numbers, suggest the cheapest
evidence they could get: an analytics event count if a tool is installed, the number of rows in
the feature's own table, or simply when they last opened it.

## Verdict

| Class | regular, or measured in use | rare | never | unknown |
|---|---|---|---|---|
| `core` | `keep` | `keep`, plus a Direction finding | `keep`, plus a Direction finding | `keep` |
| `supporting` | `keep` | `keep` | `simplify`, or `merge` into what it supports | `keep` |
| `adjacent` | `keep`; `simplify` if heavy | `keep` if light, else `park` | `cut` | `keep` if light, else `park` |
| `off-promise` | `keep`, plus a Direction question | `park` | `cut` | `park` |

Then apply the modifiers:

- **`finish`** replaces `keep` when a core or supporting feature has a part a user can reach
  that does not do its job yet: a placeholder, a control with nothing behind it, a handler
  that discards what it is given. Whether working code is correct is a code review question
  and never a reason for `finish`. An unfinished adjacent or off-promise feature is `park`:
  take the placeholder out of the user's path until the owner says whether anyone is waiting
  for it.
- **`simplify`** replaces `keep` when the cost is out of proportion to the job. Name what
  shrinks: which options, steps, screens, or upkeep go.
- **`merge`** applies when two rows do one job for the user. Put `merge` on the row that goes
  and name the survivor in its Feature cell.
- A feature nothing leads to is already parked in effect. Write `park` and put the real
  question to the owner: bring it back, or cut it.

What the verdicts mean:

| Verdict | Meaning |
|---|---|
| `keep` | Earns its keep as it is. |
| `finish` | The promise depends on it and it is not done. Complete it before adding anything. |
| `simplify` | Keep the capability, shrink its surface. |
| `merge` | Fold it into the feature that does the same job. |
| `park` | Take it out of the user's path without deleting it: remove the menu entry, hide it behind a flag, move it out of the main list or the default install. Reversible, and a cheap test of whether anyone misses it. |
| `cut` | Remove it. Only with usage evidence, and only the owner decides. |

## What gets a row

- A settings screen is not a feature. Assign each setting to the feature it configures; it
  goes where that feature goes. Settings that belong to no feature get one row only when
  enough remain to matter, classed by whether the core reads them.
- Navigation, layout, and error pages are not features. What is wrong with them is a
  Complexity finding.
- A placeholder with its own screen, menu entry, or command gets a row. A claim that exists
  only as words (a README bullet, a roadmap line, a "coming soon" label inside another screen)
  does not: note it under Direction as a promise the product does not keep.

## Writing the rows

- **Evidence** is a few telling paths, not prose. Add the fact that set the cost when it is not
  obvious: `app/recipes/ (4 screens), prisma Recipe, openai`.
- **Verdict** is the audit's recommendation. It moves when usage evidence changes, and never
  to match a decision the owner made against it. **Decision** is the owner's choice, which may
  differ. A `keep` verdict is recorded `keep` / `audit`; everything else starts
  `pending` / `—`.
- Never soften a verdict to be agreeable, and never sharpen one to look decisive. The table
  decides; usage evidence moves it.
- A `park` that rests only on `unknown` usage is provisional. Say so wherever the verdicts are
  summarized, so a first audit does not read as "half of this should go".
