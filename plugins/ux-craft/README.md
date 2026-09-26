# UX Craft

Three skills for the decisions that come before styling: how a page is structured, how a task
flows, and what things are called. Visual polish, colour, typography, and accessibility audits
are deliberately out of scope; use `impeccable`, `frontend-design`, or an accessibility auditor
for those.

| Skill | Ask it | It returns |
|---|---|---|
| `page-structure` | "structure the settings page", "what layout for the orders list" | A page blueprint: archetype, layout pattern, zones, action placement, hierarchy, states |
| `user-flow` | "design the flow for inviting a teammate", "how should checkout work" | A flow spec: steps, inputs, validation timing, confirm/undo, exits, post-submit, Mermaid diagram |
| `ui-naming` | "name the buttons on this page", "check our labels for drift", "build the glossary" | A proposal table, glossary entries, and a read-only drift report from `scan_labels.py` |

All three read `UX.md` at the project root first (platform, casing, button order, verb
vocabulary, glossary, flows) and fall back to cited literature defaults where it is silent.
`ui-naming` owns writing `UX.md`, on request only.

Install locally without the marketplace:

```sh
claude --plugin-dir plugins/ux-craft
```
