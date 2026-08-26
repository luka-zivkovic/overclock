# ironside — trace store setup

Repo: https://github.com/luka-zivkovic/ironside (self-hosting is free under
its Sustainable Use License). Requires Docker; ~2GB RAM headroom
(ClickHouse is the heavy tenant).

## Stand up

```bash
git clone https://github.com/luka-zivkovic/ironside && cd ironside
docker compose up -d --build     # postgres, clickhouse, redis, minio, api, worker, web
curl -s localhost:8788/health    # expect every store "ok"
```

Default host ports: web 8080, api 8788, postgres 5433, redis 6380,
clickhouse 8123/9000, minio 9010/9011. If any collide with your day-to-day
ports, add a `docker-compose.override.yml` remapping them (compose loads it
automatically) — and if you remap the web port, ALSO override the api
service's `WEB_ORIGINS` env to include the real browser origin, or every
`/api/auth/*` call fails with "untrusted request origin".

## Owner, then seed — order matters

```bash
docker compose exec -T -e DATABASE_URL=postgres://ironside:ironside@postgres:5432/ironside \
  api node apps/api/dist/src/scripts/owner-setup.js
# prints a one-time setup capability + /setup URL
```

Complete setup in the browser at `<your-web-origin>/setup`, or headlessly:

```bash
curl -X POST <api>/api/auth/setup -H "Content-Type: application/json" \
  -H "Origin: <your-web-origin>" \
  -d '{"token":"<capability>","username":"<you>","password":"<strong>"}'
```

Then seed the first org/project/credential:

```bash
docker compose exec -T -e DATABASE_URL=postgres://ironside:ironside@postgres:5432/ironside \
  api node apps/api/dist/src/scripts/seed.js
```

SECURITY: the seed prints an `ironside_sc_…` machine credential ONCE. It is
**write-scoped (ingest only)** — reads and the UI use your owner session.
Store the credential for the tracer config; store the owner password in a
local credentials file outside any repo.

## Verify

Log into the web UI (owner login). Ingest a probe if you want proof before
wiring the tracer:

```bash
curl -X POST <api>/api/v1/ingest -H "Authorization: Bearer <sc-credential>" \
  -H "Content-Type: application/json" \
  -d '{"events":[{"type":"trace-upsert","body":{"id":"probe-1","timestamp":"2026-01-01T00:00:00Z","name":"probe","sessionId":"probe-1","tags":[],"metadata":{}}}]}'
```

The dead-letter queue (`GET /api/v1/projects/<proj>/ingest-failures`, owner
session) is the debugging surface for anything unmappable.

Traces settle under a quiet-period watermark (default 300s without new
events) — consumers should treat unsettled traces as in-flight; see
`spec/trace-envelope-v1.md` in the repo.
