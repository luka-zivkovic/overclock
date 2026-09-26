# Page archetypes and their default blueprints

Pick the archetype first; the default blueprint is the starting point users already expect
(Jakob's law: they spend most of their time on other products). Deviate only for a stated reason.

## List (collection, index)

Job: find one item, or act on several.

```
[ Breadcrumb / section nav                                     ]
[ Title            [secondary]  [ Primary: New <object> ]      ]
[ Search  Filters  Sort                     Bulk actions (hidden until selection) ]
[ Table or cards ................................................ ]
[ Pagination / load more                                        ]
```

- Table when users compare three or more attributes per item, or sort and filter on them;
  cards when items are visual or heterogeneous and comparison is secondary; a plain list when
  one attribute identifies the item.
- Row-level actions: one inline primary (open) and the rest in a row overflow menu. Opening a
  row is a link, so it works in a new tab.
- Search, filters, sort, and the page number live in the URL, so refresh, Back, and a shared
  link return the same view. The same holds for the active tab on a detail page.
- Bulk actions appear only after selection and replace, not crowd, the toolbar.
- Empty state carries the "New <object>" action and one line on what the list will hold.

## Detail (one object)

Job: understand one thing and act on it.

```
[ Breadcrumb: Section / Parent / This object                   ]
[ Title + status badge        [secondary] [ Primary action ]    ]
[ Key facts strip (3-5 attributes)                              ]
[ Main content sections (tabs if > 4 sections) | Aside: metadata, related, activity ]
[ Danger zone (separated, at the end)                           ]
```

- The primary action is the object's most common next step (Edit, Approve, Send), not Delete.
- Metadata and related items go in the aside; on narrow viewports the aside stacks below.
- Delete and other irreversible actions sit in a separated end zone or an overflow menu.

## Form (create or edit)

Job: provide information correctly, once.

```
[ Title: New <object> / Edit <object>                          ]
[ Single column of fields, grouped under short headings         ]
[   Label above field, help text below, error below that        ]
[ Advanced or optional group (collapsed)                        ]
[ [ Cancel ]  [ Primary: Save / Create <object> ]  (platform order, see placement.md) ]
```

- Single column, fields in the order a person would naturally answer.
- Labels above fields; placeholder text never carries required information.
- Required versus optional marking follows one policy per app, recorded in `UX.md`.
- Long forms with independent parts become a wizard (one thing per step) or grouped sections
  with a sticky action bar; never a two-column field grid.
- Errors: inline next to the field plus a summary at the top with focus moved to it; user input is
  preserved.

## Dashboard (overview)

Job: notice what needs attention, then go there.

```
[ Title + time range / scope selector                           ]
[ Headline metrics row (3-5 tiles, one dominant)                ]
[ Attention list: what needs action now                         ]
[ Charts / breakdowns grid                                      ]
```

- One dominant tile or list; a dashboard with eight equal tiles has no hierarchy.
- Every tile links to the page where the user acts on it.
- No primary action button unless the dashboard is also the launch point for one task. When it
  is, that one action sits in the top zone, never in the last card.
- Show each fact once. A count in a tile, a sentence, a table header, and a badge on one page is
  four chances to disagree.

## Settings

Job: change a preference and be sure it took.

```
[ Settings nav (sidebar or tabs if > 6 groups; single page with headings otherwise) ]
[ Group heading + one-line description                          ]
[   Setting row: label, control, help                            ]
[ Save behaviour: per-section Save, or auto-save with visible "Saved" state ]
[ Danger zone: delete account, reset (separated, last)          ]
```

- Group by user goal (Notifications, Security, Billing), not by internal module.
- Pick one save model per app: explicit Save per section, or auto-save with per-row confirmation.
  Never mix within a page.

## Wizard step (one thing per page)

Job: answer one question and move on.

```
[ Step context: "Step 2 of 4 · Payment" or a progress bar       ]
[ One question or one group of tightly related fields           ]
[ Help text for this step only                                  ]
[ [ Back ]                              [ Primary: Continue ]    ]
```

- Back never loses entered data.
- The final step is a review of everything entered with edit links, then a primary that names
  the outcome (Place order, Create workspace), not Finish.

## Empty or first-run

Job: understand what this area is for and take the first step.

```
[ Illustration or icon (optional)                               ]
[ One-line what this holds + one line why it is empty            ]
[ [ Primary: the first task ]                                   ]
[ Link to docs / import / example (optional, secondary)          ]
```

- One primary action, never a tour of features.

## App shell (the frame every page shares)

Job: always show where the user is and which scope they are in, and reach any destination in one
move.

```
[ Sidebar                    | Header: [≡] Project / Section / Page         [global action] ]
[  scope switcher (project)  |---------------------------------------------------------------]
[  nav groups → items        | h1 = nav label   · status badge          [page actions]        ]
[  …                         | page content (one max width per archetype)                     ]
[  account · theme · sign out|                                                                ]
```

- The location quartet agrees on every route: active nav item, breadcrumb current page, `h1`,
  and document title use the same words. A route with no nav entry (a detail page) shows its
  parent in the breadcrumb and highlights that parent in the nav.
- Scope that changes every page's data (workspace, project, environment) sits in the sidebar
  header or as a breadcrumb segment. Keep it out of a cluster of header stats and badges.
- Navigation is grouped by one scheme: user task or object type. Mixing sequence numbers with
  other groupings reads as a broken sequence. A qualifier every item in a group shares goes on
  the group, not on each item.
- The header carries location and at most one global action, such as "New …" or "Import …".
  Counts and stats belong on the pages that explain them. A display or density setting belongs
  in the account menu, next to theme, not as a pill that looks like a button.
- Account, theme, and sign out live together in the sidebar footer's user menu.
- Shell-level states are designed like any zone (`states.md`). Loading shows a skeleton, never
  zeros; signed-out returns to sign-in and keeps the route; a failed request says what failed.
- Narrow widths: the sidebar becomes a sheet behind a menu button; the header keeps the menu
  button and the breadcrumb on one row and drops stats first.

## Pages that change with state

Some pages switch archetype as the user's data grows: a dashboard that is a first-run checklist
on day 0, a provisional summary after the first import, and a full dashboard later.

- Write one blueprint per state and name the state that selects each.
- Keep the `h1` and the location the same in every state. The state goes in the eyebrow or the
  lead sentence ("New project · no runs yet").
- Each state has exactly one primary action. The next state's actions stay hidden until the
  state arrives.
- Tell a journey one way. If the nav, the page, and a checklist all show progress, they use the
  same step names and numbers. Keep a one-time setup sequence apart from an ongoing work loop,
  and never show two numbered sequences on one screen.
- A setup checklist leaves once it is complete, or collapses to a one-line receipt. Finished work
  must not keep the top of the page.
- A one-time secret, such as an API key shown once, is the first zone in its state at every
  width until it is saved or dismissed.

## Modal or drawer (sub-page)

Use for a short task that must not lose the parent's context: confirm, quick create, a single
field edit. The structure is a mini form: title naming the task, the fields, then Cancel and a
specific primary (Delete project, Invite). A modal with tabs or scrolling is a page.

Sources: NN/g visual hierarchy and empty-state guidance, GOV.UK question pages and form structure,
Material 3 and Apple HIG component guidance, Refactoring UI on hierarchy. See the planning record
in `docs/brainstorm/ux-skill-planning-2026-09-25.md` for the full citation list.
