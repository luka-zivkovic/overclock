---
name: lessons-learned
description: Record corrections and failed approaches as durable, deduplicated lessons in .ai/memory/LESSONS.md, and surface them in later sessions so mistakes are not repeated. Use when the user corrects agent behavior ("no, use Y not X", "you made this mistake before", "I already told you this"), says "remember this for next time" or "add that to your lessons", when a tried approach failed with a diagnosed cause, or when asked "what lessons do you have for this project?". Do NOT use for ordinary requirement changes or new instructions (a changed spec is not a mistake), one-off contextual choices ("use port 4000 just for this test"), conversational disambiguation ("no, I meant the other file"), or anything containing secrets, tokens, or credentials.
---

# Lessons Learned

Turn corrections and diagnosed failures into durable lessons that future sessions actually see — a self-improvement loop that closes on its own.

User corrections evaporate when a session ends, so the same mistakes recur and the user has to repeat themselves. This skill keeps a deduplicated, evidence-counted ledger at `.ai/memory/LESSONS.md`, surfaces matching entries when relevant work starts, and promotes proven lessons toward CLAUDE.md — with user approval only.

Before any read or write under `.ai/memory/`, read `references/memory-contract.md` — it defines the LESSONS.md location, format, size cap, and safety rules. Never improvise the format.

## When to record

Record a lesson only for these signals:

- **Explicit correction of agent behavior** — "no, don't use X here, use Y", especially as a standing rule ("always", "in this project", "stop doing"). A repeated correction is the strongest signal.
- **Failed approach with a diagnosed cause** — something was tried, failed, and the why is understood well enough to state what not to retry.

Do NOT record:

- **Requirement changes** — "actually, return JSON instead of XML" is a changed spec, not a corrected mistake. Recording it would fossilize requirements as false "lessons".
- **One-off contextual choices** — "use port 4000 just for this test" applies once; persisting it would misfire later.
- **Conversational disambiguation** — "no, I meant the other file" corrects the conversation, not behavior.
- **In-the-moment preferences not confirmed as standing rules** — wait until the user repeats them.
- **Anything containing secrets, tokens, credentials, or personal data** — redact the secret (`<redacted: ...>`) and record the lesson without it, or decline to persist and say why. Hard rule from the contract, no exceptions. An explicit record request that happens to contain a secret ("note this down", "remember this") IS consent to record the redacted version: record immediately with the secret redacted and say so — do not bounce the request back as "should I save it without the secret?"; that makes the user repeat themselves.

When a signal is borderline (a preference that might be standing), ask: "Should I record that as a standing lesson for this project?" — one question beats a polluted ledger. An explicit "remember/note this" is never borderline.

## Record flow

1. **Read the contract**, then read `.ai/memory/LESSONS.md` if it exists. Missing or empty → create it from `templates/lessons.md` (read the template now; it includes the entry format and a worked example). Unparseable → treat as read-only evidence per the contract; tell the user before writing anything fresh.
2. **Dedupe by meaning, not string.** Compare the new lesson against every existing entry's When/Wrong/Right. "Use pnpm not npm" and "stop running npm install" are the same lesson. If it matches:
   - Increment **Count** and refresh **Last reinforced** in place. Update Evidence if the new occurrence is more specific. Never append a duplicate section.
3. **Conflicts: newest user statement wins.** If the new statement contradicts an existing lesson (the user changed their mind), update that lesson to the new position (reset Count to 1, note the reversal in Evidence) — do not leave two contradicting entries to fight.
4. **New lesson → append an entry** in the contract's format: a short imperative title, then **When** (trigger condition), **Wrong**, **Right**, **Evidence** (quote the correction or failure), **Count: 1**, **Last reinforced** (today). Make **When** a recognizable situation ("installing or adding JS dependencies"), not a vague topic ("packages") — surfacing depends on it.
5. **Respect the ~200-line cap.** If the write would exceed it, curate first: prune or merge the lowest-count, oldest entries. Never refuse to record, never silently drop a high-count lesson.
6. **Quote the recorded or updated lesson back** in conversation so the user can correct the record immediately.

## Promotion to CLAUDE.md

When an update brings a lesson to **Count ≥ 3**, it is proven enough for always-on context. After quoting the update, SUGGEST: show the exact line(s) that would be added to CLAUDE.md and ask for approval. Only edit CLAUDE.md after an explicit yes — CLAUDE.md loads every session, and silently editing the user's project memory breaks trust and the contract's write-safety rule. On approval, append minimally; note in the lesson's Evidence that it was promoted. On decline, drop it — do not re-ask on every reinforcement.

## Surfacing

Be honest about mechanism: this skill is routed by the user's message, so it cannot fire merely because a lesson's topic comes up. Lessons actually surface through these channels:

- **Within an active session:** once this skill is loaded (a correction was recorded, lessons were requested), keep LESSONS.md in mind for the rest of the session — when work matches an entry's **When** condition, quote that entry and follow its **Right** approach. Surface only matching entries; dumping the whole file is noise.
- **At session start (bundled hook):** the SessionStart hook in `hooks/hooks.json` (and documented in references/session-start-hook.md) injects the lesson count and an instruction to consult matching entries — the only channel that works without the user asking. It is pre-enabled when installed via the `learning-loop` plugin.
- **On warm resume (if you also run a resume/handoff skill):** the LESSONS.md format is tool-agnostic and documented in the contract, so any skill that restores prior session state can read it and surface relevant entries during its resume flow. The companion `session-memory` plugin's session-handoff skill does exactly this, and treats a lesson that contradicts a saved decision as the winner. This skill does not require that companion — surfacing degrades gracefully to the channels above without it.
- **On request** ("what lessons do you have for this project?"): present all entries, ordered by Count descending, with their Last reinforced dates.

Surfacing is read-only — never modify the file while merely consulting it.

## Reference files

- references/memory-contract.md — the storage contract. Read at the start of every flow, before touching `.ai/memory/`. Source of truth for location, entry format, size cap, and safety rules. Its LESSONS.md format is intentionally identical to the `session-memory` plugin's, so a ledger written here is readable there and vice versa.
- templates/lessons.md — fill-in-ready LESSONS.md skeleton with a worked example entry. Read when creating LESSONS.md for the first time or appending a genuinely new lesson; not needed for count increments or read-only surfacing.
- references/session-start-hook.md — the bundled SessionStart hook that surfaces the lesson count automatically at session start. Read when the user asks about automatic surfacing, hook setup, or a standalone (skill-without-plugin) install.

## Guidelines

- **Dedupe on meaning.** String matching misses rephrased corrections; a duplicated lesson splits its evidence count and undermines promotion.
- **Evidence makes lessons trustworthy.** Quote what actually happened — a lesson without evidence reads like an arbitrary rule and gets ignored.
- **Suggestion-only promotion.** The ledger is the staging area; CLAUDE.md is user territory.
- **Writes confined to `.ai/memory/`** (plus approved CLAUDE.md additions); no secrets; no auto-commit — the contract's hard rules.
- **When unsure whether something is a lesson, ask.** False positives pollute every future session; false negatives just wait for the repeat correction.
