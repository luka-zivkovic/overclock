# Reading the scan and naming features

`product_audit.py scan` emits `product-audit-scan/v1` JSON. Every path is relative to the root.
Capped lists carry `items`, `total`, and `truncated`; a truncated list means "look further",
not "that is all". Environment files are never opened.

## What the scan reports

| Key | What it is | How to read it |
|---|---|---|
| `purpose_sources` | README title and opening statement, manifest and marketplace descriptions, app manifests, page titles | Raw material for the promise. An `opening` of null means the README never says what the product is. Disagreement between sources is Direction evidence. |
| `claimed_features` | Bullets under a Features-style README heading | What the product says it does. A README that lists features in a table or in prose shows nothing here; read it. |
| `direction_documents`, `release_notes` | Roadmaps, plans, backlogs, strategy notes, and changelogs found by name | What the owner meant to build, and when things shipped. Read them before judging direction. |
| `history` | Newest and oldest commit dates, commit counts, `shallow`, and `uncommitted` counts | `shallow: true` means early dates are wrong. Non-zero `uncommitted` means the tree you are reading is not the last commit; say so in the report. |
| `stack`, `coverage` | Frameworks recognized from manifests, and counts per kind | `recognized: false` means the lists are empty because the scan could not see, not because nothing exists. |
| `surface.screens` | Destinations from file routing, router declarations, navigator registrations, and screen-named files | `route` is as written in the code; a nested router's child shows without its parent prefix. `linked_from` is how many other files name the route or build a link into it; null means not measured. |
| `surface.endpoints` | HTTP handlers, route files, server actions, RPC procedures, edge and cloud functions, one row per method | In a server-rendered app these are the screens. Router prefixes set in another file are not applied. |
| `surface.commands` | Subcommands and installed executables a user types | For a command-line product this is the feature list's skeleton. A helper script bundled inside an agent skill is run by the agent, so its subcommands are left out. |
| `surface.data_models` | Tables, models, collections | Each feature usually owns at least one. Raw SQL tables are folded away when an ORM schema exists. |
| `surface.packages` | Workspace packages, plugins, and agent skills, each with its description | For a product made of installable units this is the feature list's skeleton. A skill names its `plugin`; `user_invoked` and `argument_hint` say how a user reaches it; `has_hooks` marks a plugin that runs something on its own. |
| `surface.integrations` | Third-party services recognized from dependencies | Each is upkeep: keys, quotas, breaking changes, a bill. `imported_by_files: 0` means declared and never imported; null means it could not be told. Services called from scripts or over HTTP do not show here. |
| `surface.navigation` | Files that name several in-app destinations | Where the menus live. Read the top ones to count top-level destinations. Computed links do not show. |
| `surface.settings` | Flag-like variables, environment variables with the file that reads them, preference keys, command options, and settings screens | On a settings screen, `settings` counts toggles, choices, and inputs; `total` also counts buttons. An empty `preference_keys` means none are stored under a recognizable key, not that there are no preferences. |
| `signals.unlinked_screens` | Static screens no other file names | A lead: possibly a dead destination. Dynamic routes are left out because their links often come from data; check a dynamic screen whose `linked_from` is 0 yourself. |
| `signals.unfinished_markers` | "Coming soon", "not implemented", placeholder text, with file and line | A lead, and text only. A handler that discards its input or a button with nothing behind it does not show; you find those by reading. |
| `signals.dense_ui_files` | UI files with the most interactive controls | Where a screen may be doing too much. A count, not a verdict. |
| `signals.usage_evidence` | Whether a product-analytics dependency is installed | If one is, the owner can get real numbers; ask for them. |
| `growth.by_quarter` | Screens, endpoints, commands, models, and packages by the quarter they arrived, with commit counts | How the surface accreted. |
| `recent_commits` | Each commit inside the recent window: date, subject, and the directories it touched | Map each commit to a feature to say where the work went. `more_places` means the list of directories is cut short. |
| `areas` | Directories with first-appearance date, total commits, commits inside the recent window, and size; top level first, then the product's own, then `non_product` ones | The same picture by directory. A commit touching several directories counts in each. |
| `weight` | Shipped source files and lines, dependency counts per manifest | The size of what is being carried. Tests, examples, documentation, and developer tooling are not counted. |

Dates come from git and are measured from the newest commit, not from today, so the same
commit always scans the same. The recent window is 180 days; pass `--window-days N` to the
scan when that is longer than the history or too coarse to show a shift. `added` is the day an
item's file first appeared, carried across renames. Items that share a file are dated by their
own defining line instead (`dated_by: line`) and carry no commit counts. Squashed or shallow
history makes git dates later than the real ones; prefer the release notes when they are dated.

## From surface to features

- Name a feature the way a user would ask for it: "export my data as CSV", not `/api/export`
  or `ExportService`.
- One feature usually spans several kinds of surface: a screen or two, endpoints, a model, maybe
  an integration and some settings. Gather them under one row.
- Sign-in, billing plumbing, and sync are shared plumbing unless the product is about them.
  Give each such job one `supporting` row, not one per file.
- Aim for five to thirty rows. More than that usually means rows are routes; regroup them.
- Record when each feature arrived and how recently it was worked on, from its files. Those
  feed the direction read; they are not verdicts.

## Products that are not apps

The scan follows common web, mobile, server, and command-line conventions, and lists packages,
plugins, and skills. It does not see a desktop app's windows, a game's scenes, a library's
exported API, a spreadsheet, or navigation computed at run time. When `coverage.recognized` is
false or the lists are clearly thin:

1. Read the entry points and whatever builds the first thing a user meets.
2. List what a user can see, invoke, or configure: windows and menus, public exports, packages,
   commands and flags, documented workflows.
3. Use `recent_commits`, `areas`, and `growth` as before; they do not depend on the stack.
4. Leave snapshot counts you could not measure as `n/a`. Do not estimate them.

For a collection of packages, plugins, or skills:

- The feature is the unit a user installs or invokes by itself. A package that only bundles
  others is not a row.
- One capability shipped in two packages is one feature plus a `merge` row for the duplicate.
- Count what the user pays, not what the agent or the build runs: a bundled helper's
  subcommands and flags are internals. What the feature writes into the user's project, what
  it runs unasked, and what outside tool it needs are its surface.
- The list a user chooses from (an install table, a registry) is the navigation.

## What never counts as evidence

- Age by itself. A feature untouched for a year may be finished.
- A scan signal you did not confirm in the file.
- A count alone. Thirteen settings is a fact; "too many" needs the promise and the usage.
- README or roadmap claims about what users want. They are the owner's past intent.
- Your taste about naming, layout, or code structure.
- Anything you did not read in a file, hear from the owner, or fetch from a cited page.
