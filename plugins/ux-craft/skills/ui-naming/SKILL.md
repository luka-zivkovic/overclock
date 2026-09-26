---
name: ui-naming
description: "Name the things in an application's interface consistently: page titles, navigation labels, buttons, links, field labels, error messages, empty states, and the product's terminology, with one canonical term per concept recorded in a glossary. Use when the user asks what to call something, what a button, menu item, or page should say, how to word an error, says 'our labels are inconsistent', 'clean up the naming', 'we say delete here and remove there', or asks to build or check a glossary or run a label scan. Do NOT use for long-form prose, marketing copy, docs, commit messages, or code identifiers, for a single string the user only wants shortened, for layout (page-structure), or for step sequencing (user-flow)."
argument-hint: "[feature or page] [--scan PATH] [--write-ux]"
---

# UI naming

Think **one name per thing**. Users learn a product's vocabulary once; every synonym they meet
afterwards (Remove here, Delete there, Trash in the menu) costs a moment of doubt about whether
it is the same action. Naming work is mostly choosing the one name, writing it down, and finding
where the product drifts from it.

This pass proposes names and records decisions. It edits UI strings in the codebase only when the
user approves a proposal table, and then one term at a time with the diff shown. If the request
is outside the description, answer plainly; a question about one label gets one line, not this
procedure.

## 0. Read what the project already decided

If `UX.md` exists at the project root, read it first: Platform, Casing, Button order, Verb
vocabulary, and Glossary are settled decisions. Extend them; do not re-argue a recorded term
unless the user asks. If a design system content guide, `DESIGN.md`, or i18n source of truth
exists, it outranks the defaults in `references/`. Without any, assume a web application and
sentence case, and say so.

## 1. Inventory the concepts and actions

For the feature or page in scope, list every **object** (noun) the user sees and every
**action** (verb) they can take. For each, write the user's word for it, not the code's: no
"entity", "record", "node", table names, or internal module names. Where two words compete for
one concept, pick one with `references/labels.md` and record the loser as a rejected synonym so
it is not re-proposed.

## 2. Apply the label rules

Read `references/labels.md` before proposing; it holds the per-element rules (page titles,
navigation, buttons, links, fields, help text, empty states, confirmations, toasts) with the
sources behind them, and proposing without it reproduces the generic labels the rules exist to
remove. The rules that carry the most weight:

- Buttons say what happens: a verb plus its object (Save changes, Delete project, Invite
  people). Never OK, Yes, No, Submit, or Continue on an action that commits something; Cancel
  is literally Cancel.
- Navigation and page titles name a destination in the user's vocabulary; the title matches the
  nav label that led there.
- Links say where they go; "Click here", "Learn more", and "More" carry no scent.
- Field labels name the value in two or three words; help text answers "what format" or "why";
  placeholders never carry required information.
- Verbs come from one vocabulary: read `references/verbs.md` for the canonical verb table
  (Add vs Create, Remove vs Delete, Save vs Apply, Edit vs Change) and its meanings, so the same
  verb means the same thing everywhere.
- Errors follow `references/errors.md`: name the field or thing, say what to do, in plain words,
  with no blame and no code as the whole message.
- Casing and punctuation follow one policy from `references/casing.md`, chosen per platform and
  recorded in `UX.md`.

## 3. Scan for drift when there is code

When a codebase is present and the user asks for a check, a glossary, or consistency, run the
bundled scanner by absolute path (resolve the skill directory from the host's skill context):

```bash
python3 /absolute/path/to/ui-naming/scripts/scan_labels.py PATH [--format md|json] [--exclude GLOB ...]
```

It reads UI strings from JSX/TSX, Vue, Svelte, HTML, and i18n JSON/YAML files, and reports:
synonym clusters (delete/remove/trash), generic labels (OK, Submit, Click here), mixed casing
among button-like labels, banned words in error-like strings, trailing punctuation on labels, and
the string inventory. It never edits files and makes no network requests. Treat its report as
evidence to read, not a verdict: a synonym cluster is only drift if the words name the same
action.

## 4. Deliver the proposal

Return, in this order:

1. The naming policy in force (platform, casing, button order, save model) and where it came
   from (`UX.md`, design system, or default).
2. The proposal table: element or concept, current name(s), proposed name, the rule, the
   reference section. Mark each row keep, rename, or decide (the user must choose).
3. Glossary entries to add: term, meaning in one line, rejected synonyms.
4. Drift findings from the scan, grouped by cluster, with file and line, and the proposed
   canonical term for each cluster.
5. Open questions in one short block.

Completion check: every object and action from step 1 has exactly one proposed name; no button
in the table is OK/Yes/No/Submit/Continue on a committing action; every rename cites a rule;
every synonym cluster resolves to one term or is marked decide.

## 5. Record and apply, on request only

- With `--write-ux` or an explicit ask, write or update `UX.md` at the project root from
  `templates/UX.md`, adding only the sections and entries the user approved. Show the diff.
- To apply renames in the codebase, take the approved rows one term at a time: show every
  occurrence the scanner found, edit those, run the project's tests or type check if present,
  and stop for the next term. Never rename across the codebase in one sweep, never touch strings
  the scanner did not list, and never commit.

## Handoffs

- Long-form prose, docs, marketing pages: a writing skill such as natural-writing owns them.
- Polishing the tone of one string beyond the rules here: answer directly, or hand to
  `impeccable clarify` if it is available.
- Where a label should sit: page-structure. What order the steps come in: user-flow.
