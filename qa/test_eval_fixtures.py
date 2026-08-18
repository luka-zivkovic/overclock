from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_contract import all_suite_paths, fixture_errors, validate_suite
from fixtures.validate_root import validate_root


REPO = Path(__file__).resolve().parents[1]
EVAL_ROOT = REPO / "qa" / "evals"


class EvalFixtureParityTests(unittest.TestCase):
    def test_fixture_root_must_be_temporary_and_outside_repository(self) -> None:
        with self.assertRaisesRegex(ValueError, "temporary"):
            validate_root(Path("/opt/overclock-eval-fixtures"), REPO)
        with self.assertRaisesRegex(ValueError, "repository"):
            validate_root(REPO, REPO)

    def test_setup_refuses_to_wipe_a_marked_nonempty_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture_root = Path(temp) / "fixtures"
            fixture_root.mkdir()
            (fixture_root / ".overclock-eval-fixture-root").touch()
            sentinel = fixture_root / "keep.txt"
            sentinel.write_text("preserve\n", encoding="utf-8")
            env = dict(os.environ)
            env["EVAL_FIXTURE_DIR"] = str(fixture_root)

            completed = subprocess.run(
                ["bash", "qa/fixtures/setup.sh"],
                cwd=REPO,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("refusing to wipe existing data", completed.stderr)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")

    def test_setup_has_no_recursive_fixture_root_deletion(self) -> None:
        source = (REPO / "qa/fixtures/setup.sh").read_text(encoding="utf-8")
        self.assertNotIn('rm -rf "$ROOT"', source)

    def test_supplemental_fixture_help_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            completed = subprocess.run(
                [sys.executable, str(REPO / "qa/fixtures/additional.py"), "--help"],
                cwd=temp,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("fixture_root", completed.stdout)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_every_suite_has_valid_case_schema(self) -> None:
        errors: list[str] = []
        for suite in all_suite_paths(EVAL_ROOT):
            errors.extend(validate_suite(suite, EVAL_ROOT))
        self.assertEqual(errors, [])

    def test_generated_fixtures_cover_every_declared_case_and_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture_root = Path(temp) / "fixtures"
            env = dict(os.environ)
            env["EVAL_FIXTURE_DIR"] = str(fixture_root)
            env["EVAL_FIXTURE_SKIP_REMOTE"] = "1"
            subprocess.run(
                ["bash", "qa/fixtures/setup.sh"],
                cwd=REPO,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            errors: list[str] = []
            for suite in all_suite_paths(EVAL_ROOT):
                errors.extend(fixture_errors(fixture_root, suite, EVAL_ROOT))
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
