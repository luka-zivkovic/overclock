# Skill arm, revised instructions

`/ux-laws review /integrations` under the revised skill: forced states, false states ranked
first, Also noticed, and states not checked. Recorded verbatim below with absolute repository
paths shortened; the screenshot table is trimmed to the states reached.

---

## UX laws review: Integrations (`/integrations`)

**The screen.** This is the Setup page where the project owner connects a tracing platform (Ironside, LangSmith or Langfuse), so Rubrist can import traces and send verdicts back. On the first visit the main action is connecting one platform. On later visits it is checking that imports are actually arriving, or starting one by hand. *Assumed, not from research:* how often owners come back.

The review used the code plus the running demo at 1280px and 390px. I forced error, partial-failure and slow responses by stubbing requests. Screenshot IDs [S#] are listed under Run notes.

### 1. A failed load says "No integrations connected yet"
- **What the user experiences:** If any one of the three list requests fails, the page shows a red "Internal error" banner. Under it is the first-use empty state with Connect buttons, even when the other two providers returned connections.
- **Law:** Feedback loops (the state checklist). A failed or partly failed load must never show the first-use empty state, and one failed request must not hide what the others returned.
- **Evidence:**
  - `apps/web/src/screens/integrations.tsx:64-68` uses `Promise.all`, so one rejection throws away every result. Line `:69` never runs, and `:115-136` then render the empty state from `[]`.
  - Seen with the Ironside list stubbed to return 500 while a LangSmith and a Langfuse connection existed [S17], and again with all three failing [S18].
  - The banner doesn't name which provider failed and has no Retry.
  - Following the empty state's prompt costs the user: reconnecting a provider overwrites the existing connection (finding 3).
- **Fix:** Switch to `Promise.allSettled` and keep the lists that loaded.
  - For each failed provider, show its own `SectionLoadError` (`apps/web/src/components/rubrist/load-error.tsx:54`), worded with `loadFailure()` (`apps/web/src/lib/load-error.ts:26`), with Retry.
  - Use `PageLoadError` (`load-error.tsx:10`) when all three fail.
  - Show the empty state only when all three succeed with zero rows.
  - Cost: small.

### 2. "Import now" looks the same whether the import was queued or refused
- **What the user experiences:** The button shows "Enqueuing…" and then goes back to "Import now". Nothing says whether anything was queued, so a refused import looks like a successful one.
- **Law:** Feedback loops (confirm success where the user is looking, show errors in place) and Doherty vs honesty.
- **Evidence:**
  - `integrations.tsx:215-222` waits for the import call and ignores the result.
  - When the queue is unavailable, the API answers 202 with `queued: false` and `importJob.status: "failed"` (`apps/api/src/routes/integration-administration.ts:283-291`). The client treats any 2xx as success (`apps/web/src/lib/api/integrations.ts:355`, `:388`, `:418`).
  - In the demo, Import now on the Langfuse card returned `"Queue unavailable; Langfuse import was not enqueued"`. The page afterwards [S14] looks the same as after a stubbed `queued: true` [S24].
  - The failed job is stored (`GET /api/import-jobs` lists it), but no web screen calls `fetchImportJobs` (`lib/api/integrations.ts:112`). So cards never show the result of any import, manual or scheduled.
- **Fix:** Read `result.queued`, as `apps/web/src/screens/trace-link.tsx:205-208` already does.
  - When it is false, show `result.importJob.error` in the card's `actionError`.
  - When it is true, show "Import queued · up to {pollLimit} runs" next to the button, with a link to Live traces.
  - Then add a "Last import" cell to each card from `fetchImportJobs`, filtered by `sourceIntegrationId` (status, imported count, error).
  - Cost: small for the first part; medium with the Last import cell.

### 3. A provider's Connect button stays after it is connected, and using it overwrites or fails
- **What the user experiences:**
  - With LangSmith already connected, the header still offers "Connect LangSmith". The dialog looks like a new connection, but saving silently replaces the existing key, project, endpoint and test result.
  - For Ironside, the dark primary button walks the user through creating a one-time credential, then fails with 409 "An Ironside connection already exists".
- **Law:**
  - Visual hierarchy and Von Restorff: on a returning visit, the one element that stands out is "Connect Ironside".
  - Hick and similarity: the empty state shows six Connect buttons in two different orders, Ironside/Langfuse/LangSmith in the header and Ironside/LangSmith/Langfuse in the card.
- **Evidence:**
  - `integrations.tsx:92-100` always renders all three buttons, and `:126-134` repeats them in the other order [S1].
  - Creating a connection upserts on (project, provider) in SQLite (`apps/api/src/storage/sqlite/integration-commands.ts:32`) and in Postgres (`apps/api/src/repository.pg/integration-repository.ts:126-133`).
  - Ironside answers 409 (`integration-administration.ts:549-553`).
  - Code only: the in-memory demo store adds a second row instead, so I could not see the overwrite live.
- **Fix:**
  - Show a header Connect button only for providers that have no connection.
  - Once any connection exists, make those buttons secondary (default style) instead of primary.
  - Drop the header copies while the empty state is showing, leaving one row in one order.
  - On a connected card, add "Replace credentials". It opens the same dialog titled "Replace LangSmith credentials", with a line saying the current key and test result will be replaced.
  - Cost: small to medium.

### 4. LangSmith and Langfuse start polling untested, and keep polling after a failed test
- **What the user experiences:** After Connect, the dialog closes onto an UNTESTED card already showing "every 300s". When the test then fails (ERROR, 401), the card shows the same Wi-Fi icon and "every 300s", with no way to pause.
- **Law:** Peak-end (the connect flow ends on an unverified state, although the dialog promised verification) and similarity (Ironside cards check and toggle polling; the other two cards, with the same layout, don't).
- **Evidence:**
  - The dialog says "Rubrist verifies the remote project before importing" (`integrations.tsx:512`). The LangSmith create route saves without contacting LangSmith (`integration-administration.ts:90-120`), and `onCreated` only reloads the list (`integrations.tsx:155-158`) [S10].
  - The polling cell ignores test status (`integrations.tsx:321-335`) [S14].
  - The polling toggle exists only for Ironside (`integrations.tsx:380-396`, gated at `:385`), although the update schemas accept `pollEnabled` for both other providers (`packages/shared/src/integrations.ts:26-31`).
- **Fix:**
  - Run the provider's test automatically right after create, and land on the card with its result.
  - Show Enable/Pause polling for all three providers, with the same "test must pass first" rule as Ironside.
  - After a failed test, show "every 300s · last test failed" in `text-signal`.
  - Make the dialog sentence true, or reword it.
  - Cost: small.

### 5. URL fields reject a host without `https://` and reply with raw validation JSON
- **What the user experiences:** Typing `api.smith.langchain.com` as the endpoint, or `ironside-app.example.com` in Set web URL, shows `[ { "code": "invalid_format", "format": "url", … } ]` in red.
- **Law:** Postel's law (accept harmless variations and normalize them) and feedback loops (the error should say what to do).
- **Evidence:**
  - The client validates with Zod before sending (`lib/api/integrations.ts:127`, `:153`, `:179`, `:192`), and the screen prints the error message as is (`integrations.tsx:486` and `:607`; for the web URL, `:281` → `:419`) [S4, S26].
  - The app already turns Zod errors into readable text for page loads (`lib/load-error.ts:27`).
  - Set web URL is the app's only `window.prompt` (`integrations.tsx:271`), so it cannot validate inline.
- **Fix:** When a URL field loses focus, trim it and add `https://` if no scheme was typed, and show the corrected value in the field before sending. Credentials go to this address, so the user should see the interpreted URL before Connect.
  - If the value is still invalid, show "Enter a full URL, like https://ironside.example.com" under that field.
  - Replace the prompt with an inline `Input` (`apps/web/src/components/ui/input.tsx`) and a Save button on the card.
  - Cost: small.

### Also noticed
- "Enable polling" is disabled, and its reason exists only as a hover tooltip, which touch users never see (`integrations.tsx:385-388`) [S26].
- A failed Ironside connect says only "fetch failed", with no hint to check the URL or the token (`integrations.tsx:486`, `:607`) [S9].
- While Connect checks the remote project, the button only greys out and never says "Connecting…" (`integrations.tsx:618-620`) [S21].

### States not checked
- A successful test and the green "connected" chip: no provider was reachable from the demo.
- Saving Pause polling, Set web URL and "Use selected criterion for polling" successfully.
- The Disconnect confirm and a failed disconnect.
- No criterion selected (Import now disabled, LangSmith/Langfuse connect blocked): read from code only (`integrations.tsx:406-407`, `:608-612`).
- Scheduled polling outcomes: the demo scheduler produced none.
- Dark mode, and a long list of connections.

What already works: the dialog keeps the input and shows server errors in place [S22], and Disconnect sits apart at the card's right edge with a confirm that says past imports are kept. A failed test also shows the provider's message on the card.

Do first: finding 1. Switching to `Promise.allSettled` with per-provider errors is small, and it stops the false empty state from prompting users to overwrite connections they already have.

Want me to apply any of these? Name the ones you want and I'll implement them in build mode.

## Run notes (trimmed)

States reached at 1280 and 390: first-use empty, slow first load, one of three lists failing
with 500 while two connections existed, all three failing, Refresh failing after a good load,
all three connect dialogs (idle, validation error, slow pending, server error, Ironside network
error), create success, test pending and failed, Import now pending, a failed enqueue
(`queued: false`) and a stubbed queued enqueue that looks identical, stubbed Ironside cards
(revalidation required, polling off), and Set web URL with a scheme-less value. Failures and slow
responses were forced by stubbing the page's requests in the browser. No repository file was
changed.
