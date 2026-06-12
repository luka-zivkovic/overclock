#!/usr/bin/env bash
# Generates eval fixture projects under $EVAL_FIXTURE_DIR (default /tmp/overclock-eval-fixtures).
# Deterministic: safe to re-run; wipes and rebuilds the fixture root entirely.
set -euo pipefail
cd "$(dirname "$0")/.."          # qa/
# Fixtures MUST live outside any git repository: the skills walk up to the
# nearest .git to find the project root, so a non-git fixture inside this
# checkout would resolve to the checkout itself and write memory there.
ROOT="${EVAL_FIXTURE_DIR:-/tmp/overclock-eval-fixtures}"
rm -rf "$ROOT"
mkdir -p "$ROOT"

export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=fixture@example.com
export GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=fixture@example.com

mem() { mkdir -p "$1/.ai/memory"; }

# ---------- session-handoff ----------
SH="$ROOT/session-handoff"

# eval-0: save request — git repo mid-refactor, dirty file, no memory yet
mkdir -p "$SH/eval-0/src/middleware"
cat > "$SH/eval-0/src/middleware/auth.ts" <<'EOF'
// session-cookie auth middleware (being replaced by JWT)
export function requireSession(req: any, res: any, next: any) {
  if (!req.cookies?.sid) return res.status(401).end();
  next();
}
EOF
( cd "$SH/eval-0" && git init -q -b main && git add -A && git commit -qm "auth service baseline" \
  && git checkout -qb refactor/auth-jwt \
  && git commit -q --allow-empty -m "wip: switch middleware from session cookies to JWT" \
  && printf '\n// touched during refactor session\n' >> src/middleware/auth.ts )

# eval-1: resume request — plain project, NO saved state
mkdir -p "$SH/eval-1/src"
printf '# acme-billing\nInternal billing reconciliation service.\n' > "$SH/eval-1/README.md"
printf 'require("./reconcile");\n' > "$SH/eval-1/src/index.js"

# eval-2: resume after drift — handoff anchored to a rewritten/lost branch
mkdir -p "$SH/eval-2/src/middleware" "$SH/eval-2/test"
cat > "$SH/eval-2/src/middleware/rateLimit.ts" <<'EOF'
// Redis-backed limiter: 100 req/min per API key (rate-limiter-flexible).
// X-RL-Bypass header skips limiting. 429 body is pending the error envelope.
EOF
printf '// error envelope: { error: { code, message } }\n' > "$SH/eval-2/src/errors.ts"
printf '// app wiring: limiter mounted on /api/v1 only; /webhooks intentionally unlimited — exclusion still pending\n' > "$SH/eval-2/src/app.ts"
( cd "$SH/eval-2" && git init -q -b main && git add -A && git commit -qm "rate limiting baseline" \
  && for i in 1 2 3 4; do git commit -q --allow-empty -m "unrelated mainline change $i (drift since handoff)"; done )
mem "$SH/eval-2"
cat > "$SH/eval-2/.ai/memory/HANDOFF.md" <<'EOF'
<!-- memory-schema: v1 -->
# Session Handoff
Saved: 2026-06-03T17:42:00

## Current goal
Cap the public API free tier at 100 req/min per key without breaking the enterprise bypass header.

