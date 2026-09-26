# Navigation and information architecture rules

- **Users predict, then look.** Navigation categories are mutually exclusive and named in the
  user's vocabulary, by task or topic, never by format (Videos, PDFs) or internal module name.
  A category whose contents the user cannot predict from its label has no scent.
- **Location is always visible.** Every routed screen shows where it sits: an active nav state,
  a breadcrumb for hierarchies deeper than two levels, and step context inside a flow. The page
  title matches the label that led there.
- **Entry points sit where the task starts.** A task on an object starts on that object's page;
  a task on a collection starts on the list (its header primary action or its empty state). A
  task that starts from outside (email, notification) deep-links to the right step and preserves
  the destination through sign-in.
- **Everything shareable has a URL.** Detail pages, filtered lists, and wizard steps that a user
  may return to each get a route. Browser Back moves one step, never out of the flow.
- **Seven is a smell, not a law.** More than about seven peer items in one menu means the items
  need grouping first. Group, then count groups; test the tree with real tasks when the
  hierarchy is unclear (card sorting to build it, tree testing to check it).
- **Progressive disclosure keeps the primary path visible.** Advanced or rare options live
  behind a clearly labelled disclosure; the main task never does.
- **Global versus contextual.** Global navigation lists destinations; contextual actions live
  on the object. Do not put object actions in the global nav or destinations in an object's
  action row.
- **Consistency across the app.** Same term, same place, same icon for the same action
  everywhere; a user who learned it on one page has learned it on all.

Sources: Rosenfeld, Morville and Arango, Information Architecture for the Web and Beyond; NN/g
(3 IA mistakes, format-based navigation, breadcrumbs, "You are here", progressive disclosure,
card sorting and tree testing, consistency and standards); Laws of UX (Jakob, Hick, Miller).
