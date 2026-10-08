# What a feature page that reads well looks like

The reader is usually a colleague who wants to do one thing with the feature in the next five
minutes. Write for that person. The page is read top to bottom once, and skimmed afterwards.

## Anatomy, in order

1. **The job, one sentence.** `<Feature> lets <reader> <get this done>.` Then one sentence on when
   to use it and when not to.
2. **Walkthrough.** Numbered steps, one action each, written as what to click and what happens.
   The clip sits directly under the step it shows. Three to seven steps; more means two pages.
3. **Options**, as a table, only if the feature has settings. Option, what it does, default.
4. **Limits and gotchas**, one callout, each item one observed sentence.
5. **Related**, two or three links.

No introduction about why documentation matters, no history of the feature, no marketing
adjectives. The first sentence is the summary.

## When a clip earns its place

Record a clip when the reader clicks something and the screen changes in a way words explain
badly: a dialog opens and asks for input, a menu reveals the control, a list updates, a state
flips with visible feedback. A sequence of two or three such actions is one clip when they form
one task.

Do not record a static screen; a sentence or a plain screenshot covers it. Do not record a
settings toggle, a copy change, or a result that a sentence already states. One to four clips per
page; a page that needs more is covering more than one feature.

Clip discipline:

- 3 to 12 seconds, one interaction or one short task. The validator estimates the length.
- Start on a settled screen. The cursor travels to each target, so the reader sees where to look.
- Caption every step whose target is not obvious. The caption is a label, not a sentence.
- End holding the result for about 1.5 seconds. The loop should feel like "do this, see that".
- One viewport size and one color scheme across the page.
- Demo data only. If a screen would show real users, customers, or keys, do not record it.
- The clip must make sense muted and at a glance; nothing in a GIF can be paused by the reader.

## Captions and step text

The step text says what to do and what happens: "Click **New suite**. A dialog asks for a name."
The caption under the clip says what the reader should see when it worked: "The new suite appears
at the top of the list." Captions describe results, not the recorder's actions; "clicked the
button" is never a caption.

Name controls in bold exactly as the UI labels them. Use second person and plain verbs. Cut
"simply", "just", "easily", and any adjective that judges the feature.

## Truth

Say only what the recording showed or the code states. Where the page relies on something you did
not observe, say so in a short "Not verified" line at the end of the section, or leave it out.
Never describe behavior from memory of a similar product.

## Review checklist, used once after publishing

Read the published page as the reader, then answer each question yes or no. Fix every no and
republish once.

1. After the opening paragraph, could a new reader say what the feature does and when to use it?
2. Does every clip show a click and a visible result, in 12 seconds or less?
3. Does the step text above each clip say the same thing the clip shows, in the same order?
4. Does every caption state the result the reader should see?
5. Is any clip a static screen, or longer than one task? Replace it with a sentence or split it.
6. Is any step more than one action?
7. Are all options in the table, with nothing about settings left in prose?
8. Is there exactly one gotchas callout, and is every item in it observed?
9. Does the page claim anything that was not recorded or read in code without saying so?
10. Did `fetch` show one image block per clip, no literal `clips/` paths, and no empty bullets?

## Keeping versions

When the user asks to iterate, keep every version: `page.v1.md`, `page.v2.md`, and a
`CRITIQUE.md` that lists, per version, which checklist items failed and what changed. Publish
each version as its own page under the destination when the user wants to compare them in Notion.