## Plan
- [x] Redis-backed limiter in src/middleware/rateLimit.ts
- [~] Wire middleware into src/app.ts — done for /api/v1/*, stopped before /webhooks routes
- [ ] 429 response matching the envelope in src/errors.ts
- [ ] Integration tests in test/rateLimit.test.ts

## Decisions
- Redis counters over in-memory — 3 replicas behind the LB would triple a per-process limit.
- Limit keyed on API key, not IP — corporate NATs would throttle whole offices.

## Failed approaches
- express-rate-limit with its Redis store — FAILED: drops millisecond precision; counts reset on whole-second boundaries and burst tests flaked. Do not retry.

## Open questions
- Should the bypass header be validated against the keys table, or is the shared secret enough?

## Next steps
1. Exclude /webhooks routes from the limiter in src/app.ts.
2. Implement the 429 envelope, then run npm test -- rateLimit.

## Key files
- src/middleware/rateLimit.ts
- src/app.ts
- src/errors.ts

## Environment anchors
- Branch: feat/rate-limiting
- HEAD: 8c41f2a
- Dirty files: M src/app.ts, ?? src/middleware/rateLimit.ts
- Date: 2026-06-03
EOF

# eval-3: negative control — ordinary commit request with a handoff present
mkdir -p "$SH/eval-3/src/util"
cat > "$SH/eval-3/src/util/format.ts" <<'EOF'
export function trim(s: string): string { return s.trim(); }
EOF
cat > "$SH/eval-3/src/util/parse.js" <<'EOF'
const { trim } = require("./format");
function parseAmount(input) {
  const cleaned = trim(String(input)).replace(/[$,]/g, "");
  const value = Number.parseFloat(cleaned);
  if (Number.isNaN(value)) throw new Error(`unparseable amount: ${input}`);
  return Math.round(value * 100);
}
module.exports = { parseAmount };
EOF
cat > "$SH/eval-3/src/util/validate.js" <<'EOF'
function isValidSku(sku) { return /^[A-Z]{3}-\d{4}$/.test(String(sku)); }
module.exports = { isValidSku };
EOF
( cd "$SH/eval-3" && git init -q -b chore/ts-migration && git add -A \
  && git commit -qm "ts migration in progress: format.ts converted" )
mem "$SH/eval-3"
cat > "$SH/eval-3/.ai/memory/HANDOFF.md" <<'EOF'
<!-- memory-schema: v1 -->
# Session Handoff
Saved: 2026-06-08T11:05:00

## Current goal
Migrate src/util/ from JavaScript to TypeScript, file by file, keeping runtime behavior identical.

## Plan
- [x] Convert src/util/format.js to src/util/format.ts
- [ ] Convert src/util/parse.js to src/util/parse.ts
- [ ] Convert src/util/validate.js to src/util/validate.ts

## Decisions
- Convert one file per commit — keeps reverts cheap.

## Failed approaches
- None yet.

## Open questions
- None.

## Next steps
1. Convert src/util/parse.js next.

## Key files
- src/util/parse.js — next up

## Environment anchors
- Branch: chore/ts-migration
- HEAD: 4d09b1e
- Dirty files: clean
- Date: 2026-06-08
EOF
printf '\n// began converting: stub types pending\n' >> "$SH/eval-3/src/util/parse.js"

# eval-4: staleness — handoff >14 days old, repo ~35 commits past the anchor
mkdir -p "$SH/eval-4/src"
cat > "$SH/eval-4/src/worker.py" <<'EOF'
import queue_client

def process_batch(batch):
    for job in batch:
        queue_client.ack(job)
EOF
( cd "$SH/eval-4" && git init -q -b main \
  && GIT_AUTHOR_DATE="2026-05-18T10:00:00" GIT_COMMITTER_DATE="2026-05-18T10:00:00" \
     git add -A && GIT_AUTHOR_DATE="2026-05-18T10:00:00" GIT_COMMITTER_DATE="2026-05-18T10:00:00" \
     git commit -qm "worker baseline" )
SAVED_SHA=$(cd "$SH/eval-4" && git rev-parse --short HEAD)
( cd "$SH/eval-4" && for i in $(seq 1 35); do
    git commit -q --allow-empty -m "mainline change $i since handoff"
  done )
mem "$SH/eval-4"
sed "s/@SAVED_SHA@/$SAVED_SHA/" > "$SH/eval-4/.ai/memory/HANDOFF.md" <<'EOF'
<!-- memory-schema: v1 -->
# Session Handoff
Saved: 2026-05-18T17:30:00

## Current goal
Make the batch worker retry failed jobs with exponential backoff instead of acking everything.

## Plan
- [x] Identify ack-on-failure bug in src/worker.py
- [~] Add retry wrapper with backoff — drafting in src/retry.py, not committed
- [ ] Dead-letter queue after 5 attempts

## Decisions
- Backoff base 2s, cap 5min — matches the queue's visibility timeout.

## Failed approaches
- Retrying inside queue_client.ack — FAILED: ack is fire-and-forget at the client layer; retry must wrap process_batch.

## Open questions
- None.

## Next steps
1. Finish src/retry.py and wire it into process_batch.

## Key files
- src/worker.py

## Environment anchors
- Branch: main
- HEAD: @SAVED_SHA@
- Dirty files: ?? src/retry.py
- Date: 2026-05-18
EOF

# eval-5: pasted handoff — project exists, NO saved state on disk
mkdir -p "$SH/eval-5/src/routes"
cat > "$SH/eval-5/src/routes/import.ts" <<'EOF'
import { Router } from "express";
import multer from "multer";
const upload = multer({ storage: multer.memoryStorage() });
export const importRouter = Router();
importRouter.post("/import", upload.single("csv"), async (req, res) => {
  const rows = parseCsv(req.file!.buffer.toString("utf8"));
  await insertRows(rows);
  res.json({ imported: rows.length });
});
declare function parseCsv(s: string): unknown[];
declare function insertRows(r: unknown[]): Promise<void>;
EOF
( cd "$SH/eval-5" && git init -q -b main && git add -A && git commit -qm "csv import endpoint (buffering)" )

# ---------- lessons-learned ----------
LL="$ROOT/lessons-learned"

# eval-0: new correction — pnpm workspace, no memory yet
mkdir -p "$LL/eval-0/src"
printf '{ "name": "acme-api", "private": true, "scripts": { "test": "vitest" } }\n' > "$LL/eval-0/package.json"
printf "lockfileVersion: '9.0'\n" > "$LL/eval-0/pnpm-lock.yaml"
printf 'export const ok = true;\n' > "$LL/eval-0/src/index.ts"

# eval-1: repeat correction — existing lesson at Count 2 + CLAUDE.md guard
mkdir -p "$LL/eval-1/src"
cp "$LL/eval-0/package.json" "$LL/eval-0/pnpm-lock.yaml" "$LL/eval-1/"
cp "$LL/eval-0/src/index.ts" "$LL/eval-1/src/"
cat > "$LL/eval-1/CLAUDE.md" <<'EOF'
# acme-api

API service for Acme. Run tests with `pnpm test`. Source lives in src/.
EOF
mem "$LL/eval-1"
cat > "$LL/eval-1/.ai/memory/LESSONS.md" <<'EOF'
<!-- memory-schema: v1 -->
# Lessons

## Use pnpm, not npm
- **When:** installing, adding, or updating JS dependencies in this repo
- **Wrong:** running `npm install` / `npm i <pkg>` — regenerates package-lock.json, which conflicts with the committed pnpm-lock.yaml
- **Right:** use `pnpm install` / `pnpm add <pkg>`; the repo is a pnpm workspace
- **Evidence:** 2026-06-03 user: "don't use npm, this is a pnpm workspace"; 2026-06-08 user repeated the correction after npm install broke the lockfile
- **Count:** 2
- **Last reinforced:** 2026-06-08
EOF

# eval-2: secret redaction — deploy script project, no memory
mkdir -p "$LL/eval-2/scripts"
cat > "$LL/eval-2/scripts/deploy.sh" <<'EOF'
#!/usr/bin/env bash
curl -fsS -H "Authorization: Bearer ${DEPLOY_KEY:-}" https://deploy.example.com/api/release
EOF

# eval-3: negative control — requirement change; unrelated lesson must stay untouched
mkdir -p "$LL/eval-3/src/routes"
cat > "$LL/eval-3/src/routes/export.ts" <<'EOF'
import { Router } from "express";
import { toXML } from "../lib/xml";
export const exportRouter = Router();
exportRouter.get("/export", async (req, res) => {
  const rows = await req.app.locals.db.query("SELECT * FROM widgets");
  res.type("application/xml").send(toXML(rows));
});
EOF
mem "$LL/eval-3"
cat > "$LL/eval-3/.ai/memory/LESSONS.md" <<'EOF'
<!-- memory-schema: v1 -->
# Lessons

## Run migrations before integration tests
- **When:** running the integration test suite locally or in CI
- **Wrong:** running `pnpm test:integration` against a stale schema — tests fail with missing-column errors
- **Right:** run `pnpm db:migrate` first; the suite assumes the latest schema
- **Evidence:** 2026-05-20 integration run failed with "column widgets.sku does not exist" until migrations were applied
- **Count:** 1
- **Last reinforced:** 2026-05-20
EOF

echo "fixtures ready under $ROOT"
