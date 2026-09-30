# Grid trial: can the skill solve a search the baseline cannot? (pre-registered 2026-09-30)

This protocol was committed before any trial run. Results go in a dated section at the end, and
any deviation is recorded there as it happens.

## Question

On a search that straightforward approaches cannot finish within budget, does moonshot's
assumption-breaking step (arm B), or the same step handed to lateral-engineering (arm C), raise the
success rate over no skill (arm A)?

## Task

Fixture `eval-6` of [`qa/evals/moonshot/moonshot.evals.json`](../../evals/moonshot/moonshot.evals.json),
built by `score_run.py --build`: place 40 points on the 20 × 20 grid so that no three are collinear.
Its `check_points.py` (N = 20) is the check.

## Calibration

Author-run in C on one core of this container, 2026-09-30.

| Method | 16 × 16 | 18 × 18 | 20 × 20 |
|---|---|---|---|
| Row by row, blocked-cell masks, forward checking, lexicographic | timeout at 900 s (1.1 × 10^9 nodes) | not run | not run |
| Same with most-constrained-row branching, random order, restarts | found in 43 s and 59 s; two other seeds timed out at 120 s | timeout at 900 s | timeout at 900 s, two seeds |
| Min-conflicts local search | not run; it failed 10 × 10 and 12 × 12 in 20–30 s | not run | not run |
| Half-turn symmetric search, whole orbits | 0.01 s | 5 of 5 seeds, at most 0.32 s | 5 of 5 seeds, at most 1.8 s |
| Quarter-turn symmetric search | under 0.01 s | 5 of 5 seeds, under 0.01 s | 5 of 5 seeds, at most 0.02 s |

At 20 × 20, the approaches that keep every configuration in play fail within 15 minutes on one
core, and a search restricted to symmetric configurations succeeds in seconds. Other structural
ideas may also work, and success by any means counts. Neither skill's text names symmetry.

## Arms

- **A, no skill:** the task text only.
- **B, `/moonshot`:** the rendered skill body (`SKILL.md` sha256 `a7cbd262…`) with the task text as
  `$ARGUMENTS`, and no other skill declared.
- **C, `/moonshot` with lateral-engineering:** as B, plus a line declaring `lateral-engineering`
  available in the session with the path to its unchanged `SKILL.md`.

The task text, identical in every arm:

> Place 40 points on the 20x20 grid described in README.md so that no three are collinear;
> `python3 check_points.py` verifies. Budget: 20 minutes of wall-clock time on one CPU core. Run one
> process with one thread at a time, check the time with `date`, and stop to report when the
> budget is spent.

The preamble, identical in every arm: work only inside the copied workspace, keep temporary files
inside it, and use no network or web tools.

## Procedure

- Claude Code subagents (`general-purpose`, model alias `sonnet`) in this container.
- Five runs per arm, fifteen in all, in five batches of three launched together: one run per arm
  per batch, each in a fresh copy of the fixture.
- A run lost to infrastructure (a container restart or harness error) is repeated in a fresh
  workspace and recorded as a deviation.

## Outcomes

- **Primary:** success means the pristine checker (`score_run.py points-20`) prints PASS on the
  run's `points.txt`, and the run's wall-clock duration is at most 25 minutes (the budget plus five
  minutes for the report).
- **Integrity, per run:** checker bytes unchanged, no commits, nothing written outside the
  workspace, and the one-process rule followed as far as the report shows.
- **Secondary, descriptive only:** the approach used, whether and how arm C used
  lateral-engineering, time to the first PASS when reported, tool calls, tokens, and duration.

## Decision rule

Compare success counts between arms. With five runs per arm, a difference counts as clear only when
the gap is at least four: 4 of 5 against 0 of 5, or 5 of 5 against 1 of 5 (two-sided Fisher exact
p = 0.048). A gap of three or fewer is inconclusive at this size and is reported as such. The
primary contrasts are B against A and C against A; C against B is secondary.

- If B or C clearly beats A, the claim that the skill changes the approach earns a real, if narrow,
  result on this task family.
- If neither clearly beats A, retire that claim for this model; the skill keeps only its structure
  and honest reporting, or is retired.

## Limitations known in advance

- One task family, one model, and an author who built the skill, the task, and the scoring.
- Subagents receive skills as pasted text; arm C invokes lateral-engineering by reading its file.
- Wall-clock budgets on a shared four-core machine are noisy; batches of three keep contention
  even across arms.
