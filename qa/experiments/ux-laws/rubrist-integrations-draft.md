# Skill arm, draft instructions

`/ux-laws review /integrations` under the first draft of the skill (before forced states, the
false-state ranking rule, and Also noticed). Recorded verbatim below; run notes trimmed.

---

# UX laws review: `/integrations` (Integrations page)

I read the code and clicked through the running demo at 1280px and 390px. File paths below are relative to the rubrist repository root.

**The screen.** A project owner comes here from Sidebar → Setup → Integrations, or from the trace-link page's "Integrations → Connect Ironside" link (`apps/web/src/screens/trace-link.tsx:191`). Their job is to connect the tracing platform that already records their runs, so traces start arriving for evaluation. The primary action is **Connect ‹platform›**, and Ironside gets the primary style. Afterwards they expect a verified connection and traces showing up in Live traces. *Assumed:* most visits are first-time setup, with occasional returns to test, import or rebind. I have no usage data.

### 1. A failed Connect shows raw validation JSON, and a URL typed without `https://` is rejected
- **What the user experiences:** If you type `api.smith.langchain.com/` or `ironside.example.com`, the dialog shows `[ { "code": "invalid_format", "format": "url", "path": [ "endpointUrl" ], "message": "Invalid URL" } ]`. If the Ironside host can't be reached, it shows only `fetch failed`.
- **Law:** Postel's law: a harmless variation (no scheme, a trailing slash) is refused instead of normalized. Peak-end rule: this is the worst moment of the screen's main job, and it gets the least polish.
- **Evidence:** URLs are only trimmed before sending (`apps/web/src/screens/integrations.tsx:465`, `:474`, `:481`). The client-side schema parse throws a ZodError whose message is that JSON (`apps/web/src/lib/api/integrations.ts:127`, `:179`; `endpointUrl: z.url()` at `packages/shared/src/integrations.ts:18`). It is shown verbatim (`integrations.tsx:486`, `:607`). The server answered `{"error":"fetch failed","code":"ironside_connection_failed"}` and only `error` reached the screen. Typed input is kept, which is good.
- **Fix:** In `submit()`, add `https://` when the scheme is missing and strip a trailing slash. Write the normalized value back into the field so the user sees what will be contacted. Catch `ZodError` and show "Enter a full URL, e.g. https://api.smith.langchain.com" under that field. Turn `ironside_connection_failed` into "Couldn't reach Ironside at ‹url›. Check the deployment URL." While pending, also label the button "Connecting…" (`:618-620`), as the card buttons already do. **Cost: small.**

### 2. "Import now" never says whether anything happened
- **What the user experiences:** You click Import now, the button flickers, and the card looks exactly as before. That happens whether the import was queued or refused.
- **Law:** Feedback loops: an async action with no success or error state, and no visible status for the thing the user cares about ("are my traces arriving?").
- **Evidence:** `triggerImport` awaits the call and throws away the `{queued, importJob}` result (`integrations.tsx:215-222`). In the demo the API returned 202 with `queued:false`, `status:"failed"`, `error:"Queue unavailable; LangSmith import was not enqueued"`, and the card was unchanged. The card shows Polling, Last tested and Connected (`:317-375`) but never the last pull. `fetchImportJobs` (`apps/web/src/lib/api/integrations.ts:112`) returns jobs with `sourceIntegrationId`, but no screen uses it. The app already handles this result elsewhere (`apps/web/src/screens/trace-link.tsx:205-208`, `role="status"` at `:219`).
- **Fix:** Reuse the trace-link pattern. Show a `role="status"` line next to Import now: "Import queued: up to 25 runs. They appear in Live traces" (with a link), or `importJob.error` in `text-signal`. **Cost: small.** Optionally, add a "Last pull" line to the card from the newest import job for that integration. **Cost: medium.**

### 3. A LangSmith or Langfuse connection that fails its test keeps polling, and only Disconnect stops it
- **What the user experiences:** The card shows ERROR ("LangSmith runs request failed: 403") next to "Polling every 300s" with a live Wi-Fi icon, and there is no Pause button.
- **Law:** Jakob's law, inside this product. On this same screen, the Ironside card sets the rule: pause polling at any time, and only enable it after a passing test. The other two providers' cards break that rule.
- **Evidence:** The polling toggle is rendered only for Ironside (`integrations.tsx:380-396`, with the test-first guard at `:385-388`). The update schema already accepts `pollEnabled` for LangSmith (`packages/shared/src/integrations.ts:26-29`), and Langfuse reuses it (`:73`). A demo PATCH worked. New connections start polling while still UNTESTED.
- **Fix:** Generalize `toggleIronsidePolling` to all three providers using the existing `updateLangSmithIntegration` and `updateLangfuseIntegration` functions, with the same guard. **Cost: small.**

### 4. Two Langfuse connections are indistinguishable
- **What the user experiences:** Both cards read "Langfuse · langfuse · https://cloud.langfuse.com" with the same date. The Disconnect confirm says `Disconnect Langfuse integration "Langfuse"?`, so the user has to remember which card is which project.
- **Law:** Recognition over recall: nothing on screen identifies the remote project.
- **Evidence:** `integrationName` falls back to the provider label (`integrations.tsx:41-44`). The Langfuse form has no name field (`:517-542`), and `LangfuseIntegrationInputSchema` has no `projectName` (`packages/shared/src/integrations.ts:60-69`). The confirm text is at `integrations.tsx:232`. *Assumed:* more than one connection per provider is uncommon but real.
- **Fix:** Store and show a non-secret identifier, either a public-key hint (`pk-lf-…1a2b`) or an optional "Name" field when connecting. Use it in the card title and in the confirm text. **Cost: medium** (shared contract, API and UI).

### 5. The same three Connect choices appear twice, in two different orders
- **What the user experiences:** On an empty page you see six Connect buttons. At 390px the header's four buttons wrap into two rows above the empty state, which repeats them.
- **Law:** Hick's law: the same action is offered in more than one place on one screen. Law of similarity: one repeated set, listed in two orders.
- **Evidence:** The header order is Ironside, Langfuse, LangSmith (`integrations.tsx:92-100`). The empty state's order is Ironside, LangSmith, Langfuse (`:126-134`).
- **Fix:** Use one `PROVIDERS` array for both lists. Render the header Connect buttons only when `integrations.length > 0`, so the empty state owns the first action. Keep Refresh. **Cost: small.**

**Already works:** Test connection shows "Testing…" and puts the result on the card (status chip plus the error under Last tested). The dialog keeps focus and keeps input after an error. Disconnect is set apart from the frequent actions and says past imports are kept. The empty state explains the page and offers the first action.

**Do first:** Finding 1. Normalize URLs and replace the raw error text, because it sits on the primary action every first-time user takes.

I can apply any of these fixes if you want. Tell me which ones.

## Run notes (trimmed)

Reached on the live demo at 1280 and 390: empty state; LangSmith, Ironside, and Langfuse
dialogs; a scheme-less URL producing the raw Zod error; an unreachable Ironside; a LangSmith
connection created untested, tested to a 403, and Import now with no visible result; a delayed
Connect captured by route; four cards including two identical Langfuse cards. Not reached: a
connected Ironside card, the multi-criterion polling button, the no-criterion states, and **the
list-load error state**. No repository file was changed.
