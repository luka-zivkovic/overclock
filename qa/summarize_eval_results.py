#!/usr/bin/env python3
"""Render live-eval grades, resource metrics, and skill-vs-baseline deltas."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def render(root: Path) -> str:
    lines = ["## Live eval results"]
    grading_paths = sorted(root.glob("*/grading.json"))
    if not grading_paths:
        lines.append("(no grading artifacts)")
    for path in grading_paths:
        grade = read_json(path)
        lines.append(f"- **{path.parent.name}**: {grade['passed']}/{grade['total']}")

    lines.extend(["", "## Cost and latency"])
    metric_paths = sorted(root.glob("*/metrics.json"))
    if not metric_paths:
        lines.append("(no metric artifacts)")
    for path in metric_paths:
        metric = read_json(path)
        lines.append(
            f"- **{path.parent.name}** ({metric['variant']}): "
            f"${metric['total_cost_usd']:.4f}, {metric['duration_ms']/1000:.1f}s, "
            f"{metric['num_turns']} turns"
        )

    comparisons = []
    for baseline_dir in sorted(root.glob("*-baseline-eval-*")):
        skill_dir = root / baseline_dir.name.replace("-baseline-eval-", "-eval-", 1)
        required = [
            skill_dir / "grading.json", baseline_dir / "grading.json",
            skill_dir / "metrics.json", baseline_dir / "metrics.json",
        ]
        if not all(path.is_file() for path in required):
            continue
        skill_grade, base_grade, skill_metric, base_metric = map(read_json, required)
        comparisons.append((
            skill_dir.name,
            skill_grade["passed"], skill_grade["total"],
            base_grade["passed"], base_grade["total"],
            skill_metric["total_cost_usd"] - base_metric["total_cost_usd"],
            (skill_metric["duration_ms"] - base_metric["duration_ms"]) / 1000,
        ))

    if comparisons:
        lines.extend(["", "## Skill vs baseline"])
        for name, skill_passed, skill_total, base_passed, base_total, cost, seconds in comparisons:
            lines.append(
                f"- **{name}**: skill {skill_passed}/{skill_total}, "
                f"baseline {base_passed}/{base_total}; incremental ${cost:.4f}, {seconds:+.1f}s"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    print(render(args.results), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
