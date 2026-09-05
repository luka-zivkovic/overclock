# Lateral engineering author-run verification

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
