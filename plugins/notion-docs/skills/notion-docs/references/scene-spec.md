# Scene specification

A scene is one JSON file that the recorder turns into one GIF. Keep scenes at
`notion-docs-output/<slug>/scenes/<name>.json` and record them into
`notion-docs-output/<slug>/clips/`. Start from `templates/scene.json`.

```text
node "${CLAUDE_SKILL_DIR}/scripts/record_clip.mjs" validate scenes/<name>.json
node "${CLAUDE_SKILL_DIR}/scripts/record_clip.mjs" record   scenes/<name>.json --out clips
node "${CLAUDE_SKILL_DIR}/scripts/record_clip.mjs" snapshot scenes/<name>.json --out snapshots/<name>
```

## Top-level fields

| Field | Required | Default | Meaning |
|---|---|---|---|
| `name` | yes | | Slug `[a-z0-9-]`, up to 64 characters. Names the GIF, poster, and manifest. |
| `url` | yes | | Where the clip starts. `http://`, `https://`, or `file://`. |
| `description` | no | | One line on what the clip shows. Not rendered; helps the plan. |
| `viewport` | no | 1280×800 | Browser size in CSS pixels. Width 320..3840, height 240..2160. Keep one size per page. |
| `scale` | no | 0.75 | Output scale. 1280×800 at 0.75 gives a 960×600 GIF, which reads well in Notion. |
| `fps` | no | 10 | Frames per second kept, 4..15. 10 is smooth enough for UI and keeps files small. |
| `max_seconds` | no | 15 | Hard cap on recorded interaction time, 1..30. Over it the manifest says `too_long`. |
| `end_hold_ms` | no | 1500 | How long the final frame holds before the loop restarts, so the result registers. |
| `settle_ms` | no | 600 | Pause after each action so the reader sees what happened before the next move. |
| `timeout_ms` | no | 10000 | How long to wait for a selector before a step fails. |
| `cursor` | no | true | Draw the cursor, highlight ring, and click ripple. Set false for a bare recording. |
| `captions` | no | true | Show step captions as a pill at the bottom of the frame. |
| `color_scheme` | no | `light` | `light` or `dark`, passed to the browser. |
| `storage_state` | no | | Path, relative to the scene file, of a Playwright storage state saved by `login`. |
| `mutates` | no | false | Mark true when the recorded steps create or change data (a new suite, a key, a filed case). Orchestration such as a scheduled refresh runs these scenes after the read-only ones, so their side effects do not show up as drift on other screens. |
| `setup` | no | `[]` | Steps run before recording starts: log in, navigate, open the right screen. |
| `steps` | yes | | Recorded steps, at least one. |

## Steps

Every step has an `action`. Steps that target an element take `selector` and an optional `nth`
(0-based) when the selector matches more than one element. Any step may carry a `caption` of up
to 80 characters, shown while the step runs and until the next caption replaces it.

| Action | Fields | What the recorder does |
|---|---|---|
| `click` | `selector`, optional `button` | Highlights the element, moves the cursor to it, shows a click ripple, clicks. |
| `dblclick` | `selector` | Same choreography, double-click. |
| `hover` | `selector` | Moves the cursor onto the element without clicking. Use for menus and tooltips. |
| `fill` | `selector`, `text` or `text_env` | Clicks the field and sets its value at once. |
| `type` | `selector`, `text` or `text_env`, optional `delay_ms` | Clicks the field and types character by character (45 ms each) so the reader sees the entry. |
| `press` | `key`, optional `selector` | Presses a key (`Enter`, `Escape`, `Control+k`) on the element or the page. |
| `select` | `selector`, `value` | Picks an option in a native `<select>`. |
| `check` / `uncheck` | `selector` | Sets a checkbox or radio. |
| `scroll` | `selector` or `y` | Scrolls the element into view, or the page by `y` pixels. |
| `wait` | `ms` or `selector` (+ optional `state`) | Pauses, or waits until a selector is `visible` (default), `hidden`, `attached`, or `detached`. |
| `caption` | `text` | Shows a caption with no action; an empty string clears it. |
| `goto` | `url` | Navigates. The overlay is re-created on the new page; set the caption again afterwards. |

Recording a step adds the cursor travel (about 0.5 s), the ripple (0.16 s), the action itself,
and `settle_ms`. Three clicks and a short typed value land near 5 seconds; the validator prints an
`estimated_seconds` so you can see the length before recording.

## Selectors

Use Playwright selectors. Prefer role selectors copied from a snapshot, because they match what the
reader sees: `role=button[name="New suite"]`, `role=textbox[name="Suite name"]`,
`role=link[name="Runs"]`, `role=tab[name="Cases"]`. Other engines work when a role is missing:
`text=Suite created`, CSS such as `#save` or `[data-testid="suite-row"]`, and chains with
`>>` (`role=dialog >> role=button[name="Create"]`).

