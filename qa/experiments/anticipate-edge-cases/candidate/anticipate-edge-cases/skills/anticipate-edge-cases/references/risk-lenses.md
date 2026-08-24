# Pre-implementation risk lenses

Apply only lenses activated by the requested behavior and the pre-change repository. A lens suggests
questions; it is never evidence that a risk exists.

## Input and contract boundaries

- Empty, absent, malformed, oversized, duplicated, reordered, or version-skewed inputs.
- Defaults that differ across API, CLI, UI, configuration, or persisted state.
- Existing callers or clients that rely on an old output shape, error, status, timing, or side effect.
- Partial rollout where producers and consumers run different versions.

## State and persistence

- Initial, terminal, deleted, archived, expired, or already-processed state.
- Repeated events and the identity key that makes an operation idempotent—or fails to.
- Multi-step updates where one durable write succeeds and another fails.
- Schema migrations, backfills, old rows, nullability, downgrade, and rollback behavior.

## Identity and reference propagation

Activate this lens only when the requested behavior changes, reconciles, aliases, or reassigns an
identifier, name, key, path, owner, or other identity-bearing value.

- Persisted or external consumers that retain the old raw identity after the producer adopts a new
  one, including user-authored workflow/configuration state outside the producing subsystem.
- Consumers that re-resolve a stable logical key versus consumers that store and replay a raw ID.
- Alias, migration, reference-update, cache-invalidation, route, event, and rollback paths needed
  to keep both sides of an identity transition coherent.
- Partial propagation where the primary record succeeds but references, indexes, caches, queued
  work, or emitted payloads still point at the displaced identity.

## Failure and recovery

- Timeout after the remote side has succeeded but before acknowledgment reaches the caller.
- Retry classification, attempt limits, backoff, cancellation, and retry storms.
- Cleanup or compensation after partial success; resource release on every exit path.
- Error translation that loses the signal callers use to retry, alert, or render recovery UI.

## Concurrency, ordering, and time

- Two workers, requests, tabs, jobs, or callbacks acting on the same logical object.
- Out-of-order, late, duplicated, or re-entrant events.
- Compare-and-set, lock ownership, transaction isolation, queue visibility, and lost updates.
- Clock boundaries, time zones, daylight-saving changes, expiry races, and inclusive endpoints.

## Trust and tenancy

- Authentication versus authorization, role changes, object ownership, and cross-tenant identifiers.
- Validation before side effects, parsing ambiguity, path or URL handling, and injection surfaces.
- Secret, personal, or customer data crossing logs, errors, analytics, caches, or external services.
- Webhooks, redirects, callbacks, and other confused-deputy boundaries.

## Resource and operational limits

- Fan-out, unbounded collections, payload size, recursion, queue pressure, and rate limits.
- Slow or unavailable dependencies, circuit breaking, overload behavior, and graceful degradation.
- Observability that distinguishes success, partial success, retry, abandonment, and poison inputs.
- Configuration or feature-flag defaults, staged rollout, disablement, and emergency rollback.

## User and interface state

- Double submission, stale optimistic updates, navigation during work, and component teardown.
- Loading, empty, partial, permission-denied, offline, and error states.
- Accessibility and keyboard behavior only when the requested interaction changes them.
- Locale, Unicode, pluralization, truncation, and user-visible compatibility when applicable.

## Verification mechanism

- Whether a proposed test would execute the intended path rather than a mock or adjacent branch.
- Whether a success assertion can pass while the externally visible behavior is broken.
- Whether failure, concurrency, compatibility, and recovery behavior needs a different test level.
- Whether the pre-change repository already carries a helper or test oracle that should be reused.
