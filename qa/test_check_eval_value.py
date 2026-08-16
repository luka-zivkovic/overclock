from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_eval_value import compare
from eval_provenance import record


class EvalValueGateTests(unittest.TestCase):
    def write_grade(
        self,
        path: Path,
        passed: int,
        provenance: dict,
        total: int = 3,
    ) -> None:
        path.mkdir(parents=True)
        (path / "grading.json").write_text(
            json.dumps({"passed": passed, "total": total, "verdicts": []}),
            encoding="utf-8",
        )
        (path / "provenance.json").write_text(
            json.dumps(provenance),
            encoding="utf-8",
        )

    def write_plugin(self, root: Path) -> Path:
        plugin_root = root / "plugins"
        plugin = plugin_root / "demo"
        (plugin / ".claude-plugin").mkdir(parents=True)
        (plugin / ".claude-plugin/plugin.json").write_text(
            '{"name":"demo","version":"1.0.0"}\n',
            encoding="utf-8",
        )
        skill = plugin / "skills" / "example"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: example\ndescription: Example behavior\n---\n",
            encoding="utf-8",
        )
        return plugin_root

    def test_compares_every_mode_in_an_explicit_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            eval_root = root / "evals"
            suite = eval_root / "demo/example.evals.json"
            suite.parent.mkdir(parents=True)
            suite.write_text(
                json.dumps(
                    {
                        "skill_name": "example",
                        "install_modes": ["skill", "plugin"],
                        "value_gate": {},
                        "evals": [{"prompt": "a", "expectations": ["x"]}],
                    }
                ),
                encoding="utf-8",
            )
            plugin_root = self.write_plugin(root)
            case = json.loads(suite.read_text(encoding="utf-8"))["evals"][0]
            results = root / "results"
            for mode in ("skill", "plugin"):
                provenance = record(
                    pair_id="matrix-pair",
                    variant="skill",
                    plugin="demo",
                    skill="example",
                    suite=suite,
                    case=case,
                    index=0,
                    plugin_root=plugin_root,
                    install_mode=mode,
                )
                self.write_grade(
                    results / f"demo-example-{mode}-eval-0",
                    1,
                    provenance,
                    total=1,
                )
                self.write_grade(
                    results / f"demo-example-{mode}-baseline-eval-0",
                    0,
                    {**provenance, "variant": "baseline"},
                    total=1,
                )

            summary, failures = compare(
                results,
                "demo",
                "example",
                suite,
                eval_root,
                expected_pair_id="matrix-pair",
                plugin_root=plugin_root,
            )

        self.assertEqual(failures, [])
        self.assertEqual(summary["install_modes"], ["skill", "plugin"])
        self.assertEqual(len(summary["rows"]), 2)

    def test_compares_paired_cases_and_enforces_lift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            eval_root = root / "evals"
            suite = eval_root / "demo" / "example.evals.json"
            suite.parent.mkdir(parents=True)
            suite.write_text(
                json.dumps(
                    {
                        "skill_name": "example",
                        "value_gate": {
                            "min_case_wins": 1,
                            "max_case_losses": 0,
                            "min_total_expectation_lift": 1,
                        },
                        "evals": [
                            {"prompt": "a", "expectations": ["x", "y", "z"]},
                            {"prompt": "b", "expectations": ["x", "y", "z"]},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            results = root / "results"
            plugin_root = self.write_plugin(root)
            data = json.loads(suite.read_text(encoding="utf-8"))
            for index, (skill_passed, baseline_passed) in enumerate(((3, 1), (3, 3))):
                skill_provenance = record(
                    pair_id="pair-1",
                    variant="skill",
                    plugin="demo",
                    skill="example",
                    suite=suite,
                    case=data["evals"][index],
                    index=index,
                    plugin_root=plugin_root,
                    install_mode="plugin",
                )
                self.write_grade(
                    results / f"demo-example-plugin-eval-{index}",
                    skill_passed,
                    skill_provenance,
                )
                self.write_grade(
                    results / f"demo-example-plugin-baseline-eval-{index}",
                    baseline_passed,
                    {**skill_provenance, "variant": "baseline"},
                )
            summary, failures = compare(
                results,
                "demo",
                "example",
                suite,
                eval_root,
                expected_pair_id="pair-1",
                plugin_root=plugin_root,
            )
        self.assertEqual(failures, [])
        self.assertEqual(summary["case_wins"], 1)
        self.assertEqual(summary["total_expectation_lift"], 2)

    def test_reports_a_baseline_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            eval_root = root / "evals"
            suite = eval_root / "demo" / "example.evals.json"
            suite.parent.mkdir(parents=True)
            suite.write_text(
                json.dumps(
                    {
                        "skill_name": "example",
                        "value_gate": {},
                        "evals": [{"prompt": "a", "expectations": ["x"]}],
                    }
                ),
                encoding="utf-8",
            )
            results = root / "results"
            plugin_root = self.write_plugin(root)
            case = json.loads(suite.read_text(encoding="utf-8"))["evals"][0]
            skill_provenance = record(
                pair_id="pair-2",
                variant="skill",
                plugin="demo",
                skill="example",
                suite=suite,
                case=case,
                index=0,
                plugin_root=plugin_root,
                install_mode="plugin",
            )
            self.write_grade(
                results / "demo-example-plugin-eval-0",
                0,
                skill_provenance,
                total=1,
            )
            self.write_grade(
                results / "demo-example-plugin-baseline-eval-0",
                1,
                {**skill_provenance, "variant": "baseline"},
                total=1,
            )
            _, failures = compare(
                results,
                "demo",
                "example",
                suite,
                eval_root,
                expected_pair_id="pair-2",
                plugin_root=plugin_root,
            )
        self.assertTrue(any("case losses" in failure for failure in failures))

    def test_rejects_stale_pair_or_changed_plugin_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            eval_root = root / "evals"
            suite = eval_root / "demo/example.evals.json"
            suite.parent.mkdir(parents=True)
            suite.write_text(
                json.dumps(
                    {
                        "skill_name": "example",
                        "value_gate": {},
                        "evals": [{"prompt": "a", "expectations": ["x"]}],
                    }
                ),
                encoding="utf-8",
            )
            plugin_root = self.write_plugin(root)
            case = json.loads(suite.read_text(encoding="utf-8"))["evals"][0]
            provenance = record(
                pair_id="old-pair",
                variant="skill",
                plugin="demo",
                skill="example",
                suite=suite,
                case=case,
                index=0,
                plugin_root=plugin_root,
                install_mode="plugin",
            )
            results = root / "results"
            self.write_grade(
                results / "demo-example-plugin-eval-0",
                1,
                provenance,
                total=1,
            )
            self.write_grade(
                results / "demo-example-plugin-baseline-eval-0",
                0,
                {**provenance, "variant": "baseline"},
                total=1,
            )

            _, pair_failures = compare(
                results,
                "demo",
                "example",
                suite,
                eval_root,
                expected_pair_id="fresh-pair",
                plugin_root=plugin_root,
            )
            self.assertTrue(any("run ids" in failure for failure in pair_failures))

            (plugin_root / "demo/new.txt").write_text("changed\n", encoding="utf-8")
            _, source_failures = compare(
                results,
                "demo",
                "example",
                suite,
                eval_root,
                expected_pair_id="old-pair",
                plugin_root=plugin_root,
            )
            self.assertTrue(any("current suite" in failure for failure in source_failures))


if __name__ == "__main__":
    unittest.main()
