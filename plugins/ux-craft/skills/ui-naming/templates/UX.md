# UX decisions

Settled decisions for this application's interface. The `page-structure`, `user-flow`, and
`ui-naming` skills read this file before applying defaults; a decision recorded here is not
re-argued. Keep it short and factual; one line per decision.

## Platform

- Primary platform: web
- Frameworks and design system: (fill in)
- Component library: (fill in)

## Casing

- Labels, buttons, headings: sentence case
- Product and feature names: as branded

## Button order

- Action rows and dialogs: Cancel, then primary (trailing/right)
- Forms: primary after the last field, same order

## Save model

- Forms: explicit Save per page; unsaved-changes guard on Cancel
- Settings: (explicit per section | auto-save with per-row Saved)

## Verb vocabulary

| Verb | Means | Not |
|---|---|---|
| Create | Make a new object from nothing | Add, New (except as a label prefix: "New project") |
| Add | Attach an existing object to a container | Create |
| Delete | Permanently remove | Remove, Trash |
| Remove | Detach from a container; the object still exists | Delete |
| Save | Persist changes | Apply, Update, Submit |
| Edit | Open something for changes | Modify, Change |
| Cancel | Abandon the task with changes | Close, Back |
| Close | Dismiss with nothing pending | Cancel |

## Glossary

| Term | Meaning | Rejected synonyms |
|---|---|---|
| (term) | (one line) | (words not to use) |

## Flows

| Flow | Entry points | Steps | Landing |
|---|---|---|---|
| (name) | (where it starts) | (step names) | (where it ends) |
