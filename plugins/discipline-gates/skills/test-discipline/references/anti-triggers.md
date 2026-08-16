# Test Discipline Anti-triggers

Stay silent when no pre-edit behavioral oracle is needed. Do not invoke this skill for:

- typo, copy, comment, or one-line string fixes;
- config, version, dependency, CI, or base-image updates;
- pure renames, signature-only edits, formatting, or import ordering;
- generated files, vendored files, or lockfiles;
- ordinary new-feature implementation;
- diagnosis-only requests;
- behavior-preserving refactors whose touched behavior already has adequate tests asserting its
  observable return values, state changes, events, errors, or other effects.

Mock-only and import-only references are not behavioral coverage. New-feature tests may enter
`validate` only when the user explicitly requests a mutation check; that does not transfer
ownership of the feature workflow to this skill.

When the action does not clearly match repro, characterize, test-only, or explicit validate mode,
default to silence.
