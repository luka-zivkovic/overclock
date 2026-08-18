import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


class EvalHarnessHardeningTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
