# coeval — governed judging setup

Repo: https://github.com/luka-zivkovic/coeval (source-available; internal/
personal use permitted). Requires Node ≥24, pnpm ≥10.33, Docker.

## Stand up

```bash
git clone https://github.com/luka-zivkovic/coeval && cd coeval
pnpm install && cp .env.example .env
docker compose -f docker-compose.pg.yml up -d          # postgres :5432 by default
openssl rand -base64 32                                 # -> BETTER_AUTH_SECRET
```

`.env` essentials:

- `DATABASE_URL=postgres://coeval:coeval@localhost:5432/coeval` (adjust port
  if you remapped via an override file)
- `BETTER_AUTH_SECRET=<generated>`; `BETTER_AUTH_URL` / `TRUSTED_ORIGINS`
  matching your api/web ports (defaults 8787 / 5173; the web dev server
  honors `WEB_PORT` and `COEVAL_API_ORIGIN` if you move them)
- `ANTHROPIC_API_KEY` (or OpenAI/OpenRouter) — without one, judging is a
  deterministic mock; real verdicts need a real key. SECURITY: this key is
  spent per verdict — see cost note in judge-authoring.
- `COEVAL_BOOTSTRAP_TOKEN=<random ≥32 chars>` — enables headless agent
  bootstrap (below). Omit to force browser-only onboarding.

Run (tsx does not auto-load .env):

```bash
set -a; source .env; set +a
pnpm dev:api    # runs migrations on boot
pnpm dev:web
```

## Bootstrap a judge project headlessly

The bundled coeval-audit skill's script drives `POST /api/v1/bootstrap`:

```bash
# setup.json: {owner:{email}, project:{name, apiKeyName},
#             skill:{name, rubricMarkdown, model:{provider, modelId?, temperature}}}
# Omit skill.prompt (safe template with {{rubric_markdown}} is applied);
# omit modelId to let the server pin a catalog model; provider "mock" is
# allowed explicitly for wiring tests.
COEVAL_OWNER_PASSWORD=... node skills/coeval-audit/scripts/coeval-submit.mjs \
  setup setup.json --bootstrap-env-var COEVAL_BOOTSTRAP_TOKEN \
  --owner-password-env-var COEVAL_OWNER_PASSWORD --env-var COEVAL_API_KEY_X
```

- First bootstrap on an empty instance creates the owner (password
  required); later ones reuse the owner by email.
- The project key is saved into `.env` once, never printed. One judging
  skill per project; the version must be ACTIVE before `judge/batch` works
  (bootstrap activates it).
- Verify: `node skills/coeval-audit/scripts/coeval-submit.mjs check --env-var COEVAL_API_KEY_X`

## Submit runs

JSONL lines: `{"input": ..., "output": ..., "expected": "pass"|"fail",
"name": "..."}` — omit `expected` for unlabeled probes (judged, not counted
in agreement).

```bash
node skills/coeval-audit/scripts/coeval-submit.mjs submit runs.jsonl \
  --min-agreement 1.0 --env-var COEVAL_API_KEY_X
```

Content-hash idempotency: unchanged lines reuse verdicts (no re-spend).
Adjudication (exceptions → golden set) is dashboard-only, by design: the
human is the point.
