from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from summarize_eval_results import render


class EvalSummaryTest(unittest.TestCase):
    def test_pairs_skill_and_baseline_with_incremental_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "critical-thinking-eval-6"
            baseline = root / "critical-thinking-baseline-eval-6"
            skill.mkdir()
            baseline.mkdir()
            (skill / "grading.json").write_text(json.dumps({"passed": 5, "total": 5}))
            (baseline / "grading.json").write_text(json.dumps({"passed": 2, "total": 5}))
            (skill / "metrics.json").write_text(json.dumps({
                "variant": "skill", "total_cost_usd": 0.12,
                "duration_ms": 3000, "num_turns": 3,
            }))
            (baseline / "metrics.json").write_text(json.dumps({
                "variant": "baseline", "total_cost_usd": 0.05,
                "duration_ms": 1000, "num_turns": 1,
            }))

            summary = render(root)

        self.assertIn("skill 5/5, baseline 2/5", summary)
        self.assertIn("incremental $0.0700, +2.0s", summary)


if __name__ == "__main__":
    unittest.main()
