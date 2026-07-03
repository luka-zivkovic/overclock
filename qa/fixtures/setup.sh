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

# ---------- test-discipline ----------
TD="$ROOT/test-discipline"

# eval-0: repro happy path — real floating-point cents bug (floor vs round)
mkdir -p "$TD/eval-0/src"
printf '{ "name": "acme-billing", "private": true, "scripts": { "test": "node --test" } }\n' > "$TD/eval-0/package.json"
cat > "$TD/eval-0/src/money.js" <<'EOF'
function parseAmount(input) {
  const cleaned = String(input).trim().replace(/[$,]/g, "");
  const value = Number.parseFloat(cleaned);
  if (Number.isNaN(value)) throw new Error(`unparseable amount: ${input}`);
  return Math.floor(value * 100);
}
module.exports = { parseAmount };
EOF
mkdir -p "$TD/eval-0/tests"
( cd "$TD/eval-0" && git init -q -b main && git add -A && git commit -qm "billing baseline" )

# eval-1: repro cannot-reproduce trap — the reported bug is already fixed on HEAD
mkdir -p "$TD/eval-1/src" "$TD/eval-1/tests"
cp "$TD/eval-0/package.json" "$TD/eval-1/"
sed 's/Math.floor/Math.round/' "$TD/eval-0/src/money.js" > "$TD/eval-1/src/money.js"
( cd "$TD/eval-1" && git init -q -b main && git add -A \
  && git commit -qm "billing baseline" \
  && git commit -q --allow-empty -m "fix: parseAmount cents rounding (floor -> round)" )

