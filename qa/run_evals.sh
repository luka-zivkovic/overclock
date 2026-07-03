#!/usr/bin/env bash
# Live regression evals for Overclock skills.
#
# For each eval case: fresh `claude -p` session in its fixture (skill installed
# project-level), transcript captured, then a SECOND session with a different
# model judges the transcript + post-run file state against the case's
# expectations. Exits non-zero if any case fails.
#
# A skill's cases live at qa/evals/<plugin>/<skill>.evals.json; the plugin dir
# is derived from that path, so new plugins need no harness changes.
#
# Usage: qa/run_evals.sh [skill ...]        (default: the session-memory pair)
# Requires: claude CLI on PATH, authenticated (ANTHROPIC_API_KEY in CI).
# Cost: one runner session + one judge session per case (~10 cases total).
set -uo pipefail
cd "$(dirname "$0")"
QA="$(pwd)"
REPO="$(dirname "$QA")"
JUDGE_MODEL="${JUDGE_MODEL:-claude-haiku-4-5-20251001}"
SKILLS=("${@:-session-handoff lessons-learned}")
[ $# -eq 0 ] && SKILLS=(session-handoff lessons-learned)

command -v claude >/dev/null || { echo "claude CLI not found" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 1; }

bash fixtures/setup.sh

mkdir -p "$QA/_work"
RESULTS="$QA/_work/results"
mkdir -p "$RESULTS"
FAILED=0
TOTAL=0

for SKILL in "${SKILLS[@]}"; do
  EVALS=$(ls "$QA"/evals/*/"$SKILL.evals.json" 2>/dev/null | head -n 1)
  [ -n "$EVALS" ] || { echo "no eval suite found for skill '$SKILL' under qa/evals/*/" >&2; exit 1; }
  PLUGIN=$(basename "$(dirname "$EVALS")")
  N=$(python3 -c "import json;print(len(json.load(open('$EVALS'))['evals']))")
  for ((i=0; i<N; i++)); do
    # EVAL_ONLY=<id> re-runs a single case (debugging / post-fix verification)
    [ -n "${EVAL_ONLY:-}" ] && [ "$i" != "$EVAL_ONLY" ] && continue
    TOTAL=$((TOTAL+1))
    WORK="${EVAL_FIXTURE_DIR:-/tmp/overclock-eval-fixtures}/$SKILL/eval-$i"
    OUT="$RESULTS/$SKILL-eval-$i"
    mkdir -p "$OUT"
    PROMPT=$(python3 -c "import json;print(json.load(open('$EVALS'))['evals'][$i]['prompt'])")

    # Install the skill project-level in the fixture
    mkdir -p "$WORK/.claude/skills"
    rm -rf "$WORK/.claude/skills/$SKILL"
    cp -R "$REPO/plugins/$PLUGIN/skills/$SKILL" "$WORK/.claude/skills/$SKILL"

    echo "=== $SKILL eval-$i: run"
    # stream-json (requires --verbose) exposes tool calls, so the judge can grade
    # process expectations ("the contract was read") on evidence, not inference.
    ( cd "$WORK" && claude -p "$PROMPT" --output-format stream-json --verbose --no-session-persistence \
        --allowedTools "Bash(git *),Read,Glob,Grep,Skill,Bash(ls*),Bash(cat*),Bash(mkdir*),Bash(mv*),Bash(cp*),Bash(node*),Bash(npm test*),Bash(gh *),Write,Edit" \
      ) > "$OUT/stdout.jsonl" 2> "$OUT/stderr.log"
    python3 - "$OUT" <<'PY'
import json, sys
out = sys.argv[1]
result, tools = "", []
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
    elif ev.get("type") == "assistant":
        for block in ev.get("message", {}).get("content", []):
            if block.get("type") == "tool_use":
                inp = block.get("input", {})
                arg = inp.get("file_path") or inp.get("command") or inp.get("pattern") or ""
                tools.append(f"{block.get('name')}: {str(arg)[:160]}")
open(f"{out}/transcript.md", "w").write(result)
open(f"{out}/toolcalls.txt", "w").write("\n".join(tools) + "\n")
PY

    # Snapshot post-run memory state + git for the judge. Skills that write no
    # .ai/memory (e.g. discipline-gates) are graded on git evidence instead:
    # committed tests, restored files, and untracked leftovers.
    rm -rf "$OUT/state"; mkdir -p "$OUT/state"
    [ -d "$WORK/.ai/memory" ] && cp -R "$WORK/.ai/memory" "$OUT/state/memory"
    ( cd "$WORK" && git status --porcelain > "$OUT/state/git_status.txt" 2>/dev/null
      git log --oneline -n 8 > "$OUT/state/git_log.txt" 2>/dev/null
      git diff HEAD > "$OUT/state/git_diff.txt" 2>/dev/null
      git log -p -n 8 > "$OUT/state/git_log_full.txt" 2>/dev/null
      git ls-files --others --exclude-standard | grep -v '^\.claude/' | while read -r f; do
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

SESSION TRANSCRIPT (final response):
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
    echo "=== $SKILL eval-$i: $VERDICT"
    case "$VERDICT" in PASS) ;; *) FAILED=$((FAILED+1));; esac
  done
done

echo
echo "RESULT: $((TOTAL-FAILED))/$TOTAL cases passed (artifacts in qa/_work/results/)"
[ "$FAILED" -eq 0 ]
