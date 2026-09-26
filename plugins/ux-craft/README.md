# UX Craft

Three skills for the decisions that come before styling: how a page is structured, how a task
flows, and what things are called. They are tuned for React apps built with shadcn/ui (Radix,
Tailwind), and they name zones and decisions with shadcn components. Visual polish, colour,
typography, and accessibility audits beyond headings and page titles are deliberately out of
scope; use `impeccable`, `frontend-design`, or an accessibility auditor for those.

| Skill | Ask it | It returns |
|---|---|---|
| `page-structure` | "structure the settings page", "what layout for the orders list", "audit our dashboard and app layout" | A page blueprint (archetype, layout, zones, action placement, hierarchy, states); for an audit, measured findings with severity and `file:line` evidence, then the blueprint |
| `user-flow` | "design the flow for inviting a teammate", "how should the review queue work" | A flow spec: steps, inputs, validation timing, confirm/undo, exits, post-submit, Mermaid diagram |
| `ui-naming` | "name the buttons on this page", "check our labels for drift", "build the glossary" | A proposal table, glossary entries, and a read-only drift report from `scan_labels.py` |

All three read `UX.md` at the project root first (platform, casing, button order, verb
vocabulary, glossary, flows) and fall back to cited literature defaults where it is silent.
`ui-naming` owns writing `UX.md`, on request only. The scanner reads the glossary's rejected
synonyms, so the project's own vocabulary becomes a mechanical check. It also reads the retired
terms in a `CONCEPTS.md` kept by `project-vocabulary`, or in a `CONTEXT.md`, when either exists.

For projects that use only part of shadcn, the skills name each component as installed, to add,
or the project's own. Their default is to take dialogs, sheets, menus, tooltips, tabs, and
toasts from shadcn rather than build them by hand.

Install locally without the marketplace:

```sh
claude --plugin-dir plugins/ux-craft
```
