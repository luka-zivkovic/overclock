# Security and edge-case lenses

Start with the changed behavior, then activate the relevant lenses. Do not recite this checklist in
the output.

## Trust boundaries and data flow

- User, tenant, webhook, file, URL, header, token, model, or third-party data crossing into a more
  trusted component.
- Authorization checked on the exact object and action, after canonicalization and before side
  effects; tenant and ownership boundaries preserved across caches and queues.
- Secrets excluded from logs, errors, analytics, URLs, client bundles, generated artifacts, and
  persisted review context.
- Untrusted text kept as data rather than instructions, templates, queries, commands, paths, or
  executable markup.

## Injection and unsafe interpretation

- SQL/NoSQL/LDAP/template/shell injection, unsafe deserialization, eval-like behavior, prototype
  pollution, and regex denial of service.
- SSRF through redirects, alternate IP encodings, DNS rebinding, scheme confusion, proxy behavior,
  or metadata/private-network access.
- File traversal, archive extraction, symlink/hardlink confusion, unsafe temporary files, and
  validation performed before rather than after normalization.
- XSS and URL injection across server-rendered HTML, client DOM sinks, markdown, redirects, and
  content-security-policy assumptions.

## Cryptography, authentication, and transport

- Insecure defaults, fail-open verification, algorithm/key confusion, weak randomness, replay,
  missing expiry/audience/issuer checks, and credential rotation compatibility.
- TLS verification preserved by default; opt-outs explicit, scoped, and not silently inherited.
- Authentication state invalidation, session fixation, CSRF, origin checks, and recovery flows.

## State, concurrency, and distributed failure

- Partial writes, non-atomic multi-step updates, rollback gaps, duplicate delivery, retry storms,
  lost updates, stale reads, race windows, and idempotency-key scope.
- Timeout/cancellation propagation, resource cleanup, backpressure, queue redelivery, and
  at-least-once versus exactly-once assumptions.
- Cache invalidation and key partitioning across users, tenants, environments, versions, and
  authorization changes.

## Boundary values and lifecycle

- Empty, missing, null, zero, negative, maximum, oversized, duplicated, reordered, malformed,
  Unicode, time-zone, clock-skew, daylight-saving, and integer/precision inputs.
- First-run, upgrade, downgrade, rollback, restart, reconnect, retry, cancellation, deletion,
  migration, and partially initialized states.
- Backward/forward compatibility for APIs, events, schemas, stored data, CLI flags, configuration,
  and rolling deployments.

## Tests as evidence

Check whether tests:

- assert the externally visible result rather than an implementation detail;
- reach the failure branch, boundary value, rollback, or concurrency condition at issue;
- would fail if the new guard or behavior were removed;
- account for old persisted data and mixed-version deployment where applicable;
- avoid mocks that bypass the risky boundary.

## Silent-pass verification mechanisms

When CI, build/deploy gates, coverage or lint checks, test configuration, mocks, fixtures, setup, or
shared test infrastructure changes, test whether the mechanism can falsely report success. Inspect
error suppression, permissive exit behavior, skipped or undiscovered tests, changed path filters,
mock fidelity, environment divergence, and gates that run but no longer protect the production
path. This lens applies to the mechanism itself; an ordinary feature-test assertion does not
activate it on its own.
