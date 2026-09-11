# Capture and handoff audit repairs — 2026-09-11

## Scope

This change carries four findings from the repository audit onto current `master`:
capture redaction, Codex notification identity, Claude native skill tags, and the impossible
handoff confirmation eval. Feature Dossier and Lateral Engineering are excluded at the
maintainer's request; the dossier repairs remain with that unmerged local addition.
The upstream Skill Maintenance and focused Local Eval Stack workflows are preserved.

## Evidence tiers and acceptance

| Change | Tier | Acceptance condition |
| --- | --- | --- |
| Capture redaction | `objective` | All three standalone capture scripts remove sensitive object values, spaced quoted passwords, and nested/escaped JSON secrets before envelope serialization. pi error messages use the same redactor; unrelated values survive. |
| Codex notification selection | `objective` | Select the event's UUID even when another rollout is newer. Invalid/missing identity, no match, duplicate matches, and mismatched metadata fail before ingest. The old hook recipe with appended JSON remains compatible. |
| Claude activation tags | `objective` | Native `Skill` calls and direct `Read` calls yield deterministic, deduplicated tags; namespaces survive. Bash/Grep path mentions do not count as activations. |
| Handoff confirmation | `rubric` | Initial resume verifies state, presents the brief, and waits. A real user confirmation then authorizes the local migration without reopening the settled decision, repeating confirmation, or connecting to a database. |

`qa/test_eval_stack.py` exercises the real mappers and CLI using synthetic data. It also checks
60,000-character ordinary and repeated-key output with a five-second subprocess timeout and
the expected 50 KB truncation. This guards against excessive regex backtracking found during
the repair. Free-text redaction remains best-effort; these checks do not prove arbitrary prose
contains no secrets.

Notification parsing follows the [official Codex contract](https://learn.chatgpt.com/docs/config-file/config-advanced#notifications),
consulted on 2026-09-10: the appended JSON contains `type: agent-turn-complete` and `thread-id`.
Filename/metadata agreement and ambiguity refusal are additional importer checks.

## Behavioral and routing coverage

- `qa/evals/eval-stack/local-eval-stack.evals.json` retains all seven upstream cases and adds
  `native-skill-and-private-envelope` and `notification-session-identity`. Both use local synthetic
  fixtures without network ingest, real logs, credentials, or persistent configuration changes.
- `qa/evals/session-memory/session-handoff.evals.json` case 7 now has a genuine initial resume
  turn and a subsequent confirmation turn. Setup tool calls/results are available to the judge,
  so waiting followed by implementation no longer requires an imaginary user reply.
- Both suites declare `skill` and `plugin` evidence: Eval Stack now has two skills, and Session
  Memory has siblings and a startup hook. No external composition is declared; `stack` is not
  applicable. Existing trigger descriptions are unchanged. The session-handoff battery already
  excludes ordinary in-conversation continuation. Native trace-tag classification has its own
  deterministic positive and negative controls.

## Harness mechanics

Tier: `objective`. `continue_after_setup` requires nonempty setup turns with the target installed.
The candidate setup explicitly activates the namespaced target and verifies its availability,
loaded plugin, and isolated API authentication. The final ordinary prompt must resume the same
successful session. Setup tool evidence reaches the judge; baseline sessions remain skill-free.
Unit tests cover the case contract, same-session continuity, unsuccessful/missing setup refusal,
tool-evidence retention, and generated fixture parity.

## Validation and limits

Local validation on the audit-only branch passes: **378 unit tests**, all 18 skill validators,
18 PASS/0 WARN/0 FAIL in the skill audit, all eight shared-file groups, documentation claims
(125 cases/18 distributions), the 12-package catalog, version bumps against `origin/master`,
shell syntax, and diff whitespace checks. Native Claude validation passes for the marketplace
and all three affected plugins. Independent Claude Fable 5.1 review is pending.

Live paired behavioral judging and routing runs remain pending because the isolated eval harness lacks
`ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN`. No measured model-quality improvement is claimed
from deterministic tests or a source review. The catalog changes versions only; existing Setup
cases still cover report-only behavior.
