# Layout pattern catalog

Choose by content shape and the user's activity, not by habit. Each pattern lists what it needs
and what rules it out. When two patterns fit, prefer the simpler one.

| Pattern | Use when | Rules it out | Narrow viewport |
|---|---|---|---|
| **Single column** | Forms; reading; any page where order matters and the user works top to bottom | Content the user must compare side by side | Already narrow-safe |
| **Centered narrow** (max ~640px) | Sign-in, sign-up, short forms, confirmations, one-question wizard steps | More than one group of fields; tables | Full width with same order |
| **Sidebar + content** | Section navigation with more than six destinations; settings with many groups; docs | Fewer than four destinations (use tabs or a single page); mobile-first products where the sidebar would always be a drawer | Sidebar becomes a top select or drawer; content first |
| **Master–detail (split)** | Browsing many items while keeping one open: inbox, conversations, file browser | Items that need the full width to be understood; fewer than ~10 items | Two screens: list, then detail with Back |
| **Table page** | Lists where users compare three or more attributes, sort, filter, or select many | Items that are mostly images; fewer than ~5 items with one attribute | Cards or a stacked key-value list; keep sort and filter as a sheet |
| **Card grid** | Homogeneous visual items (projects, templates, media) where recognition beats comparison | Attribute-heavy comparison (use a table); text-only items | One or two columns |
| **Dashboard grid** | Overview pages with metric tiles, an attention list, and charts | Task pages; anything with a primary form | Tiles stack in priority order |
| **Tabbed sections** | A detail page with more than four sections of independent content | Sections the user must see together; fewer than three sections | Tabs stay, scroll horizontally, or become an accordion |
| **Wizard step** | Multi-step tasks, high stakes, or dependent steps (later questions depend on earlier answers) | Short forms (fewer than ~6 fields) that fit one screen | Same |
| **Full-screen focus** | Editors, composers, players: one task, distractions removed | Anything needing navigation while working | Same |
| **Two-pane editor + preview** | Content where the result differs from the input (markdown, code, email templates) | Plain forms | Toggle between edit and preview |

## Decision rules

1. **Order matters → single column.** Forms are single column. A two-column field grid makes the
   reading order ambiguous and doubles the scan cost (Wroblewski; NN/g form usability).
2. **Compare → table. Recognize → cards. Identify → list.** Count the attributes a user weighs
   before choosing an item. Three or more: table. One, and the item is visual: cards. One, and
   it is a name: plain list.
3. **Keep context → master–detail or drawer.** If the user opens many items in a session and
   returns to the list each time, keep the list visible. If they open one and leave, a full
   detail page is clearer and gives the detail its own URL.
4. **Six or more navigation destinations → sidebar.** Fewer: tabs or a single page with
   headings. Pure counts are a starting point; group first, then count groups.
5. **More than one screenful of independent form groups → wizard or sectioned form with a sticky
   action bar.** Decide by dependency: if later groups depend on earlier answers, wizard; if the
   groups are independent and the user may edit any, sectioned form.
6. **Dashboards are not task pages.** If the page has a primary action that creates or edits, it
   is a list or a form with a summary strip, not a dashboard.
7. **Narrow first.** Decide the stacking order at the same time as the desktop layout. The zone
   that serves the job stacks first; navigation and metadata move to a drawer, select, or below.

## Grid and reading order

- Western readers scan in an F pattern on text-heavy pages and a Z pattern on sparse pages: the
  top-left carries identity and location, the top-right carries the primary action on web list
  and detail pages, and the eye returns to the left edge for each row.
- Keep one consistent content max-width per archetype across the app; a settings page that is
  narrower than the list page reads as a different product.

Sources: NN/g F-shaped pattern, visual hierarchy, and table/list guidance; Wroblewski, Web Form
Design; GOV.UK Service Manual on form structure; Material 3 layout guidance; Refactoring UI.
