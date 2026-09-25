# Action placement and platform conventions

Detect the platform from `UX.md`, the framework, or the user. Apply one platform's conventions
per app and never mix them. Where `UX.md` records a choice, it wins.

## Universal rules

- **One primary action per page.** Filled, dominant, named with a verb and object. A second
  filled button halves the impact of both (GOV.UK button guidance; Material 3 buttons).
- **Primary action position by archetype.** List and detail pages: header, trailing side (top
  right on left-to-right web). Forms and wizard steps: after the last field, in the action row.
  Modals: action row at the bottom.
- **Destructive actions are separated.** Not adjacent to the primary action, visually distinct,
  placed at the end of the page, in a danger zone, or behind an overflow menu. Consequential
  options next to benign ones cause slips (NN/g).
- **Confirmation or undo, not both by default.** Reversible destructive actions get undo
  (a toast with Undo). Irreversible ones get a confirmation that names the object and count
  ("Delete 3 files?") with a specific primary (Delete), never OK/Yes. Confirmations on
  repetitive actions train users to click through, so reserve them for non-routine actions.
- **Reach on touch.** Primary actions inside the lower and central thumb zone; destructive
  actions outside it; targets at least 24×24 CSS px (WCAG 2.2 target size), 44 pt on iOS and
  48 dp on Android.
- **Proximity carries meaning.** Field labels sit closer to their own field than to neighbours;
  related actions share a container; unrelated ones do not.

## Button order in an action row

| Platform | Order (left to right, LTR) | Alignment | Source |
|---|---|---|---|
| Web app, Apple-style, iOS, macOS | Cancel/secondary, then primary | Trailing (right) in dialogs and forms | Apple HIG Alerts and Buttons; NN/g OK-Cancel |
| Android, Material | Dismissive (Cancel), then confirming (primary) | Trailing (right) | Material 3 Dialogs |
| Windows desktop | Primary, then Cancel | Right-aligned row | Microsoft Win32 UX guide |
| GOV.UK-style public service forms | Primary first, secondary after | Left-aligned to the form | GOV.UK Design System Button |

Rule: follow the platform, record the choice in `UX.md` under Button order, and flag any screen
that deviates from the app's own recorded order. Do not argue the general question; NN/g's
answer is "be consistent with the platform".

## Cancel, Close, Back

- **Cancel** abandons a task with changes; **Close** dismisses something without pending
  changes; **Back** returns one step keeping data. Use the one that matches what happens
  (NN/g Cancel vs Close).
- A dialog with only one action needs only that action; do not add Cancel to an informational
  message.

## Header zone contents (list and detail pages, web)

Left: breadcrumb or section label above the page title, then the title (matching the navigation
label that led here). Right: secondary actions as outlined or text buttons, then the single
primary. Status badges sit beside the title, not beside the actions.

## Row and item actions

One inline action per row at most (usually open or the most common verb). The rest in a row
overflow menu. Bulk actions appear in the toolbar only once items are selected.

## Sticky action bars

Use when the form is longer than one screen and has a single Save. The bar shows only Cancel and
the primary, plus an unsaved-changes indicator. Do not put navigation in it.

Sources: Apple HIG (Alerts, Buttons, Writing), Material 3 (Buttons, Dialogs), Microsoft Win32
UX guide (Dialog Boxes, Command Buttons), GOV.UK Design System (Button), NN/g (OK-Cancel or
Cancel-OK?, Consequential options near benign options, Confirmation dialogs, Cancel vs Close,
Fitts's law), WCAG 2.2 target size minimum, Hoober on mobile grip and thumb zones.
