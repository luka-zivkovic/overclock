# The five states of a data zone

Every zone that shows data from somewhere else (a list, a chart, a detail, a search result) is
designed in five states (Hurff's UI stack). A blueprint that shows only the ideal state ships a
blank table with no next step.

| State | When | What it must contain |
|---|---|---|
| **Ideal** | Data is present and normal | The designed layout |
| **Empty** | Nothing exists yet, a filter matched nothing, or everything is done | Which empty it is (below), one primary action, and one line on what will appear here. Never an unexplained blank. |
| **Loading** | Data is being fetched | Under ~1 s: nothing or a subtle indicator. 1–10 s: a skeleton in the shape of the ideal state (lists, cards) or a spinner for small regions. Over ~10 s: say what is still loading, with an estimate if known and a way to leave. Buttons that triggered the load enter a disabled loading state. |
| **Partial** | Some data, not enough to look "right" (one row, one card, first week of a chart) | The ideal layout without the awkwardness: no chart with one point; a short list without pagination; an invitation to add more. |
| **Error** | The fetch or action failed | What failed in the user's words, what they can do, and the data that did load if any. Never colour-only; never a raw code as the whole message. Preserve user input on form errors. |

## Three kinds of empty

- **First use:** nothing exists yet. Say what the zone will hold and offer the action that
  creates the first item.
- **No matches:** a search or filter matched nothing. Echo the query or filters and offer
  Clear filters.
- **All done:** the user cleared the queue or finished the list. Say so plainly and offer the
  next useful place. This is an outcome, not an absence.

A failed load is none of these. Rendering an error as "No items yet" tells the user there is
nothing when the truth is unknown.

## Rules

- Empty states carry exactly one primary action and no feature tour (NN/g empty states).
- Skeletons for content whose shape is known; spinners for small, shape-unknown regions
  (NN/g skeleton screens).
- Response-time limits: 0.1 s feels instant, 1 s keeps the flow of thought, and 10 s is the
  limit of attention. Design feedback for each threshold (Nielsen, response times). Doherty and
  Thadani (1982) measured productivity rising as response time fell from seconds to 0.3 s and
  below. The widely quoted "400 ms Doherty threshold" does not appear in their paper.
- Every wait ends. Each request gets a timeout. Past about 10 seconds the zone says what it is
  still waiting on, and at the timeout it becomes the error state. A spinner that can run
  forever reads as a hang.
- Any action that takes longer than a second confirms completion (inline saved state, a toast,
  or a change on the page). Silent success reads as failure.
- Show an error where it happened. A field error sits by the field. A section error sits inside
  that section with Retry while the rest of the page keeps working. A page error replaces the
  page's content and keeps the header and navigation. An account or connection problem is a
  banner above every page until it clears.
- Offer Retry only when retrying can work. When the cause needs the user (signed out, no
  permission, missing setup), offer the action that fixes it instead: Sign in, Open settings,
  or who to ask.
- Design for edge content, not just the five states. Each data zone survives a 200-character
  name, missing optional fields, and both one row and ten thousand rows. Truncate with the full
  text available, show "—" for a missing value, and paginate or virtualize long lists.
- The states table in the blueprint lists these five per data zone. A zone whose states are
  "same as the list above" may say so once.
- A value that has not loaded is not zero. Show a skeleton or "—" until data arrives. `?? 0` on
  a count reports "nothing waiting" when the truth is "unknown".
- Decide which component owns each state. When a layout renders its own loading or error UI while
  data is missing, the page's loading and error branches never run. Keep the state in one place.
- In shadcn: `Skeleton` for loading shapes, `Spinner` inside the triggering `Button` (disabled,
  with "Saving…"), `Empty` for empty states, and `Alert variant="destructive"` with a Retry button
  for errors. Use the project's own components where it has them (`shadcn.md` › Take inventory
  first).

Sources: Scott Hurff, the UI stack; NN/g on empty states, skeleton screens, progress
indicators, response-time limits, visibility of system status, and error-message guidelines;
Doherty and Thadani, "The Economic Value of Rapid Response Time" (IBM, 1982); Open Design's
state-coverage craft rules and run-error design (nexu-io/open-design).
