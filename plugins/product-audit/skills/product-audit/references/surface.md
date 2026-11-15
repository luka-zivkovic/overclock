# Reading the scan and naming features

`product_audit.py scan` emits `product-audit-scan/v1` JSON. Every path is relative to the root.
Capped lists carry `items`, `total`, and `truncated`; a truncated list means "look further",
not "that is all". Environment files are never opened.

## What the scan reports

| Key | What it is | How to read it |
|---|---|---|
| `purpose_sources` | README title and opening statement, manifest descriptions, app manifests, page titles and meta descriptions | Raw material for the promise. An `opening` of null means the README never says what the product is. Disagreement between sources is Direction evidence. |
| `claimed_features` | Bullets under a Features-style README heading | What the product says it does. Compare with what the code carries, both ways. |
| `direction_documents` | Roadmaps, plans, ideas, backlogs found by name | What the owner meant to build next. Read them before judging direction. |
| `stack` | Frameworks recognized from manifests | Tells you which routing conventions the scan could follow. |
| `coverage` | Counts per kind and whether any convention was recognized | `recognized: false` means the lists below are empty because the scan could not see, not because nothing exists. |
| `surface.screens` | Destinations from file routing, router declarations, navigator registrations, and screen-named files | `route` is as written in the code; a nested router's child shows without its parent prefix. `linked_from` is how many other files name it; null means not measured (root, dynamic, or relative routes). |
| `surface.endpoints` | HTTP handlers, route files, server actions, RPC procedures, edge and cloud functions | In a server-rendered app these are the screens. Router prefixes set in another file are not applied. |
| `surface.commands` | Subcommands and installed executables | For a command-line product this is the feature list's skeleton. |
| `surface.data_models` | Tables, models, collections | Each feature usually owns at least one. Raw SQL tables are folded away when an ORM schema exists; the count is in `sql_tables_folded_into_orm_models`. |
| `surface.integrations` | Third-party services recognized from dependencies | Each is upkeep: keys, quotas, breaking changes, a bill. |
| `surface.navigation` | Files that name several in-app destinations | Where the menus live. Read the top ones to count top-level destinations. Computed links do not show. |
| `surface.settings` | Flag-like environment variables, persisted preference keys, command options, and settings screens with their control counts | The configuration a user or operator must understand. |
| `signals.unlinked_screens` | Screens no other file names | A lead: possibly a dead destination. Confirm before reporting. |
| `signals.unfinished_markers` | "Coming soon", "not implemented", placeholder text, with file and line | A lead: surface a user can reach that does nothing yet. |
| `signals.dense_ui_files` | UI files with the most interactive controls | Where a screen may be doing too much. A count, not a verdict. |
| `signals.usage_evidence` | Whether a product-analytics dependency is installed | If one is, the owner can get real numbers; ask for them. |
| `growth.by_quarter` | Screens, endpoints, commands, and models by the quarter their file first appeared, with commit counts | How the surface accreted. `shallow_history: true` means the clone is truncated and early quarters are wrong. |
| `areas` | Source directories with first-appearance date, total commits, commits inside the recent window, and size | Where the effort went. Compare recent commits per area with the class of the features living there. |
| `weight` | Source files and lines, dependency counts per manifest | The size of what is being carried. |

Dates and the recent window are measured from the newest commit, not from today, so the same
commit always scans the same. `added` is the day an item's file first appeared, carried across
renames. Several models in one schema file share that file's date, so read a model's arrival
from the feature's other files.

## From surface to features

- Name a feature the way a user would ask for it: "export my data as CSV", not `/api/export`
  or `ExportService`.
- One feature usually spans several kinds of surface: a screen or two, endpoints, a model, maybe
  an integration and some settings. Gather them under one row.
- Sign-in, account settings, billing plumbing, error pages, and navigation chrome are shared
  plumbing unless the product is about them. Give plumbing one `supporting` row per job, not
  one per file.
- Aim for five to thirty rows. More than that usually means rows are routes; regroup them.
- A feature that exists only in the README, a roadmap, or a "coming soon" label is not a
  feature. Note it under Direction as a promise the product does not keep.
- Record the first-appearance date and recent activity for each feature from its files. They
  feed the direction read; they are not verdicts.

## When the patterns do not fit

The scan follows common web, mobile, server, and command-line conventions. It does not see a
desktop app's windows, a game's scenes, a library's exported API, a plugin collection's
packages, a spreadsheet, or navigation computed at run time. When `coverage.recognized` is
false or the lists are clearly thin:

1. Read the entry points and whatever builds the first thing a user meets.
2. List what a user can see, invoke, or configure: windows and menus, public exports, packages,
   commands and flags, documented workflows.
3. Use `areas` and `growth` as before; they do not depend on the stack.
4. Leave snapshot counts you could not measure as `n/a`. Do not estimate them.

## What never counts as evidence

- Age by itself. A feature untouched for a year may be finished.
- A scan signal you did not confirm in the file. `unlinked_screens` misses links built from
  variables; `unfinished_markers` matches comments and error strings.
- A count alone. Fourteen toggles is a fact; "too many" needs the promise and the usage.
- README or roadmap claims about what users want. They are the owner's past intent.
- Your taste about naming, layout, or code structure.
- Anything you did not read in a file, hear from the owner, or fetch from a cited page.
