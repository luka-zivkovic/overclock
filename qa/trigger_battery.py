#!/usr/bin/env python3
"""Measure skill routing precision against should/should-not-trigger prompts.

Each prompt runs in a fresh temporary project with one skill installed. Skills that
write a deterministic contract file can use a contract-file detector; other skills
are detected from the Claude Code `Skill` tool call in stream-json output. CLI errors
abort the run instead of being misclassified as "did not trigger".

Usage:
  qa/trigger_battery.py qa/trigger-battery/lessons-learned.json
  qa/trigger_battery.py qa/trigger-battery/natural-writing.json --model MODEL

Results are written under qa/_work/trigger-battery/ and are gitignored.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ALLOWED = "Skill,Agent,Read,Glob,Grep,Bash(ls*),Bash(cat*),Bash(mkdir*),Write,Edit"

sys.path.insert(0, str(REPO / "tools"))
from validate_skill import parse_frontmatter  # noqa: E402


def locate_skill(battery: dict) -> Path:
    skill = battery["skill"]
    plugin = battery.get("plugin")
    if plugin:
        path = REPO / "plugins" / plugin / "skills" / skill
        if not (path / "SKILL.md").is_file():
            raise ValueError(f"skill not found: {path}")
        return path

    matches = sorted((REPO / "plugins").glob(f"*/skills/{skill}"))
    matches = [path for path in matches if (path / "SKILL.md").is_file()]
    if not matches:
        raise ValueError(f"no plugin contains skill {skill!r}")
    if len(matches) > 1:
        choices = ", ".join(str(path.relative_to(REPO)) for path in matches)
        raise ValueError(f"skill {skill!r} is distributed by multiple plugins; set 'plugin': {choices}")
    return matches[0]


def current_description(skill_dir: Path) -> str:
    frontmatter, _ = parse_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    description = frontmatter.get("description", "")
    if not description:
        raise ValueError(f"{skill_dir}/SKILL.md has no description")
    return description


def swap_description(text: str, description: str) -> str:
    """Replace a one-line description with a JSON-quoted YAML scalar."""
    quoted = json.dumps(description, ensure_ascii=False)
    updated, count = re.subn(r"(?m)^description:.*$", f"description: {quoted}", text, count=1)
    if count != 1:
        raise ValueError("SKILL.md needs one top-level, one-line description field")
    return updated


def selected_skill(stdout: str, skill: str) -> bool:
    """Return whether stream-json contains a Skill tool call selecting `skill`."""
    for raw in stdout.splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "assistant":
            continue
        for block in event.get("message", {}).get("content", []):
            if block.get("type") != "tool_use" or block.get("name") != "Skill":
                continue
            tool_input = block.get("input", {})
            selected = tool_input.get("skill") or tool_input.get("name") or ""
            if str(selected).split(":")[-1] == skill:
                return True
    return False


def result_metadata(stdout: str) -> dict:
    """Extract cost/latency metadata from the final stream-json result event."""
    metadata = {"duration_ms": 0, "total_cost_usd": 0.0, "num_turns": 0}
    for raw in stdout.splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "result":
            continue
        for key in metadata:
            if event.get(key) is not None:
                metadata[key] = event[key]
    return metadata


def run_prompt(skill_dir: Path, skill: str, description: str, prompt: str, model: str,
               detector: dict) -> dict:
    with tempfile.TemporaryDirectory() as temp:
        cwd = Path(temp)
        destination = cwd / ".claude" / "skills" / skill
        shutil.copytree(skill_dir, destination)
        plugin_agents = skill_dir.parent.parent / "agents"
        if plugin_agents.is_dir():
            shutil.copytree(plugin_agents, cwd / ".claude" / "agents")
        skill_md = destination / "SKILL.md"
        skill_md.write_text(
            swap_description(skill_md.read_text(encoding="utf-8"), description),
            encoding="utf-8",
        )

        completed = subprocess.run(
            [
                "claude", "-p", prompt, "--model", model,
                "--output-format", "stream-json", "--verbose",
                "--no-session-persistence", "--allowedTools", ALLOWED,
            ],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            error = completed.stderr.strip() or completed.stdout[-500:].strip()
            raise RuntimeError(f"claude exited {completed.returncode}: {error}")

        kind = detector.get("type", "skill_tool")
        if kind == "skill_tool":
            fired = selected_skill(completed.stdout, skill)
        elif kind == "contract_file":
            relative = detector.get("path")
            if not relative:
                raise ValueError("contract_file detector requires a path")
            fired = (cwd / relative).is_file()
        elif kind == "skill_or_contract":
            relative = detector.get("path")
            if not relative:
                raise ValueError("skill_or_contract detector requires a path")
            fired = selected_skill(completed.stdout, skill) or (cwd / relative).is_file()
        else:
            raise ValueError(f"unknown detector type: {kind}")
        return {"fired": fired, **result_metadata(completed.stdout)}


def score(skill_dir: Path, skill: str, description: str, battery: dict, model: str) -> dict:
    detector = battery.get("detector", {"type": "skill_tool"})
    rows = []
    for kind, prompts in (("should", battery["should_trigger"]),
                          ("should_not", battery["should_not"])):
        for prompt in prompts:
            result = run_prompt(skill_dir, skill, description, prompt, model, detector)
            rows.append({"kind": kind, "prompt": prompt, **result})
    correct = sum(1 for row in rows if (row["kind"] == "should") == row["fired"])
    return {
        "correct": correct,
        "total": len(rows),
        "duration_ms": sum(row["duration_ms"] for row in rows),
        "total_cost_usd": sum(row["total_cost_usd"] for row in rows),
        "num_turns": sum(row["num_turns"] for row in rows),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("battery", type=Path)
    parser.add_argument("--model", default="claude-sonnet-4-6")
    args = parser.parse_args()

    battery = json.loads(args.battery.read_text(encoding="utf-8"))
    skill = battery["skill"]
    skill_dir = locate_skill(battery)
    variants = battery.get("variants") or {"current": current_description(skill_dir)}
    output_dir = REPO / "qa" / "_work" / "trigger-battery"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Trigger battery for {skill} (model={args.model})")
    print(f"Source: {skill_dir.relative_to(REPO)}")
    print(
        f"{len(battery['should_trigger'])} should-trigger + "
        f"{len(battery['should_not'])} should-not x {len(variants)} variant(s)\n"
    )

    scores = {}
    for label, description in variants.items():
        print(f"-- scoring variant: {label}")
        result = score(skill_dir, skill, description, battery, args.model)
        scores[label] = result
        for row in result["rows"]:
            kind, prompt, fired = row["kind"], row["prompt"], row["fired"]
            passed = (kind == "should") == fired
            print(
                f"     [{'OK ' if passed else 'MISS'}] "
                f"want {'fire' if kind == 'should' else 'silent':6} "
                f"got {'fired' if fired else 'silent':6} | {prompt[:58]} "
                f"| {row['duration_ms']/1000:.1f}s ${row['total_cost_usd']:.4f}"
            )
        print(
            f"   => {label}: {result['correct']}/{result['total']} | "
            f"{result['duration_ms']/1000:.1f}s ${result['total_cost_usd']:.4f}\n"
        )

    artifact = {
        "skill": skill,
        "source": str(skill_dir.relative_to(REPO)),
        "model": args.model,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "scores": scores,
    }
    (output_dir / f"{skill}.results.json").write_text(
        json.dumps(artifact, indent=1) + "\n", encoding="utf-8"
    )

    ranked = sorted(scores.items(), key=lambda item: item[1]["correct"], reverse=True)
    baseline_label = "baseline" if "baseline" in scores else next(iter(variants))
    baseline = scores[baseline_label]["correct"]
    print("scoreboard:")
    for label, result in ranked:
        delta = result["correct"] - baseline
        suffix = " <- baseline" if label == baseline_label else f" ({delta:+d} vs baseline)"
        print(
            f"  {result['correct']}/{result['total']}  {label}{suffix} | "
            f"{result['duration_ms']/1000:.1f}s ${result['total_cost_usd']:.4f}"
        )

    winner, result = ranked[0]
    if winner == baseline_label or result["correct"] <= baseline:
        print(f"\nDECISION: keep {baseline_label} ({baseline}/{result['total']}).")
    else:
        print(
            f"\nDECISION: candidate {winner!r} leads "
            f"({result['correct']}/{result['total']} vs {baseline}/{result['total']}). "
            "Re-run before changing the shipped description."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
