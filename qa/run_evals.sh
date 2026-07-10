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
# Set BASELINE=1 to run the same cases with all skills disabled. Baseline expectation
# failures are reported but do not make the process fail; harness/runtime errors still do.
# Requires: claude CLI on PATH, authenticated (ANTHROPIC_API_KEY in CI).
# Cost: one evaluated turn + one judge turn per case, plus optional setup turns.
set -euo pipefail
cd "$(dirname "$0")"
QA="$(pwd)"
REPO="$(dirname "$QA")"
JUDGE_MODEL="${JUDGE_MODEL:-claude-haiku-4-5-20251001}"
TARGETS=("$@")
[ $# -eq 0 ] && TARGETS=(session-memory/session-handoff session-memory/lessons-learned)
BASELINE="${BASELINE:-0}"
[[ "$BASELINE" =~ ^[01]$ ]] || { echo "BASELINE must be 0 or 1" >&2; exit 1; }
VARIANT=$([ "$BASELINE" -eq 1 ] && echo baseline || echo skill)
ALLOWED_TOOLS="Bash(git *),Read,Glob,Grep,Skill,Agent,Bash(ls*),Bash(cat*),Bash(mkdir*),Bash(mv*),Bash(cp*),Bash(rm *),Bash(python3 *),Bash(node*),Bash(npm test*),Bash(gh *),Write,Edit"

command -v claude >/dev/null || { echo "claude CLI not found" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 1; }

mkdir -p "$QA/_work"
RESULTS="$QA/_work/results"
mkdir -p "$RESULTS"
FAILED=0
TOTAL=0
RUN_LABELS=()
bash fixtures/setup.sh

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

  # A distribution may reuse an identical behavioral suite without duplicating it.
  EVALS=$(python3 - "$EVALS" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1]).resolve()
