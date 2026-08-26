# Authoring a judge: rubric, calibration, cost

## Rubric = the skill's contract as probes

One judging skill per coeval project, one project per judged skill. Derive
the rubric from the skill's SKILL.md invariants (and its eval suite if it
has one), structured as:

1. What INPUT/OUTPUT the judge sees, one paragraph.
2. `PASS requires ALL of:` 4–6 **specific, checkable probes** — mechanical
   where possible (banned-word lists, "verdict stated before plan",
   "verbatim span preserved byte-for-byte"). Vague rubrics measure judge
   mood; verdict stability is a property of rubric specificity.
3. `FAIL if ANY of:` the failure modes the skill exists to prevent —
   including OVER-application (firing where the skill says stay silent).
4. `AMBIGUOUS if:` the skill's anti-trigger cases, with the instruction
   spelled out: *return the verdict `ambiguous`, do NOT return pass*.
   Caveat: binary verdict kinds may coerce to pass/fail depending on
   coeval version (see coeval#172) — adjudicate anti-trigger verdicts by
   hand regardless.
5. A calibration note: verdicts are opinions until a golden set exists.

Pin the model binding explicitly (mid-tier model, temperature 0). Never
judge an edit with the same model context that produced it.

## Calibration batch before trust

Three crafted items per skill, named `<skill>-calib#N`:

- **pass exemplar** — satisfies every probe (input from a real scenario)
- **fail exemplar** — realistically violates 1–2 core probes
- **anti-trigger probe** — input the skill should NOT engage; submit
  UNLABELED and adjudicate the verdict by hand

Submit with `--min-agreement 1.0`. Labeled disagreement means a weak
exemplar or an ambiguous probe — decide which; they have opposite fixes.
Crafted cases calibrate the JUDGE's discrimination; they say nothing about
the skill's real failure modes. Golden sets grow from real captured runs.

## Cost discipline

Every fresh verdict is a model call over the full rubric + case (~3–9k
input tokens each in practice). Rules of thumb:

- Mid-tier judge model unless disagreement analysis proves otherwise.
- Never auto-judge an unbounded stream (a tracer integration) before
  estimating volume; curated submission is the default.
- Idempotency is your friend: resubmitting unchanged JSONL re-spends
  nothing.

## The loop once live

Capture real runs (tracer tags tell you where a skill fired) → submit the
interesting ones → adjudicate exceptions in the dashboard → promote golden
cases → the gate arms (recommended ≥5 golden) → future rubric edits
regression-test against it. First skill to an armed gate proves the
pattern; only then expand the judged roster.
