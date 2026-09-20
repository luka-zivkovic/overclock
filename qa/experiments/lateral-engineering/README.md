# Lateral engineering author-run verification

Two rounds are recorded. The **0.1.0 draft** round (2026-09-05) is below under "Draft round".
The **arbitrage revision** round (2026-09-20) reran the same two prompts under the revised skill;
see "Revision round" at the end. Both are `subjective` tier author-run evidence.

## Draft round

- **Date:** 2026-09-05.
- **Evidence tier:** `subjective`. These are the author's requested self-runs and qualitative
  review, not independent model grading, measured novelty, or evidence of baseline improvement.
- **Executor:** the authoring Codex session, applying the written skill and its moves catalog to
  the two prompts below. No peer agent or independent harness produced or graded these outputs.
- **Scope:** target skill instructions and bundled moves only; no sibling workflow or hook was
  invoked. This is not an isolated install-mode measurement: the author retained conversation
  context. The committed live suite and routing battery both declare target-only `skill` mode.
- **Source:** `plugins/lateral-engineering/skills/lateral-engineering/`, version 0.1.0.
- **Acceptance claim:** the recorded outputs satisfy the requested format and received qualitative
  review of their assumption changes, costs, grounding, and practical spine. Creativity remains
  an author judgment. Structural checks do not establish reliability across unseen prompts.

## Cases and results

1. "How could a coding harness be optimized so a 4B model like Gemma E4B can reliably produce
   games like 2048 and minesweeper, generalizing to other games?"
   - Output: [game-harness.md](game-harness.md).
   - Six assumptions; five reframings; all five have costs and grounding; three use `Untested`.
   - Random draw: **costs zero at rest**.
   - Qualitative review: the goal contains outcomes rather than harness/model/source-code nouns.
     The 4B constraint survives in the proposals. The frontier idea explicitly narrows initial
     support instead of disguising abstention as universal generalization. The oblique idea
     eliminates idle generation compute, not all storage or client hardware costs.
   - Prosecution outcome summary: reject a DSL-only candidate as familiar language restriction;
     push it into using model tokens to select distinguishing examples among candidate programs.
     Reject prompt enlargement/retry multiplication as conventional reliability tuning. These
     summaries record filter effects, not the private draft or reasoning transcript.
   - Residual: the question-selection experiment tests one semantic subproblem. It cannot validate
     the whole compiler, game generation quality, or cross-genre generalization.

2. "Our trace-annotation pipeline for LLM evals is slow because every trace goes through a human
   review queue. How else could this be done?"
   - Output: [trace-annotation.md](trace-annotation.md).
   - Six assumptions; five reframings; all five have costs and grounding; two use `Untested`.
   - Random draw: **operated by someone who can't code**.
   - Qualitative review: the goal names trustworthy judgments and human effort, not traces,
     queues, or pipelines. The five proposals change completeness, timing, unit, reviewer agency,
     and disagreement semantics respectively. The core composes allocation with smaller review
     units and explicitly distinguishes their separate evidence requirements.
   - Prosecution outcome summary: reject parallel reviewers/faster queues as capacity tuning;
     push indiscriminate sampling into decision-specific stopping with explicit inclusion
     probabilities and uncertainty. Reject cluster-label propagation without context validation.
   - Residual: sequential inference and context compression can bias decisions. The output names
     that risk; it does not establish statistically valid implementation or authorize deployment.

The oblique constraints were drawn before generating each output with Python
`secrets.choice` over the skill's ten-entry list, without relevance-based redraws.
Both runs considered all six families in generation and retained five distinct survivors.
Family coverage and prosecution are author process notes, not mechanically verified facts.

## Checks and revisions

Run `python3 qa/experiments/lateral-engineering/check_outputs.py` for deterministic format
checks: counts, sequential numbering, 3–5 word names, distinct assumption references, 2–4
sentence paragraphs, stated costs, grounding labels, valid oblique tags, and named ideas/risk
in the core. Human review checks mechanism-free goals, costs that reflect the mechanism,
grounding validity, distinctness, actual prosecution, and coherent composition.