seen = set()
while True:
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
  LABEL="$PLUGIN-$SKILL"
  [ "$BASELINE" -eq 1 ] && LABEL="$LABEL-baseline"
  RUN_LABELS+=("$LABEL")
  N=$(python3 -c "import json;print(len(json.load(open('$EVALS'))['evals']))")
  for ((i=0; i<N; i++)); do
    CASE_ID=$(python3 -c "import json;c=json.load(open('$EVALS'))['evals'][$i];print(c.get('id', $i))")
    # EVAL_ONLY=<id> re-runs a single declared case id.
    [ -n "${EVAL_ONLY:-}" ] && [ "$CASE_ID" != "$EVAL_ONLY" ] && continue
    TOTAL=$((TOTAL+1))
    WORK="${EVAL_FIXTURE_DIR:-/tmp/overclock-eval-fixtures}/$SKILL/eval-$i"
    OUT="$RESULTS/$LABEL-eval-$CASE_ID"
    rm -rf "$OUT"
    mkdir -p "$OUT"
    : > "$OUT/stderr.log"
    PROMPT=$(python3 -c "import json;print(json.load(open('$EVALS'))['evals'][$i]['prompt'])")

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
        echo "=== $SKILL eval-$i: setup turn $((turn+1))/$SETUP_N"
        ( cd "$WORK" && claude -p "$SETUP_PROMPT" --output-format json \
            "${SETUP_SESSION_ARGS[@]}" --disable-slash-commands --allowedTools "$ALLOWED_TOOLS" \
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

    # Install only for the evaluated turn. Baselines disable every skill, including
    # user/global skills, so they measure the underlying model rather than another plugin.
    rm -rf "$WORK/.claude/skills"
    rm -rf "$WORK/.claude/agents"
    mkdir -p "$WORK/.claude/skills"
    FINAL_SKILL_ARGS=""
    if [ "$BASELINE" -eq 0 ]; then
      SKILLS_TO_INSTALL=$(python3 -c "import json;c=json.load(open('$EVALS'))['evals'][$i];print(' '.join(['$SKILL', *c.get('additional_skills', [])]))")
      for INSTALL_SKILL in $SKILLS_TO_INSTALL; do
        SOURCE_SKILL="$REPO/plugins/$PLUGIN/skills/$INSTALL_SKILL"
        [ -f "$SOURCE_SKILL/SKILL.md" ] || { echo "missing integration skill: $SOURCE_SKILL" >&2; exit 1; }
        cp -R "$SOURCE_SKILL" "$WORK/.claude/skills/$INSTALL_SKILL"
      done
      if [ -d "$REPO/plugins/$PLUGIN/agents" ]; then
        mkdir -p "$WORK/.claude/agents"
        cp -R "$REPO/plugins/$PLUGIN/agents/." "$WORK/.claude/agents/"
      fi
    else
      FINAL_SKILL_ARGS="--disable-slash-commands --disallowedTools Agent"
    fi

    echo "=== $SKILL eval-$CASE_ID: run ($VARIANT)"
    # stream-json (requires --verbose) exposes tool calls, so the judge can grade
    # process expectations ("the contract was read") on evidence, not inference.
    ( cd "$WORK" && claude -p "$PROMPT" --output-format stream-json --verbose \
        "${FINAL_SESSION_ARGS[@]}" $FINAL_SKILL_ARGS --allowedTools "$ALLOWED_TOOLS" \
      ) > "$OUT/stdout.jsonl" 2>> "$OUT/stderr.log"
    python3 - "$OUT" <<'PY'
import json, sys
out = sys.argv[1]
result, tools, metrics = "", [], {}
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
                if block.get("name") == "Skill":
                    arg = " ".join(str(x) for x in (inp.get("skill"), inp.get("args")) if x)
                else:
                    arg = (inp.get("file_path") or inp.get("command") or inp.get("pattern")
                           or inp.get("subagent_type") or inp.get("description")
                           or inp.get("name") or "")
                tools.append(f"{block.get('name')}: {str(arg)[:500]}")
open(f"{out}/transcript.md", "w").write(result)
open(f"{out}/toolcalls.txt", "w").write("\n".join(tools) + "\n")
json.dump(metrics, open(f"{out}/runner-metrics.json", "w"), indent=1)
PY

    # Snapshot post-run memory state + git for the judge. Skills that write no
    # .ai/memory (e.g. discipline-gates) are graded on git evidence instead:
    # committed tests, restored files, and untracked leftovers.
    rm -rf "$OUT/state"; mkdir -p "$OUT/state"
    [ -d "$WORK/.ai/memory" ] && cp -R "$WORK/.ai/memory" "$OUT/state/memory"
    ( cd "$WORK" && git status --porcelain --untracked-files=all 2>/dev/null \
        | grep -Ev '^\?\? \.claude/(skills|agents)/' > "$OUT/state/git_status.txt" || true
      git log --oneline -n 8 > "$OUT/state/git_log.txt" 2>/dev/null
      git diff HEAD > "$OUT/state/git_diff.txt" 2>/dev/null
      git log -p -n 8 > "$OUT/state/git_log_full.txt" 2>/dev/null
      git ls-files --others --exclude-standard | grep -Ev '^\.claude/(skills|agents)/' | while read -r f; do
        printf '\n=== untracked: %s ===\n' "$f"; cat "$f" 2>/dev/null
      done > "$OUT/state/untracked.txt" ) || true

    # Judge with a different model, fresh context
    python3 - "$EVALS" "$i" "$OUT" > "$OUT/judge-prompt.txt" <<'PY'
import json, sys, pathlib
evals, idx, out = sys.argv[1], int(sys.argv[2]), pathlib.Path(sys.argv[3])
case = json.load(open(evals))["evals"][idx]
state = ""
mem = out / "state" / "memory"
if mem.exists():
    for f in sorted(mem.rglob("*")):
        if f.is_file():
            state += f"\n--- {f.relative_to(out/'state')} ---\n{f.read_text(errors='replace')}\n"
for name in ("git_status.txt", "git_log.txt", "git_diff.txt", "git_log_full.txt", "untracked.txt"):
    p = out / "state" / name
    if p.exists() and p.read_text().strip():
        state += f"\n--- {name} ---\n{p.read_text()}\n"
print(f"""You are an independent QA judge. Grade an AI coding session against expectations.
You did not produce this transcript. Be strict: an expectation passes only on evidence.
Negative expectations ("X does not happen") fail only on positive evidence X happened.

USER PROMPT GIVEN TO THE SESSION:
{case['prompt']}

EXPECTATIONS (grade each):
{json.dumps(case['expectations'], indent=1)}

TOOL CALLS MADE BY THE SESSION (name: primary argument, in order):
{(out / 'toolcalls.txt').read_text(errors='replace') if (out / 'toolcalls.txt').exists() else '(none recorded)'}

PRIOR TURNS IN THE SAME SESSION:
{(out / 'context-transcript.md').read_text(errors='replace') if (out / 'context-transcript.md').exists() and (out / 'context-transcript.md').read_text().strip() else '(none)'}

EVALUATED FINAL-TURN RESPONSE:
{(out / 'transcript.md').read_text(errors='replace')}

POST-RUN FILE STATE:
{state if state.strip() else '(no .ai/memory directory exists after the run)'}

Respond with ONLY a JSON object: {{"verdicts": [{{"expectation": "...", "verdict": "PASS|FAIL", "why": "..."}}], "passed": N, "total": N}}""")
PY
    claude -p "$(cat "$OUT/judge-prompt.txt")" --model "$JUDGE_MODEL" --output-format json \
      --no-session-persistence --allowedTools "" > "$OUT/judge-raw.json" 2>> "$OUT/stderr.log"
    VERDICT=$(python3 - "$OUT" <<'PY'
import json, re, sys
out = sys.argv[1]
raw = json.load(open(f"{out}/judge-raw.json")).get("result", "")
m = re.search(r"\{.*\}", raw, re.S)
try:
    g = json.loads(m.group(0))
    json.dump(g, open(f"{out}/grading.json", "w"), indent=1)
    print("PASS" if g["passed"] == g["total"] else f"FAIL {g['passed']}/{g['total']}")
except Exception as e:
    print(f"JUDGE-ERROR {e}")
PY
)
    python3 - "$OUT" "$VARIANT" <<'PY'
import glob, json, pathlib, sys
out, variant = pathlib.Path(sys.argv[1]), sys.argv[2]
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
    echo "=== $SKILL eval-$CASE_ID: $VERDICT ($VARIANT)"
    case "$VERDICT" in PASS) ;; *) FAILED=$((FAILED+1));; esac
  done
done

echo
echo "RESULT: $((TOTAL-FAILED))/$TOTAL cases passed ($VARIANT; artifacts in qa/_work/results/)"
python3 - "$RESULTS" "$VARIANT" "${RUN_LABELS[@]}" <<'PY'
import json, pathlib, sys
root, variant, labels = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
rows = []
for label in labels:
    for path in root.glob(f"{label}-eval-*/metrics.json"):
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
[ "$BASELINE" -eq 1 ] || [ "$FAILED" -eq 0 ]
