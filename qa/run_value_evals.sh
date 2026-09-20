#!/usr/bin/env bash
# Run paired no-skill and skill variants, then enforce each suite's value gate.
set -euo pipefail
cd "$(dirname "$0")/.."

TARGETS=("$@")
[ "${#TARGETS[@]}" -gt 0 ] || {
  echo "usage: qa/run_value_evals.sh plugin/skill [...]" >&2
  exit 2
}

# Whole-suite thresholds cannot be applied honestly to an EVAL_ONLY slice.
[ -z "${EVAL_ONLY:-}" ] || {
  echo "value comparison requires the full suite; unset EVAL_ONLY" >&2
  exit 2
}
# Resolve and validate every target before the first model call (including groups).
python3 - "${TARGETS[@]}" <<'PY'
import pathlib, re, sys
sys.path.insert(0, 'qa')
from check_eval_value import value_thresholds
from eval_contract import load_suite, validate_suite
root = pathlib.Path('qa/evals')
for target in sys.argv[1:]:
    if re.fullmatch(r'[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*', target) is None:
        raise SystemExit(f'invalid value-comparison target: {target}')
    plugin, skill = target.split('/')
    suite = root / plugin / f'{skill}.evals.json'
    try:
        _, data = load_suite(suite, root)
        errors = validate_suite(suite, root)
        if errors:
            raise ValueError('; '.join(errors))
        value_thresholds(data)
    except (ValueError, OSError) as exc:
        raise SystemExit(f'{target}: {exc}')
PY

# Pin the requested execution settings across both arms instead of inheriting
# an agent's changing local defaults.
export EVAL_MODEL="${EVAL_MODEL:-claude-sonnet-5}"
export EVAL_EFFORT="${EVAL_EFFORT:-medium}"

PAIR_ID=$(python3 -c 'import uuid; print(uuid.uuid4())')
STATUS=0
EVAL_PAIR_ID="$PAIR_ID" BASELINE=1 bash qa/run_evals.sh "${TARGETS[@]}" || STATUS=$?
EVAL_PAIR_ID="$PAIR_ID" BASELINE=0 bash qa/run_evals.sh "${TARGETS[@]}" || STATUS=$?
for target in "${TARGETS[@]}"; do
  VALUE_MODE_ARGS=()
  [ -z "${EVAL_INSTALL_MODE:-}" ] || VALUE_MODE_ARGS=(--install-mode "$EVAL_INSTALL_MODE")
  python3 qa/check_eval_value.py qa/_work/results "$target" \
    --pair-id "$PAIR_ID" ${VALUE_MODE_ARGS[@]+"${VALUE_MODE_ARGS[@]}"} || STATUS=$?
done
exit "$STATUS"
