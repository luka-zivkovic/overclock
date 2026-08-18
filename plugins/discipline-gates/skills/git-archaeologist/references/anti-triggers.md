# Git Archaeologist Anti-triggers

Stay silent unless the requested change weakens a named defensive construct in existing committed
code. Do not invoke this skill for:

- typo, copy, comment, or one-line string fixes;
- config, version, dependency, CI, or base-image updates;
- pure renames, signature-only edits, formatting, or import ordering;
- behavior-preserving control-flow rewrites or helper extraction that retain every guard,
  retry, lock, bound, and defensive effect;
- ordinary early returns that do not reject invalid or unsafe state;
- new features, pure additions, generated files, vendored files, or lockfiles;
- a construct introduced only by uncommitted or brand-new code.

A committed construct in a dirty file still has recoverable history. When the requested operation
is ambiguous, default to silence rather than inventing a weakening.
