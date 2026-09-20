import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


class EvalHarnessHardeningTests(unittest.TestCase):
    def test_real_target_extractor_retains_visible_events_and_requires_completion(self):
        source = (REPO / "qa/run_evals.sh").read_text()
        code = source.split('    PYTHONPATH="$QA" python3 - "$OUT" <<\'PY\'\n', 1)[1].split('\nPY\n', 1)[0]
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            records = [
                {"type": "assistant", "message": {"content": [{"type": "text", "text": "Extra preamble."}]}},
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "saved.md"}}]}},
                {"type": "user", "message": {"content": [{"type": "tool_result", "content": "saved", "tool_use_id": "read-1"}]}},
                {"type": "result", "subtype": "success", "result": "Six-line brief.", "total_cost_usd": 0.125},
            ]
            for complete in (True, False):
                records[-1]["subtype"] = "success" if complete else "error_max_turns"
                (out / "stdout.jsonl").write_text("\n".join(json.dumps(row) for row in records))
                result = subprocess.run([sys.executable, "-", str(out)], input=code,
                    env={**os.environ, "PYTHONPATH": str(REPO / "qa")}, capture_output=True, text=True)
                if complete:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    events = json.loads((out / "turn-events.json").read_text())
                    self.assertEqual(events[0]["content"]["text"], "Extra preamble.")
                    self.assertEqual(events[2]["content"]["type"], "tool_result")
                    self.assertEqual(json.loads((out / "runner-metrics.json").read_text())["total_cost_usd"], 0.125)
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("evaluated turn did not complete", result.stderr)
        self.assertIn("(out / 'turn-events.json').read_text", source)

    def test_setup_failures_leave_artifacts_and_do_not_skip_later_cells(self):
        # Execute the runner's real setup block, replacing only the paid CLI with a protocol stub.
        source = (REPO / "qa/run_evals.sh").read_text()
        block = source[source.index("    # Optional setup turns"):
                       source.index('    echo "=== $SKILL eval-$CASE_ID: run ($VARIANT)"')]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            suite = root / "suite.json"
            suite.write_text(json.dumps({"evals": [{"setup_turns": ["Start the workflow."]}]}))
            (root / "work").mkdir()
            script = "set -euo pipefail\n" + (
                f"QA={shlex.quote(str(REPO / 'qa'))}\n"
                f"EVALS={shlex.quote(str(suite))}\n"
                f"ARTIFACTS={shlex.quote(str(root))}\n"
                f"WORK={shlex.quote(str(root / 'work'))}\n"
            ) + r'''
i=0
BASELINE=0
SETUP_WITH_PLUGINS=1
PLUGIN=test-plugin
SKILL=test-skill
VARIANT=skill
INSTALL_MODE=skill
ALLOWED_TOOLS=''
FINAL_MODE_ARGS=(--plugin-dir synthetic-plugin)
EVAL_CLAUDE_ARGS=(--settings synthetic-settings)
INFRA_FAILED=0
FAILED=0
run_eval_claude() {
  if [ "$SCENARIO" = cli_error ]; then return 7; fi
  if [ "$SCENARIO" = malformed ]; then printf 'not-json\n'; return; fi
  python3 - "$SESSION_ID" "$SCENARIO" <<'PYCODE'
import json, sys
session, scenario = sys.argv[1:]
print(json.dumps({"type": "system", "subtype": "init", "session_id": session,
    "slash_commands": [] if scenario == "unverified" else ["test-plugin:test-skill"],
    "plugins": [{"name": "test-plugin"}], "apiKeySource": "apiKeyHelper"}))
print(json.dumps({"type": "result", "subtype": "success", "session_id": session,
    "result": "Ready for confirmation.", "total_cost_usd": 0.125, "num_turns": 1,
    "duration_ms": 10, "usage": {"input_tokens": 10, "output_tokens": 4}}))
PYCODE
}
for SCENARIO in cli_error malformed unverified good; do
  OUT="$ARTIFACTS/$SCENARIO"
  mkdir -p "$OUT"
  CASE_ID="$SCENARIO"
''' + block + r'''
  echo "EVALUATED:$SCENARIO"
done
echo "SUMMARY:failed=$FAILED infra=$INFRA_FAILED"
[ "$INFRA_FAILED" -eq 0 ]
'''
            completed = subprocess.run(["bash", "-c", script], cwd=REPO,
                                       text=True, capture_output=True, timeout=10)
            self.assertEqual(completed.returncode, 1, completed.stderr)
            self.assertIn("EVALUATED:good", completed.stdout, completed.stderr)
            self.assertIn("SUMMARY:failed=3 infra=1", completed.stdout)
            for scenario in ("cli_error", "malformed", "unverified"):
                self.assertNotIn(f"EVALUATED:{scenario}", completed.stdout)
                failure = json.loads((root / scenario / "invocation.json").read_text())
                self.assertFalse(failure["verified"])
                metrics = json.loads((root / scenario / "metrics.json").read_text())
                self.assertEqual(metrics["infrastructure_error"], "setup_failed")
                self.assertFalse((root / scenario / "grading.json").exists())
            metrics = json.loads((root / "unverified" / "metrics.json").read_text())
            self.assertEqual(metrics["total_cost_usd"], 0.125)
            self.assertEqual(metrics["input_tokens"], 10)

    def test_artifact_deletion_uses_numeric_index_not_declared_id(self):
        source = (REPO / "qa/run_evals.sh").read_text(encoding="utf-8")
        self.assertIn('OUT="$RESULTS/$LABEL-eval-$i"', source)
        self.assertNotIn('OUT="$RESULTS/$LABEL-eval-$CASE_ID"', source)
        self.assertIn("unsafe eval id", source)

    def test_live_runner_loads_disposable_mode_specific_packages(self):
        source = (REPO / "qa/run_evals.sh").read_text(encoding="utf-8")
        self.assertIn('PLUGIN_COPY_ROOT=$(mktemp -d', source)
        self.assertIn("materialize_installation", source)
        self.assertIn('EVAL_INSTALL_MODE="${EVAL_INSTALL_MODE:-}"', source)
        self.assertIn('LABEL="$DISTRIBUTION_LABEL-$INSTALL_MODE"', source)
        self.assertIn('FINAL_MODE_ARGS+=(--plugin-dir "$DEST_PLUGIN")', source)
        self.assertNotIn('FINAL_MODE_ARGS+=(--plugin-dir "$REPO/plugins', source)
        self.assertIn('validate_judge_result.py', source)
        self.assertNotIn('/.claude/skills/', source)

    def test_live_runner_supports_composition_plugin_setup_and_full_tool_inputs(self):
        source = (REPO / "qa/run_evals.sh").read_text(encoding="utf-8")
        self.assertIn("resolve_install_modes", source)
        self.assertIn('case.get("setup_with_plugins"', source)
        self.assertIn("SETUP_EFFECTIVE_PROMPT", source)
        self.assertIn('/toolcalls.json"', source)
        self.assertIn('/invocation.json"', source)
        self.assertIn("invocation_evidence", source)
        self.assertIn('run_eval_claude -p "$EFFECTIVE_PROMPT"', source)
        self.assertIn("INSTALLATION MODE:", source)
        self.assertIn('\"$INSTALL_MODE\" > \"$OUT/judge-prompt.txt\"', source)
        self.assertNotIn("str(arg)[:500]", source)

    def test_live_runner_can_pin_evaluated_model_and_effort_without_changing_judge(self):
        source = (REPO / "qa/run_evals.sh").read_text(encoding="utf-8")
        self.assertIn('EVAL_MODEL="${EVAL_MODEL:-}"', source)
        self.assertIn('EVAL_MODEL_ARGS=(--model "$EVAL_MODEL")', source)
        self.assertGreaterEqual(
            source.count('${EVAL_MODEL_ARGS[@]+"${EVAL_MODEL_ARGS[@]}"}'), 2
        )
        self.assertIn('EVAL_EFFORT="${EVAL_EFFORT:-}"', source)
        self.assertIn('EVAL_EFFORT_ARGS=(--effort "$EVAL_EFFORT")', source)
        self.assertGreaterEqual(
            source.count('${EVAL_EFFORT_ARGS[@]+"${EVAL_EFFORT_ARGS[@]}"}'), 2
        )
        self.assertIn('EVAL_DEBUG="${EVAL_DEBUG:-0}"', source)
        self.assertIn('--debug-file "$OUT/claude-debug.log"', source)
        self.assertGreaterEqual(
            source.count('${EVAL_DEBUG_ARGS[@]+"${EVAL_DEBUG_ARGS[@]}"}'), 2
        )
        self.assertIn('--model "$JUDGE_MODEL"', source)
        self.assertIn('"requested_eval_model": requested_eval_model or None', source)
        self.assertIn('"requested_eval_effort": requested_eval_effort or None', source)

    def test_live_runner_fails_before_execution_on_fixture_contract_errors(self):
        source = (REPO / "qa/run_evals.sh").read_text(encoding="utf-8")
        self.assertIn("fixture_errors", source)
        self.assertIn("fixture contract failed", source)

    def test_live_runner_uses_bounded_no_follow_state_capture(self):
        source = (REPO / "qa/run_evals.sh").read_text(encoding="utf-8")
        self.assertIn('"$QA/snapshot_eval_state.py"', source)
        self.assertNotIn('cp -R "$WORK/.ai/memory"', source)
        self.assertNotIn('cat "$f"', source)
        self.assertNotIn("mem.rglob", source)

    def test_live_runner_requires_fail_closed_sandbox_and_sanitized_auth(self):
        source = (REPO / "qa/run_evals.sh").read_text(encoding="utf-8")
        self.assertIn("eval_sandbox.py check-version", source)
        self.assertNotIn("--bare", source)
        self.assertIn('--tools "$AVAILABLE_TOOLS"', source)
        self.assertIn(
            'AVAILABLE_TOOLS="Bash,Edit,Read,Glob,Grep,Skill,Task,Write"',
            source,
        )
        self.assertIn('--setting-sources ""', source)
        self.assertIn("--permission-mode dontAsk", source)
        self.assertIn("env -i", source)
        self.assertIn("CLAUDE_CODE_DISABLE_CLAUDE_MDS=1", source)
        self.assertIn("CLAUDE_CODE_DISABLE_AUTO_MEMORY=1", source)
        self.assertIn("EVAL_SHELL=$(command -v bash)", source)
        self.assertIn('CLAUDE_CODE_SHELL="$EVAL_SHELL"', source)
        self.assertIn('TEMP_PARENT=/tmp', source)
        self.assertIn('EVAL_TEMP_PARENT must be absolute', source)
        self.assertIn('mktemp -d "$TEMP_PARENT/overclock-eval-auth.', source)
        self.assertIn("read_eval_api_key.py", source)
        self.assertIn("HOST_NODE_BIN=$(command -v node || true)", source)
        self.assertIn('cp "$HOST_NODE_BIN" "$EVAL_TOOL_ROOT/node"', source)
        self.assertIn('unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN', source)
        allowed_line = next(
            line for line in source.splitlines() if line.startswith("ALLOWED_TOOLS=")
        )
        self.assertNotIn("Bash(gh *)", allowed_line)

    def test_paired_value_runner_forces_variants_and_fresh_provenance(self):
        source = (REPO / "qa/run_value_evals.sh").read_text(encoding="utf-8")
        self.assertIn('EVAL_PAIR_ID="$PAIR_ID" BASELINE=1', source)
        self.assertIn('EVAL_PAIR_ID="$PAIR_ID" BASELINE=0', source)
        self.assertIn('--pair-id "$PAIR_ID"', source)
        runner = (REPO / "qa/run_evals.sh").read_text(encoding="utf-8")
        self.assertIn('"$QA/eval_provenance.py"', runner)

    def test_trigger_battery_also_loads_the_plugin(self):
        source = (REPO / "qa/trigger_battery.py").read_text(encoding="utf-8")
        self.assertIn('for item in ("--plugin-dir", str(destination_copy))', source)
        self.assertIn("materialize_installation", source)
        self.assertIn("resolve_install_modes", source)
        self.assertNotIn('cwd / ".claude" / "skills"', source)


class LiveEvalWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (REPO / ".github/workflows/evals.yml").read_text(
            encoding="utf-8"
        )

    def test_workflow_lists_every_behavioral_distribution(self):
        for suite in sorted((REPO / "qa/evals").glob("*/*.evals.json")):
            plugin = suite.parent.name
            skill = suite.name.removesuffix(".evals.json")
            with self.subTest(distribution=f"{plugin}/{skill}"):
                self.assertIn(f"{plugin}/{skill}", self.source)

    def test_workflow_maps_every_routing_battery(self):
        for battery in sorted((REPO / "qa/trigger-battery").glob("*.json")):
            with self.subTest(battery=battery.stem):
                self.assertIn(battery.stem, self.source)

    def test_workflow_defaults_to_bounded_sonnet_5_evidence(self):
        self.assertIn("default: critical-thinking/critical-thinking", self.source)
        self.assertIn("default: claude-sonnet-5", self.source)
        self.assertIn("options: [skill, declared, plugin, stack]", self.source)
        self.assertIn("default: skill", self.source)
        self.assertIn("routing_samples:", self.source)
        self.assertIn("default: 1", self.source)
        self.assertIn('requires confirm_all=true', self.source)

    def test_compare_dispatch_executes_and_propagates_the_real_gate(self):
        block = self.source.split("          run_suite() {", 1)[1].split(
            '          if [[ "$TARGET"', 1)[0]
        function = "run_suite() {" + block
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "qa").mkdir()
            (root / "qa/run_value_evals.sh").write_text('echo "PAIRED:$*"\nexit 7\n')
            (root / "qa/run_evals.sh").write_text('echo "ORDINARY:$*"\nexit 0\n')
            for enabled, expected, status in (("true", "PAIRED", 7), ("false", "ORDINARY", 0)):
                result = subprocess.run(["bash", "-c", f"COMPARE_BASELINE={enabled}\n" + function +
                                         "\nrun_suite session-memory/session-handoff"],
                                        cwd=root, capture_output=True, text=True)
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual(result.stdout.strip(), f"{expected}:session-memory/session-handoff")

    def test_partial_value_run_is_rejected_before_model_execution(self):
        result = subprocess.run(["bash", "qa/run_value_evals.sh", "session-memory/session-handoff"],
                                cwd=REPO, env={**os.environ, "EVAL_ONLY": "7"},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("full suite", result.stderr)

    def test_missing_gate_is_rejected_before_model_execution(self):
        result = subprocess.run(["bash", "qa/run_value_evals.sh", "overclock-setup/setup"],
                                cwd=REPO, env={**os.environ, "EVAL_ONLY": ""},
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing value_gate", result.stderr)
        self.assertNotIn("live evals require", result.stderr)

    def test_value_wrapper_preserves_failures_and_pairs_both_arms(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            qa = root / "qa"
            qa.mkdir()
            # Use the real shell wrapper and schema validator; replace only the
            # paid runner and comparator process to exercise orchestration.
            for source in (REPO / "qa").glob("*.py"):
                if not source.name.startswith("test_"):
                    shutil.copy2(source, qa / source.name)
            shutil.copy2(REPO / "qa/run_value_evals.sh", qa / "run_value_evals.sh")
            suite = qa / "evals/demo/example.evals.json"
            suite.parent.mkdir(parents=True)
            suite.write_text(json.dumps({"skill_name": "example", "invocation": "explicit",
                "install_modes": ["skill"], "value_gate": {},
                "evals": [{"prompt": "Do the task.", "expectations": ["Correct result."]}]}))
            (qa / "run_evals.sh").write_text(
                'echo "RUN:$BASELINE:$EVAL_PAIR_ID:$EVAL_MODEL:$EVAL_EFFORT"\n'
                '[ "$BASELINE" != 1 ] || exit "$STUB_BASELINE_STATUS"\n')
            (qa / "check_eval_value.py").write_text(
                'import os, sys\n'
                'def value_thresholds(data): return data["value_gate"]\n'
                'if __name__ == "__main__":\n'
                '    print("COMPARE:" + sys.argv[sys.argv.index("--pair-id") + 1])\n'
                '    sys.exit(int(os.environ["STUB_COMPARE_STATUS"]))\n')
            for baseline_status, compare_status in ((7, 0), (0, 1), (0, 0)):
                result = subprocess.run(["bash", "qa/run_value_evals.sh", "demo/example"],
                    cwd=root, env={**os.environ, "EVAL_ONLY": "", "EVAL_INSTALL_MODE": "",
                        "EVAL_MODEL": "test-model", "EVAL_EFFORT": "medium",
                        "STUB_BASELINE_STATUS": str(baseline_status),
                        "STUB_COMPARE_STATUS": str(compare_status)}, capture_output=True, text=True)
                self.assertEqual(result.returncode, baseline_status or compare_status, result.stderr)
                lines = [line.split(":") for line in result.stdout.splitlines()]
                self.assertEqual(len(lines), 3, result.stdout)
                self.assertEqual([lines[0][:2], lines[1][:2], lines[2][:1]],
                                 [["RUN", "1"], ["RUN", "0"], ["COMPARE"]])
                self.assertEqual(lines[0][2], lines[1][2])
                self.assertEqual(lines[1][2], lines[2][1])
                self.assertEqual(lines[0][3:], ["test-model", "medium"])


if __name__ == "__main__":
    unittest.main()
