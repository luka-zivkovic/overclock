#!/usr/bin/env python3
"""Gate a skill's behavioral results against its no-skill baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval_contract import load_suite
from eval_packaging import resolve_install_modes
from eval_provenance import record


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def compare(
    results: Path,
    plugin: str,
    skill: str,
    suite: Path,
    eval_root: Path,
    *,
    expected_pair_id: str | None = None,
    plugin_root: Path | None = None,
    install_mode: str | None = None,
) -> tuple[dict, list[str]]:
    resolved_suite, data = load_suite(suite, eval_root)
    source_plugins = plugin_root or eval_root.parent.parent / "plugins"
    gate = data.get("value_gate")
    if not isinstance(gate, dict):
        return {}, [f"{suite}: missing value_gate"]
    allowed = {
        "min_case_wins",
        "max_case_losses",
        "min_total_expectation_lift",
    }
    unknown = set(gate) - allowed
    if unknown:
        return {}, [f"{suite}: unknown value gate fields: {sorted(unknown)}"]
    defaults = {
        "min_case_wins": 1,
        "max_case_losses": 0,
        "min_total_expectation_lift": 1,
    }
    thresholds = {**defaults, **gate}
    if not all(
        isinstance(value, int) and value >= 0 for value in thresholds.values()
    ):
        return {}, [f"{suite}: value gate thresholds must be non-negative integers"]

    rows = []
    for index, case in enumerate(data["evals"]):
        modes = resolve_install_modes(
            case,
            plugin,
            suite=data,
            override=install_mode,
        )
        for mode in modes:
            skill_dir = results / f"{plugin}-{skill}-{mode}-eval-{index}"
            baseline_dir = (
                results / f"{plugin}-{skill}-{mode}-baseline-eval-{index}"
            )
            skill_grade_path = skill_dir / "grading.json"
            baseline_grade_path = baseline_dir / "grading.json"
            skill_provenance_path = skill_dir / "provenance.json"
            baseline_provenance_path = baseline_dir / "provenance.json"
            if not all(
                path.is_file()
                for path in (
                    skill_grade_path,
                    baseline_grade_path,
                    skill_provenance_path,
                    baseline_provenance_path,
                )
            ):
                return {}, [
                    f"missing paired grading/provenance artifacts for "
                    f"{plugin}/{skill} {mode} eval-{index}"
                ]
            skill_grade = read_json(skill_grade_path)
            baseline_grade = read_json(baseline_grade_path)
            skill_provenance = read_json(skill_provenance_path)
            baseline_provenance = read_json(baseline_provenance_path)
            skill_pair = skill_provenance.get("pair_id")
            baseline_pair = baseline_provenance.get("pair_id")
            if (
                not isinstance(skill_pair, str)
                or skill_pair != baseline_pair
                or (expected_pair_id is not None and skill_pair != expected_pair_id)
            ):
                return {}, [
                    f"paired artifacts have stale or mismatched run ids for "
                    f"{plugin}/{skill} {mode} eval-{index}"
                ]
            current_skill = record(
                pair_id=skill_pair,
                variant="skill",
                plugin=plugin,
                skill=skill,
                suite=resolved_suite,
                case=case,
                index=index,
                plugin_root=source_plugins,
                install_mode=mode,
            )
            current_baseline = {
                **current_skill,
                "variant": "baseline",
            }
            if (
                skill_provenance != current_skill
                or baseline_provenance != current_baseline
            ):
                return {}, [
                    "paired artifacts do not match current "
                    "suite/case/plugin sources for "
                    f"{plugin}/{skill} {mode} eval-{index}"
                ]
            expected_total = len(case["expectations"])
            for label, grade in (
                ("skill", skill_grade),
                ("baseline", baseline_grade),
            ):
                passed = grade.get("passed")
                total = grade.get("total")
                if (
                    not isinstance(passed, int)
                    or isinstance(passed, bool)
                    or not isinstance(total, int)
                    or isinstance(total, bool)
                    or total != expected_total
                    or not 0 <= passed <= total
                ):
                    return {}, [
                        f"{label} grading artifact has invalid counts for "
                        f"{plugin}/{skill} {mode} eval-{index}"
                    ]
            rows.append(
                {
                    "index": index,
                    "id": case.get("id", index),
                    "install_mode": mode,
                    "skill_passed": skill_grade["passed"],
                    "baseline_passed": baseline_grade["passed"],
                    "lift": skill_grade["passed"] - baseline_grade["passed"],
                }
            )

    case_wins = sum(row["lift"] > 0 for row in rows)
    case_losses = sum(row["lift"] < 0 for row in rows)
    total_lift = sum(row["lift"] for row in rows)
    summary = {
        "plugin": plugin,
        "skill": skill,
        "install_modes": list(dict.fromkeys(row["install_mode"] for row in rows)),
        "case_wins": case_wins,
        "case_losses": case_losses,
        "total_expectation_lift": total_lift,
        "thresholds": thresholds,
        "rows": rows,
    }
    failures = []
    if case_wins < thresholds["min_case_wins"]:
        failures.append(
            f"case wins {case_wins} < {thresholds['min_case_wins']}"
        )
    if case_losses > thresholds["max_case_losses"]:
        failures.append(
            f"case losses {case_losses} > {thresholds['max_case_losses']}"
        )
    if total_lift < thresholds["min_total_expectation_lift"]:
        failures.append(
            "total expectation lift "
            f"{total_lift} < {thresholds['min_total_expectation_lift']}"
        )
    return summary, failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("target", help="plugin/skill")
    parser.add_argument(
        "--eval-root",
        type=Path,
        default=Path(__file__).resolve().parent / "evals",
    )
    parser.add_argument("--pair-id")
    parser.add_argument(
        "--install-mode",
        choices=("skill", "plugin", "stack"),
    )
    args = parser.parse_args()
    if args.target.count("/") != 1:
        parser.error("target must be plugin/skill")
    plugin, skill = args.target.split("/", 1)
    suite = args.eval_root / plugin / f"{skill}.evals.json"
    try:
        summary, failures = compare(
            args.results,
            plugin,
            skill,
            suite,
            args.eval_root,
            expected_pair_id=args.pair_id,
            install_mode=args.install_mode,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"VALUE-GATE ERROR: {exc}")
        return 2
    if summary:
        print(json.dumps(summary, indent=1))
    if failures:
        print("VALUE GATE FAILED: " + "; ".join(failures))
        return 1
    print("VALUE GATE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