# eval-2: characterize — quirky untested function; tests/ exists but covers another module
mkdir -p "$TD/eval-2/src" "$TD/eval-2/tests"
printf '{ "name": "acme-reports", "private": true, "scripts": { "test": "node --test" } }\n' > "$TD/eval-2/package.json"
cat > "$TD/eval-2/src/duration.js" <<'EOF'
function formatDuration(totalSeconds) {
  if (totalSeconds < 0) return "0s";
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = Math.floor(totalSeconds % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}
module.exports = { formatDuration };
EOF
cat > "$TD/eval-2/src/sku.js" <<'EOF'
function isValidSku(sku) { return /^[A-Z]{3}-\d{4}$/.test(String(sku)); }
module.exports = { isValidSku };
EOF
cat > "$TD/eval-2/tests/sku.test.js" <<'EOF'
const { test } = require("node:test");
const assert = require("node:assert");
const { isValidSku } = require("../src/sku");

test("accepts well-formed SKUs", () => assert.strictEqual(isValidSku("ABC-1234"), true));
test("rejects malformed SKUs", () => assert.strictEqual(isValidSku("abc-12"), false));
EOF
( cd "$TD/eval-2" && git init -q -b main && git add -A && git commit -qm "reports baseline" )

# eval-3: validate — committed vacuous test (asserts a local reimplementation, never imports src)
mkdir -p "$TD/eval-3/src" "$TD/eval-3/tests"
printf '{ "name": "acme-orders", "private": true, "scripts": { "test": "node --test" } }\n' > "$TD/eval-3/package.json"
cat > "$TD/eval-3/src/order.js" <<'EOF'
function applyDiscount(total, pct) {
  if (pct < 0 || pct > 1) throw new Error(`invalid discount: ${pct}`);
  return total - total * pct;
}
module.exports = { applyDiscount };
EOF
cat > "$TD/eval-3/tests/order.test.js" <<'EOF'
const { test } = require("node:test");
const assert = require("node:assert");

test("applyDiscount computes the discounted total", () => {
  const applyDiscount = (total, pct) => total - total * pct;
  assert.strictEqual(applyDiscount(100, 0.1), 90);
});
EOF
( cd "$TD/eval-3" && git init -q -b main && git add -A && git commit -qm "orders baseline with discount test" )

# eval-4: negative control — version bump, no gate ceremony expected
mkdir -p "$TD/eval-4/src"
printf '{ "name": "acme-widget", "private": true, "version": "1.1.0" }\n' > "$TD/eval-4/package.json"
printf 'module.exports = { widget: true };\n' > "$TD/eval-4/src/index.js"
( cd "$TD/eval-4" && git init -q -b main && git add -A && git commit -qm "widget baseline" )

# ---------- git-archaeologist ----------
GA="$ROOT/git-archaeologist"

# eval-0: clamp with recoverable intent — introducing commit cites OOM + issue link
mkdir -p "$GA/eval-0/src"
cat > "$GA/eval-0/src/worker.js" <<'EOF'
async function processBatch(jobs) {
  for (const job of jobs) await handle(job);
}
async function handle(job) { /* ... */ }
module.exports = { processBatch };
EOF
( cd "$GA/eval-0" && git init -q -b main && git add -A && git commit -qm "worker baseline" )
cat > "$GA/eval-0/src/worker.js" <<'EOF'
const MAX_BATCH = 100;

async function processBatch(jobs) {
  const batch = jobs.slice(0, MAX_BATCH);
  for (const job of batch) await handle(job);
  return jobs.length - batch.length;
}
async function handle(job) { /* ... */ }
module.exports = { processBatch };
EOF
( cd "$GA/eval-0" && git add -A \
  && git commit -qm "fix: clamp batch size to 100 — >100 jobs OOMs the 512MB worker container (fixes #42)" \
  && printf 'module.exports = { retries: 3 };\n' > src/config.js && git add -A && git commit -qm "add worker config" \
  && printf '# worker\nBatch job worker.\n' > README.md && git add -A && git commit -qm "add readme" \
  && printf 'module.exports.metrics = true;\n' >> src/config.js && git add -A && git commit -qm "enable metrics" \
  && git commit -q --allow-empty -m "chore: unrelated mainline change" )

# eval-1: unrecoverable intent — guard introduced by an uninformative "wip" commit
mkdir -p "$GA/eval-1/src"
cat > "$GA/eval-1/src/validate.js" <<'EOF'
function validateEvent(event) {
  return { ok: true, event };
}
module.exports = { validateEvent };
EOF
( cd "$GA/eval-1" && git init -q -b main && git add -A && git commit -qm "validator baseline" )
cat > "$GA/eval-1/src/validate.js" <<'EOF'
function validateEvent(event) {
  if (!event || typeof event.type !== "string") return { ok: false, event: null };
  return { ok: true, event };
}
module.exports = { validateEvent };
EOF
( cd "$GA/eval-1" && git add -A && git commit -qm "wip" \
  && printf '# events\n' > README.md && git add -A && git commit -qm "add readme" \
  && git commit -q --allow-empty -m "chore: bump deps" )

# eval-2: retry with recoverable intent — introducing commit names the flaky upstream
mkdir -p "$GA/eval-2/src"
cat > "$GA/eval-2/src/fetch.js" <<'EOF'
async function fetchUpstream(url) {
  return request(url);
}
async function request(url) { /* ... */ }
module.exports = { fetchUpstream };
EOF
( cd "$GA/eval-2" && git init -q -b main && git add -A && git commit -qm "fetcher baseline" )
cat > "$GA/eval-2/src/fetch.js" <<'EOF'
async function fetchUpstream(url) {
  let retries = 3;
  for (;;) {
    try {
      return await request(url);
    } catch (err) {
      if (retries-- <= 0) throw err;
      await new Promise((r) => setTimeout(r, 250 * (3 - retries)));
    }
  }
}
async function request(url) { /* ... */ }
module.exports = { fetchUpstream };
EOF
( cd "$GA/eval-2" && git add -A \
  && git commit -qm "add retry: upstream flakes ~1/50 requests in prod, exhausting the queue" \
  && printf '# fetcher\n' > README.md && git add -A && git commit -qm "add readme" )

# eval-3: negative control — rename inside defensive code, no archaeology expected
mkdir -p "$GA/eval-3/src"
cp "$GA/eval-2/src/fetch.js" "$GA/eval-3/src/fetch.js"
( cd "$GA/eval-3" && git init -q -b main && git add -A && git commit -qm "fetcher baseline" )

# eval-4: REAL open-source history — npm/node-semver pinned just before its
# module split. The MAX_LENGTH=256 guard's blame tip is two style commits
# ("Apply 'standard'", "Fix code style"); the true introducing commit is
# c80180d "Prevent version strings > 256 chars, or with giant numbers" (2015
# hardening against pathological version strings). Real history stresses what
# synthetic fixtures cannot: walking past formatting commits to real intent.
# The clone is cached across runs; evals already require network for the model
# API, so the one-time clone adds no new dependency.
SEMVER_URL="https://github.com/npm/node-semver.git"
SEMVER_SHA="07244f913d0502d9400a88629710517ca9b7d702"
CACHE="${EVAL_FIXTURE_CACHE:-/tmp/overclock-eval-fixture-cache}/node-semver"
if [ ! -d "$CACHE/.git" ]; then
  git clone -q "$SEMVER_URL" "$CACHE" \
    || { echo "fixture eval-4 needs one-time network access to clone node-semver" >&2; exit 1; }
fi
git -C "$CACHE" cat-file -e "$SEMVER_SHA" 2>/dev/null || git -C "$CACHE" fetch -q origin
git clone -q --no-hardlinks "$CACHE" "$GA/eval-4"
( cd "$GA/eval-4" && git checkout -qb pinned "$SEMVER_SHA" \
  && git remote set-url origin "$SEMVER_URL" )

# ---------- natural-writing ----------
NW="$ROOT/natural-writing"

# eval-0: draft from scratch — near-empty blog project
mkdir -p "$NW/eval-0/blog"
printf '# team blog\nPosts live in blog/.\n' > "$NW/eval-0/README.md"
( cd "$NW/eval-0" && git init -q -b main && git add -A && git commit -qm "blog scaffold" )

# eval-1: revise an AI-flavored draft in place; one load-bearing caveat must survive
mkdir -p "$NW/eval-1/draft"
cat > "$NW/eval-1/draft/launch-post.md" <<'EOF'
# Announcing QueryPilot — Your Data's New Best Friend

In today's fast-paced world, teams need to leverage their data more than ever. That's why we're
thrilled to announce QueryPilot — a robust, seamless analytics layer that lets you delve into
your data warehouse without writing a single line of SQL.

**Effortless setup.** Getting started is like conducting an orchestra — every integration plays
its part in perfect harmony. Simply connect your warehouse and QueryPilot handles the rest.

**Powerful insights.** Furthermore, QueryPilot doesn't just surface numbers — it weaves a rich
tapestry of context around every metric. It's worth noting that while results may vary and every
data stack is different and your mileage may depend on configuration, QueryPilot only supports
Postgres 14 or newer — older versions silently return incomplete results.

**Built to scale.** QueryPilot is a testament to what modern infrastructure can achieve. It
utilizes cutting-edge caching to deliver crucial performance gains.

In conclusion, QueryPilot represents a paradigm shift in how teams interact with data. Buckle up —
the journey is just beginning. Let's dive in together.
EOF
( cd "$NW/eval-1" && git init -q -b main && git add -A && git commit -qm "launch post draft" )

# eval-2: verbatim preservation — customer quote (with AI tells INSIDE it) must stay byte-identical
mkdir -p "$NW/eval-2/site"
cat > "$NW/eval-2/site/customers.md" <<'EOF'
# What our customers say

Our platform helps teams leverage synergies and delve into robust, seamless workflows — empowering
stakeholders to unlock crucial value at every touchpoint. Furthermore, it's worth noting that our
solution represents a paradigm shift in the landscape of modern collaboration.

> "We rolled it out in a week — the team was able to leverage it immediately, and honestly it just
> works. Couldn't be happier." — Dana R., VP Engineering at Coastline Freight

In conclusion, teams that embrace our platform embark on a transformative journey toward a rich
tapestry of productivity.
EOF
( cd "$NW/eval-2" && git init -q -b main && git add -A && git commit -qm "customers page" )

# eval-3: negative control — commit message request on a real staged change
mkdir -p "$NW/eval-3/src"
cat > "$NW/eval-3/src/retry.js" <<'EOF'
async function withRetry(fn, attempts = 3) {
  for (;;) {
    try { return await fn(); }
    catch (err) { if (--attempts <= 0) throw err; }
  }
}
module.exports = { withRetry };
EOF
( cd "$NW/eval-3" && git init -q -b main && git add -A && git commit -qm "retry helper" \
  && sed -i.bak 's/attempts = 3/attempts = 5/' src/retry.js && rm -f src/retry.js.bak )

# eval-4: negative control — single-line reword; rest of the file must stay untouched
mkdir -p "$NW/eval-4/site"
cat > "$NW/eval-4/site/index.md" <<'EOF'
# Ship your changelog automatically, every single week, without thinking about it

Changelog entries write themselves from your merged PRs — you review, click publish, and your
users stay in the loop. Integrates with GitHub and GitLab.

Pricing starts at $12/month for teams of any size.
EOF
( cd "$NW/eval-4" && git init -q -b main && git add -A && git commit -qm "landing page" )

echo "fixtures ready under $ROOT"
