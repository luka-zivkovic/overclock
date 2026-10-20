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
