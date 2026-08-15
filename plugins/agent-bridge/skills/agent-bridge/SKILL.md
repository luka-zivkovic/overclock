---
name: agent-bridge
description: "Use a DIFFERENT installed coding provider (Codex or Gemini when you are Claude; any provider other than the one now running) as a bounded leaf collaborator while the current agent keeps ownership of the user's task. The trigger is that the user names such a different provider as the actor — Codex, Gemini, 'another installed coding provider', 'cross-provider help', or agent-bridge itself. When a request names a different provider, this skill owns it even if the verb is review, critique, diagnose, second opinion, or implement: 'use Codex as a second reviewer for this diff', 'ask Codex to diagnose why this parser fails', 'get Gemini's independent critique', 'implement the fix but delegate these paths to Gemini in an isolated workspace', 'use that cross-provider help now'. Route here for those over sibling review, critique, debugging, or interview skills, which handle the same verbs only when the current agent does the work itself with no different provider named. Also use when work is blocked and the user authorized cross-provider help in this conversation. This skill is the only sanctioned path to another provider: never construct ad hoc codex, gemini, or claude CLI commands for consultation or delegation. Consult for read-only analysis; delegate only when the user's request already authorizes implementation, with exact allowed paths and acceptance checks. Do not use for routine work the current agent can finish directly, for review/critique/diagnosis the current agent should do itself when no different provider is named, to collect extra votes, or without current authorization to share scoped context externally. Do NOT use for same-harness requests — asking the current harness to spawn, call, or delegate to another session of itself (for example Claude Code asked to open another Claude Code session) is not cross-provider; decline it directly without this skill. Do not use to let two agents write the active checkout concurrently."
---

# Agent Bridge

Keep ownership of the user's task. Use a different installed harness only as a leaf collaborator,
then verify its claims or changes yourself. Never treat another model's answer as proof.

The command examples below use Claude Code's `${CLAUDE_SKILL_DIR}` and
`${CLAUDE_PROJECT_DIR}` variables. On Codex, Gemini, or another host that does not define them, use
the host-declared installed directory for this `agent-bridge` skill and the authorized current
project root as absolute paths. Do not scan user directories or plugin caches to discover either
path. The parent keeps its normal task tools so it can inspect a candidate patch and run independent
verification after applying it.

## Preserve authority and external-sharing boundaries

- Require current-conversation authorization to send the scoped task or repository content to
  another provider. Installing this skill is not blanket consent for silent external calls. The
  bridge cannot enforce this; it forwards only an allowlisted, provider-scoped environment to the
  child, so unrelated secrets stay in the parent, but the consent decision is yours.
- Use `consult` unless the user already asked to implement, fix, or modify the project. Diagnosis,
  review, research, and planning alone stay read-only under the provider's own sandbox; the bridge
  reports `workspace_changed` if the active tree moved during a consultation, but does not itself
  prevent a provider from writing.
- Delegate only a bounded outcome with explicit allowed paths. The worker may edit only its isolated
  temporary clone; it must not commit, push, publish, invoke another agent, or touch the active
  checkout.
- Never silently substitute a provider. Report missing binaries, authentication failures, timeouts,
  malformed output, or scope violations as failures.
- Do not consult repeatedly until a provider agrees. One pass per material question is the default.

Read [references/collaboration-contract.md](references/collaboration-contract.md) before the first
delegated write in a conversation. It defines request fields, result states, and integration gates.

## Select the mode

Use `consult` for a focused independent analysis, critique, diagnosis, alternative, or verification.
The external harness gets read-only repository access and returns advice. Re-check decision-changing
claims against current evidence before using them.

Use `delegate` for a concrete implementation subtask only when all are true:

1. the user authorized implementation in the parent task;
2. the repository is clean and has an exact `HEAD`;
3. allowed paths and acceptance criteria are concrete;
4. the parent can inspect and validate a returned patch before applying it; and
5. the selected provider is a different harness from the current one.

If any delegate condition fails, keep working in the parent or use `consult`; do not weaken the gate.

