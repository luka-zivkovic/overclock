# Overclock — ecosystem position

Where Overclock sits in the broader AI trust & reliability ecosystem, and the small
number of cross-repo decisions that touch this repo. Read [`docs/strategy.md`](strategy.md)
first: nothing here changes the operating rules there. All sibling product names below
are **working names**.

This file is repo documentation, not shippable content. It lives outside `plugins/`,
so it ships to no user and needs no version bump.

## The ecosystem (siblings, all working names)

| Product | Layer | One-liner |
|---|---|---|
| **overclock** (this repo) | Agent behavior | Claude Code plugins with explicit boundaries and behavioral evals |
| **ironside** | Trace system of record | Durable record of what agents actually did |
| **coeval** | Judging | Governed LLM judging + gates |
| **skillguard** | Skill supply chain | Static + behavioral verification of skills/plugins (`~/startups/skill-guard`) |
| **release-layer** | Shipping | Demand-gated shadow/canary shipping |

## 1. Overclock's position: the agent-behavior layer

Overclock continues as a **personal toolkit**, unchanged. Usefulness is the only gate;
the operating principles and candidate ledger in `strategy.md` remain the authority on
what gets built here. The ecosystem does not turn Overclock into a product line, and no
sibling product gets to add a gate to this repo's build decisions. What the siblings
*do* get from Overclock: a real, maintained set of skills with real evals to test
against.

## 2. Dogfood bridge — planned, small

Overclock's 6 plugins get `skillguard gate` in CI, making this repo skillguard's first
real user.

**Honest framing: this is an integration test, NOT demand evidence.** Running
skillguard against our own plugins proves the tool executes end-to-end on a real
plugin corpus. It says nothing about whether anyone else wants it — Overclock would
adopt it because it's ours, which is exactly the kind of evidence the candidate-ledger
discipline exists to discount. Do not cite this bridge as a demand signal anywhere in
skillguard's own ledger.

Scope stays small: one CI step, no restructuring of `plugins/` or `qa/` to accommodate
it.

## 3. The one-harness decision — OPEN (owner: Luka)

**Status: no decision yet. This section records the trade-offs, not a verdict.**

skillguard M1 needs the behavioral-eval mechanics that live in
[`qa/run_evals.sh`](../qa/run_evals.sh) — but ported to TypeScript. Maintaining two
harnesses forever (Python here, TS there) is waste.

**Options:**

- **(a) Port once to TS; Overclock consumes it.** One harness, one set of fixes.
  Cost: a real port of proven Python machinery, plus migration risk for the 66-case
  corpus and the graders that already work. Overclock takes a dependency on a sibling
  repo for its own CI.
- **(b) Keep Python; defer skillguard M1.** Zero disruption here; the harness that
  works keeps working. Cost: skillguard M1 stalls, or eventually builds its own TS
  harness anyway and the duplication becomes permanent.

**Hard prerequisite either way:** skillguard M1 runs *untrusted* skills, which is
unsafe without container/VM isolation. Overclock's harness only ever evals its own
trusted skills — that is *why* running unsandboxed has been fine here, and why the
mechanics cannot be lifted as-is. The sandbox is a skillguard problem, not an
Overclock one, but it blocks option (a) from being "just a port."

## 4. Candidate ledger — unchanged

The existing verdicts stand as recorded in
[`docs/strategy.md#skill-candidate-ledger`](strategy.md#skill-candidate-ledger):
**PR-reviewer** (STRONG, Phase-0 gate pending) and **super-plan-mode** (PARKED).
Nothing in this ecosystem plan reopens, strengthens, or weakens either — link there,
don't duplicate here.
