# UX decisions

Settled decisions for this application's interface. The `page-structure`, `user-flow`, and
`ui-naming` skills read this file before applying defaults; a decision recorded here is not
re-argued. Keep it short and factual; one line per decision. The label scanner reads the
Glossary, Casing, and Scanner sections directly.

## Platform

- Primary platform: web
- Frameworks and design system: React + shadcn/ui (Radix, Tailwind, lucide icons)
- Filled (primary) button variant: default (confirm in components/ui/button.tsx)
- Toasts: sonner · Confirmations: AlertDialog · Forms: react-hook-form + zod

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

The scanner reports every interface string that uses a rejected synonym. Separate synonyms with
commas. A parenthetical note, such as "(Technical view only)", is ignored by the scanner and kept
for people.

| Term | Meaning | Rejected synonyms |
|---|---|---|
| (term) | (one line) | (words not to use) |

## Flows

| Flow | Entry points | Steps | Landing |
|---|---|---|---|
| (name) | (where it starts) | (step names) | (where it ends) |

## Scanner

- Label props: (component props that carry interface text, e.g. eyebrow, subtitle)
- Exclude: (globs for generated or fixture files)
