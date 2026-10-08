---
name: notion-docs
description: "Write a Notion documentation page for a product feature with short recorded GIF clips that show what to click and what happens. Use when the user explicitly invokes notion-docs or asks to document a feature, write a how-to, walkthrough, or guide in Notion with GIFs, screen recordings, or click-through previews. Plans the page, records each clip from the real web UI with the bundled Playwright recorder, writes the page in Notion-flavored Markdown, uploads the clips through the Notion connector when it is available, and reads the result back for a critique pass. Do not invoke automatically, and do not use for API or reference docs, README or code-comment changes, Notion edits that need no walkthrough, marketing copy, desktop or terminal apps, or a feature with no reachable UI."
argument-hint: "[feature] [--url APP_URL] [--to NOTION_PAGE_URL]"
disable-model-invocation: true
---

# Notion Docs

Show the click. A feature page is read in a minute, not studied: one sentence on what the
feature does, a short clip under each step that shows the control being clicked and what
happens, text that says the same thing in words, and the rest in a table or a callout. Every clip
is recorded from the real UI by the bundled recorder. A clip that could not be recorded is left
out and the page says what was not shown; nothing is staged or drawn by hand.

The commands use Claude Code's `${CLAUDE_SKILL_DIR}` variable. On a host that does not define it,
use the installed directory of this `notion-docs` skill as an absolute path.

## Boundaries

- **Web UIs only.** The feature must be reachable in a browser from this machine: a local dev
  server, a staging URL, or an authenticated app through a saved storage state. For anything
  else (CLI, desktop, an unreachable deployment) write the page without clips and say why.
- **Secrets never reach a scene, a clip, or the page.** Credentials enter only through
  `setup` steps that read `text_env`, or through a storage state file made with `login`. Both
  stay out of `notion-docs-output/` and out of version control. Record against demo or seeded
  data; if a screen would show real customer data, do not record it.
- **Writes stay in two places:** `notion-docs-output/<slug>/` in the project (or a directory the
  user names) and the Notion page the user named. Nothing is committed; remind the user to add
  the output directory to `.gitignore` if it is not already ignored.
- **Notion changes are additive and targeted.** Create the page the user named, or a private
  draft when no destination was given, and say so. When updating an existing page, insert or
  replace only the section being documented; never remove or move child pages or databases.
- **Right-sized.** One page per feature, one to four clips per page, each clip 3 to 12 seconds
  showing one interaction. A setting that toggles, a label change, or a one-line answer gets a
  sentence, not a clip. If the user asked for text only, record nothing.

## 0. Check the recorder

```text
node "${CLAUDE_SKILL_DIR}/scripts/record_clip.mjs" doctor
```

`ready: true` means Playwright and Chromium are installed under the deps directory
(`~/.cache/notion-docs/deps` unless `--deps DIR` or `NOTION_DOCS_DEPS` says otherwise). If not,
tell the user that `setup` installs Playwright 1.63 there and downloads Chromium when no matching
build is cached, then run:

```text
node "${CLAUDE_SKILL_DIR}/scripts/record_clip.mjs" setup
```

No ffmpeg or image library is needed; the recorder encodes the GIF itself.

## 1. Learn the feature from facts

- Read the code, existing docs, and tickets for the feature. Note where it lives in the UI, what
  each control does, and what the reader is trying to get done.
- Confirm the URL and how to log in. For a login form, write `setup` steps that use `text_env`.
  For SSO or anything interactive, have the user run `login` once from the project root:
  `node "${CLAUDE_SKILL_DIR}/scripts/record_clip.mjs" login --url APP_URL --out .notion-docs-auth/state.json`
  and point scenes at that file with `storage_state`, which is relative to the scene file:
  `"../../../.notion-docs-auth/state.json"` from `notion-docs-output/<slug>/scenes/`.
- Take a snapshot of each screen you will record so selectors come from the real accessibility
  tree, not from memory:
  `node "${CLAUDE_SKILL_DIR}/scripts/record_clip.mjs" snapshot SCENE.json --out DIR`
  It writes `snapshot.png`, `snapshot.aria.yaml`, and prints `role=` selectors for every button,
  link, and field it found.

## 2. Plan the page

Copy [templates/plan.md](templates/plan.md) to `notion-docs-output/<slug>/plan.md` and fill it
in: who reads the page, the one-sentence job of the feature, and the candidate interactions.
Keep an interaction as a clip only when something the reader clicks produces a visible result
that words explain badly. For each kept clip write the trigger, the result the reader should
see, and the caption. Cap the list at four. Use
[references/page-craft.md](references/page-craft.md) for the anatomy of a page that reads well
and the review checklist; skipping it produces the classic failures, a GIF of a static screen or
a wall of toggles.

