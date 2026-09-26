# The five states of a data zone

Every zone that shows data from somewhere else (a list, a chart, a detail, a search result) is
designed in five states (Hurff's UI stack). A blueprint that shows only the ideal state ships a
blank table with no next step.

| State | When | What it must contain |
|---|---|---|
| **Ideal** | Data is present and normal | The designed layout |
| **Empty** | Nothing exists yet, or a filter matched nothing | Why it is empty (first-time vs. no matches), one primary action (create the first item, or clear filters), one line on what will appear here. Never an unexplained blank. |
| **Loading** | Data is being fetched | Under ~1 s: nothing or a subtle indicator. 1–10 s: a skeleton in the shape of the ideal state (lists, cards) or a spinner for small regions. Over ~10 s: a progress indicator with an estimate and a way to leave. Buttons that triggered the load enter a disabled loading state. |
| **Partial** | Some data, not enough to look "right" (one row, one card, first week of a chart) | The ideal layout without the awkwardness: no chart with one point; a short list without pagination; an invitation to add more. |
| **Error** | The fetch or action failed | What failed in the user's words, what they can do (Retry, Go back), and the data that did load if any. Never colour-only; never a raw code as the whole message. Preserve user input on form errors. |

## Rules

- Empty states carry exactly one primary action and no feature tour (NN/g empty states).
- Skeletons for content whose shape is known; spinners for small, shape-unknown regions
  (NN/g skeleton screens).
- Response-time limits: 0.1 s feels instant, 1 s keeps the flow of thought, 10 s is the limit of
  attention; design feedback for each threshold (Nielsen response times; Doherty threshold at
  ~400 ms for interactive feedback).
- Any action that takes longer than a second confirms completion (inline saved state, a toast,
  or a change on the page). Silent success reads as failure.
- The states table in the blueprint lists these five per data zone. A zone whose states are
  "same as the list above" may say so once.
- A value that has not loaded is not zero. Show a skeleton or "—" until data arrives. `?? 0` on
  a count reports "nothing waiting" when the truth is "unknown".
- Decide which component owns each state. When a layout renders its own loading or error UI while
  data is missing, the page's loading and error branches never run. Keep the state in one place.
- In shadcn: `Skeleton` for loading shapes, `Spinner` inside the triggering `Button` (disabled,
  with "Saving…"), `Empty` for empty states, and `Alert variant="destructive"` with a Retry button
  for errors (`shadcn.md`).

Sources: Scott Hurff, the UI stack; NN/g on empty states, skeleton screens, progress
indicators, response-time limits, and visibility of system status; Laws of UX, Doherty threshold.
