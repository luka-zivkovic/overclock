# The twenty laws

Sixteen come from Jon Yablonski's Laws of UX (lawsofux.com). Visual hierarchy, progressive
disclosure, recognition over recall, and feedback loops are long-standing interaction design
principles; the last two match Nielsen's heuristics "recognition rather than recall" and
"visibility of system status".

Each entry gives the claim, what to look for in code or on screen, the default fix, and how the
law gets misused. Cite a law only when its "look for" is actually present.

## Choices

### Hick's law
Decision time grows with the number and complexity of choices offered at the same moment.
- Look for: several equal-weight buttons side by side; the same action offered in more than one
  place on one screen; long unsorted option lists; no default.
- Fix: one primary action per screen; a recommended default; group, sort, or search long lists;
  move rare options behind "More" or a secondary menu.
- Misuse: it does not mean fewer features. An expert scanning a familiar list is faster with it
  visible than behind extra clicks.

### Miller's law
Working memory holds only a handful of items at once (Miller, 1956: "seven, plus or minus two").
- Look for: information the user must hold in mind across steps or screens; long unbroken strings
  (keys, IDs, phone numbers); comparisons that require remembering the other screen.
- Fix: chunk long strings and lists into meaningful groups; keep the information needed for a
  decision on the screen where the decision is made.
- Misuse: it is not a limit on how many items a menu or page may show. Never cite it to cut a list
  to seven.

### Progressive disclosure
Show what most people need now; reveal advanced or rare options when they are asked for.
- Look for: advanced settings mixed with basic ones; every field of a long form shown at once;
  explanations and caveats at full weight before the user has done anything.
- Fix: an "Advanced" disclosure; a staged or multi-step flow; details on demand next to the thing
  they explain.
- Misuse: hiding something the user needs on most visits, or hiding it where they would not look.

### Tesler's law
Every task has complexity that cannot be removed, only moved between the user and the system.
- Look for: the user typing what the app could infer (dates, units, region, IDs it already knows);
  manual formatting; settings that exist only because the code did not pick a default.
- Fix: smart defaults, detection, prefill, and autocomplete, so the code carries the complexity.
- Misuse: hiding complexity that still matters, so the user loses control or cannot see why
  something happened.

### Occam's razor
Among designs that work equally well, prefer the one with fewer parts.
- Look for: decorative elements, duplicate controls, explanatory text that restates the label,
  sections that do not serve the screen's job.
- Fix: remove an element; if the job still works, keep it removed.
- Misuse: removing something whose work then falls on the user (see Tesler).

## Layout

### Visual hierarchy
Size, weight, color, contrast, and position decide what is seen first and the reading order.
- Look for: the primary action no more prominent than secondary ones; several elements competing
  at the same weight; the heading that names the page smaller than chrome around it.
- Fix: one dominant element per screen, usually the primary action or the main content; step
  sizes and weights down from it.
- Misuse: emphasis by decoration (badges, colors, all caps) instead of structure.

### Law of proximity
Things placed close together are read as related.
- Look for: labels nearer to the neighboring field than to their own; equal spacing everywhere so
  groups dissolve; an action far from the thing it acts on.
- Fix: tight spacing inside a group and visibly larger spacing between groups; put each action
  next to its object.
- Misuse: crowding unrelated items just to save space.

### Law of similarity
Elements that look alike are read as alike in kind and behavior.
- Look for: links and plain text styled the same; buttons with different styles doing the same
  thing; the same style used for clickable and non-clickable items; the same set of options listed
  in a different order in two places.
- Fix: one style per role, applied everywhere on the screen and across the app; one order for a
  repeated set.
- Misuse: forcing different things to look the same for tidiness.

### Law of common region
Elements inside a shared boundary (card, panel, background) are read as a group.
- Look for: related controls with no shared container; cards that wrap unrelated things; nested
  boxes that blur which group an item belongs to.
- Fix: one container per real group; flatten nesting that carries no meaning.
- Misuse: boxing every element so boundaries stop meaning anything.

### Von Restorff effect
The item that differs from its neighbors gets noticed and remembered.
- Look for: several highlighted elements competing; the primary action styled like its
  neighbors; a warning that looks like ordinary text.
- Fix: exactly one distinct element per screen for the main action, and a distinct, consistent
  treatment for warnings.
- Misuse: relying on color alone (color-blind users, dark mode). Pair it with shape, size,
  position, or text.

### Serial position effect
People remember the first and last items in a sequence best and the middle least.
- Look for: the most-used navigation item or option buried in the middle of a list; the key fact
  of a paragraph in the middle.
- Fix: put the most important items first and last; lead with the key fact.
- Misuse: reordering a list the user knows by heart, which breaks Jakob's law for them.

### Aesthetic-usability effect
People judge attractive interfaces as easier to use and forgive their small problems
(Kurosu and Kashimura, 1995).
- Look for: misalignment, inconsistent spacing, mixed styles that make a working screen feel
  broken; or a polished screen whose tasks still fail.
- Fix: consistent alignment, spacing, and type; then judge the screen by whether its tasks work.
- Misuse: treating polish as proof of usability. Attractive screens hide friction in testing.

## Actions

