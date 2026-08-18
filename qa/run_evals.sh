#!/usr/bin/env bash
# Live regression evals for Overclock skills.
#
# For each eval case: a fresh fixture, optional setup turns that establish real
# prior context, then an evaluated `claude -p` turn with the skill installed.
# A separate model judges the conversation + post-run file state against the
# case's expectations. Exits non-zero if any case fails.
#
# A skill's cases live at qa/evals/<plugin>/<skill>.evals.json; the plugin dir
# is derived from that path, so new plugins need no harness changes.
#
# Usage: qa/run_evals.sh [[plugin/]skill ...]  (default: the session-memory pair)
# Set EVAL_INSTALL_MODE=skill|plugin|stack to override suite/case declarations.
# With no override, every case runs its committed `install_modes` matrix.
# Behavioral suites invoke their target explicitly. Implicit selection belongs to
# qa/trigger_battery.py so routing and behavior cannot mask one another.
# Set BASELINE=1 to run the same cases with all skills disabled. Baseline expectation
# failures are reported but do not make the process fail; harness/runtime errors still do.
# Requires: sandbox-capable claude CLI and ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN.
# Cost: one evaluated turn + one judge turn per case, plus optional setup turns.
set -euo pipefail
cd "$(dirname "$0")"
QA="$(pwd)"
REPO="$(dirname "$QA")"
JUDGE_MODEL="${JUDGE_MODEL:-claude-haiku-4-5-20251001}"
EVAL_MODEL="${EVAL_MODEL:-}"
EVAL_MODEL_ARGS=()
if [ -n "$EVAL_MODEL" ]; then
  [[ "$EVAL_MODEL" =~ ^[A-Za-z0-9][A-Za-z0-9._:@/-]*$ ]] || {
    echo "unsafe EVAL_MODEL" >&2
    exit 1
  }
  EVAL_MODEL_ARGS=(--model "$EVAL_MODEL")
fi
EVAL_EFFORT="${EVAL_EFFORT:-}"
EVAL_EFFORT_ARGS=()
if [ -n "$EVAL_EFFORT" ]; then
  [[ "$EVAL_EFFORT" =~ ^(low|medium|high|xhigh|max)$ ]] || {
    echo "EVAL_EFFORT must be low, medium, high, xhigh, or max" >&2
    exit 1
  }
  EVAL_EFFORT_ARGS=(--effort "$EVAL_EFFORT")
