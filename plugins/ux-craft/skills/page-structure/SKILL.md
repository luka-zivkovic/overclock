---
name: page-structure
description: "Decide how one application page, screen, or the app shell is structured before it is styled, or review the structure of one that exists: its archetype (list, detail, form, dashboard, settings, wizard step, empty state, app shell), layout pattern, zones, where the primary and destructive actions sit, visual hierarchy, the empty/loading/error states, and how it stacks on phones. Tuned for React + shadcn/ui apps. Use when the user asks how to structure, lay out, organize, or arrange a page, screen, panel, or modal, says 'what layout should this be', 'where should this button go', 'this page feels cluttered', asks to audit or review an existing page's or the app's layout ('audit the dashboard', 'review our app layout'), or is about to build a new page and has not decided its shape. Do NOT use for colour, typography, spacing values, animation, or visual polish (that is styling work), for a single element's wording (ui-naming), for multi-screen sequencing (user-flow), for marketing or landing pages, or for a page whose structure the user has already specified and just wants implemented."
argument-hint: "[page or screen] [--platform web|ios|android|desktop]"
---

# Page structure

Think in **zones**. A page is a job plus a handful of zones that serve it; almost every
structural problem is a zone doing two jobs, a zone missing, or the primary action outside the
zone where the user looks for it. Decide the zones before any styling, and produce a blueprint
the user can implement or hand back to you to build.

This is a structural pass. It does not choose colours, type, or spacing values, and it does not
implement unless the user asks for that after the blueprint. If the request is outside the
description, answer it plainly without this procedure.

## 0. Read what the project already decided

If `UX.md` exists at the project root, read it first. Its Platform, Button order, and Flows
sections override every default below; a page that belongs to a named flow inherits that flow's
step context. If a design system, `DESIGN.md`, or component library is present, its components
are the vocabulary for the blueprint. Without either, assume a web application and say so.

When the project has `components.json` or `components/ui/`, it is a shadcn/ui app. Read
`references/shadcn.md`: it maps each zone to shadcn components, gives the Tailwind responsive
rules, and explains why a stock `CardTitle` is not a heading. Then open
`components/ui/button.tsx` and note which variant is the filled one. Projects rename variants,
and counting the wrong variant miscounts every page's primary action.

If the user asks to review or audit screens that already exist, follow `references/review.md`
instead of writing a blank-slate blueprint. It holds the render-and-measure checks, the
code-only checks (dead state branches, missing data shown as zero, mislabelled counts), and the
finding format. Its deliverable ends with this skill's blueprint for the fixed page.

## 1. Name the page's job

Write one line: "On this page the user **[does X]** so that **[Y]**." One page, one job. If the
line needs "and", the page is two pages or a page with a secondary zone, and the blueprint
must say which.

Then pick the archetype from `references/archetypes.md`; it holds the default blueprint for each
archetype (list, detail, form, dashboard, settings, wizard step, empty or first-run, app shell),
and skipping it produces layouts invented per page instead of the pattern users already know.
State the archetype and, if the page blends two, which one leads.

If the page changes with the user's state (a day-0 checklist that becomes a dashboard), name the
states from the data conditions that switch them and follow `archetypes.md` › Pages that change
with state. Each state gets its own blueprint under one stable title.

## 2. Inventory everything the page must carry

List each element, then classify it:

- **Primary action**: exactly one per page. The verb the job line names.
- **Secondary actions**: support the job; visible but subordinate.
- **Destructive or irreversible actions**: delete, cancel subscription, revoke.
- **Primary content**: what the user came to see or edit.
- **Supporting content**: context, metadata, help.
- **Navigation and location**: where the user is and how they leave.
- **Status and feedback**: saved state, progress, errors.

Cut before arranging. Anything that does not serve the job line moves to another page or behind
progressive disclosure (an Advanced section, an overflow menu, a drawer). The primary path never
hides behind disclosure. When the inventory has more than seven top-level choices in one zone,
group them; a menu of twelve peers is a search problem, not a menu.

## 3. Choose the layout pattern

Read `references/layouts.md` before choosing; it is the pattern catalog with the conditions each
pattern needs and the conditions that rule it out. Choosing from memory tends to yield a
two-column sidebar for everything. Decide:

- the pattern (single column, centered narrow, sidebar, master–detail, card grid, table page,
  dashboard grid, tabbed sections, wizard step, full-screen focus);
- the content shape that justified it (how many items, how many attributes compared, whether
  items are homogeneous, whether the user edits or reads);
- how it collapses on a narrow viewport (which zone stacks first, which controls move to a
  sheet or menu). In Tailwind that means a single-column base with breakpoints that add columns,
  and action rows that wrap (`shadcn.md` › Responsive rules). A three-column grid with no base
  style clips its buttons at 390 px.

## 4. Assign zones and place actions

Fill a zone table: zone, contents, why. Every element from step 2 lands in exactly one zone.

Placement follows `references/placement.md`, which holds the per-platform rules for primary
action position, button order, destructive separation, and mobile reach; placing actions without
it mixes conventions that users read as inconsistency. The rules that hold everywhere:

- The primary action sits where the eye ends after reading the page's purpose: the header for
  list and detail pages, the end of the form for forms, the end of the step for wizards.
- One filled, dominant button per page. Secondary actions are lighter, not the primary heavier.
- Destructive actions are never adjacent to the primary action. They live in a separated zone
  (a danger section, an overflow menu, the far side of an action bar) and read as different.
- Related controls share a container; a label sits closer to its own field than to the next
  field; identical-looking controls behave identically.
- Location is visible: the active nav item, the breadcrumb's current page, the page's single
  `h1`, and the document title use the same words, so the user can always see where this page
  sits.

## 5. Set the hierarchy

Name the single most dominant element (usually the page title or the primary content) and the
order in which the eye should move. Front-load headings and list items with the words that
carry meaning; users scan the first two words. Everything not in that order is quieter.

## 6. Design the states

For every zone that shows data, define the five states from `references/states.md` (ideal,
empty, loading, partial, error); it also carries the rules for what an empty state must contain
and when to use a skeleton versus a spinner. A blueprint without states ships an empty table with
no next step.

## 7. Deliver the blueprint

Return, in this order:

1. The job line and archetype.
2. An ASCII wireframe of the desktop layout and, if it differs, the narrow layout.
3. The zone table (zone, contents, why).
4. Placement decisions with the rule that justified each, citing the reference file section.
5. The states table (zone, empty, loading, partial, error).
6. Open questions: anything you assumed that the user should confirm, in one short block.

Completion check:

- the wireframe shows every element from the inventory once;
- exactly one primary action appears per state;
- the narrow layout keeps that action fully visible;
- the location quartet agrees;
- every data zone has all five states;
- no rule is asserted without a reference section behind it.

If the user then asks you to build it, implement the blueprint with the project's existing
components and keep the zone names as component or section names.

## Handoffs

- Styling, colour, typography, spacing rhythm, motion: stop at the blueprint and say the visual
  pass is separate. If `impeccable` or `frontend-design` is available, name it as the next step.
- The wording of labels and buttons in the blueprint: use whatever `UX.md` records; if it is
  silent, use plain verb-plus-object placeholders and suggest `ui-naming` for the pass.
- If the page turns out to be one step of a task with several screens, produce this page's
  blueprint and suggest `user-flow` for the sequence.
