# notion-docs evidence record

Evidence tiers for the 0.1.0 release, following `docs/skill-authoring-notes.md`.

## Recorder: `objective`

`qa/test_notion_docs.py` pins, without a browser:

- scene validation and its named errors (slug, URL, viewport, unknown action, empty steps,
  wait with both `ms` and `selector`, missing storage state);
- the secrets rule: `text_env` only in setup, a literal value typed into a credential-looking
  field is an error in recorded steps and a warning in setup;
- `doctor` reports `ready: false` with the `setup` hint and writes nothing; `record` without
  Playwright exits 1 naming `setup` and writes no GIF;
- a PNG-to-GIF round trip decoded by an independent LZW/GIF decoder written in the test: frame
  count after duplicate merging, merged delays, loop count 0, exact pixels for frames within the
  palette, and a bounded error for a frame with more than 256 colors while a flat band stays exact.

## Manual recording (2026-10-07)

Against a local fixture page (sidebar, list, a `New suite` button that opens a dialog with a
`Suite name` field and a `Create suite` button, a toast, a prepended row), the scene in
`plugins/notion-docs/skills/notion-docs/templates/scene.json` minus the storage state recorded as:

| Measure | Value |
|---|---|
| Steps | 6, all `ok` |
| Interaction time | 6.0 s |
| GIF | 960×600, 34 frames, 7.9 s with the end hold, 755 KB, 256-color palette |
| Wall clock | 8.9 s including browser launch and encoding |

Chromium decoded the GIF (`naturalWidth` 960) and sampled frames at 0.3 s, 2.2 s, 4.2 s, and
6.5 s showed the cursor, the highlight ring on the focused field, the caption pill, and the final
held frame with the new row at the top of the list. An independent Python parser counted 34 image
descriptors, loop extension 0, delays from 50 ms to 1500 ms.

Grounding that shaped the recorder: Playwright's bundled ffmpeg exposes only `png` and `libvpx`
encoders, and no system ffmpeg was present, so frames are captured over the DevTools screencast
and the GIF is encoded in the script.

## Skill: `rubric`

`qa/evals/notion-docs/notion-docs.evals.json` holds five cases that run without a browser:
plan-and-scenes with validation, a static toggle that earns no clip, a literal password in a
recorded step, publishing with no connector or token, and an API-reference request outside scope.
Live results are not yet recorded; run `qa/run_evals.sh notion-docs/notion-docs` and append the
result here before claiming the routing or behavioral thresholds are met.

## First real use: a Test suites page (2026-10-07)

Subject: the **Test suites** feature of an internal evaluation tool, documented against its local
dev stack with seeded demo data. Login ran in unrecorded `setup` steps with the password read
through `text_env`. Three versions were published as child pages of one private draft page in
Notion; every version, scene, clip, manifest, and the critique live in that project's checkout
under `notion-docs-output/test-suites/` (untracked).

| Version | Clips | What changed |
|---|---|---|
| v1 | create-suite 9.4 s / 2.95 MB, file-case 7.0 s / 1.79 MB, read-results 6.3 s / 1.66 MB | first pass |
| v2 | same | jargon grounded at first use; step 2 and its caption rewritten to say only what the clip shows; step 3 split; run buttons named |
| v3 | create-suite 8.6 s / 2.72 MB, file-case 5.9 s / 1.76 MB, read-results 6.3 s / 1.66 MB, run-locally 6.4 s / 1.28 MB | Run locally dialog recorded; create clip at a 450 ms settle; file-case without the opening scroll; local-runs fact moved into the callout |

Right-sizing held: of five candidate interactions, the Schedule & alerts cadence click produced
no visible result on recording and became table text, and Run on CI was left to text because it
dispatches a real run. Two Save buttons and two Save changes buttons caused strict-mode failures
that the manifest named exactly; `nth: 0` fixed the one that mattered.

**Incident.** A re-recording of create-suite reported `status: ok` while its last frame showed
the dialog still open with `API error 409: slug already exists`; the scene's final wait had matched
the list entry left by the previous recording. Fixes shipped in 0.1.0: the recorder writes
`<name>.last.png`, SKILL.md and `references/scene-spec.md` require a final wait that only the
action can satisfy and a look at the last frame, and the manifest's `ok` is documented as "the
steps ran", not "the app did what the caption says". The connector's `suggested_markdown` shape
(`<image src="file-upload://…"></image>` with the caption as inner text) was verified by fetching
the pages back and recorded in `references/notion-delivery.md`.

## Second real use: an eleven-page onboarding handbook (2026-10-07)

Eleven onboarding pages for the same tool's new team members, blueprinted on the team's earlier
onboarding notes and written from the current app, its in-app manual, the repository docs, and a
sibling repository's eval-authoring skill. 22 clips (18 new, 4 reused from the Test suites page),
each 4 to 11 seconds, 37 MB in total, published under one private draft parent with cross-links
between pages.

What the final-frame check caught before publishing: a clip ending on an upstream 502 (the local
stack has no key for that service) under a caption promising the span tree, a caption that disagreed with an open
dropdown, and a closing Cancel that hid the state the caption described. Two scenes failed on
strict-mode and a missing control and were fixed from the manifest's error text alone. The pattern
"look at the last frame; end on a wait only the action can satisfy" held up as the single most
useful rule of the skill. Full record in that project's checkout under
`notion-docs-output/handbook/CRITIQUE.md`.
