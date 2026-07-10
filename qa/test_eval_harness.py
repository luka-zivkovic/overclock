import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


class EvalHarnessHardeningTests(unittest.TestCase):
    def test_artifact_deletion_uses_numeric_index_not_declared_id(self):
        source = (REPO / "qa/run_evals.sh").read_text(encoding="utf-8")
        self.assertIn('OUT="$RESULTS/$LABEL-eval-$i"', source)
        self.assertNotIn('OUT="$RESULTS/$LABEL-eval-$CASE_ID"', source)
        self.assertIn("unsafe eval id", source)

    def test_live_runner_loads_the_real_plugin_and_validates_judge_shape(self):
        source = (REPO / "qa/run_evals.sh").read_text(encoding="utf-8")
        self.assertIn('--plugin-dir "$SOURCE_PLUGIN"', source)
        self.assertIn('validate_judge_result.py', source)
        self.assertNotIn('/.claude/skills/', source)

    def test_trigger_battery_also_loads_the_plugin(self):
        source = (REPO / "qa/trigger_battery.py").read_text(encoding="utf-8")
        self.assertIn('"--plugin-dir", str(destination_plugin)', source)
        self.assertNotIn('cwd / ".claude" / "skills"', source)


if __name__ == "__main__":
    unittest.main()
