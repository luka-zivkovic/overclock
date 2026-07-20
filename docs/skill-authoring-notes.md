# Skill-authoring notes from external repo audits

Conventions worth borrowing, lifted from two audited repos (2026-07-19):

- **mattpocock/skills** — "Skills For Real Engineers"; the meta-skill `writing-great-skills` is its
  theory of skill design.
- **EveryInc/compound-engineering-plugin** — 31 skills; `CONCEPTS.md` glossary plus a dogfooded
  `docs/solutions/skill-design/` corpus of ~30 skill-design learnings.

These are authoring conventions, not skill candidates — skill adoption verdicts live in
`docs/brainstorm/external-eval-*.md`. Nothing here is binding until it's applied to a skill (which
is a shipping change: version bump + evals per the maintainer contract).

## From mattpocock/skills (`writing-great-skills`)

**Leading words.** Anchor each skill on one compact concept already living in the model's
pretraining that the agent "thinks with" while running the skill (`tight`, `red`, `seam`,
`fog of war`, `tracer bullet`). Serves predictability twice: anchors execution in the body, and
anchors invocation when the same word appears in prompts/docs. Overclock skills mostly lack a
deliberate leading word; worth checking on the next skill build.

**Named failure modes as an authoring checklist.** Complements our right-sizing discipline:

- *no-op line* — "a line the model already obeys by default." Test: does it change behavior vs the
  base model? If not, delete it.
- *negation* — "don't think of an elephant names the elephant." Prompt the positive behavior
  instead of prohibiting the negative.
- *sediment* — "stale layers that settle because adding feels safe and removing feels risky."
  Audit SKILL.md bodies for lines nobody would re-add today.
- *premature completion* — cured by **checkable completion criteria**: the skill states an
  observable condition (a command output, a file state), not "when done."

**Two-loads model.** A model-invoked skill costs *context load* (its description sits in the
window every turn); a user-invoked skill costs *cognitive load* (the user must remember it
exists). Pick invocation mode to minimize the right one. Router skills cure piled-up cognitive
load — relevant only if the kit grows well past its current size (overclock-setup partially plays
this role today).

**Right-sizing convergence.** Their independent rule matches ours: model-invoked descriptions need
concrete positive triggers and explicit anti-triggers, and trivial work stays a silent no-op. Two
repos arriving at the same discipline independently is decent evidence it's load-bearing.

## From compound-engineering-plugin

**CONCEPTS.md pattern.** A repo-root glossary giving one-paragraph names to the repo's own design
primitives ("evidence dossier", "confidence anchor", "detached job"), so skills reference
mechanisms without redefining them. Rules worth keeping if we adopt one: the file stands on its
own (no file paths, no current config values — "state the behavior, not the number"); terms enter
by accretion *and* proactive seeding; one term per concept, retired synonyms recorded as aliases.

**Pass paths, not content.** Fan-out subagents write full artifacts (dossiers, findings) to a
scratch dir and return only a path + gist; the orchestrator reads artifacts back when assembling.
Documented rationale (their issue #956): a subagent asked to return a long prose body
intermittently returns an executive summary instead. Paired with a hardened scratch-dir idiom
(per-uid `/tmp` root, symlink refusal, `umask 077`, random run id). Directly relevant to our
`.claude/workflows/*.js` fan-outs, which currently return content inline through schemas.

**Confidence anchors over continuous scores.** Findings use a small fixed scale tied to
behavioral criteria (0/25/50/75/100 with named meanings), never free floats — "the model cannot
calibrate self-reported confidence at that granularity." Severity is kept orthogonal to
*autofix class* (applied-silently / gated-auto / manual / advisory): urgency and how safely a fix
can be auto-applied are different axes. Relevant to the PR-reviewer phase-0 rubric and any future
review skill.

**Standing residuals in watch loops.** In any long-running loop, an item that needs a human
*parks that item* and blocks the final done-declaration, but never ends the loop — "ending the
whole loop the moment one item needs a human is the primary failure mode."

**Load stubs.** When content moves to a `references/` file, the inline pointer names what the file
contains *and the failure mode of skipping it*, so the load is structurally necessary rather than
optional flavor. Sharper than a bare link; our SKILL.md → references links mostly already do this,
but it's a good review lens.

**Session-settled decisions.** Decisions the user examined-and-chose carry a provenance label
through multi-step pipelines; downstream steps augment but never re-ask, and contradict only on
evidence. An agent never labels its own unexamined proposal as settled.

**Testing skills as static artifacts.** They assert shell-safety, frontmatter validity, cross-skill
naming invariants, and *doc-claim accuracy* (cited paths/links must exist in the tree) in ordinary
unit tests over the markdown. Overclock's `tools/` + `qa/` already do most of this
(validate_skill, audit_skills, shared-files, version-bump); the one mechanism worth considering is
a **doc-claims check** — verify that file paths cited inside SKILL.md/references actually exist.

## Micro-lift candidates (follow-ups, each a shipping change)

Small mechanisms worth lifting into existing skills if their parent candidates don't get adopted
whole (verdicts in the external-eval log):

- *Never simplify away a safety check* — **executed 2026-07-20**: owned by
  discipline-gates/git-archaeologist 0.1.4 (simplify-framed trigger surface) and pr-feedback's
  rubric. CE's extra nuance ("honor deliberate duplication pinned by a settled decision") rides
  with the settled-decisions lift below.
- *Silent-pass verification trigger* — a CI/merge-gate change gets adversarial review regardless of
  diff size, "its risk isn't blast radius, it's fidelity — it can go green while the real thing is
  red."
- *Decision primer for re-runs* — a review skill re-run on the same artifact carries prior-round
  applied/rejected decisions so rejected findings don't resurface.
