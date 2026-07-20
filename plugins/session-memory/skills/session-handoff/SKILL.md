---
name: session-handoff
description: Save and restore working state across Claude Code sessions via a structured HANDOFF.md under .ai/memory/. Use when the user wants to stop and preserve state ("let's stop here for today", "checkpoint this session", "write a handoff", "I'm about to run out of context, save our state") or to restore it ("resume where we left off", "continue from last session", "what were we working on?"); also use when the user has no local handoff file but pastes or says they copied a handoff from another machine. Produces a handoff file with goal, plan, decisions, failed approaches, next steps, and git anchors, plus a warm-start brief on resume. Do NOT use for ordinary git commit/push requests, for "continue" meaning the next step of the current in-conversation task, or for human-facing summaries like PR descriptions or status reports.
---

# Session Handoff

Capture working state when a session pauses; restore it warm when work resumes.

Claude Code sessions are stateless — closing a session or hitting compaction loses in-flight plans, decisions, and failed attempts, so the next session starts cold and repeats work (including re-trying approaches that already failed). This skill writes a structured handoff at pause time and verifies it against reality at resume time.

Before any read or write under `.ai/memory/`, read `references/memory-contract.md` — it defines file locations, formats, size caps, archive rules, the precedence rule, and safety rules shared with the lessons-learned skill. Never improvise the format.

## Trigger discipline

- "Continue" / "resume" referring to the task already in flight in this conversation is NOT a resume-from-disk request. Only restore from disk when the user refers to a previous session or asks what was being worked on.
- "Commit this" / "push" is git workflow, not session state.
- Checkpointing is user-initiated or at natural milestones (a phase finished, about to attempt something risky, context running low) — never continuous, never every few minutes.

## Save flow

Run when the user asks to stop, checkpoint, or save state.

1. **Read the contract** (`references/memory-contract.md`) so the location, format, and caps are exact.
2. **Capture git anchors** — these make staleness detectable at resume:
   ```bash
   git branch --show-current && git rev-parse --short HEAD && git status --porcelain
   ```
   Non-git project: record today's date and mtimes of the key files instead.
3. **Archive any existing handoff.** If `.ai/memory/HANDOFF.md` exists, move it to `archive/HANDOFF-<timestamp>.md` per the contract (retention: last 5). Never silently overwrite — the old handoff may be the only record of a concurrent session's work.
4. **Write the new HANDOFF.md** from `templates/handoff.md` (read the template now; it is fill-in-ready). Fill every section from the actual conversation:
   - **Current goal** — what we are ultimately trying to achieve, one or two sentences.
   - **Plan** — each step with status (done / in-progress / todo). Mid-task save: mark the in-progress step and note exactly where in it work stopped.
   - **Decisions** — each with its rationale and a provenance label: `[user-directed]` (the
     user stated the choice), `[user-approved]` (proposed in-session, examined and accepted by
     the user), or `[agent-proposed]` (not yet examined by the user). A decision without its
     why gets re-litigated next session. Never label the agent's own unexamined proposal as
     user-directed or user-approved.
   - **Failed approaches** — what was tried, why it failed, and what ruled it out. This is the highest-value section: it is the only thing preventing the next session from burning time on the same dead ends.
   - **Open questions** — unresolved unknowns, including anything awaiting the user.
   - **Next steps** — concrete first actions for the next session, specific enough to start cold.
   - **Key files** — paths touched or central to the work.
   - **Environment anchors** — the git data from step 2 plus the save date.
5. **Redact before writing.** Scan for secrets (API keys, tokens, passwords, env var values in error output) and replace with `<redacted: ...>`. Never auto-commit; writes stay inside `.ai/memory/`.
6. **Confirm to the user** — one line stating where the handoff was saved and what it covers.

Stay within the ~150-line cap: compress decisions prose first, never drop failed approaches or anchors.

## Resume flow

Run when the user asks to resume, continue from a past session, or asks what was being worked on.

