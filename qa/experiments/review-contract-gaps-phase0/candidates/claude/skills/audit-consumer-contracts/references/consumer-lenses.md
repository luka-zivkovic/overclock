# Consumer verification lenses

Apply only lenses supported by the surfaced contract. They are verification prompts, not finding
quotas.

## Persisted identity

Check workflow JSON, configuration, database values, caches, serialized payloads, URLs, event names,
and user-authored expressions that store a raw key or identity. Determine whether aliases,
migrations, or re-resolution preserve old values.

## Precedence and reachability

Check earlier truthy values, fallback ordering, shadowing branches, default values, unconditional
returns, and sibling conditions that can make new code unreachable. Use values from the real
producer rather than a simplified test fixture.

## Version and feature gating

Trace version ranges, feature flags, node or resource types, permissions, and rollout configuration.
Verify both the changed path and consumers that share the underlying option/schema object.

## Schema and propagation

Trace a changed field, enum, event, route, or emitted value through parsing, validation, storage,
transport, and display. Check both readers and writers and any old-version compatibility path.

## Failure and ownership

When the touched value crosses retries, callbacks, transactions, or ownership boundaries, check
idempotency, partial failure, cleanup, and which component owns the final state.

## Defeating evidence

Actively seek guards, type constraints, platform guarantees, aliases, migrations, and realistic
tests that make the suspected violation impossible. Record these as defeated rows rather than
review comments.
