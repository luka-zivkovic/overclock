---
name: skill-maintenance
description: "Maintain a judged agent skill from its coeval evidence: pull findings (recurring failure clusters, human override reasons, golden deltas) via the coeval MCP tools or findings CLI, translate them into ONE bounded SKILL.md patch on a workshop copy, co-evolve the judge's rubric through coeval's guarded flow when an invariant moves, validate pre-merge with a casefile scan plus golden re-runs and a gate check, and open a PR citing the findings. Use when someone asks to improve, patch, or maintain a skill based on its eval findings, apply coeval findings to a skill, or run the skill-maintenance loop. Do NOT use when the target skill has no findings (no findings = no patch — never invent improvements), for authoring a new skill or a first rubric, for standing up ironside/coeval/casefile (that is local-eval-stack), to adjudicate verdicts (human-only in the coeval dashboard, no tool by design), or to merge anything — the human merges, always."
---

# Skill maintenance

The human-in-the-loop maintenance loop for a judged skill: **findings →
one bounded workshop patch → co-evolved rubric → gated validation → PR**.
Findings inform, humans decide, gates verify. The exact tool calls,
commands, and the pre-/post-merge split live in
`references/maintenance-loop.md` — skip it and you will guess tool names
and run the expensive validation at the wrong time.

## Phases (in order; stop the pass wherever the evidence runs out)

1. **Pull findings** for the target skill from its coeval bench project:
   MCP tools `get_project`, `get_findings`, `get_cases`, `get_golden`
   (`submit_runs` and `run_gate_check` come later), or the findings CLI.
   No findings → report that and stop. An empty pass is a correct pass.
2. **Draft ONE bounded patch on a workshop copy.** Cluster recurring
   failures and human override reasons; translate the strongest cluster
   into a minimal SKILL.md diff on a copy of the skill — never edit the
   live skill in place, never fold multiple unrelated clusters into one
   patch.
3. **Rubric co-evolution check.** Diff the patch against the judging
   skill's rubric probes. If an invariant moved, the judge still enforces
   yesterday's contract and will fail future runs for obeying the new
   skill — propose the paired rubric edit through coeval's guarded flow
   (new version → regression vs golden → block-on-flip). Skill and judge
   move together, or the bench silently measures the previous version.
4. **Validate pre-merge (the expensive half — requires executing the
   skill).** Casefile scan of the workshop copy; re-run the patched skill
   on the golden set's inputs; `run_gate_check` against the paired rubric
   version (golden agreement must hold); `submit_runs` with a fresh
   corpus. This is rubric-tier evidence — record the gate result with the
   run.
5. **Open a PR citing findings as evidence** — finding ids, clusters,
   override reasons, gate result. The human merges, always. Post-merge
   work is mechanical only (see the reference).

## Failure modes (hard boundaries)

- **No findings = no patch.** Improvement ideas without findings behind
  them are inventions, not maintenance.
- **Never weaken a rubric or a test to make the skill pass.** A rubric
  edit exists to track a moved invariant and must survive the golden
  regression; loosening a probe to green a patch corrupts the bench.
- **Never auto-merge.** The loop's terminal output is an open PR.
- **Never adjudicate.** There is no adjudication tool, by design;
  exceptions are decided by the human in the coeval dashboard.
- **One bounded patch per pass, never a rewrite.** Remaining clusters
  wait for the next pass; a rewrite needs its own evidence plan.

## Definition of done

An open, unmerged PR whose description cites the findings consumed, the
gate-check result (golden agreement held), the fresh-corpus submission,
and — when an invariant moved — the paired rubric version. Merge and
everything after it belong to the human.
