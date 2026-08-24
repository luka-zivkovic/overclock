#!/bin/bash
# Supply-chain tripwire: scan this checkout with casefile, compare contentHash
# to the previous scan, fail loudly on criticals. Agent harnesses load skills
# from this checkout live, so every pull is a supply-chain event.
# Requires: a Casefile build with explicit --config support. CI temporarily uses published 0.1
# in artifact-local compatibility mode until the config-aware release is available on npm.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$(mktemp)"

PREV=$(casefile history "$ROOT" --json 2>/dev/null | python3 -c \
  "import json,sys; r=json.load(sys.stdin); print(r[0]['contentHash'] if r else '')" 2>/dev/null || echo "")

casefile scan "$ROOT" --config "$ROOT/casefile.config.json" --json --out "$OUT" --fail-on none >/dev/null

CUR=$(python3 -c "import json; print(json.load(open('$OUT'))['artifact']['contentHash'])")
CRIT=$(python3 -c "import json; print(json.load(open('$OUT'))['summary']['critical'])")
SUPP=$(python3 -c "import json; print(json.load(open('$OUT'))['summary']['suppressed'])")

if [ -n "$PREV" ] && [ "$PREV" != "$CUR" ]; then
  echo "casefile: content drift since last scan ($PREV -> $CUR)"
fi
echo "casefile: criticals=$CRIT suppressed=$SUPP (report: $OUT)"
if [ "$CRIT" -gt 0 ]; then
  echo "casefile: CRITICAL findings — review before trusting these skills:" >&2
  python3 -c "
import json
for f in json.load(open('$OUT'))['findings']:
    if f['severity']=='critical': print(f\"  {f['ruleId']}  {f['file']}: {f['message'][:100]}\")" >&2
  exit 1
fi
