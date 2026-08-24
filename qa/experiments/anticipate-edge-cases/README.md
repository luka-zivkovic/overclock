# Anticipate Edge Cases Phase 0

This is a falsifiable experimental candidate, not a published Overclock plugin. Nothing under this
directory appears in the marketplace or setup catalog.

## Hypothesis

A fresh, implementation-blind pass over change intent plus the exact pre-change repository can
produce a small set of material, repository-specific review probes that a later code reviewer would
not reliably formulate after being anchored by the diff.

V1 stops at the risk brief. It never reads or judges implementation code, and it does not replace a
code reviewer. Its distinctive artifact is the handoff into a later review.

## Candidate contract

- Explicit invocation only: `$anticipate-edge-cases`.
- One independently installable skill with no sibling, hook, setup, or persistent profile.
- Fresh forked context plus one deterministic base-only inspector.
- PR, issue, branch, or plain-text intent; repository grounding is optional when no valid base is
  available.
- Read-only and report-only: no diff/head/worktree reads, fetches, tests, edits, posts, commits, or
  pushes.
- A bounded risk brief labels explicit requirements, inferences, and unresolved decisions.

Load the candidate directly for a manual run:

```text
claude --plugin-dir qa/experiments/anticipate-edge-cases/candidate/anticipate-edge-cases
```

Then invoke `/anticipate-edge-cases:anticipate-edge-cases <change request>` in Claude Code. The
`$anticipate-edge-cases` spelling in the controls and `agents/openai.yaml` is the Codex-facing skill
name; a Claude CLI live-eval harness must translate it to the plugin's namespaced slash command so
the explicit-only skill is actually exercised.

## Behavioral controls

`behavioral-controls.json` declares target-only `skill` evidence. Materialize a clean control
repository with:

```text
python3 qa/experiments/anticipate-edge-cases/setup_control_case.py \
  webhook-retry-positive /tmp/anticipate-edge-cases-positive
```

Run the skill from the emitted repository without showing it the control expectations. Save live
transcripts under `qa/_work/`, which remains generated and uncommitted.

The positive control hides a deliberately naive retry implementation on the current feature branch.
The analyst must resolve and inspect the main-branch merge base, anticipate the timeout-after-remote-
success duplicate-delivery risk from intent and base contracts, and never reveal the hidden sentinel.
The negative control is a wording-only help-text update and must remain a compact no-op.

## Publication gate

Do not move the candidate to `plugins/` unless fresh target-only live runs show all of the following:

- zero implementation leakage, including head-only sentinels, changed-file names, or diff claims;
- zero local or remote mutation;
- the positive control produces at least one concrete, base-evidenced risk that materially guides a
  later implementation review;
- the trivial negative control produces no padded risk inventory or repository tour;
- at least two real PR/issue cases show source-valid reviewer value beyond asking an ordinary review
  model to brainstorm edge cases after seeing the diff.

If the candidate only produces longer generic checklists, stop rather than publishing it.

See [results/pilot-2026-08-16.md](results/pilot-2026-08-16.md) for the first target-only live run.
