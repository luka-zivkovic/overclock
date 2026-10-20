---
name: ux-laws
description: "Apply twenty named UX laws (Hick, Fitts, Jakob, Miller, Doherty, proximity, similarity, common region, visual hierarchy, progressive disclosure, recognition over recall, Von Restorff, peak-end, goal-gradient, serial position, Tesler, Postel, Occam, feedback loops, aesthetic-usability) to one screen, view, component, or user flow. Use only when the user explicitly invokes ux-laws. Build mode designs and implements a view with the laws as decision rules and reports the decisions that changed. Review mode audits an existing view from its code and, when the app runs, its rendered states, and reports at most five ranked findings with file:line evidence and concrete fixes. Do not invoke automatically, and do not use for backend, API, CLI, or data work, brand or visual identity, copy-only edits, or a formal WCAG conformance audit."
argument-hint: "[build|review] <route, file, component, or description>"
disable-model-invocation: true
---

# UX Laws

The laws of UX are heuristics from perception and cognitive psychology. Use them as decision
rules for one screen at a time. Each law you cite must change a decision or expose a real problem
on this screen; a tour of all twenty is a failed result.

## Modes

- `build`: the user wants a new view or a change to one. Design with the laws, implement, report.
- `review`: the user points at an existing view. Read-only. Report findings.
- No mode given: `review` when the target already exists and the user asks how it is; `build`
  when they ask for something new or changed. If it is still ambiguous, ask once.

## Scope first

- One screen, view, component, or flow per run. If the user names a whole app, take the screen on
  its main path (the one a new user must get through), say which one you chose, and offer the next
  at the end.
- A one-line tweak (rename a label, nudge a color) gets the tweak and at most one sentence naming a
  law, if one applies. No full pass.
- No user-facing interface in scope (backend, API, CLI output, data pipeline): say so and stop.
- Copy-only, brand or visual identity, or WCAG conformance requests: say this skill covers
  interaction and layout, apply only the laws that fit, and leave the rest out of scope.

## 1. Frame the screen

Before applying any law, establish from code, routes, product docs (`PRODUCT.md`, `README`, design
notes), and the running app:

- who arrives here, from where, and how often (first visit or daily use);
- the screen's one job and its primary action. If you cannot name a single primary action, that is
  already a finding;
- what the user expects to happen after that action.

Mark anything you assumed. Never invent product facts or user research.

## 2. Look at it

- Read the view's code: route, component tree, every state it renders (loading, empty, error,
  success, disabled), the handler behind each action, and the components and tokens the project
  already uses.
- If the app can run locally, render the view and screenshot it at about 1280px and 390px wide,
  plus every state you can reach (empty, error, after submit, a long list). If it cannot run, work
  from code and say the review is code-only.
- Force the states the app will not show on its own. Intercept or stub the view's requests (for
  example with a browser automation route) to return an error, an empty result, one failure among
  several requests, and a slow response. For every state in the state checklist in
  [references/laws.md](references/laws.md), know whether you saw it, read it from code, or did not
  check it. A state you did not check is unknown, not fine.
- The project's own conventions count as Jakob's law for its returning users. Note them before
  proposing anything that departs from them.

## 3. Walk the five passes

Ask each pass's questions about this screen. Definitions, symptoms, default fixes, and misuse
warnings for every law are in [references/laws.md](references/laws.md); read the entry for a law
before you cite it.

1. **Choices.** How many options compete at the same moment? Is there a sensible default? What
   could wait behind a disclosure? Who carries the complexity, the user or the code?
   (Hick, Miller, progressive disclosure, Tesler, Occam)
2. **Layout.** Where does the eye land first, and is that the primary action? Do spacing, borders,
   and styling group things the way they belong together? Does exactly one thing stand out?
   (visual hierarchy, proximity, similarity, common region, Von Restorff, serial position,
   aesthetic-usability)
3. **Actions.** Are the primary and frequent targets large and close to where attention already
   is? Does the screen behave like other apps and like the rest of this app? Can the user pick
   instead of remember? Does input accept reasonable variations? (Fitts, Jakob, recognition over
   recall, Postel)
4. **Response.** What does the user see within 400 ms of each action? Does every async action have
   pending, success, and error states, and every collection an empty state? Can an error be fixed
   in place without losing input? (Doherty, feedback loops)
5. **Progress and ending.** In a multi-step flow, does the user know where they are and how much is
   left? What is the worst moment, and what is the last thing they see? (goal-gradient, peak-end)

## 4. Resolve tensions

Laws pull against each other. When two point different ways, decide for this screen's user and
job, and say which won and why. The common pairs are under Tensions in
[references/laws.md](references/laws.md).

## Build mode

- Use the project's existing components, tokens, and patterns. Do not add dependencies, restyle
  the brand, or edit files beyond the view and what it directly needs without asking first.
- Build every state the view can be in, not only the happy path.
- If the app runs, screenshot the result and recheck it against the five passes before reporting.
- Report what you built, then **UX decisions**: at most five lines, each
  `law → decision → file:line`, only for laws that changed something.
- Never commit.

## Review mode

- Read-only: do not edit files.
- Report at most five findings, ranked by how much each costs the user on the screen's main job:
  first anything that shows the user something untrue (a failure shown as empty or as success, a
  broken connection shown as healthy), then anything that blocks the primary action, then friction,
  then polish. Each finding has:
  - **What the user experiences**, in one plain sentence;
  - **Law**, and why it applies here;
  - **Evidence**: `file:line`, plus the screenshot or state when you have one;
  - **Fix** in this project's components, with its cost (small, medium, or large).
- If you verified more problems than fit, list at most three under **Also noticed**, one line each
  with `file:line`. Never add unverified or generic items there.
- Say which states you did not check.
- Close with at most two lines on what already works and the one fix to do first.
- A view in good shape gets a short answer that says so. Do not pad to five or invent problems to
  fill the list.
- Offer to apply the fixes. Apply them only after the user agrees; that run follows build mode for
  the fixes they named.

## Honesty rules

- The laws are heuristics, not proof. Do not predict conversion, speed, or satisfaction numbers.
- Cite numbers only as [references/laws.md](references/laws.md) gives them (400 ms, 44 pt, 48 dp,
  24 CSS px).
- Miller's law is about working memory, not a cap on menu items. Do not cite it to cut a list to
  seven.
- Keep what you observed (code, screenshot) separate from what you assume about users.
- When the running app uses demo, mock, or seeded data, check what you saw against the real
  storage or API code before reporting it. Behavior only the demo produces is not a finding.
