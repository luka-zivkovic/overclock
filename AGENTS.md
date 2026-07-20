# Overclock maintainer contract

Overclock is a repository of independently installable Claude Code plugins. Keep repository
instructions provider-neutral here; `CLAUDE.md` imports this file for Claude Code.

## Product decisions

- Read `docs/strategy.md` before proposing or building a skill. It is the source of truth for
  build/no-build decisions and assessed candidates.
- Treat `docs/brainstorm/SHORTLIST.md` as evidence accrual, not a roadmap.
- Preserve Overclock's core boundaries: setup is report-only, hooks are small and read-only, and
  skills do not auto-commit or silently broaden their write scope.

## Skill and plugin invariants

- Shipped skills live at `plugins/<plugin>/skills/<skill>/SKILL.md`; each plugin is independently
  installable and owns its manifest at `plugins/<plugin>/.claude-plugin/plugin.json`.
- Every skill distribution must carry `agents/openai.yaml` with quoted `display_name`,
  `short_description` (25–64 characters), and a one-sentence `default_prompt` that names the skill
  as `$<skill-name>`.
- Invocation policy must agree across harnesses:
  - A skill with `disable-model-invocation: true` must set
    `policy.allow_implicit_invocation: false` in `agents/openai.yaml`.
  - A model-invoked skill must not set `policy.allow_implicit_invocation: false`.
- Model-invoked descriptions need concrete positive triggers and explicit anti-triggers. Preserve
  the existing right-sizing discipline: trivial or out-of-scope work should remain a silent no-op.
- Keep `SKILL.md` focused on core execution. Put branch-specific detail in directly linked
  `references/`, deterministic helpers in `scripts/`, reusable output material in `assets/`, and
  fill-in documents in `templates/`.
- Files listed together in `tools/shared-files.txt` are intentionally duplicated and must remain
  byte-identical.

## Publication invariants

- A change anywhere under `plugins/<plugin>/` is a shipping change. Bump that plugin's manifest
  version and the matching entry in `.claude-plugin/marketplace.json`.
- Keep published versions in
  `plugins/overclock-setup/skills/setup/references/capabilities.json` synchronized with the
  marketplace. Because the catalog ships inside `overclock-setup`, changing it also requires an
  `overclock-setup` version bump.
- Record user-visible shipped changes under the relevant plugin in `CHANGELOG.md`.
- `session-memory` and `learning-loop` are mutually exclusive packages. Preserve the symmetric
  conflict declaration and their intentionally shared lesson format.

## Evidence requirements

- Behavioral changes require a committed live-eval case or an explicit reason the existing case
  already covers them.
- Routing changes require positive and negative controls. Update the trigger battery when that
  skill has one; add one for a new model-invoked skill whose routing is not fully exercised by its
  behavioral suite.
- Do not treat `qa/_work/` output as source. It is generated local evidence and stays uncommitted.
- Prefer deterministic assertions for structure, versions, file state, and safety boundaries;
  reserve model grading for behavior that cannot be checked mechanically.

## Validation

Run the checks relevant to the change, then the full local suite before handoff:

```bash
for d in plugins/*/skills/*/; do python3 tools/validate_skill.py "$d"; done
python3 tools/audit_skills.py plugins --fail-on fail
python3 tools/check_shared_files.py
python3 tools/check_setup_catalog.py
python3 -m unittest discover -s qa -p 'test_*.py'
python3 tools/check_version_bump.py --base origin/master
```

When plugin manifests or marketplace metadata change, also run `claude plugin validate .` and
validate each affected plugin directory when the Claude CLI is available.
