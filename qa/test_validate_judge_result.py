import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_judge_result import normalize


class ValidateJudgeResultTests(unittest.TestCase):
    def test_rejects_empty_eval_expectations(self):
        raw = json.dumps({"verdicts": [], "passed": 0, "total": 0})
        with self.assertRaisesRegex(ValueError, "non-empty"):
            normalize(raw, [])

    def test_rejects_empty_zero_of_zero_for_nonempty_expectations(self):
        raw = json.dumps({"verdicts": [], "passed": 0, "total": 0})
        with self.assertRaisesRegex(ValueError, "0 verdicts for 1 expectations"):
            normalize(raw, ["must happen"])

    def test_rejects_unknown_verdict_enum(self):
        raw = json.dumps(
            {"verdicts": [{"verdict": "MAYBE", "why": "unclear"}], "passed": 1, "total": 1}
        )
        with self.assertRaisesRegex(ValueError, "PASS or FAIL"):
            normalize(raw, ["must happen"])

    def test_computes_counts_instead_of_trusting_judge_counters(self):
        raw = json.dumps(
            {
                "verdicts": [
                    {"verdict": "PASS", "why": "evidence"},
                    {"verdict": "FAIL", "why": "missing"},
                ],
                "passed": 99,
                "total": 99,
            }
        )
        grading = normalize(raw, ["first", "second"])
        self.assertEqual(grading["passed"], 1)
        self.assertEqual(grading["total"], 2)
        self.assertEqual([row["expectation"] for row in grading["verdicts"]], ["first", "second"])


if __name__ == "__main__":
    unittest.main()
