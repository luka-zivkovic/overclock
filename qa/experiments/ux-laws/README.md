# ux-laws author-run verification

- **Date:** 2026-10-20.
- **Evidence tier:** `rubric` for the committed live suite; this record is author-run evidence
  judged by the authoring session, not a blind comparison, and it covers review mode on one page.
- **Target:** Rubrist (`luka-zivkovic/rubrist` at `78dcecc`), web app route `/integrations`
  (`apps/web/src/screens/integrations.tsx`). No earlier Rubrist UX audit round covered this page.
- **Setup:** two isolated demo instances (in-memory data, auth off) so arms could not see each
  other's state. Each arm was a fresh general-purpose agent with the same repository, Playwright,
  screenshot helper, and read-only rule. The skill arms were told to read `SKILL.md` and follow
  it as if the user had typed `/ux-laws review /integrations`; the baseline got a plain request
  to review the page's UX. The Rubrist working tree stayed clean in every run.

## Runs

| Run | Instructions | Record |
|---|---|---|
| Baseline | no skill | [rubrist-integrations-baseline.md](rubrist-integrations-baseline.md) |
| Draft | first draft of `SKILL.md` | [rubrist-integrations-draft.md](rubrist-integrations-draft.md) |
| Revised | forced states, false states first, Also noticed, states not checked | [rubrist-integrations-revised.md](rubrist-integrations-revised.md) |

## Findings checked against source

Every row below was checked by the author against the cited code or a screenshot.

| Problem | Baseline | Draft | Revised |
|---|---|---|---|
| One failed provider list renders "No integrations connected yet" (`Promise.all`, `:64`) | ranked 2 | missed (state not reached) | ranked 1, forced by stubbing |
| Import now discards `queued: false`; success and refusal look identical | ranked 1 | ranked 2 | ranked 2 |
| Reconnecting a provider silently overwrites the existing connection (upsert on project and provider) | missed | missed | ranked 3, from storage code |
| LangSmith and Langfuse poll while untested or failing, with no pause | yes | ranked 3 | ranked 4 |
| Dialog promises verification that LangSmith and Langfuse never do (`:512`) | yes | missed | yes |
| Scheme-less URL rejected with raw validation JSON | yes | ranked 1 | ranked 5 |
| Six Connect buttons in two orders; Ironside primary even when connected or wrong for the project | yes | ranked 5 | yes |
| Connect never says "Connecting…"; Ironside failure says only "fetch failed" | yes | yes | Also noticed |
| Disabled Enable polling explains itself only in a hover tooltip | missed | missed | Also noticed |
| Card errors not announced, 10.5px, placed beside Disconnect on phones | yes | missed | missed |
| Import now still enabled on error and revalidation cards | yes | missed | missed |
| Formatting and copy polish (every 300s, timestamps, criterion wording, sort order) | yes | missed | missed |

**Demo artifact.** The baseline (item 7) and the draft (finding 4) both reported two
indistinguishable connections of one provider. That cannot happen outside the in-memory demo:
both storage backends keep one connection per project and provider. The revised run read the
storage code, marked its observation code-only, and did not report it. The added honesty rule
(check demo behavior against real storage before reporting it) records that lesson; existing
case 0's "no finding is contradicted by the code" expectation covers the general principle, so
no new live case was added for it.

## Reading

- The draft was precise (every finding valid, exact lines, sized fixes, one fix to do first) but
  found less than the baseline, and missed the most serious problem because it skipped states the
  demo would not show. That drove the forced-state and false-state-first rules and the sixth live
  case.
- The revised run matched the baseline on the top problems, added one high-severity problem the
  baseline missed (silent overwrite), avoided the demo artifact both earlier runs reported, and
  proposed fixes in Rubrist's own components (`PageLoadError`, `SectionLoadError`,
  `loadFailure`).
- The baseline remains broader on accessibility and polish. The five-finding cap and three
  Also noticed lines trade that breadth for a ranked, actionable list; whether that trade is right
  for the user is not settled by one page.
- Not established: build mode, other pages or apps, blind judging, repeated runs, or live-suite
  results.

## Build round (2026-10-20)

- **Request, identical for both arms:** show on each connection card of `/integrations` what its
  imports have actually done, using the existing `fetchImportJobs` client, web app only.
- **Setup:** two git worktrees of Rubrist at `78dcecc`, each with its own demo instance. The
  baseline got the request as written; the skill arm got it as `/ux-laws build …` and read
  `SKILL.md` (revised version, including the demo-data rule). Neither committed.
- **Verification:** both builds pass `pnpm --filter @rubrist/web typecheck` and the full web suite
  when rerun by the author (baseline 91 files and 640 tests, skill 90 files and 636 tests).
