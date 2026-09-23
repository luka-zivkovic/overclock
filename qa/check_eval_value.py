#!/usr/bin/env python3
"""Gate a skill's behavioral results against its no-skill baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval_contract import load_suite
from eval_packaging import resolve_install_modes
from eval_provenance import record
from eval_runtime import harness_hash
from validate_judge_result import normalize


def value_thresholds(data: dict) -> dict:
    gate = data.get("value_gate")
    defaults = {"min_case_wins": 1, "max_case_losses": 0,
                "min_total_expectation_lift": 1}
    if not isinstance(gate, dict):
        raise ValueError("missing value_gate; a baseline run alone cannot establish benefit")
    if set(gate) - set(defaults):
        raise ValueError(f"unknown value gate fields: {sorted(set(gate) - set(defaults))}")
    thresholds = {**defaults, **gate}
    if any(type(value) is not int or value < 0 for value in thresholds.values()):
        raise ValueError("value gate thresholds must be non-negative integers")
    return thresholds


def checked_grade(grade: dict, expectations: list[str]) -> dict:
    if not isinstance(grade, dict) or type(grade.get("passed")) is not int or type(grade.get("total")) is not int:
        raise ValueError("grading artifact has invalid counts")
    normalized = normalize(json.dumps(grade), expectations)
    # normalize binds positions for live judge output; stored artifacts must already
    # carry those exact labels and counts. Never trust an edited aggregate alone.
    if grade != normalized:
        raise ValueError("grading artifact does not match declared expectations and verdict counts")
    return normalized


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
    try:
        thresholds = value_thresholds(data)
    except ValueError as exc:
        return {}, [f"{suite}: {exc}"]

    rows = []
    observed_pair = expected_pair_id
    observed_runtime = None
    current_harness_hash = harness_hash()
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
            runtime_paths = [skill_dir / "runtime.json", baseline_dir / "runtime.json"]
            if not all(
                path.is_file()
                for path in (
                    skill_grade_path,
                    baseline_grade_path,
                    skill_provenance_path,
                    baseline_provenance_path,
                    *runtime_paths,
                    skill_dir / "invocation.json",
                )
            ):
                return {}, [
                    f"missing paired grading/provenance artifacts for "
                    f"{plugin}/{skill} {mode} eval-{index}"
                ]
            try:
                skill_grade = checked_grade(read_json(skill_grade_path), case["expectations"])
                baseline_grade = checked_grade(read_json(baseline_grade_path), case["expectations"])
            except ValueError as exc:
                return {}, [f"{plugin}/{skill} {mode} eval-{index}: {exc}"]
            runtimes = [read_json(path) for path in runtime_paths]
            required_runtime = {"schema_version", "claude_version", "eval_model",
                                "eval_effort", "judge_model", "allowed_tools",
                                "available_tools", "harness_sha256"}
            if any(not isinstance(item, dict) or set(item) != required_runtime
                   or type(item.get("schema_version")) is not int or item["schema_version"] != 1
                   or any(not isinstance(item.get(key), str) or not item[key]
                          for key in required_runtime - {"schema_version"})
                   for item in runtimes):
                return {}, ["missing or invalid paired runtime context"]
            if observed_runtime is None:
                observed_runtime = runtimes[0]
            if any(item != observed_runtime for item in runtimes):
                return {}, ["paired runtime mismatch (model, effort, judge, tools, CLI or harness)"]
            if observed_runtime["harness_sha256"] != current_harness_hash:
                return {}, ["paired artifacts do not match current harness sources"]
            if read_json(skill_dir / "invocation.json").get("verified") is not True:
                return {}, ["target skill invocation was not verified"]
            skill_provenance = read_json(skill_provenance_path)
            baseline_provenance = read_json(baseline_provenance_path)
            skill_pair = skill_provenance.get("pair_id")
            baseline_pair = baseline_provenance.get("pair_id")
            if (
                not isinstance(skill_pair, str)
                or skill_pair != baseline_pair
                or (observed_pair is not None and skill_pair != observed_pair)
            ):
                return {}, [
                    f"paired artifacts have stale or mismatched run ids for "
                    f"{plugin}/{skill} {mode} eval-{index}"
                ]
            observed_pair = skill_pair
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
            regressed = [before["expectation"] for before, after in zip(
                baseline_grade["verdicts"], skill_grade["verdicts"]
            ) if before["verdict"] == "PASS" and after["verdict"] == "FAIL"]
            rows.append(
                {
                    "index": index,
                    "id": case.get("id", index),
                    "install_mode": mode,
                    "skill_passed": skill_grade["passed"],
                    "baseline_passed": baseline_grade["passed"],
                    "lift": skill_grade["passed"] - baseline_grade["passed"],
                    "regressed_expectations": regressed,
                }
            )

    case_wins = sum(row["lift"] > 0 and not row["regressed_expectations"] for row in rows)
    case_losses = sum(bool(row["regressed_expectations"]) for row in rows)
    total_lift = sum(row["lift"] for row in rows)
    summary = {
        "plugin": plugin,
        "skill": skill,
        "pair_id": observed_pair,
        "runtime": observed_runtime,
        "install_modes": list(dict.fromkeys(row["install_mode"] for row in rows)),
        "case_wins": case_wins,
        "case_losses": case_losses,
        "total_expectation_lift": total_lift,
        "thresholds": thresholds,
        "rows": rows,
    }
    failures = []
    for mode in summary["install_modes"]:
        selected = [row for row in rows if row["install_mode"] == mode]
        wins = sum(row["lift"] > 0 and not row["regressed_expectations"] for row in selected)
        losses = sum(bool(row["regressed_expectations"]) for row in selected)
        lift = sum(row["lift"] for row in selected)
        if wins < thresholds["min_case_wins"]:
            failures.append(f"{mode}: case wins {wins} < {thresholds['min_case_wins']}")
        if losses > thresholds["max_case_losses"]:
            failures.append(f"{mode}: case losses {losses} > {thresholds['max_case_losses']}")
        if lift < thresholds["min_total_expectation_lift"]:
            failures.append(f"{mode}: total expectation lift {lift} < {thresholds['min_total_expectation_lift']}")
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
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
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
