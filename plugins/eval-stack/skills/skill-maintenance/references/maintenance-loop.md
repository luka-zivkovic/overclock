# The maintenance loop, step by step

Target: one judged skill (e.g. natural-writing) that already has a coeval
bench project — one project per judged skill. If the bench does not exist
yet, standing it up is local-eval-stack's territory (its judge-authoring
reference), not this loop's.

## 0. Connect to coeval

MCP (preferred where the harness supports it): coeval's MCP server (in
the coeval repo under tools/mcp/) is a thin wrapper over the HTTP API —
one config line, authenticated with a project-scoped `coeval_sk_` key,
same protocol against localhost or a hosted instance. The tools:

| Tool | Use in this loop |
|---|---|
| `get_project` | resolve the bench project and its ACTIVE rubric version for the target skill |
| `get_findings` | failure clusters, human override reasons, judge–human disagreement patterns, golden deltas since a date |
| `get_cases` | the concrete judged cases behind a cluster — read them before believing the cluster label |
| `get_golden` | the adjudicated golden set: inputs for re-running the skill, baseline for regression |
| `submit_runs` | submit the fresh corpus produced by the patched skill (batch contract, content-hash idempotent) |
| `run_gate_check` | regression: golden agreement must hold for the skill-patch × rubric-version pair |

There is deliberately **no adjudicate tool**: adjudication (exception →
golden) is dashboard-only, because the human is the point.

CLI fallback (works everywhere): the findings command in the coeval-audit
script family, run from a coeval checkout:

```bash
node skills/coeval-audit/scripts/coeval-submit.mjs check --env-var COEVAL_API_KEY_<PROJECT>     # connectivity
node skills/coeval-audit/scripts/coeval-submit.mjs findings --env-var COEVAL_API_KEY_<PROJECT>  # the findings export
```

## 1. Pull findings

`get_project` → `get_findings`, bounded with a since-date: findings a
previously merged patch already consumed are spent, not evidence for a
new one. Then `get_cases` for the top cluster(s) and read the actual
inputs/outputs — a cluster label is a hypothesis; the cases are the
evidence.

STOP conditions (end the pass, report "no actionable findings"):

- zero findings for the skill;
- only findings already consumed by a merged patch;
- clusters with no human adjudications or override reasons behind them
  (judge-only noise is not a mandate to edit).

## 2. Workshop copy + bounded patch

```bash
cp -r <skills-repo>/plugins/<plugin>/skills/<skill> "$(mktemp -d)/workshop-<skill>"
```

Draft the patch against the copy, never the live path. Bounded means:

- addresses ONE recurring cluster (plus the override reasons that
  corroborate it);
- touches SKILL.md and at most one directly linked reference;
- every changed line traces to a finding id — a line no finding demands
  does not ship;
- reviewable in one sitting. Anything larger is a rewrite: a different
  project with its own evidence plan.

## 3. Rubric co-evolution

Fetch the active rubric version (`get_project`). For every probe, ask:
does the patch change the invariant this probe checks? If yes:

1. Draft the paired probe edit alongside the skill patch.
2. Propose it through coeval's guarded rubric flow: create a NEW rubric
   version — never edit the active version in place — then regression vs
   the golden set; any golden flip blocks activation until the human
   adjudicates it.
3. Cross-reference: the skill PR names the proposed rubric version, and
   the rubric version's notes name the skill patch.

If no probe is affected, state "rubric unaffected" in the PR as a checked
claim — you diffed patch against probes — not as a default.

## 4. Pre-merge validation (expensive — requires executing the skill)

All of this happens for the PR, before any merge:

1. Casefile scan the workshop copy with the repo's suppression policy,
   e.g. `casefile scan <workshop-dir> --config casefile.config.json
   --fail-on warning --no-store`.
2. Re-run the patched skill on the golden set's INPUTS (`get_golden`) —
   fresh executions of the workshop copy, never replayed old outputs.
3. `run_gate_check` with the fresh outputs against the paired rubric
   version: golden agreement must hold. A flip means the patch or the
   rubric is wrong — decide which and fix that one; never loosen the
   rubric or drop a golden case to pass.
4. `submit_runs` with a small fresh corpus (non-golden inputs) so the
   next maintenance pass has findings about THIS version.
5. Record the evidence-tier block (rubric tier, per overclock's
   skill-authoring notes): coeval revision, project, golden-set size,
   baseline/candidate revisions, gate result.

## 5. The PR

Copy the workshop skill back onto the live path in a feature branch and
open the PR. The description carries: finding ids/clusters consumed,
override reasons addressed, the rubric verdict (paired version id or
"rubric unaffected"), the gate-check output, the fresh-corpus submission
reference, and the evidence tier. **The human merges.** Never merge,
enable auto-merge, or approve it yourself.

## Post-merge (mechanical only — no skill execution, no judging)

- **casefile CI** on the merged tree — already automatic in a repo with
  the hook/workflow wired; nothing to run by hand.
- **Version bump** — the plugin/skill version that ships the update.
  Repos whose CI gates on it (like overclock) carry the bump inside the
  PR itself; it stays mechanical either way.
- **Optional re-baseline** — `submit_runs` with a corpus from the merged
  version, so future golden growth reflects the shipped skill rather
  than the pre-patch one.

Nothing post-merge re-judges or re-gates. If a post-merge step seems to
need a fresh verdict, the validation belonged in step 4 and the pass was
sequenced wrong.