Selectors are strict: a selector that matches two elements fails with a "strict mode violation"
naming both. Add `nth`, scope with `>>`, or use a more specific name. Run `snapshot` on the exact
screen and copy the `suggested_selectors`; `snapshot.aria.yaml` holds the full tree for anything
the summary left out, and `snapshot --after-steps` shows the tree after the recorded steps have run.

## Secrets and logins

- `text_env` reads an environment variable at run time and is allowed only in `setup` steps.
  The validator rejects it in recorded steps, and rejects literal text typed into a field whose
  selector looks like a credential (`password`, `secret`, `token`, `api key`).
- For single sign-on or any interactive login, run
  `login --url APP_URL --out .notion-docs-auth/state.json` once; the recorder opens a headed
  browser, you log in, press Enter, and the session is saved. Point scenes at it with
  `storage_state`. Keep `.notion-docs-auth/` out of version control and out of the output bundle.
- Record against demo or seeded data. Nothing in the recorder blurs or masks content.

## Outputs

`record` writes into `--out`:

- `<name>.gif`: the clip, global 256-color palette, loops forever.
- `<name>.png`: the poster, the first recorded frame at GIF size.
- `<name>.last.png`: the final frame, for checking that the clip ends on the claimed result.
- `<name>.manifest.json`: `status`, `width`, `height`, `frames`, `duration_ms`, `bytes`,
  `recorded_ms`, and one entry per step with `status` and `duration_ms`.

| `status` | Meaning | What to do |
|---|---|---|
| `ok` | Every step ran, duration within `max_seconds`, file under 8 MiB. | Look at `<name>.last.png`, then use the clip. `ok` means the steps ran, not that the app did what the caption says. |
| `failed` | A step failed; `error` names it. `<name>.failed.png` shows the screen at failure, `<name>.partial.gif` what was recorded. | Fix the selector or the wait, or drop the clip. |
| `too_long` | Interaction ran past `max_seconds`. | Split the scene into two clips, or shorten the typed text and waits. |
| `too_large` | GIF above 8 MiB. | Lower `scale` or `fps`, or shorten the scene. |

Only `ok` clips go on the page.

## Checking scenes against a changed UI

```text
node "${CLAUDE_SKILL_DIR}/scripts/record_clip.mjs" check scenes/<name>.json --out checks [--baseline baselines/<name>.aria.yaml]
```

`check` logs in through `setup`, saves the screen's accessibility tree as `checks/<name>.aria.yaml`,
then runs the recorded steps without recording. Before each step that targets an element it
reports the selector's resolution: `ok` (one visible match), `hidden` (matches but not visible),
`ambiguous` (several matches and no `nth`), or `missing`. A step that cannot run is `failed` and
the steps after it `not_reached`. With `--baseline`, it also lists interactive elements (buttons,
links, fields, tabs, headings) that were added or removed since the baseline was saved, so a
renamed button or a new tab is visible without watching a clip.

`check` runs the steps for real, so a scene that creates data leaves it in the app. Mark such
scenes `mutates: true` and run them last; otherwise a suite created by one scene appears as an
added option on the next scene's screen and reads as drift.

The report `checks/<name>.check.json` carries `status`: `ok`, `drift` (steps resolve but the
screen's controls changed), or `broken` (a step is missing, ambiguous, or failed). Exit code 1
means `broken`. Save the new `.aria.yaml` as the next baseline once the page text has been
reviewed against it.

```text
node "${CLAUDE_SKILL_DIR}/scripts/record_clip.mjs" sheet --clips clips --out clips/sheet.png [--columns 2]
```

`sheet` lays out every `<name>.last.png` in a directory as one labelled image, for checking that
each clip ends on the state its caption claims.

## Troubleshooting

- *The clip ends on an error but the manifest says `ok`*: the final `wait` matched something that
  was already on the page (a row with the same name, a heading). Wait for a change that only the
  action can cause: `{"action": "wait", "selector": "role=dialog", "state": "hidden"}` after a
  Create, or a toast such as `text=Suite created`. Always check `<name>.last.png`.

- *Strict mode violation*: two elements match. Add `nth` or scope the selector.
- *Element is not visible / not attached*: add a `wait` with a selector before the step, or a
  `scroll`. If the element lives in a menu, `hover` or `click` the opener first.
- *A caption vanished after navigation*: `goto` and in-app route changes that reload the document
  reset the overlay. Add a `caption` step after the navigation.
- *The clip starts mid-animation*: add `{"action": "wait", "ms": 500}` as the first step, or
  move the opening navigation into `setup`.
- *No frames*: the page never painted (blank URL, blocked load). Check `url` and `setup` in a
  `snapshot` first.
