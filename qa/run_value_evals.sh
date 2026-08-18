#!/usr/bin/env bash
# Run paired no-skill and skill variants, then enforce each suite's value gate.
set -euo pipefail
cd "$(dirname "$0")/.."

TARGETS=("$@")
[ "${#TARGETS[@]}" -gt 0 ] || {
  echo "usage: qa/run_value_evals.sh plugin/skill [...]" >&2
  exit 2
}

PAIR_ID=$(python3 -c 'import uuid; print(uuid.uuid4())')
EVAL_PAIR_ID="$PAIR_ID" BASELINE=1 qa/run_evals.sh "${TARGETS[@]}"
EVAL_PAIR_ID="$PAIR_ID" BASELINE=0 qa/run_evals.sh "${TARGETS[@]}"
for target in "${TARGETS[@]}"; do
  VALUE_MODE_ARGS=()
  [ -z "${EVAL_INSTALL_MODE:-}" ] || VALUE_MODE_ARGS=(--install-mode "$EVAL_INSTALL_MODE")
  python3 qa/check_eval_value.py qa/_work/results "$target" \
    --pair-id "$PAIR_ID" "${VALUE_MODE_ARGS[@]}"
done
