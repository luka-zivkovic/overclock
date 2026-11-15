# Product audit

<!-- product-audit: v1 -->

This file records one audit: what the product promises, what it carries, what earns its keep,
and what to do next. Verdicts are the audit's recommendations; the Decision column belongs to
the owner. Edit anything in plain language; keep the `F1`, `X1`, `D1`, `O1`, `G1`, `N1` labels
so the pieces can point at each other.

<!-- guide: every "guide" comment is an instruction for filling the template. Delete them all; the check rejects a report that still has one. -->

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
| Packages | n/a |
| Settings and flags | n/a |
| Integrations | n/a |
| Top-level destinations | n/a |
| Steps to the core action | n/a |

Measured: <the path walked to the core action, and how any measure was translated for this product>

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

Promised but not built: <claims in the README or a roadmap with no code behind them, or "nothing">
Built but never mentioned: <features the README does not mention, or "nothing">

## 4. Complexity

<!-- guide: at most five structural findings; how a screen looks is not listed here. With no finding, keep the line "None." and no rows; with findings, delete it. -->

| ID | Finding | Evidence | Simpler |
|----|---------|----------|---------|

None.

## 5. Direction

Verdict: <focused, drifting, split, or undefined>

<Why, with the evidence: class shares, where recent work went, whether the sources agree.>

### The choice

<!-- guide: two or three options unless the verdict is focused; then write "None." instead. -->

- D1 <an option the owner could take, and what follows from it> (recommended): <one-line reason tied to the evidence>
- D2 <another option>

## 6. Outside view

<!-- guide: keep either the product table with its sources, or one "Not run:" line with nothing else in the section. Never both. -->

Not run: <the reason it was skipped>

| ID | Product | Why comparable | What it covers | Source |
|----|---------|----------------|----------------|--------|
| O1 | <product name> | <same job, similar scale> | <one line> | <page URL> (checked <YYYY-MM-DD>) |

Searched: <the search terms used, and how many searches and pages>
Differentiator: <what this product does that none of the others mention>

### Readings

- (F2) supports: <what the comparison shows about that verdict>

### Gaps

- G1 <something all or all but one of the products have and the core job needs, as a question>

## 7. Next moves

A suggestion, not a commitment. Every move points at a feature, finding, option, or gap above.

### Next

- N1 (F2) <the one move that is right whichever option the owner picks>

### Then

- N2 (X1, F2) <a later move>

## 8. History

- <YYYY-MM-DD>: <feature count by class>; direction <verdict>
