# Baseline: no skill

Prompt: "Review the UX of one page in a real web app and tell the owner what to improve" (the
Integrations page at `/integrations`), with the same repository, demo instance, Playwright
access, and read-only rule as the skill arms. Recorded verbatim below; run notes trimmed to the
states reached.

---

# Integrations page (/integrations): UX review

## Summary

The page is clean and calm. The connect dialog is built well: focus lands on the first field, Tab stays inside the dialog, Escape closes it and focus goes back to the button that opened it. The problems come after you click a button. **The page often doesn't tell you what happened, and sometimes it tells you the wrong thing.** An import that never started looks the same as one that worked. A failed list request looks like "you have no integrations". A connection with a rejected key still looks like it is polling. Fix those first. After that, give each card one clear next step, and then reduce the header to a single connect entry point.

## Priority fixes

### 1. Action results are thrown away. "Import now" can fail with no sign at all. (Critical)

In the demo I clicked **Import now** on a LangSmith card. The API returned 202 with `queued: false`. The import job was recorded as `failed: "Queue unavailable; LangSmith import was not enqueued"`. The page showed nothing: no message, no change to the card (screenshot 13).

`triggerImport` (`screens/integrations.tsx` ~210–222) ignores the response and just reloads the list. The failure happened because the demo has no queue, but the UI bug is general: whenever `queued` is false, the user gets no signal.

There is also nowhere on the page to see what imports or sync-back have done. `fetchImportJobs` and `fetchFeedbackSyncs` exist in `lib/api/integrations.ts`, but no screen uses them. Meanwhile the Overview's Sync-back tile ("97%") links here with "open integrations →", and this page has nothing about sync-back. In the demo, Overview also says "1,248 traces imported" while this page says "No integrations connected yet". That is probably seed data, but it shows the gap.

**Fix:**
- Show the result inline on the card:
  - "Import queued: up to 25 runs."
  - "Import didn't start: the job queue is unavailable."
- Add an activity line to each card, built from the two endpoints that already exist: "Last import 3 min ago · 25 runs · 0 failed · Last sync-back …".

### 2. If one provider's list fails, the page wrongly says there are no integrations. (Critical)

`load()` uses `Promise.all` over the three provider lists (line 64). If any one request fails, all results are dropped. I made the Langfuse list return 500 in the browser. The page then showed a bare "Internal Server Error" banner **and** "No integrations connected yet" with three Connect buttons, even though two LangSmith connections existed (screenshot 23). That invites duplicate connections.

**Fix:**
- Use `Promise.allSettled`. Show whatever loaded and name the provider that failed: "Couldn't load Langfuse connections. Retry".
- Never show the empty state while any list request has errored.

### 3. "Connect" doesn't check the connection, but the copy says it does. (High)

- **Saved without a check.** LangSmith and Langfuse connections are saved straight away as **UNTESTED**, with polling already on every 300s (screenshot 10). With a bogus key I only found out after clicking **Test connection** separately, and that button is the least prominent one on the card.
- **Copy for the wrong provider.** The dialog text says "Rubrist verifies the remote project before importing settled trace versions and sending assessments" (line 512). That is shown for all three providers. Neither the verification nor "settled trace versions" applies to LangSmith or Langfuse; both are Ironside concepts.

**Fix:**
- Run the existing test endpoint as part of Connect and keep the dialog open until it finishes.
  - On success: "Found runs in atlas-support-prod."
  - On failure: keep the fields filled in and show the reason.
- If you keep the current flow, make **Test connection** the primary button on untested cards. Either way, write the dialog copy separately for each provider.

### 4. Card actions don't follow the card's state. (High)

- **Import now looks like the main action even when it can't work.** On an ERROR card (403) and on an Ironside REVALIDATION REQUIRED card, Import now is still enabled and is the only outlined button (screenshots 14, 22). For revalidation the server will refuse it ("must be tested successfully before importing"). The card never says what to do next.
- **Polling looks active on a broken connection.** The ERROR card still shows a Wi-Fi icon and "every 300s", which reads as running and healthy.
- **No pause for LangSmith or Langfuse.** Only Ironside has a pause button. The API accepts `pollEnabled`, `pollIntervalSeconds` and `pollLimit` for all three providers.
- **No way to fix credentials.** The Ironside API supports changing the URL and API key in place (keeping the import position when it is the same project), but the UI has no control for it. For LangSmith and Langfuse the only option is to disconnect and reconnect.

**Fix: one primary action per state.**

| State | Primary action | Guidance on the card |
|---|---|---|
| Untested | Test connection | |
| Error | Update credentials | Then test again |
| Revalidation required | Re-test | "Ironside now reports a different project. Re-test to confirm, or disconnect." |

- Disable Import now unless the last test passed, and give the reason in the tooltip.
- Add a pause toggle for every provider.
- Add an Edit dialog that reuses the connect form.

### 5. Error messages are raw, small, and not read out to screen readers. (High)