1. **Read the contract**, then look for `.ai/memory/HANDOFF.md` at the repo root.
2. **No file or empty file → cold start.** Say plainly that no saved session state exists, and offer to start tracking from now on. Never fabricate prior context — a confident invented "we were working on X" is worse than admitting a cold start. Exception — **pasted handoff**: if the user pastes handoff content into chat (switched machines, recovered from scrollback, another tool), accept it: use the sections that exist, name the ones that are missing, treat its anchors as unverifiable (handle per step 4's rewritten-history rule), and offer to write it to `.ai/memory/HANDOFF.md` (archiving any existing file first). If a pasted handoff and the file on disk disagree, the pasted one is newer input — say so and ask which to trust.
3. **Unparseable or hand-edited file** (missing/unknown `memory-schema` marker, mangled sections) → treat it as read-only evidence: quote what is salvageable, tell the user the file did not match the expected format, and do not rewrite or overwrite it without their say-so.
4. **Verify anchors against current reality:**
   ```bash
   git branch --show-current && git rev-parse --short HEAD && git status --porcelain
   ```
   Compare with the handoff's Environment anchors. On mismatch, quantify the drift — e.g. "branch moved from `feat/auth` to `main`", "12 commits since the handoff (`git rev-list --count <saved-sha>..HEAD`)", "key file `src/auth.ts` no longer exists". Drift means the saved plan may no longer be true: warn and re-verify the affected steps instead of blindly executing the old plan.
   - **Rewritten history:** if the saved sha is unreachable (`git cat-file -e <sha>` fails or `rev-list` errors — rebase, force-push, shallow clone), say so explicitly, fall back to `git log --oneline --since=<saved date>` for a picture of what happened, treat ALL Plan step statuses as unverified, and get explicit user confirmation before executing any step of the saved plan. Never read an unreachable sha as "no commits since the handoff".
   - **Staleness threshold:** if the handoff is more than ~14 days old or more than ~30 commits behind, do not attempt line-by-line reconciliation — state explicitly that the handoff is too stale for that. Report the gap, quote the handoff's goal/decisions/failed-approaches as background, and RECOMMEND a fresh start (archiving the old handoff) as the default, naming full reconciliation only as the alternative if the user insists. Do not present "resume as planned" as the leading option for a stale handoff.
5. **Surface lessons and solutions.** If `.ai/memory/LESSONS.md` exists, read it and quote the entries whose **When:** condition matches the work being resumed (read-only). If a lesson contradicts a handoff Decision, the lesson outranks it — flag the conflict in the brief, don't silently pick. If `.ai/memory/SOLUTIONS.md` exists, also surface (read-only) any entry whose **Symptoms**/**Context** match the resumed work — fold it into the same Drift & lessons line; a stored solution is applied only after verifying its context still exists (current source outranks it).
6. **Return the warm-start brief** in exactly this six-line shape and order. For a resume request,
   these six lines are the entire user-facing response: no preamble, verification report, code
   fence, blank lines, extra sections, recommendations after the brief, or reordered labels.
   Fold drift, stale-state choices, missing sections, and fresh-start advice into the labeled
   values. Compress values rather than wrapping the structure; use `none recorded` / `none found`
   when a field has no content:
   Goal: ...
   Plan status: ...
   Decisions in force: ...
   Do-not-retry: ...
   Drift & lessons: ...
   Proposed next step: ... Confirm?
7. **Confirm direction before acting.** The brief ends with the proposed next step and a question — the user may have changed direction since the save. Do not start executing until they confirm.

## Auto-load at session start (optional hook)

This skill fires when the user asks; it cannot fire merely because a handoff exists on disk. A SessionStart hook closes that gap by mentioning a parked handoff (and lesson count) automatically at session start — see references/session-start-hook.md (bundled and pre-enabled when installed via the session-memory plugin; a copy-paste settings.json snippet for standalone installs). Without it, resume happens only on request.

## Reference files

- references/memory-contract.md — the shared storage contract. Read at the start of both flows, before touching `.ai/memory/`. Source of truth for paths, formats, caps, archive retention, precedence, and safety rules.
- templates/handoff.md — fill-in-ready HANDOFF.md skeleton with a worked example. Read during the save flow at step 4; not needed on resume.
- references/session-start-hook.md — optional SessionStart hook for auto-surfacing parked memory. Read when the user asks for auto-resume behavior or hook setup.

## Guidelines

- **Never fabricate prior state.** No handoff means cold start, said in those words.
- **Failed approaches are first-class.** Capture why each failed — "tried X, didn't work" without the cause invites a retry.
- **Warn on drift, don't obey a stale plan.** Anchors exist precisely so the resume flow can distrust the file when the repo moved on.
- **User-settled decisions stay settled.** After resume, a `[user-directed]` or `[user-approved]`
  decision is augmented, never re-asked: do not reopen it or propose the alternative it already
  rejected. Contradict it only when new material evidence emerged since the save — present that
  evidence once, plainly, and let the user re-decide. `[agent-proposed]` and unlabeled decisions
  remain open to ordinary revision (older handoffs without labels stay valid).
- **Writes confined to `.ai/memory/`; no secrets; no auto-commit.** These keep the skill safe to ship in real repositories.
- **Concurrent sessions** are last-writer-wins on HANDOFF.md; the archive preserves the loser. Mention the limitation if the user hits it; do not build locking.
