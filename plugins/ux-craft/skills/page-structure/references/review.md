# Reviewing an existing page or app shell

Use this when the user asks to review, audit, or critique the structure of screens that already
exist. The output is a set of findings plus a blueprint for the fixed page. A review that only
reads code misses what renders. A review that only looks at screenshots misses dead branches and
data mislabels. Do both.

## 1. Scope one round

One round covers the app shell plus one page (or one flow), in every state that page has. Name
the states from the code: the data conditions that switch layouts (first run, empty, partial,
populated), the user's role, display or density modes, and variants such as tracing versus
dataset projects. Later pages are later rounds.

## 2. Gather the evidence

Read:

- the router config;
- the layout components (shell, sidebar, header, breadcrumb resolver);
- the page and the components it renders;
- `components/ui/button.tsx`, to learn which variant is filled (`shadcn.md`);
- `UX.md` and any product-language or design doc the project treats as authoritative.

Then render the page. Run the app locally and capture it at 1440×900 and 390×844 for each state
and display mode.

When the local data cannot reach a state, stub the data request. With Playwright, rewrite the
JSON in `page.route` to change only the fields that select the state. Say in the report that
those values are synthetic.

Render the loading, error, and signed-out states the same way: delay the request, return a 500,
return a 401.

## 3. Measure, do not eyeball

Take these checks from the rendered page:

| Check | How | Finding when |
|---|---|---|
| Horizontal overflow | `document.documentElement.scrollWidth > clientWidth` at 390 px | Any overflow |
| Clipped controls | A button whose box exceeds an `overflow: hidden` ancestor | Any clipped action, above all the primary |
| Filled buttons per state | Count visible elements styled as the filled variant | Not exactly one per state (zero is fine only when the state has no task) |
| Primary above the fold | The filled button's top edge versus the viewport height | The state's one task starts below the fold |
| Headings | `document.querySelectorAll("h1")` | Not exactly one `h1`, or its text is not the nav label |
| Document title | `document.title` on every route | Two routes share a title |
| Location | Active nav item, breadcrumb text, `h1`, document title | Any of the four disagree |
| Target size | Interactive elements smaller than 24×24 CSS px | Any, outside inline text links |

## 4. Read the code for what rendering cannot show

- **Dead branches.** A parent layout that renders its own loading or error UI while data is
  missing never mounts the page's loading or error branch. Delete those branches or move the
  state into the page.
- **Missing data shown as a value.** `?? 0` or `|| 0` on counts turns "not loaded" into "zero".
- **Mislabelled data.** Compare every label with the query or field behind it: a count labelled
  "this week" that has no time filter; a status printed as a raw enum.
- **Hardcoded diagnostics.** Fixed error strings shown regardless of the actual failure.
- **Breadcrumb resolution.** Prefix matching that lets `/a` shadow `/a/b`; routes with no crumb;
  crumbs that are not links.
- **Fixed grids and non-wrapping rows.** The patterns in `shadcn.md` › Responsive rules.
- **Repeated facts.** The same count or action offered in several zones of one page.
- **Vocabulary.** Run the `ui-naming` scanner when it is available. When it is not, grep for the
  glossary's rejected synonyms.

## 5. Write findings

Give each finding a stable ID (S1… for the shell, P1… for the page) and these fields:

- **Title**: the defect in one line, stated as fact ("The topbar shows numbers it does not have").
- **Severity** (NN/g scale):
  - **4** misstates data or blocks the page's job;
  - **3** is a likely wrong turn, a lost location, or a hidden or clipped primary action;
  - **2** slows, repeats, or muddles, and the user recovers;
  - **1** is cosmetic.
- **Evidence**: `file:line` plus the rendered measurement or screenshot state. Mark anything
  inferred rather than observed as an assumption.
- **Rule**: the reference and section it breaks (`archetypes.md` › Dashboard). No rule, no finding.
- **Proposal** and **status**:
  - *fix* when no product decision is needed;
  - *decide* when the user must choose;
  - *keep* for what holds up.

List what holds up as well; a review that only criticises cannot be trusted to have looked.

## 6. Deliver

In this order:

1. A top-findings table in fix order.
2. The shell findings, then the page findings.
3. The page's blueprint from `SKILL.md` steps 2–7, one per state where the layout changes.
4. Open questions, as the *decide* items.

Before handing off, re-open every cited `file:line` and check that it says what the finding
claims. When the user wants a record, write it where they say, or propose
`docs/ux-audit/<date>-<scope>.md`, and write it only after they agree.

Sources: NN/g, How to conduct a heuristic evaluation, and Severity ratings for usability problems;
WCAG 2.2 (2.4.2 Page titled, 1.3.1 Info and relationships, 2.5.8 Target size minimum); Hurff, the
UI stack.
