# Right-sizing — the one triage question

Shared triage rule for the discipline-gates plugin. Duplicated byte-identical into each
skill's `references/`; `tools/shared-files.txt` guards the copies against drift.

Answer ONE binary question before engaging any gate:

> Does a structural trigger apply — AND is observable behavior or defensive intent at stake?

- A **structural trigger** is a concrete action class named in the skill: about to fix a
  reported bug with a stated symptom; about to edit code with no behavioral test coverage; a
  new test just went green; about to delete or weaken a guard / early return / retry / sleep /
  lock / clamp. Never a vibe ("this code looks risky / surprising").
- If the answer is no, or the change matches `anti-triggers.md` → **silent no-op**. Do the
  requested work without mentioning the gate.
- If yes → engage exactly the one matching mode. The structural check IS the right-size gate;
  there is no extra ceremony to scale up or down.

One hard safety contract rides above everything: test-discipline's validate mode restores
mutated production code unconditionally — on failure, on surprise, on interruption — before
any reporting or further work. A gate that leaves the tree mutated is worse than no gate.