Before the self-runs, reconcile the prompt's six-family-plus-oblique requirement with its
4–6-output limit by requiring at least seven private candidates and 4–6 final survivors.
Keep previous-round convictions inside the core to preserve the exact output skeleton.
Distinguish role-based prosecution from fabricated claims about a named real engineer.
Neither completed self-run required a subsequent skill-text change to meet the checks.

The live suite includes the two exact prompts, a previous-round prosecution control, a safe
production guidance negative, and thin-input calibration. The routing battery supplies ten
positive and twelve closed-world negative controls. Run them with:

```sh
bash qa/run_evals.sh lateral-engineering/lateral-engineering
python3 qa/trigger_battery.py qa/trigger-battery/lateral-engineering.json
```

The authoring environment has a Claude CLI but neither `ANTHROPIC_API_KEY` nor
`ANTHROPIC_AUTH_TOKEN`. The isolated live harness intentionally excludes host OAuth/keychain
credentials, so live behavior, routing scores, and paired baseline gains are **not measured**.
The declared value gate is for a later paired run, not a passing result. Generated `qa/_work/`
artifacts are not source and are not part of the distribution.

## Local validation result

All 367 repository unit tests passed on the PR branch based on
`f6cbd795afdee0676a4b807d152fd63dacf8db02`. All 19 skill distributions passed validation and the
repository audit; shared-file equality, documentation claims, setup catalog synchronization,
and version checks against `origin/master` passed. Claude validated the marketplace and both
affected plugin directories. The skill-creator validator passed using an ephemeral Python
environment with PyYAML because the host Python lacked that dependency.

The standalone ZIP contains only `SKILL.md`, `agents/openai.yaml`, and `references/moves.md`
under `lateral-engineering/`. Its CRC check and byte-for-byte comparison with source passed.
[source-record.json](source-record.json) pins the tested source and example hashes. The
PR branch contains only Lateral Engineering and its required publication/evaluation integration;
unrelated Feature Dossier work remains outside this branch.

## Revision round (2026-09-20)

**Why the skill changed.** A critical-thinking pass compared the draft procedure with how Naughty
Dog solved Crash Bandicoot's PlayStation constraints: camera on rails so visibility could be
precomputed offline, a virtual-memory scheme streaming 64 KB pages off the CD, a disc-layout
search tool, a domain language, crates added in a Saturday to fill empty levels. Every one of
those ideas was an arbitrage between a numeric wall and a surplus the standard design ignored,
and most came from facts specific to that machine. The draft skill received only the prompt, had
no wall, no inventory, forbade self-imposed constraints, and convicted ideas for being familiar
rather than for leaving the wall untouched. The revision adds a **Wall** line, an **Inventory**
step (surplus, fixed, ratings, negotiable freedoms), an **Arbitrage** move family with an
`accepts:` tag for offered constraints, a prosecution test based on wall movement and cost
instead of "would a senior engineer say this in ten minutes", and a deeper **The stack** closer.
Body size fell from ~2204 to ~2061 estimated tokens.

**Rerun protocol.** Same two prompts, oblique constraints drawn with `secrets.choice` before
generation (`explainable in one sentence to a child`; `reversible at any point`), inventory values
supplied as labelled working assumptions because no user was present. Outputs:
[game-harness-v2.md](game-harness-v2.md) and [trace-annotation-v2.md](trace-annotation-v2.md).
`check_outputs.py` accepts both skeletons and passes on all four files.

**Pre-registered pass signal.** At least one idea per prompt that names the wall, exploits a
stated inventory fact, and could not have been written from the prompt alone.

**Side by side, author judgment.**

| Prompt | Same idea re-anchored | New in v2 | Dropped from v1 |
|---|---|---|---|
| Game harness | Checks Before Code ≈ v1 Semantic Windtunnel; Distil One Game Family ≈ v1 Generalization Frontier | Sample Thousands, Ship One (spends the surplus, carries the k experiment); Cache The Model's Knowledge (newly free frontier model at design time); Grade By Play, Not Code | Dormant Repair Capsules; Grow A Failure Alphabet |
| Trace annotation | Judge State, Not Narrative ≈ v1 Spend Judgment At Authoring; Reviewers Write Checks ≈ v1 Let Reviewers Rewrite Outcomes | Humans Grade The Judge (spends judge tokens, moves the wall to task-type count); Disagreement Is The Queue; Label Once, Replay Forever | Retire Questions Before Traces; Keep Disagreement As Structure |

