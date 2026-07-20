---
name: solutions
description: "Capture a verified solution to a nontrivial problem in .ai/memory/SOLUTIONS.md — symptoms, what didn't work, the fix, and why it works — and reuse it when the same symptoms come back. Use when a hard problem is confirmed solved after real diagnostic effort or failed attempts ('that worked', 'it's fixed', 'finally — that was it') , when the user says 'capture this solution' or 'save this fix for next time', when starting on a problem whose symptoms might match a previously captured solution ('have we hit this before?'), or when asked to review or clean up the solutions ledger. Do NOT use for trivial or one-line fixes, routine feature completion, an unverified 'this should work', corrections of agent behavior or workflow rules (that is lessons-learned territory), or one-off environmental flukes that carry no reusable diagnosis. Secrets are never persisted; capture requests containing secrets record only the redacted solution."
---

# Solutions

Capture what actually fixed a hard problem, so the next time its symptoms appear the diagnosis
is a lookup instead of a re-derivation.

Solved problems evaporate the same way corrections do: the fix ships, the session ends, and
three weeks later the same symptoms cost the same investigation — including re-trying the same
dead ends. This skill keeps a deduplicated ledger at `.ai/memory/SOLUTIONS.md` whose entries
lead with symptoms (the retrieval key) and always record what did NOT work.

Before any read or write under `.ai/memory/`, read `references/memory-contract.md` — it defines
the SOLUTIONS.md format, size cap, ownership, and safety rules shared with the session-handoff
and lessons-learned skills. Never improvise the format.

## Boundary with lessons-learned

One question routes the content: **is this about the project, or about how to work?**

- A solved project problem — symptoms, root cause, fix — is a **solution** (this skill).
- A correction of agent behavior or a standing workflow rule ("stop using npm", "always run
  the linter first") is a **lesson** (lessons-learned).
- A dead end hit while solving goes inside the solution's **What didn't work** line, not as a
  separate lesson — unless the user also corrected how the agent worked, in which case both
  skills apply to their own halves.

## Capture flow

Fires when a nontrivial problem is confirmed solved: the fix is verified (test went green,
behavior observed correct), and the road there involved real diagnosis or failed attempts. A
trivial fix that took one obvious edit is a silent no-op — capturing it would bury the ledger.

1. **Read the contract**, then `.ai/memory/SOLUTIONS.md` if it exists. Missing → create from
   `templates/solutions.md` (read it now; it is fill-in-ready). Unparseable → read-only
   evidence per the contract; tell the user before writing fresh.
2. **Dedupe by root cause, not wording.** Compare against existing entries' Symptoms and Why
   it works. Same root cause and same fix → update that entry in place (refresh **Date**,
   enrich Symptoms/What-didn't-work with the new occurrence); never append a duplicate. Same
   symptoms but a genuinely different cause → new entry whose Symptoms line names the
   distinguishing detail.
3. **New entry → append** in the contract's format: a problem-shaped title, **Symptoms**
   (observable failure — exact error text beats a paraphrase), **Context** (module, stack, the
   situation where this applies), **What didn't work** (each failed attempt with why, when
   diagnosed), **Solution** (the fix, concrete), **Why it works** (the root cause the fix
   addresses), **Verified** (how the fix was confirmed), **Date**. Make Symptoms the sharpest
   line — retrieval matches on it.
4. **Redact before writing.** Secrets, tokens, connection strings, personal data → `<redacted:
   ...>` per the contract's hard rule. An explicit capture request containing a secret is
   consent to record the redacted version immediately — do not bounce the request back.
5. **Respect the ~250-line cap.** Curate before exceeding: merge overlapping entries, retire
   the oldest ones whose Context no longer exists. Never silently drop a recent entry.
6. **Quote the recorded or updated entry back** so the user can correct it immediately.

## Retrieval flow

Fires when work starts on a problem whose symptoms might already be in the ledger, or the user
asks "have we hit this before?".

1. Read `.ai/memory/SOLUTIONS.md` (read-only — never modify while consulting).
2. Match the current symptoms against entries' **Symptoms** and **Context**. Quote a matching
   entry, including its What-didn't-work line — skipping known dead ends is half the value.
3. **Verify before applying.** A stored solution describes the codebase as it was on its Date.
   Check the cited context still exists and the fix still fits; where the entry's Verified line
   names a test, prefer re-running it. A solution that no longer matches reality is a refresh
   candidate (below), not something to force-apply.
4. No match → say so briefly and proceed normally; never stretch a non-matching entry to fit.

## Refresh flow — suggestion-first

Fires on request ("clean up the solutions file") or when retrieval hits an entry that no longer
matches the codebase. Never runs silently in the background.

1. For each entry under review, check its Context against the current tree and propose exactly
   one outcome: **Keep** (still accurate), **Update** (code moved or the fix evolved — show the
   corrected entry), **Merge** (overlaps a sibling — show the merged entry), or **Retire**
   (implementation and problem domain are gone — delete; git history is the archive).
2. Present the proposals and apply only what the user approves. Match the ledger to reality,
   never the reverse — refreshing documents the code; it never edits code.

## Reference files

- references/memory-contract.md — the shared storage contract. Read at the start of every flow,
  before touching `.ai/memory/`. Source of truth for location, entry format, size cap,
  ownership, and safety rules.
- templates/solutions.md — fill-in-ready SOLUTIONS.md skeleton with a worked example entry.
  Read when creating the file or appending a genuinely new entry.

## Guidelines

- **Symptoms are the index.** A vague Symptoms line ("build issues") makes the entry
  unfindable; quote the error.
- **What didn't work is first-class.** It is the line that stops the next session from burning
  an hour on the same dead end.
- **Verified or it isn't a solution.** "Should work" never enters the ledger.
- **Writes confined to `.ai/memory/`; no secrets; no auto-commit** — the contract's hard rules.
- **When unsure whether a solve is ledger-worthy, ask** — one question beats a ledger full of
  trivia, and an explicit "capture this" is never borderline.
