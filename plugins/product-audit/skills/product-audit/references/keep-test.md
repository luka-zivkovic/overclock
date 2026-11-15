# The keep test

A feature earns its keep when what it adds to the promise is worth the surface it costs. Judge
each feature on three things, each from a short fixed scale, then read the verdict off the
table. Fixed anchors keep two audits of the same product comparable.

## Class: how it relates to the promise

Take the feature away in your head and read the promise again.

| Class | The test |
|---|---|
| `core` | The promise becomes false without it. |
| `supporting` | The promise still reads true, but a core feature stops working or cannot be reached: sign-in, sync, the settings the core needs, billing in a product that is sold. |
| `adjacent` | Same subject, same person, but the promise holds without it and no core feature depends on it. |
| `off-promise` | It serves a different job or a different person than the promise names. |

A promise needs few things to be true. If more than half the rows come out `core`, the rows
are being graded kindly: run the removal test again.

## Cost: what the feature alone carries

Count the signals the feature owns by itself:

1. its own top-level navigation entry or command group;
2. three or more screens or commands;
3. its own data model;
4. its own third-party integration;
5. five or more settings, options, or flags.

| Cost | Anchor |
|---|---|
| `heavy` | two or more signals |
| `moderate` | exactly one signal |
| `light` | none; it lives inside surface that exists anyway |

## Usage: who actually uses it

| Label | Meaning |
|---|---|
| `measured: <numbers and period>` | The owner reported analytics, row counts, or logs. |
| `owner: regular` / `owner: rare` / `owner: never` | The owner's statement about use, theirs or their users'. |
| `unknown` | Nobody has said. This is the label until the owner answers. |

When the owner is the only user, their own use is the whole picture. Usage is never inferred
from code age, commit counts, or how finished a feature looks.

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

- **`finish`** replaces `keep` when a core or supporting feature has unfinished parts a user
  can reach. An unfinished adjacent or off-promise feature is `park`: take the placeholder out
  of the user's path until the owner says whether anyone is waiting for it.
- **`simplify`** replaces `keep` when the cost is out of proportion to the job. Name what
  shrinks: which options, steps, or screens go.
- **`merge`** applies when two rows do one job for the user. Put `merge` on the row that goes
  and name the survivor in its Feature cell.

What the verdicts mean:

| Verdict | Meaning |
|---|---|
| `keep` | Earns its keep as it is. |
| `finish` | The promise depends on it and it is not done. Complete it before adding anything. |
| `simplify` | Keep the capability, shrink its surface. |
| `merge` | Fold it into the feature that does the same job. |
| `park` | Take it out of the user's path without deleting it: remove the menu entry, hide it behind a flag. Reversible, and a cheap test of whether anyone misses it. |
| `cut` | Remove it. Only with usage evidence, and only the owner decides. |

## Writing the rows

- **Evidence** is a few telling paths, not prose. Add the fact that set the cost when it is not
  obvious: `app/recipes/ (4 screens), prisma Recipe, openai`.
- **Verdict** is the audit's recommendation and never changes after the owner answers.
  **Decision** is the owner's choice, which may differ. A `keep` verdict is recorded
  `keep` / `audit`; everything else starts `pending` / `—`.
- Never soften a verdict to be agreeable, and never sharpen one to look decisive. The table
  decides; usage evidence moves it.