- The pass signal is met for both prompts, with the caveat that the inventory was assumed by the
  author rather than supplied by a user, so "not writable from the prompt alone" is weaker than
  it would be with a real inventory.
- Every v2 entry states what it does to the wall; no v1 entry did. Two v2 entries per prompt
  carry an `accepts:` trade the user can refuse.
- The revision is not uniformly more inventive. v1's Dormant Repair Capsules and Retire
  Questions Before Traces were more surprising than anything in v2, and v2's Humans Grade The
  Judge and Disagreement Is The Queue are close to known practice in model evaluation. Under
  the draft's ten-minute test they would have been convicted; under the revised test they acquit
  because they move the assumed wall by roughly 85 percent. That trade, leverage over surprise,
  is the deliberate change, and whether it is the right trade for a given user is a preference,
  not something these runs can settle.
- Confound: v1 was produced by a Codex session and v2 by a Claude session, so model and skill
  changed together. A clean comparison needs the same model on both skill versions, which the
  committed live suite provides once credentials are available.

**Routing.** The description now triggers on "what could we trade" and on the user *saying* a
design is stuck rather than the model judging it so, and adds "a walkthrough of standard options"
as an anti-trigger. The battery gained one positive (a wall-and-trade prompt), one negative (a
standard-options walkthrough), and a `stack` mode with `critical-thinking` and `groundwork`, the
nearest neighbours for "reframe", "stress-test", and "walk me through", so a critique or
elicitation prompt must route to the sibling and never here. Live routing remains unmeasured.

## De-anchoring round (2026-09-20)

**Finding.** The revision's body opened with the Crash Bandicoot story and cited its tricks in
two more places, and the Arbitrage family used Crash as the anchor precedent for every move. The
v2 outputs show the effect: 4 of 10 ideas cite Crash, Naughty Dog, GOOL, or "on rails" as their
grounding, against 0 of 10 in the draft outputs. A worked example in the instructions had become
the model's default precedent, which both steers ideation toward that story's shape and inflates
the grounding signal, since citing the skill's own example is not independent grounding.

**Change.** The story is gone from `SKILL.md`; the body keeps only the abstract principle, an
arbitrage between a wall and a surplus, and the leading word is "arbitrage". In the catalog,
Crash is one precedent among three or four per Arbitrage move rather than the frame, and a rule
at the top of the catalog says its precedents illustrate moves and are not a source list. Step 4
of the skill repeats that rule. Body size is ~2076 estimated tokens.

**Rerun.** Same two prompts, fresh blind draws (`operated by someone who can't code`;
`buildable with 1995 technology`), same assumed inventories. Outputs:
[game-harness-v3.md](game-harness-v3.md) and [trace-annotation-v3.md](trace-annotation-v3.md).
Anchor leakage is 0 of 11 ideas. The arbitrage ideas survived the removal: Sample Thousands,
Ship One, Distil One Game Family, Humans Grade The Judge, Disagreement Is The Queue, and Label
Once, Replay Forever are all present with the same mechanism and now carry precedents from their
own fields (best-of-N with a verifier, PuzzleScript, acceptance sampling, query-by-committee,
standard-cell libraries). That is the evidence the framing works without the story. Two entries
are new under the fresh oblique draws: Repair By Playing, Not Editing makes the non-coding player
the repair oracle, and Sample Like A Pollster fixes human effort per release at a constant sample
size, which re-derives the draft's Retire Questions Before Traces from a different lens and is
recorded as such rather than as a new idea.

**Judgment.** The pre-registered pass signal still holds on v3 for both prompts, with the same
caveats as v2: assumed inventories, author-run, and a model change between v1 and v3. The
comparison that matters for the maintainer is v2 against v3: same skill procedure, same author,
same day, story present versus absent. The arbitrage ideas are unchanged and the citations moved
from the skill's example to independent precedents, so the story was steering the grounding, not
producing the ideas.
