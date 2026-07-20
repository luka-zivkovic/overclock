---
name: project-vocabulary
description: "Build and maintain the project's domain vocabulary as a standalone glossary (CONCEPTS.md at the repository root), and keep conversation honest against it: challenge fuzzy or conflicting terms ('you say account — the glossary's Customer, or User?'), record what domain nouns actually mean, and flag ambiguities. Use when domain terms are used inconsistently or fuzzily in work on a domain-carrying project, when the user corrects TERMINOLOGY ('no, we call that a Workspace, not a Team'), when a new load-bearing domain noun gets settled in conversation, or when asked to create, update, or review the project glossary. Do NOT use for corrections of agent behavior or workflow rules ('stop using npm' — that is lessons-learned territory), throwaway scripts or prototypes, repositories with no real domain vocabulary (generic utilities, dotfiles), general programming vocabulary (function, endpoint, cache), or one-off wording preferences in a single document. Trivial work never triggers glossary ceremony."
---

# Project Vocabulary

Keep one ubiquitous language per project, written down. When "account" means Customer in the
billing module, User in the auth module, and either in conversation, every feature discussion
silently forks. This skill maintains `CONCEPTS.md` at the repository root — a glossary and
nothing else — and actively uses it in conversation rather than merely appending to it.

## The glossary file

`CONCEPTS.md` at the repository root. Lazy creation: the file exists only once there is a
term worth recording — never scaffold an empty glossary "to be filled later".

File craft (the rules that keep it useful):

- **It stands on its own.** No file paths, class names, or current configuration values —
  those go stale silently. State the behavior, not the number: "imports are chunked so memory
  stays bounded", not "chunksize=50000 in loader.py".
- **One term per concept.** Pick the winner; record retired synonyms as aliases ("Workspace —
  formerly 'Team', 'Org'") so old code and docs remain navigable.
- **Definitions are behavioral.** What the thing is, what it is not, and the nearest term it
  gets confused with.
- **A Flagged Ambiguities tail.** Terms known to be contested or fuzzy live at the bottom,
  named as unresolved — an honest ambiguity beats a premature definition.
- **Update inline, not in batches.** A term settled in conversation is recorded now, in one
  small edit; a "glossary cleanup session" is a smell that inline discipline lapsed.

Terms enter two ways:

- **Accretion** — a conversation settles or corrects a term; record it as it happens.
- **Seeding** — when starting sustained work in a domain area with no glossary coverage,
  proactively define the few core nouns the area is built around. The nouns a system is built
  around rarely break, so they rarely come up as corrections — yet they are exactly what a
  newcomer (or next session) needs first.

## Using it in conversation

The glossary earns its place by being applied, not just written:

- **Challenge fuzzy usage.** When a term is used in a way the glossary contradicts, say so at
  the moment it matters: "The glossary defines *cancellation* as end-of-period; this flow
  reads like immediate revocation — which do you mean?"
- **Sharpen overloaded words.** When a conversation leans on an undefined, load-bearing noun
  ("account", "job", "sync"), pin it before building on it — one question, not a workshop.
- **Stress-test new definitions** with one or two edge scenarios before recording ("if a
  Customer has zero Users, is it still a Workspace?"). A definition that survives its edge
  cases is worth writing down.
- **Cross-reference against code when it matters.** If the glossary and the code disagree
  (the glossary says Workspace, the schema says teams), surface the mismatch honestly —
  record the term the project has chosen and note the legacy name as an alias; never claim
  the code matches when it doesn't.

## Boundary with lessons-learned

One question routes a correction: **is it about what a thing is called, or about how to
work?**

- "No — we call that a *Workspace*, not a Team" → **glossary** (this skill).
- "No — stop using npm, this repo uses pnpm" → **lessons-learned** (session-memory /
  learning-loop, where installed). This skill never writes `LESSONS.md` or `.ai/memory/`.
- A correction carrying both ("we call it a Workspace, and always scope queries to it")
  splits: the term goes to the glossary; the behavioral rule belongs to lessons-learned.

## Write discipline

- Writes are confined to `CONCEPTS.md` at the repository root. No secrets, credentials, or
  personal data ever enter the glossary. Never auto-commit.
- Quote any recorded or changed definition back in conversation so the user can correct it
  immediately.
- An existing hand-maintained CONCEPTS.md is respected: match its structure, edit minimally,
  and never rewrite it wholesale without being asked.

## Right-sizing

- A trivial edit, a throwaway script, or a repo with no domain (a dotfiles repo, a small
  generic utility) never triggers glossary work — stay silent.
- One fuzzy term in an otherwise clear conversation gets one clarifying question, not a
  glossary session; record the answer only if the term is load-bearing and settled.
- When unsure whether a term is worth recording, ask — an explicit "add this to the glossary"
  is never borderline.