### Fitts's law
The time to reach a target grows with its distance and shrinks with its size.
- Look for: small primary or frequent targets; icon-only buttons with tiny hit areas; primary
  actions far from where the user's attention or cursor already is; destructive and safe actions
  packed together.
- Fix: larger hit areas for primary and frequent actions; place actions next to the content they
  act on; separate destructive actions from frequent ones. Touch targets: 44 x 44 pt (Apple Human
  Interface Guidelines) or 48 x 48 dp (Material Design); WCAG 2.2 success criterion 2.5.8 sets a
  24 x 24 CSS px minimum.
- Misuse: making every target huge, which costs hierarchy.

### Jakob's law
Users spend most of their time on other products and expect yours to work the same way. Inside
one product, its own pages set the expectation for returning users.
- Look for: custom controls where a standard one exists; familiar patterns placed somewhere
  unusual; this screen behaving differently from the rest of the app.
- Fix: the standard pattern, or the pattern the rest of the app already uses.
- Misuse: copying a competitor's flaw because it is common.

### Recognition over recall
Showing the options beats making the user remember them.
- Look for: blank inputs that expect an exact name or ID; commands that must be memorized;
  instructions given on a previous screen and needed on this one.
- Fix: pickers, autocomplete, recent items, visible examples, and labels that stay visible while
  the user types (not placeholder-only labels).
- Misuse: showing every option at once (see Hick).

### Postel's law
Be liberal in what you accept and conservative in what you send (Postel, RFC 760, 1980).
- Look for: inputs that reject harmless variations (spaces, dashes, case, pasted whitespace, a
  trailing slash on a URL); errors that ask the user to reformat.
- Fix: accept the variants, normalize them in code, and show the normalized value.
- Misuse: silently guessing when a wrong guess has a cost (dates, amounts, destinations). Show the
  interpretation and let the user confirm it.

## Response

### Doherty threshold
Productivity rises when the system responds within about 400 ms (Doherty and Thadani, 1982).
- Look for: actions with no visible change until a request finishes; full-page spinners for small
  updates; buttons that can be clicked again while their request is pending.
- Fix: acknowledge every action within 400 ms (pressed state, inline spinner, optimistic update);
  skeletons in the content's shape for loads; disable the trigger while it is pending.
- Misuse: optimistic updates that do not visibly roll back on failure.

### Feedback loops
Every action gets a visible result, and the system's state is always visible.
- Look for: missing pending, success, or error states; success shown somewhere the user is not
  looking; errors that clear the form or only appear in the console; lists with no empty state.
- Fix: work through the state checklist below for every action and collection on the screen.
- Misuse: toasts for everything, so real errors get dismissed with the noise.

## Progress and ending

### Goal-gradient effect
People speed up as they near a goal (Hull, 1932), and a visible head start increases completion
(Kivetz, Urminsky, and Zheng, 2006).
- Look for: multi-step flows with no indication of position or remaining steps; setup checklists
  that never show progress.
- Fix: "Step 2 of 3", progress bars, checklists that tick, and credit for steps already done.
- Misuse: fake progress, or progress bars on single-step tasks.

### Peak-end rule
People judge an experience mostly by its most intense moment and its end, not its average.
- Look for: the worst moment (a failed save, a cryptic error, a lost draft) left unpolished; flows
  that end on a blank screen or an abrupt redirect.
- Fix: invest in error recovery at the hardest point and in a clear ending: confirmation, what
  happened, and the next step.
- Misuse: celebration screens that delay the user's next task.

## State checklist

For every async action:
- idle: enabled, or disabled with the reason visible;
- pending: acknowledged within 400 ms, trigger disabled, progress near the trigger, and an upper
  bound: work pending well past its expected time reads as stuck, says what to check, and stops
  any automatic refreshing;
- success: confirmed where the user is looking, with the next step if there is one;
- error: shown in place, saying what happened and what to do, input kept, retry when retrying can
  work.

For every collection or data view:
- loading in the shape of the content;
- first-use empty (explain and offer the first action), filtered empty (offer to clear the
  filter), and failed (offer retry) as distinct states. A failed or partly failed load must never
  render the first-use empty state: telling someone they have nothing invites them to recreate
  what they already have;
- several requests behind one view: one failing should not hide what the others returned;
- long content: long names, many items, and missing values shown as missing rather than as zero.

## Tensions

- **Occam vs Tesler.** Removing a control can push its work onto the user. Remove only what the
  code can do for them or what they rarely need.
- **Hick vs recognition over recall.** Hiding options speeds the decision but forces recall. Hide
  the rare ones; keep the frequent ones visible.
- **Progressive disclosure vs daily experts.** First-visit users need the minimum; daily users want
  density and shortcuts. Decide from the frequency you established when framing the screen.
- **Von Restorff vs similarity.** Make one thing stand out on a screen, but use the same highlight
  treatment across the app, or the pattern stops meaning anything.
- **Postel vs clear errors.** Accept variants, but confirm an interpretation whenever a wrong guess
  would cost the user.
- **Doherty vs honesty.** Optimistic feedback must show failure as clearly as it showed success.
- **Aesthetic-usability vs evidence.** Polish makes a screen feel easier; judge it by whether its
  tasks work.