## 3. Record the clips

One scene per clip, starting from [templates/scene.json](templates/scene.json). The field and
action reference is [references/scene-spec.md](references/scene-spec.md); read it before writing
a scene, because the validator rejects secrets in recorded steps and the timing fields decide
whether the clip is readable. Run the recorder commands in this step from
`notion-docs-output/<slug>/`, where `scenes/` and `clips/` live; `${CLAUDE_SKILL_DIR}` is
absolute, so only the scene and output paths depend on the working directory. From anywhere
else, write the bundle paths out in full.

```text
node "${CLAUDE_SKILL_DIR}/scripts/record_clip.mjs" validate scenes/<name>.json
node "${CLAUDE_SKILL_DIR}/scripts/record_clip.mjs" record scenes/<name>.json --out clips
```

`record` writes `clips/<name>.gif`, a poster `clips/<name>.png`, the final frame
`clips/<name>.last.png`, and `clips/<name>.manifest.json`. Open the poster **and the last frame**
and read the manifest. Use a clip only when its manifest `status` is `ok` and the last frame shows
the result the caption claims: the recorder cannot see an application error, so a dialog that
stayed open with a red message under a "done" caption is caught only by looking. End every scene
with a `wait` that can succeed only after the action, such as the dialog `hidden` or a toast
visible; a wait for text that may already be on the page passes at once and proves nothing. A
failed step names the selector that missed: re-snapshot and fix it, or drop the clip. `too_long`
means split the scene; `too_large` means lower `scale` or `fps`. Each clip starts on a settled
screen, the cursor travels to each target with a highlight ring and a click ripple, captions name
the step, and the final frame holds for `end_hold_ms` so the result registers.

With many clips, review them in one image rather than one file at a time:

```text
node "${CLAUDE_SKILL_DIR}/scripts/record_clip.mjs" sheet --clips clips --out clips/sheet.png
```

When the UI may have changed since a scene was written, run `check` before `record`: it runs the
scene without recording, reports each selector as `ok`, `hidden`, `ambiguous`, or `missing`, and
diffs the screen's accessibility tree against a saved baseline so new or removed controls show up
before a clip is re-recorded against a page that no longer matches its text.

## 4. Write the page

Write `notion-docs-output/<slug>/page.md` from
[templates/feature-page.md](templates/feature-page.md) in Notion-flavored Markdown, following
[references/notion-markdown.md](references/notion-markdown.md). Notion's syntax differs from
GitHub Markdown in ways that break blocks: callouts, toggles, and tables are tags, children are
indented with tabs, and `![caption](clips/<name>.gif)` places a clip. Rules that matter most:

- Lead with the job of the feature and when to use it; no marketing adjectives.
- Steps are numbered, one action each, written as what to click and what happens. The clip sits
  directly under the step it shows, and its caption says what the reader should see.
- Options and settings go in a table; limits and gotchas go in one callout; related pages at the
  end.
- Say only what you observed in the recording or read in the code. Name what was not verified.

## 5. Deliver to Notion

Follow [references/notion-delivery.md](references/notion-delivery.md). With the Notion connector
available: upload each GIF through `create-file-upload`, place the returned `suggested_markdown`
where the local `![...](clips/...)` reference was, create or update the page, then `fetch` it and
confirm every clip rendered as an image block. Without the connector, use the `NOTION_TOKEN`
API recipe for the clips or hand over the local bundle with the three-line paste instruction.
The upload headers carry a bearer token: pass them to `curl` and never write them into the bundle.

## 6. Read it back once

Fetch the published page and read it as the intended reader, against the review checklist in
`references/page-craft.md`. Fix what fails (a clip that does not earn its place, a step whose
text and clip disagree, a missing result caption), republish once, and stop. Save the earlier
`page.md` as `page.v1.md` so the revision is visible.

## Done when

- `notion-docs-output/<slug>/` holds `plan.md`, `scenes/`, `clips/` with every used clip's
  manifest at `status: ok`, and `page.md`.
- The Notion page exists at the destination with one image block per clip, verified by `fetch`.
- The report to the user gives the page URL, each clip's name, length, and size, what was not
  verified or not shown, the output directory, and the `.gitignore` reminder.
