---
name: natural-writing
description: "Write or edit prose (blog posts, articles, essays, newsletters, narrative docs) so it reads as naturally human-written, not AI-flavored. Use when drafting or revising human-facing prose for publication and you want to avoid the tells that make text read as AI-generated: em-dashes, words like 'delve'/'tapestry'/'leverage', uniform sentence rhythm, hedging, analogies, and bot scaffolding ('In conclusion', 'Let's dive in'). Do NOT use for code, code comments, commit messages, API/reference docs that need precise terms, one-line UI strings, or quotes to preserve verbatim."
---

# Natural Writing

AI prose has a sound: even sentence lengths, em-dashes everywhere, a handful of overused words, tidy scaffolding like "Furthermore" and "In conclusion." Readers now spot it and discount it. This skill writes and edits prose so the draft reads like a person wrote it, so you can use AI for a blog post or article without rewriting it line by line to undo the tells.

It is stateless and lightweight on purpose: a writing discipline, not a tool. No memory, no ceremony.

## When it fires (and when it doesn't)

Fires for **multi-sentence prose meant for human readers**: blog posts, articles, essays, newsletters, landing copy, narrative sections of docs.

Stay silent. Do not apply this for:
- Code, code comments, config.
- Commit messages, PR titles.
- API / reference docs where a precise technical term is the *right* word.
- One-line UI strings, labels, error messages.
- Do not rewrite quoted/cited spans or verbatim data inside an otherwise in-scope piece;
  preserve those spans byte-for-byte while editing the surrounding prose.
- Legal or precise technical text where a qualifier is load-bearing.

Never run the full pass on a single sentence. If someone asks to reword one line, just reword it.

## The rules

1. **No em-dashes or en-dashes.** Use a comma, a period, or two short sentences. Use "to" for ranges (9 to 5, not 9–5). This is the single loudest AI tell, so it is rule one.
2. **Cut AI-tell vocabulary.** Replace with the plain word: delve → look at; leverage → use; utilize → use; tapestry / realm / landscape → drop; testament to → shows; underscore / highlight → show; crucial / pivotal / vital → important (or cut); robust / seamless / synergy / paradigm / "boasts" → say what you mean; "it's worth noting" / "in today's fast-paced world" → delete.
3. **Drop bot scaffolding.** No "In conclusion", "Furthermore", "Moreover", "Firstly / Secondly", "Let's dive in", "Without further ado", "Buckle up." Just say the thing. Don't preview an argument before you make it or recap it after.
4. **Vary the rhythm.** Mix short sentences with longer ones. Uniform sentence length is the second loudest tell, and so is a run of identical short ones. A two-word sentence is fine. Join closely related ideas with a plain "and", "because", or "so" when they belong together; only split ideas that are genuinely separate. Over-splitting makes prose choppy. Don't chain a long run of clauses with "and… and… and."
5. **Use everyday words and contractions.** Write the way you'd explain it to a smart friend. "Don't", "it's", "you'll" are natural, not sloppy.
6. **Be concrete.** Prefer a specific noun, number, or example over a vague placeholder ("situation", "process", "factor"), and a named source over "experts say" or "studies show."
7. **Lead with the point, hedge after.** State the claim cleanly first, then the one caveat that actually matters. Cut the pile of qualifiers before the claim ("while it's mixed and context-dependent, there may be some reason to think…"). Keep the real caveat; drop the throat-clearing.
8. **Cut canned or decorative analogies.** Say the thing directly instead of reaching for
   the stock symphony, dance, tapestry, or journey. Preserve an author's original metaphor
   when it carries meaning or voice, and do not invent a new one unless the user wants it.
9. **Strong verbs.** Don't bury the action in a noun: "decide", not "make a decision"; "investigate", not "conduct an investigation"; "to configure the runner, set…", not "configuring the runner involves…".
10. **Active voice; name who did what.** "The team missed the deadline", not "the deadline was missed." Passive is fine only when the actor is genuinely unknown or irrelevant.
11. **Don't bold for decoration.** Bolding the lead phrase of every bullet just for emphasis is a classic AI tell. Bold is fine only as a real structural header on a list item, where the bold text names the thing and the rest explains it, e.g. "**Live feedback loop.** Poll the file and react as events arrive."

See `references/examples.md` for before/after pairs that show each rule in action (curated from the `mine-writing-rules` corpus).

## How to work

- **Drafting:** write it naturally with these rules from the start, not as a cleanup afterthought.
- **Ground concepts before prose leans on them.** A term, name, or idea the reader can't be
  assumed to know must be introduced — or be a stated prerequisite of the piece — before a later
  sentence depends on it. While drafting or revising, track where each concept first appears; when
  a passage leans on something introduced later or never, move the introduction earlier or add the
  one-line grounding at first use. Ground in place; don't bolt on a glossary. (Structural
  counterpart to the style rules: reordering here is fine, but it still preserves the author's
  meaning and voice.)
- **Revising a draft — two passes:**
  - *Pass 1 — fix violations.* Go rule by rule above and fix what breaks them.
  - *Pass 2 — cut what doesn't earn its place.* Remove words, sentences, and whole sections that add nothing. A first draft usually runs ~25% longer than it needs to. But preserve the author's meaning and voice, and keep the one caveat that matters. Cutting a real qualifier to sound confident is worse than leaving it.
- Match how the author actually writes. Don't flatten their voice into a generic plain one.

## Revision report (on request only)

By default, just return the rewritten prose. When the user asks to *see what changed* (or for a long, heavily-edited piece), produce the visual diff:

1. Build a JSON file using the schema documented at the top of
   `assets/revision-report.html` (original, revised, and ordered changes with `type` =
   `keep` | `delete` | `rewrite`).
2. Run the bundled helper through its host-provided absolute skill path:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/build_revision_report.py" DATA_JSON OUTPUT_HTML --root "${CLAUDE_PROJECT_DIR}"
   ```
   This helper is mandatory: it validates the schema, confines input/output paths to the project,
   refuses linked or existing output paths, and embeds UTF-8 JSON as base64 so HTML or `</script>`
   cannot become executable markup. Do not call Read on the report template or any file under
   `assets/`; the helper owns that trusted asset. Never insert report data manually. If
   the helper cannot run, report the error and do not create a fallback HTML report. Use
   `--replace` only after the user explicitly approves replacing the named existing regular file.
3. Remove the temporary JSON data file unless the user asked to keep it, then tell the user
   the report path. It renders Original, Revised, and Diff tabs.

Never generate the report for a one-liner or a trivial edit. It is opt-in, so it stays out of the way.

## Overrides

These are sensible defaults, not laws. If the project's `CLAUDE.md` or the user states a style preference (keep em-dashes, use our house terms, a specific tone), that preference wins.
