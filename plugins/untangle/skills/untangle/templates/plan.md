# Untangle plan

<!-- untangle-plan: v1 -->

This file is the single record of the survey, the decisions, the work, and what comes next.
Section 3 is the checklist: `[ ]` means not done yet, `[x]` means done, and the line beneath a
done item says what happened and how it was checked. Edit anything in plain language; keep the
`T1`, `C1`, `F1`, `N1` labels so the pieces can point at each other.

## 1. Spine

<One sentence: what this project is trying to be.>

Source: <files the sentence was built from, or "asked the user">

## 2. Threads

| ID | Thread | Role | Evidence | Decision | Decided by |
|----|--------|------|----------|----------|------------|
| T1 | <the main thing> | spine | <paths> | keep | survey |
| T2 | <a side quest> | side-quest | <paths and the signal that placed it> | pending | — |

Roles: `spine`, `supporting`, `side-quest`, `abandoned`, `contradicting`. A checklist item marked `(H1)`
comes from a hygiene signal rather than a thread.
Decisions: `keep`, `park`, `delete`, `merge`, `pending`. Only the user decides `park`, `delete`, or
`merge`; the survey may propose, never decide.

## 3. Checklist

Ordered. Do one item at a time, verify it, tick it, then commit.

- [ ] C1 (H1) <hygiene step> | paths: <comma-separated paths> | verify: <observable check>
- [ ] C2 (T2) <park or delete step> | paths: <paths> | verify: <observable check>

## 4. Foundations

At most three decision-level findings about the spine. Line-level code quality is not listed here.

| ID | Finding | Evidence | Cost of keeping | Cost of changing now | Cost of changing later |
|----|---------|----------|-----------------|----------------------|------------------------|

None.

## 5. Suggested next moves

A suggestion, not a commitment. Every move points at a thread, finding, or checklist item above.

### Next

- N1 (T1) <the one move to make once the checklist is done>

### Then

- N2 (C2) <a later move, pointing at a thread, finding, or checklist item>

### Parked ideas

- T2: <one line on what the parked thread was trying to do>
