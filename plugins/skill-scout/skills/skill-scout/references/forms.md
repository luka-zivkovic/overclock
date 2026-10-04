# Choosing the form

A recurring pattern deserves the smallest mechanism that removes the repetition. Most clusters
are not skills. Decide in this order and stop at the first match.

## 1. Already covered

`installed_matches` lists installed skills or commands whose name and positive triggers share
the cluster's terms.

- The matching skill appears in `skills_used_in_these_sessions`: the pattern is covered. Skip
  it.
- The matching skill never ran in those sessions while the user typed the request by hand: the
  skill is **under-triggering**. Propose a **trigger fix**: a new description for the existing
  skill that adds the user's actual phrasing as positive triggers. Keep its anti-triggers. Name
  the existing skill instead of drafting a new name.
- A match is decorative when the shared terms are generic ("write", "change", "file"). Ignore it.

## 2. A standing preference

Corrections (`kind: correction`) and "always/never" requests describe how the agent should
behave everywhere, not a procedure. Propose an **instruction line** for CLAUDE.md or AGENTS.md:
one sentence, placed at user level when the cluster spans projects and in that repository's file
when it does not. If a lessons or memory skill is installed, mention that it would have captured
this, and still give the line.

## 3. A deterministic reaction to an event

"After every edit run the formatter", "before each commit run the tests": the same action with
no judgment, triggered by an event the harness can see. Propose a **hook** (event, matcher, and
command). A skill would only remind the model to do what a hook guarantees.

## 4. A fixed prompt with a slot

The same short request with a varying argument and no branching ("open a PR for this", "commit
and push with a message"): propose a **command**, which in Claude Code is a user-invoked skill
with a short body. Name the argument. Not every short request qualifies: the base model already
handles "fix the tests" and "commit this" without help.

## 5. A procedure with judgment

The user re-explains a multi-step procedure, its format, or its constraints every time: grouping,
ordering, sections, what to check, where to stop. That is a **skill**. Write the description from
the samples' own vocabulary. Make it model-invoked only when a natural phrase triggers it and an
anti-trigger is easy to state; otherwise user-invoked. Long, near-verbatim repeated prompts
(`verbatim: true`, high `median_words`) are the strongest skill signal: the user is pasting
instructions that should live in a file.

## 6. Nothing

Drop the cluster when the samples do not share one intent, when it spans fewer than two
sessions after your review, when the requests depend on context that differs every time, or
when the base model already does it from a short request. Record it under **Considered and
skipped** with the reason.

## Drafting the description

- Lead with what the skill produces, then "Use when …" with two or three triggers in the
  user's phrasing from the samples, then "Do not use for …" naming the nearest neighbor
  (an installed skill, or the adjacent request the user also makes).
- No secret, path, or project name the user would not want shared, even when a sample carries
  one.
- Check the draft name against `installed`; a collision means a trigger fix or a different name.

## Evidence in the reason

Quote at most two samples, verbatim and short, and cite counts exactly as the helper reported
them. A proposal without a quote or with a rounded-up count is not evidence-backed.