- **Screens:** one harness stubbed identical integrations and import jobs for both builds and
  captured five states. Side-by-side images (baseline left, skill right) are in
  [build-screens/](build-screens/): mixed history, phone width, no imports, import history
  failing, and import history still loading.
- **Observed differences:** the skill build leads each card with the answer ("25 new traces
  arrived 11 min ago") and keeps history behind a closed disclosure; the baseline places the
  section below the existing facts and lists every recent import. On a failed history request the
  skill build offers one page-level Retry; the baseline shows an error on each card with no retry.
  The skill build also changed the provider lists to load independently (the false empty state
  from the review round), which the request did not ask for; it flagged that itself.
- **Blind judgment:** a fresh agent saw only the two diffs and the five screenshots per build,
  under randomly assigned labels, and was told not to read anything that could identify the
  authors. It chose the skill build overall with medium confidence, winning five of seven criteria
  (answering "are traces arriving?", clarity, recovery, phone layout, fit with the app's own
  components). The baseline won code risk and, narrowly, honesty of states.
- **The baseline's advantages, verified by the author:** it marks a queued or running import
  older than 15 minutes as stuck and stops polling (`STALE_IN_FLIGHT_MS`), while the skill build
  refreshes every 5 s for as long as a job stays in flight. The skill build's screen test reads the
  real clock and asserts "started 15s ago", so it can fail intermittently; the baseline uses fake
  timers. The baseline also stayed strictly inside the request.
- **Changes after this round:** the state checklist now gives pending an upper bound (stuck after
  its expected time, say what to check, stop automatic refreshing), with live case 6, and build
  mode now offers problems outside the request instead of fixing them unasked, added to case 2's
  process expectation. Neither change has been rerun against Rubrist.

## Redesign round: Loadout (2026-10-20)

- **Target:** Loadout (`luka-zivkovic/loadout` at `b4600a4`), the My devices page (`/devices`,
  `Devices` in `web/Views.tsx`): connect and approve were split into unrelated panels, CLI steps
  showed before any device existed, and a member arriving from the CLI's `/devices?code=` link
  found the prefilled code below the fold under "No devices connected".
- **Request, identical for both arms:** redesign the whole screen (layout, order, copy, and
  components may all change), keeping the visual language and existing API calls, web only.
  Builds used the latest skill, including the scope and pending-bound rules.
- **Setup:** two git worktrees, each with its own server and data. One harness then started a
  fresh instance per build, claimed the same admin, ran a real `team login` from the CLI, captured
  seven states, approved the real code through the API, and confirmed the CLI reported
  "Connected" for every build. Three-column images (original, without skill, with the skill) are
  in [redesign-screens/](redesign-screens/).
- **Verification:** the author reran both builds: `npm run check` passes and `npm test` passes
  72 of 72 for each. The baseline changed 5 files (+1,021/−366); the skill build changed 3
  (+1,328/−351).
- **Blind judgment:** the same protocol as the build round, with the original screens as a shared
  "before". The judge also applied each patch to a scratch copy and type-checked it. It chose the
  skill build with **low** confidence, splitting the eight criteria 3–3 with two ties. The skill
  build won arriving from the CLI link (Approve above the fold on desktop and at the fold on
  phone, versus a scroll), honesty of states (slow, stale-list, and stalled states; expired codes
  hide Approve), and phone layout. The baseline won the first visit (a vertical, tagged step list
  where the skill's two columns put an empty code box at top right), the returning member, and fit
  with the visual language. Copy and code quality tied.
- **Both are clearly better than the original**, per the judge: one guided flow with approval in
  place replaces the separate dialog and side panel.
- **Verified by the author:** the skill build adds 18 `useState` flags to `Views.tsx` against the
  baseline's 5 and sorts errors by regex on the server's message text (`Views.tsx:1081`); the
  baseline's step 1 falls back to "Loading instructions…" if instructions fail, and only the skill
  build uses `preventScroll` when moving focus.
- **Change after this round:** build mode now models a flow's states as one explicit value with
  named steps and branches on codes or statuses, not message text, with case 2's state
  expectation extended. Not yet rerun.

## Can it redesign a whole bad screen?

On this evidence, yes for one screen at a time: both arms rewrote the page's structure, flow,
states, and copy within the existing visual language, and both results beat the original. The
skill's edge over a strong plain request was small here (a low-confidence win), concentrated on
the most common path and on honest states, and it cost code complexity. Outside what was tested:
a multi-screen or navigation redesign, and a visual-identity overhaul, which the skill
deliberately leaves to the project's style and to visual-design tools.