- **Raw validation output.** A URL typed without `https://` shows the raw Zod issue array in three places: the Ironside deployment URL (screenshot 06), the LangSmith endpoint (41) and Set web URL (40). It looks like `[ { "code": "invalid_format", … "message": "Invalid URL" } ]`. It comes from the client-side `Schema.parse` in `lib/api/integrations.ts`.
- **Unhelpful network messages.** An unreachable Ironside shows only "fetch failed" (05). A rejected key shows "LangSmith runs request failed: 403" (12).
- **Placement and size.**
  - Card errors are 10.5px mono, the smallest text on the card.
  - Errors from card actions appear in the action row. On a phone that puts them right next to Disconnect, so they read as if they belong to it (32).
- **Screen readers.** Card action errors have no `role="alert"` or `aria-live`, so screen-reader users won't hear them.

**Fix:**
- Validate URLs per field. Accept a missing scheme by adding `https://`.
- Translate known failures:
  - "Couldn't reach https://ironside.invalid. Check the URL and that Rubrist's server can reach it."
  - "LangSmith rejected this API key (403). Check the key has access to atlas-support-prod."
- Show card errors next to the status chip, in body-size text, inside a live region.

### 6. Too many Connect buttons, and the wrong one is primary. (Medium)

- **Six buttons, two orders.** The empty state shows six Connect buttons: three in the header and three in the body. The order differs: the header has Ironside, Langfuse, LangSmith; the body has Ironside, LangSmith, Langfuse (screenshots `_integrations_1440`, `_integrations_390`). On a phone the header buttons wrap into two ragged rows.
- **Primary doesn't match the project.** This project is "LangSmith Support Agent" (`traceProvider: langsmith`), yet **Connect Ironside** is the filled primary button everywhere.
- **Ironside can be "connected" twice.** Connect Ironside stays available after an Ironside connection exists. The server only rejects it after the user has filled in the form ("An Ironside connection already exists…").

**Fix:**
- Use one "Connect a source" button in the header, opening a picker with a one-line description per provider.
- In the empty state, show provider tiles and hide the header buttons.
- Make the project's own provider the default.
- Disable Connect Ironside once one exists, with the tooltip "One Ironside connection per project. Edit the existing one."

### 7. Cards are hard to tell apart and to scan. (Medium)

- **Duplicate titles.** A LangSmith connection without a project name is titled "LangSmith · langsmith". Two of them look identical. The disconnect confirmation then says `Disconnect LangSmith integration "LangSmith"?` for either one.
  - Show a distinguishing detail, such as the key suffix and "default project".
  - Say which project gets imported when the name is blank.
- **Order.** Cards are sorted newest first, so broken connections end up at the bottom. Sort the ones that need attention to the top.
- **Formatting.**
  - "every 300s" should read "every 5 min".
  - "10/20/2026, 7:46:24 PM" works better as "Tested 2 min ago", with the full time in a tooltip.
  - The lowercase mono "· langsmith" repeats the title.
- **Unexplained criterion text.**
  - "polling selected criterion" doesn't name the criterion. Use something like "Imports judged by Support Answer Quality v1.2.0".
  - "Use selected criterion for polling" doesn't say what is being replaced. Use "Switch imports from v1.1 to Support Answer Quality v1.2.0".

### 8. Smaller items (Low)

- **Native browser prompt for Set web URL.** It has no validation, loses what you typed when the save fails, and doesn't match the custom dialog. Move it into the Edit dialog from item 4.
- **Ironside dialog terminology.** The text says "Integration credential" and "one-time token", but the field is labeled "API key". The text also mentions the URL first, while the form asks for the key first. Pick one name and match the field order.
- **No explanation for a disabled Connect button.** Nothing marks which fields are required. While a submit is in progress the button stays labeled "Connect" (only greyed out). Use "Connecting…".
- **No confirmation after Disconnect.** The card just disappears. A short "Disconnected atlas-support-prod. Past imports kept." would help.
- **Small buttons and type on phones.** Buttons are 28px tall at 390px width. That meets the WCAG 2.2 AA 24px minimum but is tight for touch. Key details are set in 10–11px mono.

## What works well

- **Dialog keyboard handling** is correct: focus on the first field, Tab stays inside, Escape closes, focus returns to the trigger.
- **The forms are thoughtful:** secrets are masked; optional fields are labeled; the Ironside web URL helper text explains when the field is needed and what it falls back to; the disconnect confirmation reassures that "past imports are kept".
- **Ironside quarantine is visible:** the REVALIDATION REQUIRED chip shows, and Enable polling is disabled with a tooltip giving the reason.
- **Layout holds up:** it reflows cleanly at 820px and 390px with no horizontal scroll, and dark mode works.

## Suggested order of work

1. Items 1 and 2: make sure the page never shows a false state.
2. Items 3 and 4: test on connect, and one primary action per card state.
3. Item 5: readable error messages.
4. Items 6 and 7: header and card polish.

## Run notes (trimmed)

Reached on the live demo: empty state at 1440 and 390; all three connect dialogs; Ironside
filled, submitting, unreachable, and scheme-less URL errors; LangSmith scheme-less URL; a
LangSmith connection created untested, testing, failing with 403, and Import now with no
feedback; several cards at 1440, 820, and 390; Disconnect; dark mode. Simulated by intercepting
the page's GET requests: a healthy Ironside card, a revalidation-required card, one provider list
returning 500, a slow first load, a refresh with data loaded, an inline action error on a phone,
and Set web URL with an invalid value. Not reached: a real successful test or import, and the
no-criterion state. No repository file was changed.
