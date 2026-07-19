# Finding contract

## Reporting threshold

Report a finding only when a concrete failure is attributable to the reviewed change and the
available repository evidence supports it. Prefer one root-cause finding over several symptom
comments. Omit pure style, already-enforced lint, pre-existing defects, hypothetical future misuse,
and improvements with no plausible failure mode.

## Priorities

- **P0 — stop everything:** an immediately exploitable security issue, irreversible widespread data
  loss, or outage with no practical containment. Use rarely.
- **P1 — block merge:** a clear correctness, security, integrity, compatibility, or availability
  regression that affects normal or credible production use.
- **P2 — fix deliberately:** a real, localized defect or failure-path gap that is less urgent but
  still worth maintainer attention. Do not use P2 as a home for nits.

Priority reflects impact and likelihood, not how difficult the fix is. If the impact depends on an
unknown deployment fact, state the dependency and lower confidence.

## Required anatomy

Each finding must contain:

1. `[P0|P1|P2]` and a short imperative title.
2. The exact changed file, line, diff side (`LEFT` or `RIGHT`), and source text that anchors the
   defect.
3. A reproducible input, state, or event sequence.
4. The resulting user, security, data, availability, or maintenance impact.
5. Evidence from current code/tests/configuration and, only when materially useful, a verified
   repository-profile source or precedent.
6. A concrete fix direction or decisive question.
7. Confidence: `high` or `medium`. Do not publish low-confidence findings.

Before prose output, represent these fields with `references/finding-schema.json` and pass them
through `scripts/validate_findings.py`. A finding that cannot survive the mechanical changed-line
and source-text gate is not ready to report.

The suggested comment must stand on its own for the PR author. Avoid generic phrases such as
"consider handling errors" or "this may be insecure."

A suggested comment is text for a human to decide whether to post. It never grants authority to
edit code, apply the suggestion, create a commit, push, or publish the comment.

## Changed-line anchoring

Anchor on a changed line that creates the issue or is the narrowest useful place to fix it. It is
valid to explain consequences in unchanged callers or consumers, but do not attach comments to
unchanged lines. If no changed line can honestly anchor the concern, put it in a clearly labeled
review-level question or omit it.

## Security language

Name the exact attacker-controlled input, trust-boundary crossing, missing control, and consequence.
Use "vulnerability" or "exploit" only when reachability and impact are established. Otherwise use a
precise conditional statement and identify the fact that remains unknown.

## Empty reviews

An empty review is successful when no candidate finding survives. Summarize the highest-risk areas
examined and any inspection blind spots without adding praise or filler.
