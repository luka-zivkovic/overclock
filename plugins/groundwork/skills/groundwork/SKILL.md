---
name: groundwork
description: "Interview the user about a piece of work, one question at a time, until a shared understanding is reached — then stop, summarize, and wait for confirmation before anything is built. Every question ships a recommended answer; facts the environment can answer are looked up, never asked. Use ONLY for explicit elicitation requests: 'grill me about this', 'interview me', 'ask me questions until we're aligned', 'walk me through the decisions one by one', 'help me pin down what I actually want before we build'. Do NOT use to critique, evaluate, stress-test, or give a verdict on reasoning or a plan (that is critical-thinking territory), for routine implementation after decisions are already made, when one ordinary clarifying question would do (just ask it), for open-ended brainstorming, or merely because a task looks ambiguous — an ambiguous task gets a normal clarifying question, not an interview."
---

# Groundwork

Interview relentlessly, one question at a time, until the work is genuinely understood — and
only then build. The output of a groundwork session is a confirmed shared understanding, not
code.

The failure this prevents: an agent fills ambiguity with assumptions, builds the wrong thing
politely, and the user discovers the misunderstanding in the diff. Grilling moves that
discovery to the cheapest possible moment — before anything exists.

## The primitive

1. **One question per turn.** Never batch questions; a wall of questions is bewildering and
   gets shallow answers. Ask, wait, incorporate the answer, then ask the next.
2. **Every question ships a recommended answer** with a one-line reason. The user should be
   able to move fast by replying "yes" — a question without a recommendation outsources work
   the interviewer should have done.
3. **Facts are looked up; decisions are asked.** Before asking anything, check whether the
   environment already holds the answer — files, configs, package manifests, git history,
   existing docs. Asking the user something `Grep` could answer wastes their attention and
   erodes trust in the remaining questions. The decisions, though, are theirs: tradeoffs,
   scope, taste, priorities.
4. **Walk the decision tree in dependency order.** Resolve the decisions that other decisions
   hang on first; let each answer reshape what still needs asking. Drop questions that
   earlier answers made moot — an interview is a path through a tree, not a fixed list.
5. **No question cap.** Depth is steered by the user in natural language — "keep it quick",
   "just the essentials", "go deeper on the data model" — by changing step size, not by a
   number. When the user signals speed, ask fewer, chunkier questions; never respond to a
   speed signal by silently assuming the remaining answers.

## The gate — refuse to act until confirmed

Grilling never slides into implementation. When the open decisions are resolved:

1. **Summarize the shared understanding**: the goal, each decision with the user's choice and
   its why, and anything explicitly deferred. Keep it compact enough to read in one screen.
2. **Ask for confirmation** of the summary. Corrections reopen exactly the affected
   questions.
3. Only after an explicit yes does any building start — and if session-memory's
   session-handoff is installed, the confirmed choices are exactly its `[user-directed]` /
   `[user-approved]` decisions, ready to carry into a handoff.

If the user says "just build it" mid-interview, that is confirmation authority — state the
assumptions being locked in for the unresolved questions (with the recommended answers as the
defaults), then proceed.

## Boundaries

- **Elicitation, not evaluation.** Grilling asks what the user wants; it never judges whether
  their reasoning is sound. A request to critique, stress-test, sanity-check, or give a
  verdict belongs to critical-thinking — hand off rather than interviewing.
- **Not a substitute for one question.** When a task has a single material ambiguity, ask
  that one question inline like a normal turn. The interview loop is for work with several
  interdependent open decisions.
- **Not planning.** Grilling produces decisions; plan mode and feature-dev turn confirmed
  decisions into implementation plans. Grilling ends where they begin.
- Works with or without a repository: for non-code work (a doc, a decision, an event), the
  facts-vs-decisions split still applies — read what exists before asking.
