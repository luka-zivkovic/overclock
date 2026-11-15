# Product audit

<!-- product-audit: v1 -->

This file records one audit: what the product promises, what it carries, what earns its keep,
and what to do next. Verdicts are the audit's recommendations; the Decision column belongs to
the owner. Edit anything in plain language; keep the `F1`, `X1`, `D1`, `O1`, `G1`, `N1` labels
so the pieces can point at each other.

## 1. Promise

<One sentence: who this is for and what it does for them.>

Source: <files the sentence came from, "inferred from the code", or "the owner">
Stage: <who uses it today and what the owner wants from it, with where that came from>

## 2. Snapshot

| Measure | Count |
|---------|-------|
| Features | 0 |
| Core | 0 |
| Supporting | 0 |
| Adjacent | 0 |
| Off-promise | 0 |
| Screens | n/a |
| Endpoints | n/a |
| Commands | n/a |
| Data models | n/a |
| Settings and flags | n/a |
| Integrations | n/a |
| Top-level destinations | n/a |
| Steps to the core action | n/a |

Counts are whole numbers, or `n/a` when they could not be measured.

## 3. Features

| ID | Feature | Class | Evidence | Cost | Usage | Verdict | Decision | Decided by |
|----|---------|-------|----------|------|-------|---------|----------|------------|
| F1 | <what a user can do> | core | <file paths> | moderate | unknown | keep | keep | audit |
| F2 | <another thing a user can do> | adjacent | <paths and what sets the cost> | heavy | unknown | park | pending | — |

Class: `core`, `supporting`, `adjacent`, `off-promise`. Cost: `light`, `moderate`, `heavy`.
Usage: `unknown`, `owner: regular`, `owner: rare`, `owner: never`, or `measured: <numbers>`.
Verdict and Decision: `keep`, `finish`, `simplify`, `merge`, `park`, `cut`; a Decision may also
be `pending`. Decided by: `audit` only for keeping what the audit would keep, otherwise `owner`
or `owner-delegated`, and `—` while pending.

## 4. Complexity

At most five structural findings. How a screen looks is not listed here. With no finding, keep
the line `None.` and no rows.

| ID | Finding | Evidence | Simpler |
|----|---------|----------|---------|

None.

## 5. Direction

Verdict: <focused, drifting, split, or undefined>

<Why, with the evidence: class shares, where recent work went, whether the sources agree.>

### The choice

- D1 <an option the owner could take, and what follows from it> (recommended)
- D2 <another option>

## 6. Outside view

Keep either the product table with its sources, or one `Not run:` line. Never both.

Not run: <the reason it was skipped>

| ID | Product | Why comparable | What it covers | Source |
|----|---------|----------------|----------------|--------|
| O1 | <product name> | <same job, similar scale> | <one line> | <page URL> (checked <YYYY-MM-DD>) |

### Readings

- (F2) supports: <what the comparison shows about that verdict>

### Gaps

- G1 <something nearly every comparable product has and the core job needs, as a question>

## 7. Next moves

A suggestion, not a commitment. Every move points at a feature, finding, option, or gap above.

### Next

- N1 (F2) <the one move to make first>

### Then

- N2 (X1) <a later move>

## 8. History

- <YYYY-MM-DD>: <feature count by class>; direction <verdict>