## Check provider readiness

Run the deterministic helper rather than constructing provider CLI commands yourself:

```text
python3 "${CLAUDE_SKILL_DIR}/scripts/agent_bridge.py" check \
  --provider <claude|codex|gemini>
```

`check` verifies executable availability and version output only. Authentication is verified by the
actual run. Do not install a CLI, log in, change provider configuration, or expose credentials.
Gemini runs fail closed when the project contains `.env`, `.gemini/.env`,
`.gemini/settings.json`, or `.gemini/sandbox.Dockerfile`, because its CLI loads those
repository-controlled files at startup and has no equivalent of Claude's safe mode.

## Build one bounded request

Pass JSON on standard input. Keep context minimal and exclude secrets, unrelated files, prior model
answers, and persuasive framing. A delegate request must include non-empty `allowed_paths` and
`acceptance_criteria`.

```json
{
  "task": "Implement idempotent cancellation for queued jobs.",
  "context": "The parent owns API changes; this worker owns only the queue module.",
  "allowed_paths": ["src/queue", "tests/queue"],
  "acceptance_criteria": [
    "Repeated cancellation is a no-op after the first success",
    "Existing queue tests still pass"
  ],
  "verification": ["npm test -- queue"]
}
```

Paths are repository-relative. Use `.` only when the user truly delegated the whole repository
change. Never include `.git` or paths that escape the repository.

## Run the leaf collaborator

For consultation:

```text
python3 "${CLAUDE_SKILL_DIR}/scripts/agent_bridge.py" run \
  --provider <provider> --mode consult --cwd "${CLAUDE_PROJECT_DIR}" <<'AGENT_BRIDGE_REQUEST'
<request JSON>
AGENT_BRIDGE_REQUEST
```

For isolated implementation delegation:

```text
python3 "${CLAUDE_SKILL_DIR}/scripts/agent_bridge.py" run \
  --provider <provider> --mode delegate --cwd "${CLAUDE_PROJECT_DIR}" \
  --allow-write <<'AGENT_BRIDGE_REQUEST'
<request JSON>
AGENT_BRIDGE_REQUEST
```

The helper never falls back to another provider. A successful delegate run returns a result path,
result digest, patch path, patch digest, exact base SHA, changed paths, verification reported by the
worker, and the worker's raw final answer. The temporary clone remains available for inspection.

## Validate delegated work before integration

Use the exact result path and SHA-256 printed by `run`:

```text
python3 "${CLAUDE_SKILL_DIR}/scripts/agent_bridge.py" inspect \
  --result <absolute-result-path> --sha256 <result-sha256>
```

Then independently:

1. inspect every changed hunk and ensure it solves the delegated objective;
2. reject unsupported claims and out-of-scope changes;
3. confirm the worker's verification is relevant rather than trusting its summary; and
4. apply only when the active repository is still clean at the recorded base SHA.

Apply the digest-locked patch through the helper:

```text
python3 "${CLAUDE_SKILL_DIR}/scripts/agent_bridge.py" apply \
  --cwd "${CLAUDE_PROJECT_DIR}" \
  --result <absolute-result-path> --sha256 <result-sha256>
```

`apply` revalidates the result, patch digest, base SHA, clean active worktree, and allowed paths, then
uses `git apply --check` before applying. It never stages or commits. After applying, run the relevant
project checks yourself; the worker's test report is evidence, not verification of the active tree.

For a consultation, incorporate only claims you can support. For a delegation, report which provider
worked, what was accepted or rejected, files applied, parent-side verification, and residual risks.

## Stop conditions

Stop without improvising when the helper reports `unavailable`, `same_harness`, `recursive_call`,
`dirty_repository`, `provider_failed`, `timed_out`, `scope_violation`, `stale_base`, or
`invalid_result`. Also stop on `unsafe_provider_configuration`, `workspace_changed`,
`workspace_tampered`, or `result_too_large`; never answer on behalf of a provider that did not run
and never manually apply an unvalidated patch after the helper refuses it.
