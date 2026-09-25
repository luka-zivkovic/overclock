# Casing and punctuation policy per platform

Pick one policy per app, record it in `UX.md` under Casing, and lint against it. Mixed casing
across an app is the most visible naming drift and the cheapest to detect.

| Platform or system | Buttons and labels | Headings and titles | Source |
|---|---|---|---|
| Web app (default) | Sentence case | Sentence case | Atlassian, Material, Microsoft, GOV.UK all default to sentence case |
| Material / Android | Sentence case | Sentence case | Material 3 UX writing |
| Apple (iOS, macOS) | Title Case for buttons, menu items, and titles; sentence case for body, help, and alert messages | Title Case | Apple HIG Writing |
| Windows / Fluent | Sentence case | Sentence case | Microsoft Writing Style Guide |
| Vercel-style product UI | Title Case for product headings and buttons; sentence case for marketing | Title Case | Vercel Web Interface Guidelines (house style; record if adopted) |

## Punctuation

- No trailing period on buttons, labels, menu items, headings, tooltips of a few words.
- Full sentences (help text, errors, empty-state lines) end with a period; a single fragment
  does not.
- Ellipsis (…, the single character) on actions that open a further step and on progress
  labels (Saving…). Three dots are acceptable if the font lacks the glyph; be consistent.
- No exclamation marks in interface text; no question marks except in real questions
  (confirmation titles).
- Ampersand only in space-constrained labels where the design system allows it; otherwise "and".
- Numbers: numerals for counts (3 files), words for none ("No files"). Pluralize by count with
  proper forms, never "file(s)".
- Contractions are fine in sentences (can't, don't); never in button labels.

## Capitalization of product terms

- Branded names as branded (GitHub, iPhone). Generic concepts lower case even when the product
  treats them as features (workspace, project) unless the glossary in `UX.md` capitalizes them
  deliberately.

## Detecting mixed casing

A label is Title Case when every word longer than three letters starts with a capital; sentence
case when only the first word (and proper nouns) does. The scanner reports the ratio among
button-like strings; a split near 50/50 is drift, a small minority is usually proper nouns or
brand names to review.

Sources: Atlassian Language and grammar; Material 3 UX writing best practices; Apple HIG Writing;
Microsoft Writing Style Guide (capitalization, punctuation); GOV.UK style guide; Vercel Web
Interface Guidelines.