fi
EVAL_DEBUG="${EVAL_DEBUG:-0}"
[[ "$EVAL_DEBUG" =~ ^[01]$ ]] || {
  echo "EVAL_DEBUG must be 0 or 1" >&2
  exit 1
}
TARGETS=("$@")
[ $# -eq 0 ] && TARGETS=(session-memory/session-handoff session-memory/lessons-learned)
BASELINE="${BASELINE:-0}"
[[ "$BASELINE" =~ ^[01]$ ]] || { echo "BASELINE must be 0 or 1" >&2; exit 1; }
EVAL_INSTALL_MODE="${EVAL_INSTALL_MODE:-}"
if [ -n "$EVAL_INSTALL_MODE" ] && [[ ! "$EVAL_INSTALL_MODE" =~ ^(skill|plugin|stack)$ ]]; then
  echo "EVAL_INSTALL_MODE must be skill, plugin, or stack" >&2
  exit 1
fi
VARIANT=$([ "$BASELINE" -eq 1 ] && echo baseline || echo skill)
ALLOWED_TOOLS="Bash(git *),Read,Glob,Grep,Skill,Task,Bash(ls*),Bash(cat*),Bash(mkdir*),Bash(mv*),Bash(cp*),Bash(rm *),Bash(python3 *),Bash(node*),Bash(npm test*),Write,Edit"
AVAILABLE_TOOLS="Bash,Edit,Read,Glob,Grep,Skill,Task,Write"

command -v claude >/dev/null || { echo "claude CLI not found" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 1; }
EVAL_SHELL=$(command -v bash)
[ -x "$EVAL_SHELL" ] || { echo "bash executable not found" >&2; exit 1; }
EVAL_PAIR_ID="${EVAL_PAIR_ID:-$(python3 -c 'import uuid; print(uuid.uuid4())')}"
[[ "$EVAL_PAIR_ID" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]] || {
  echo "unsafe EVAL_PAIR_ID" >&2
  exit 1
}
CLAUDE_BIN=$(command -v claude)
CLAUDE_VERSION=$("$CLAUDE_BIN" --version)
python3 eval_sandbox.py check-version "$CLAUDE_VERSION"

if [ -n "${EVAL_TEMP_PARENT:-}" ]; then
  TEMP_PARENT="$EVAL_TEMP_PARENT"
elif [ "$(uname -s)" = "Darwin" ]; then
  # macOS's per-user TMPDIR is deeply nested. Claude Code's Seatbelt profile
  # repeats sandbox paths enough to exceed ARG_MAX for Bash tool dispatch.
  TEMP_PARENT=/tmp
else
  TEMP_PARENT="${TMPDIR:-/tmp}"
fi
[[ "$TEMP_PARENT" == /* ]] || { echo "EVAL_TEMP_PARENT must be absolute" >&2; exit 1; }
[ -d "$TEMP_PARENT" ] && [ -w "$TEMP_PARENT" ] || {
  echo "eval temp parent is not a writable directory: $TEMP_PARENT" >&2
  exit 1
}

if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  EVAL_API_KEY="$ANTHROPIC_API_KEY"
elif [ -n "${ANTHROPIC_AUTH_TOKEN:-}" ]; then
  EVAL_API_KEY="$ANTHROPIC_AUTH_TOKEN"
else
  echo "live evals require ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN; host OAuth/keychain credentials are intentionally isolated" >&2
  exit 1
fi

AUTH_ROOT=$(mktemp -d "$TEMP_PARENT/overclock-eval-auth.XXXXXX")
FIXTURE_ROOT=""
PLUGIN_COPY_ROOT=""
EVAL_TOOL_ROOT=""
cleanup() {
  [ -z "$AUTH_ROOT" ] || rm -rf "$AUTH_ROOT"
  [ -z "$EVAL_TOOL_ROOT" ] || rm -rf "$EVAL_TOOL_ROOT"
  [ -z "$PLUGIN_COPY_ROOT" ] || rm -rf "$PLUGIN_COPY_ROOT"
  [ -z "$FIXTURE_ROOT" ] || rm -rf "$FIXTURE_ROOT"
}
trap cleanup EXIT
AUTH_KEY_FILE="$AUTH_ROOT/api-key"
umask 077
printf '%s\n' "$EVAL_API_KEY" > "$AUTH_KEY_FILE"
chmod 600 "$AUTH_KEY_FILE"
EVAL_API_KEY=""
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN

if [ -n "${EVAL_FIXTURE_DIR:-}" ]; then
  FIXTURE_PARENT="$EVAL_FIXTURE_DIR"
  mkdir -p "$FIXTURE_PARENT"
else
  FIXTURE_PARENT="$TEMP_PARENT"
fi
FIXTURE_ROOT=$(mktemp -d "$FIXTURE_PARENT/overclock-eval-run.XXXXXX")
PLUGIN_COPY_ROOT=$(mktemp -d "$TEMP_PARENT/overclock-eval-plugins.XXXXXX")
EVAL_TOOL_ROOT=$(mktemp -d "$TEMP_PARENT/overclock-eval-tools.XXXXXX")
cp "$QA/fake_gh.py" "$EVAL_TOOL_ROOT/gh"
chmod 700 "$EVAL_TOOL_ROOT/gh"
HOST_NODE_BIN=$(command -v node || true)
if [ -n "$HOST_NODE_BIN" ] && [ -x "$HOST_NODE_BIN" ]; then
  # NVM and similar managers keep Node under the user profile, which the live
  # sandbox correctly denies. Copy only the resolved executable into the
  # disposable read-only tool root so JavaScript fixtures retain a real test seam.
  cp "$HOST_NODE_BIN" "$EVAL_TOOL_ROOT/node"
  chmod 500 "$EVAL_TOOL_ROOT/node"
fi
mkdir -p "$QA/_work"
RESULTS="$QA/_work/results"
mkdir -p "$RESULTS"
FAILED=0
INFRA_FAILED=0
TOTAL=0
RUN_OUTS=()

run_eval_claude() {
  env -i \
    HOME="$CASE_RUNTIME/home" \
    CLAUDE_CONFIG_DIR="$CASE_RUNTIME/config" \
    TMPDIR="$CASE_RUNTIME/tmp" \
    PATH="$EVAL_TOOL_ROOT:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin" \
    USER="${USER:-overclock-eval}" \
    LOGNAME="${LOGNAME:-overclock-eval}" \
    SHELL="$EVAL_SHELL" \
    CLAUDE_CODE_SHELL="$EVAL_SHELL" \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    DISABLE_AUTOUPDATER=1 \
    DISABLE_ERROR_REPORTING=1 \
    DISABLE_TELEMETRY=1 \
    DISABLE_BUG_COMMAND=1 \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    CLAUDE_CODE_DISABLE_CLAUDE_MDS=1 \
    CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 \
    "$CLAUDE_BIN" "$@"
}

for TARGET in "${TARGETS[@]}"; do
  if [[ "$TARGET" == */* ]]; then
    PLUGIN=${TARGET%%/*}
    SKILL=${TARGET#*/}
    EVALS="$QA/evals/$PLUGIN/$SKILL.evals.json"
    [ -f "$EVALS" ] || { echo "no eval suite found for distribution '$TARGET'" >&2; exit 1; }
  else
    SKILL=$TARGET
    MATCHES=("$QA"/evals/*/"$SKILL.evals.json")
    [ -e "${MATCHES[0]}" ] || { echo "no eval suite found for skill '$SKILL'" >&2; exit 1; }
    [ "${#MATCHES[@]}" -eq 1 ] || {
      echo "multiple plugin distributions contain '$SKILL'; use plugin/skill" >&2
      exit 1
    }
    EVALS=${MATCHES[0]}
    PLUGIN=$(basename "$(dirname "$EVALS")")
  fi
  [[ "$PLUGIN" =~ ^[a-z0-9][a-z0-9-]*$ ]] || {
    echo "unsafe plugin name '$PLUGIN'" >&2
    exit 1
  }
  [[ "$SKILL" =~ ^[a-z0-9][a-z0-9-]*$ ]] || {
    echo "unsafe skill name '$SKILL'" >&2
    exit 1
  }

  # A distribution may reuse an identical behavioral suite without duplicating it.
  EVALS=$(python3 - "$EVALS" "$QA/evals" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1]).resolve()
boundary = pathlib.Path(sys.argv[2]).resolve()
seen = set()
while True:
    try:
        path.relative_to(boundary)
    except ValueError:
        raise SystemExit(f"eval extends path escapes qa/evals: {path}")
    if path in seen:
        raise SystemExit(f"cyclic eval extends chain at {path}")
    seen.add(path)
    data = json.load(open(path))
    parent = data.get("extends")
    if not parent:
        print(path)
        break
    path = (path.parent / parent).resolve()
PY
)
  DISTRIBUTION_LABEL="$PLUGIN-$SKILL"
  # Build every distribution in a fresh owned child. Two plugins may expose the
  # same skill name; neither may inherit files mutated by an earlier distribution.
  DISTRIBUTION_FIXTURE_ROOT=$(mktemp -d "$FIXTURE_ROOT/$DISTRIBUTION_LABEL.XXXXXX")
  EVAL_FIXTURE_DIR="$DISTRIBUTION_FIXTURE_ROOT" bash fixtures/setup.sh
  N=$(python3 -c "import json;print(len(json.load(open('$EVALS'))['evals']))")
  FIXTURE_ERRORS=$(PYTHONPATH="$QA" python3 - "$DISTRIBUTION_FIXTURE_ROOT" "$EVALS" "$QA/evals" <<'PY'
import pathlib, sys
from eval_contract import fixture_errors

errors = fixture_errors(
    pathlib.Path(sys.argv[1]),
    pathlib.Path(sys.argv[2]),
    pathlib.Path(sys.argv[3]),
)
print("\n".join(errors))
PY
)
  if [ -n "$FIXTURE_ERRORS" ]; then
    echo "fixture contract failed for $PLUGIN/$SKILL:" >&2
    printf '%s\n' "$FIXTURE_ERRORS" >&2
    exit 1
  fi
  for ((i=0; i<N; i++)); do
    CASE_ID=$(python3 -c "import json;c=json.load(open('$EVALS'))['evals'][$i];print(c.get('id', $i))")
    [[ "$CASE_ID" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]] || {
      echo "unsafe eval id '$CASE_ID' in $EVALS" >&2
      exit 1
    }
    # EVAL_ONLY=<id> re-runs a single declared case id.
    [ -n "${EVAL_ONLY:-}" ] && [ "$CASE_ID" != "$EVAL_ONLY" ] && continue
    INSTALL_MODES=()
    while IFS= read -r INSTALL_MODE; do
      [ -n "$INSTALL_MODE" ] && INSTALL_MODES+=("$INSTALL_MODE")
    done < <(PYTHONPATH="$QA" python3 - "$EVALS" "$i" "$PLUGIN" "$EVAL_INSTALL_MODE" <<'PY'
import json, sys
from eval_packaging import resolve_install_modes

suite = json.load(open(sys.argv[1]))
case = suite["evals"][int(sys.argv[2])]
override = sys.argv[4] or None
print(*resolve_install_modes(case, sys.argv[3], suite=suite, override=override), sep="\n")
PY
)
    [ "${#INSTALL_MODES[@]}" -gt 0 ] || {
      echo "no install modes resolved for $PLUGIN/$SKILL eval-$CASE_ID" >&2
      exit 1
    }
    for INSTALL_MODE in "${INSTALL_MODES[@]}"; do
    TOTAL=$((TOTAL+1))
    # Each matrix cell receives a fresh copy of the trusted fixture template.
    # Mutations from one install mode can never influence another mode.
    MODE_FIXTURE_ROOT=$(mktemp -d "$FIXTURE_ROOT/$DISTRIBUTION_LABEL-$INSTALL_MODE.XXXXXX")
    cp -R "$DISTRIBUTION_FIXTURE_ROOT/." "$MODE_FIXTURE_ROOT/"
    WORK="$MODE_FIXTURE_ROOT/$SKILL/eval-$i"
    LABEL="$DISTRIBUTION_LABEL-$INSTALL_MODE"
    [ "$BASELINE" -eq 1 ] && LABEL="$LABEL-baseline"
    # Artifact paths are derived only from the numeric array index. The declared id is
    # metadata/filtering input and can never influence a deletion target.
    OUT="$RESULTS/$LABEL-eval-$i"
    rm -rf "$OUT"
    mkdir -p "$OUT"
    printf '%s\n' "$CASE_ID" > "$OUT/case-id.txt"
    RUN_OUTS+=("$OUT")
    : > "$OUT/stderr.log"
    PROMPT=$(python3 -c "import json;print(json.load(open('$EVALS'))['evals'][$i]['prompt'])")
    INVOCATION=$(python3 -c "import json;print(json.load(open('$EVALS'))['invocation'])")
    [ "$INVOCATION" = "explicit" ] || {
      echo "unsupported behavioral invocation '$INVOCATION' in $EVALS" >&2
      exit 1
    }

    python3 "$QA/eval_provenance.py" \
      --output "$OUT/provenance.json" \
      --pair-id "$EVAL_PAIR_ID" \
      --variant "$VARIANT" \
      --plugin "$PLUGIN" \
      --skill "$SKILL" \
      --suite "$EVALS" \
      --case-index "$i" \
      --install-mode "$INSTALL_MODE" \
      --plugin-root "$REPO/plugins"
    CASE_PLUGIN_ROOT="$PLUGIN_COPY_ROOT/$LABEL/eval-$i"
    rm -rf "$CASE_PLUGIN_ROOT"
    # All three modes use the same no-follow packager. `skill` synthesizes a
    # target-only plugin; `plugin` copies only the owner; `stack` copies every
    # declared composition plugin. Even baselines materialize the intended
    # package so provenance binds the comparison to identical source bytes.
    PYTHONPATH="$QA" python3 - \
      "$REPO/plugins" "$CASE_PLUGIN_ROOT" "$PLUGIN" "$SKILL" \
      "$INSTALL_MODE" "$EVALS" "$i" > "$OUT/plugin-dirs.txt" <<'PY'
import json, pathlib, sys
from eval_packaging import materialize_installation

suite = json.load(open(sys.argv[6]))
case = suite["evals"][int(sys.argv[7])]
result = materialize_installation(
    source_plugin_root=pathlib.Path(sys.argv[1]),
    destination_root=pathlib.Path(sys.argv[2]),
    target_plugin=sys.argv[3],
    target_skill=sys.argv[4],
    mode=sys.argv[5],
    config=case,
)
for path in result.plugin_dirs:
    print(path)
PY
    FINAL_MODE_ARGS=()
    if [ "$BASELINE" -eq 0 ]; then
      while IFS= read -r DEST_PLUGIN; do
        [ -n "$DEST_PLUGIN" ] && FINAL_MODE_ARGS+=(--plugin-dir "$DEST_PLUGIN")
      done < "$OUT/plugin-dirs.txt"
    else
      FINAL_MODE_ARGS=(--disable-slash-commands --disallowedTools Task)
    fi
    if [ "$BASELINE" -eq 0 ]; then
      EFFECTIVE_PROMPT=$(PYTHONPATH="$QA" python3 - "$PLUGIN" "$SKILL" "$PROMPT" <<'PY'
import sys
from eval_invocation import explicit_prompt

print(explicit_prompt(sys.argv[1], sys.argv[2], sys.argv[3]), end="")
PY
)
    else
      EFFECTIVE_PROMPT="$PROMPT"
    fi
    printf '%s\n' "$EFFECTIVE_PROMPT" > "$OUT/effective-prompt.txt"
    CASE_RUNTIME="$FIXTURE_ROOT/runtime/$LABEL/eval-$i"
    mkdir -p "$CASE_RUNTIME/home" "$CASE_RUNTIME/config" "$CASE_RUNTIME/tmp"
    CASE_SETTINGS="$OUT/eval-settings.json"
    python3 "$QA/eval_sandbox.py" settings \
      --work "$WORK" \
      --plugin-root "$CASE_PLUGIN_ROOT" \
      --runtime-root "$CASE_RUNTIME" \
      --tool-root "$EVAL_TOOL_ROOT" \
      --repository "$REPO" \
      --auth-root "$AUTH_ROOT" \
      --key-file "$AUTH_KEY_FILE" \
      --key-reader "$QA/read_eval_api_key.py" \
      > "$CASE_SETTINGS"
    EVAL_CLAUDE_ARGS=(
      --settings "$CASE_SETTINGS"
      --setting-sources ""
      --strict-mcp-config
      --no-chrome
      --permission-mode dontAsk
      --tools "$AVAILABLE_TOOLS"
    )
    EVAL_DEBUG_ARGS=()
    if [ "$EVAL_DEBUG" -eq 1 ]; then
      EVAL_DEBUG_ARGS=(--debug api --debug-file "$OUT/claude-debug.log")
    fi
    SETUP_WITH_PLUGINS=$(python3 - "$EVALS" "$i" <<'PY'
import json, sys
case = json.load(open(sys.argv[1]))["evals"][int(sys.argv[2])]
print("1" if case.get("setup_with_plugins", False) else "0")
PY
)

    # Optional setup turns create genuine prior context before the skill is installed.
    # This lets evals test anchoring, self-consistency, and evidence-based reversals.
    SETUP_N=$(python3 -c "import json;print(len(json.load(open('$EVALS'))['evals'][$i].get('setup_turns', [])))")
    : > "$OUT/context-transcript.md"
    FINAL_SESSION_ARGS=(--no-session-persistence)
    if [ "$SETUP_N" -gt 0 ]; then
      SESSION_ID=$(python3 -c 'import uuid;print(uuid.uuid4())')
      for ((turn=0; turn<SETUP_N; turn++)); do
        SETUP_PROMPT=$(python3 -c "import json;print(json.load(open('$EVALS'))['evals'][$i]['setup_turns'][$turn])")
        if [ "$turn" -eq 0 ]; then
          SETUP_SESSION_ARGS=(--session-id "$SESSION_ID")
        else
          SETUP_SESSION_ARGS=(--resume "$SESSION_ID")
        fi
        if [ "$SETUP_WITH_PLUGINS" -eq 1 ] && [ "$BASELINE" -eq 0 ]; then
          SETUP_MODE_ARGS=("${FINAL_MODE_ARGS[@]}")
          SETUP_EFFECTIVE_PROMPT=$(PYTHONPATH="$QA" python3 - \
            "$PLUGIN" "$SKILL" "$SETUP_PROMPT" <<'PY'
import sys
from eval_invocation import explicit_prompt

print(explicit_prompt(sys.argv[1], sys.argv[2], sys.argv[3]), end="")
PY
)
        else
          SETUP_MODE_ARGS=(--disable-slash-commands --disallowedTools Task)
          SETUP_EFFECTIVE_PROMPT="$SETUP_PROMPT"
        fi
        printf '%s\n' "$SETUP_EFFECTIVE_PROMPT" > "$OUT/setup-effective-$turn.txt"
        echo "=== $SKILL eval-$i: setup turn $((turn+1))/$SETUP_N"
        ( cd "$WORK" && run_eval_claude -p "$SETUP_EFFECTIVE_PROMPT" --output-format json \
            ${EVAL_MODEL_ARGS[@]+"${EVAL_MODEL_ARGS[@]}"} \
            ${EVAL_EFFORT_ARGS[@]+"${EVAL_EFFORT_ARGS[@]}"} \
            ${EVAL_DEBUG_ARGS[@]+"${EVAL_DEBUG_ARGS[@]}"} \
            "${SETUP_SESSION_ARGS[@]}" "${SETUP_MODE_ARGS[@]}" \
            "${EVAL_CLAUDE_ARGS[@]}" --allowedTools "$ALLOWED_TOOLS" \
          ) > "$OUT/setup-$turn.json" 2>> "$OUT/stderr.log"
        python3 - "$SETUP_PROMPT" "$OUT/setup-$turn.json" >> "$OUT/context-transcript.md" <<'PY'
import json, pathlib, sys
prompt, result_path = sys.argv[1], pathlib.Path(sys.argv[2])
result = json.loads(result_path.read_text()).get("result", "")
print(f"USER:\n{prompt}\n\nASSISTANT:\n{result}\n")
PY
      done
      FINAL_SESSION_ARGS=(--resume "$SESSION_ID")
    fi

    echo "=== $SKILL eval-$CASE_ID: run ($VARIANT)"
    # stream-json (requires --verbose) exposes tool calls, so the judge can grade
    # process expectations ("the contract was read") on evidence, not inference.
    ( cd "$WORK" && run_eval_claude -p "$EFFECTIVE_PROMPT" --output-format stream-json --verbose \
        ${EVAL_MODEL_ARGS[@]+"${EVAL_MODEL_ARGS[@]}"} \
        ${EVAL_EFFORT_ARGS[@]+"${EVAL_EFFORT_ARGS[@]}"} \
        ${EVAL_DEBUG_ARGS[@]+"${EVAL_DEBUG_ARGS[@]}"} \
        "${FINAL_SESSION_ARGS[@]}" "${FINAL_MODE_ARGS[@]}" \
        "${EVAL_CLAUDE_ARGS[@]}" --allowedTools "$ALLOWED_TOOLS" \
      ) > "$OUT/stdout.jsonl" 2>> "$OUT/stderr.log"
    python3 - "$OUT" <<'PY'
import json, sys
out = sys.argv[1]
result, tools, structured_tools, metrics = "", [], [], {}
for line in open(f"{out}/stdout.jsonl"):
    line = line.strip()
    if not line:
        continue
    try:
        ev = json.loads(line)
    except json.JSONDecodeError:
        continue
    if ev.get("type") == "result":
        result = ev.get("result", "")
        metrics = {
            key: ev.get(key) for key in (
                "duration_ms", "duration_api_ms", "ttft_ms", "num_turns",
                "total_cost_usd", "usage", "modelUsage", "permission_denials",
            ) if key in ev
        }
    elif ev.get("type") == "assistant":
        for block in ev.get("message", {}).get("content", []):
            if block.get("type") == "tool_use":
                inp = block.get("input", {})
                structured_tools.append({"name": block.get("name"), "input": inp})
                tools.append(
                    f"{block.get('name')}: "
                    f"{json.dumps(inp, ensure_ascii=False, sort_keys=True)}"
                )
open(f"{out}/transcript.md", "w").write(result)
open(f"{out}/toolcalls.txt", "w").write("\n".join(tools) + "\n")
json.dump(
    structured_tools,
    open(f"{out}/toolcalls.json", "w"),
    ensure_ascii=False,
    indent=1,
)
json.dump(metrics, open(f"{out}/runner-metrics.json", "w"), indent=1)
PY
    INVOCATION_STATUS=0
    if [ "$BASELINE" -eq 0 ]; then
      PYTHONPATH="$QA" python3 - \
        "$OUT/stdout.jsonl" "$OUT/effective-prompt.txt" "$PLUGIN" "$SKILL" \
        > "$OUT/invocation.json" <<'PY' || INVOCATION_STATUS=$?
import json, pathlib, sys
from eval_invocation import invocation_evidence

evidence = invocation_evidence(
    pathlib.Path(sys.argv[1]),
    plugin=sys.argv[3],
    skill=sys.argv[4],
    effective_prompt=pathlib.Path(sys.argv[2]).read_text(encoding="utf-8").rstrip("\n"),
)
print(json.dumps(evidence, indent=1))
raise SystemExit(0 if evidence["verified"] else 1)
PY
    else
      printf '%s\n' '{"mode":"baseline","verified":true}' > "$OUT/invocation.json"
    fi

    # Snapshot through a bounded, root-confined, no-follow reader. Evaluated
    # agents control fixture paths, so ordinary cp/cat/pathlib traversal is unsafe.
    rm -rf "$OUT/state"
    python3 "$QA/snapshot_eval_state.py" --work "$WORK" --output "$OUT/state"

    # Judge with a different model, fresh context
    python3 - "$EVALS" "$i" "$OUT" "$INSTALL_MODE" > "$OUT/judge-prompt.txt" <<'PY'
import json, sys, pathlib
evals, idx, out, install_mode = (
    sys.argv[1],
    int(sys.argv[2]),
    pathlib.Path(sys.argv[3]),
    sys.argv[4],
)
case = json.load(open(evals))["evals"][idx]
state = ""
for name in (
    "memory.txt",
    "git_status.txt",
    "git_log.txt",
    "git_diff.txt",
    "git_log_full.txt",
    "untracked.txt",
):
    p = out / "state" / name
    if p.exists() and p.read_text().strip():
        state += f"\n--- {name} ---\n{p.read_text()}\n"
print(f"""You are an independent QA judge. Grade an AI coding session against expectations.
You did not produce this transcript. Be strict: an expectation passes only on evidence.
Negative expectations ("X does not happen") fail only on positive evidence X happened.

USER PROMPT GIVEN TO THE SESSION:
{case['prompt']}

INSTALLATION MODE:
{install_mode}

EXPECTATIONS (grade each):
{json.dumps(case['expectations'], indent=1)}

	TOOL CALLS MADE BY THE SESSION (name: primary argument, in order):
	{(out / 'toolcalls.txt').read_text(errors='replace') if (out / 'toolcalls.txt').exists() else '(none recorded)'}

	TARGET INVOCATION EVIDENCE:
	{(out / 'invocation.json').read_text(errors='replace') if (out / 'invocation.json').exists() else '(missing)'}

PRIOR TURNS IN THE SAME SESSION:
{(out / 'context-transcript.md').read_text(errors='replace') if (out / 'context-transcript.md').exists() and (out / 'context-transcript.md').read_text().strip() else '(none)'}

EVALUATED FINAL-TURN RESPONSE:
{(out / 'transcript.md').read_text(errors='replace')}

POST-RUN FILE STATE:
{state if state.strip() else '(no .ai/memory directory exists after the run)'}

Respond with ONLY a JSON object: {{"verdicts": [{{"expectation": "...", "verdict": "PASS|FAIL", "why": "..."}}], "passed": N, "total": N}}""")
PY
    run_eval_claude -p "$(cat "$OUT/judge-prompt.txt")" \
      --model "$JUDGE_MODEL" --output-format json \
      --no-session-persistence "${EVAL_CLAUDE_ARGS[@]}" --allowedTools "" \
      > "$OUT/judge-raw.json" 2>> "$OUT/stderr.log"
    JUDGE_STATUS=0
    VERDICT=$(python3 "$QA/validate_judge_result.py" \
      "$OUT/judge-raw.json" "$EVALS" "$i" "$OUT/grading.json") || JUDGE_STATUS=$?
    [ "$JUDGE_STATUS" -eq 0 ] || INFRA_FAILED=1
    if [ "$INVOCATION_STATUS" -ne 0 ]; then
      VERDICT=FAIL
      INFRA_FAILED=1
      echo "target invocation could not be verified for $PLUGIN/$SKILL eval-$CASE_ID" >&2
    fi
    python3 - "$OUT" "$VARIANT" "$EVAL_MODEL" "$EVAL_EFFORT" <<'PY'
import glob, json, pathlib, sys
out, variant, requested_eval_model, requested_eval_effort = (
    pathlib.Path(sys.argv[1]),
    sys.argv[2],
    sys.argv[3],
    sys.argv[4],
)
parts = []
for path in [*sorted(out.glob("setup-*.json")), out / "runner-metrics.json", out / "judge-raw.json"]:
    if not path.exists():
        continue
    try:
        parts.append(json.loads(path.read_text()))
    except json.JSONDecodeError:
        pass

def usage_total(key):
    return sum((part.get("usage") or {}).get(key, 0) or 0 for part in parts)

metrics = {
    "variant": variant,
    "requested_eval_model": requested_eval_model or None,
    "requested_eval_effort": requested_eval_effort or None,
    "total_cost_usd": sum(part.get("total_cost_usd", 0) or 0 for part in parts),
    "duration_ms": sum(part.get("duration_ms", 0) or 0 for part in parts),
    "num_turns": sum(part.get("num_turns", 0) or 0 for part in parts),
    "input_tokens": usage_total("input_tokens"),
    "output_tokens": usage_total("output_tokens"),
    "cache_read_input_tokens": usage_total("cache_read_input_tokens"),
    "cache_creation_input_tokens": usage_total("cache_creation_input_tokens"),
}
(out / "metrics.json").write_text(json.dumps(metrics, indent=1) + "\n")
PY
    echo "=== $SKILL eval-$CASE_ID: $VERDICT ($VARIANT; $INSTALL_MODE)"
    case "$VERDICT" in PASS) ;; *) FAILED=$((FAILED+1));; esac
    done
  done
done

[ "$TOTAL" -gt 0 ] || {
  echo "no eval cases matched${EVAL_ONLY:+ EVAL_ONLY=$EVAL_ONLY}" >&2
  exit 1
}

echo
echo "RESULT: $((TOTAL-FAILED))/$TOTAL cases passed ($VARIANT; artifacts in qa/_work/results/)"
python3 - "$VARIANT" "${RUN_OUTS[@]}" <<'PY'
import json, pathlib, sys
variant, outputs = sys.argv[1], [pathlib.Path(item) for item in sys.argv[2:]]
rows = []
for output in outputs:
    path = output / "metrics.json"
    data = json.loads(path.read_text())
    if data.get("variant") == variant:
        rows.append(data)
print(
    "METRICS: "
    f"${sum(r['total_cost_usd'] for r in rows):.4f}, "
    f"{sum(r['duration_ms'] for r in rows) / 1000:.1f}s cumulative, "
    f"{sum(r['num_turns'] for r in rows)} turns, "
    f"{sum(r['input_tokens'] for r in rows)} input + "
    f"{sum(r['output_tokens'] for r in rows)} output tokens"
)
PY
[ "$INFRA_FAILED" -eq 0 ] || exit 1
[ "$BASELINE" -eq 1 ] || [ "$FAILED" -eq 0 ]
