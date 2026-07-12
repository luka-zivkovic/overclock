#!/usr/bin/env python3
"""Measure skill routing precision against should/should-not-trigger prompts.

Each prompt runs in a fresh temporary project with the skill's real plugin loaded.
This exercises shipped namespaces, sibling skills, agents, hooks, and manifests. Skills
that write a deterministic contract file can use a contract-file detector; other skills
are detected from the Claude Code `Skill` tool call in stream-json output. CLI errors
abort the run instead of being misclassified as "did not trigger".

Usage:
  qa/trigger_battery.py qa/trigger-battery/lessons-learned.json
  qa/trigger_battery.py qa/trigger-battery/natural-writing.json --model MODEL
  qa/trigger_battery.py qa/trigger-battery/test-discipline.json --samples 3

Results are written under qa/_work/trigger-battery/ and are gitignored.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import selectors
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parent.parent
ALLOWED = "Skill,Agent,Read,Glob,Grep,Bash(ls*),Bash(cat*),Bash(mkdir*),Write,Edit"
DEFAULT_TIMEOUT_SECONDS = 180.0

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


def materialize_fixture(cwd: Path, battery: dict) -> None:
    """Create optional repo-owned text fixtures for routing prompts that name files."""
    files = battery.get("fixture_files", {})
    if not isinstance(files, dict) or not all(
        isinstance(name, str) and isinstance(content, str)
        for name, content in files.items()
    ):
        raise ValueError("fixture_files must map relative paths to text")
    for name, content in files.items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError(f"unsafe fixture path: {name!r}")
        destination = cwd / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    if battery.get("fixture_git"):
        env = dict(os.environ)
        env.update(
            {
                "GIT_AUTHOR_NAME": "fixture",
                "GIT_AUTHOR_EMAIL": "fixture@example.com",
                "GIT_COMMITTER_NAME": "fixture",
                "GIT_COMMITTER_EMAIL": "fixture@example.com",
            }
        )
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=cwd, env=env, check=True)
        subprocess.run(["git", "add", "-A"], cwd=cwd, env=env, check=True)
        subprocess.run(["git", "commit", "-qm", "routing fixture"], cwd=cwd, env=env, check=True)


def stop_process(process: subprocess.Popen) -> None:
    """Stop a Claude process and any children it launched."""
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=2)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if process.poll() is None:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.wait()


def run_streaming_command(command: list[str], cwd: Path, skill: str,
                          stop_on_skill: bool, timeout_seconds: float) -> dict:
    """Run one session, optionally stopping as soon as its Skill route is observable."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    assert process.stdout is not None
    output: list[str] = []
    fired = False
    stopped_early = False
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        deadline = started + timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                stop_process(process)
                tail = "".join(output)[-500:].strip()
                suffix = f"; last output: {tail}" if tail else ""
                raise RuntimeError(
                    f"claude timed out after {timeout_seconds:g}s{suffix}"
                )
            events = selector.select(timeout=min(0.25, remaining))
            if events:
                line = process.stdout.readline()
                if line:
                    output.append(line)
                    if stop_on_skill and selected_skill(line, skill):
                        fired = True
                        stopped_early = True
                        stop_process(process)
                        break
                elif process.poll() is not None:
                    break
            elif process.poll() is not None:
                remainder = process.stdout.read()
                if remainder:
                    output.append(remainder)
                break
    finally:
        selector.close()
        if process.poll() is None:
            stop_process(process)
        process.stdout.close()

    stdout = "".join(output)
    if not stopped_early and process.returncode != 0:
        error = stdout[-500:].strip()
        raise RuntimeError(f"claude exited {process.returncode}: {error}")
    elapsed_ms = round((time.monotonic() - started) * 1000)
    metadata = result_metadata(stdout)
    if not metadata["duration_ms"]:
        metadata["duration_ms"] = elapsed_ms
    return {
        "stdout": stdout,
        "fired": fired or selected_skill(stdout, skill),
        "stopped_early": stopped_early,
        **metadata,
    }


def run_prompt(skill_dir: Path, skill: str, description: str, prompt: str, model: str,
               detector: dict, battery: dict, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
               route_only: bool = True) -> dict:
    with tempfile.TemporaryDirectory() as temp:
        cwd = Path(temp)
        materialize_fixture(cwd, battery)
        source_plugin = skill_dir.parent.parent
        destination_plugin = cwd / "plugin-under-test"
        shutil.copytree(source_plugin, destination_plugin)
        destination = destination_plugin / "skills" / skill
        skill_md = destination / "SKILL.md"
        skill_md.write_text(
            swap_description(skill_md.read_text(encoding="utf-8"), description),
            encoding="utf-8",
        )

        kind = detector.get("type", "skill_tool")
        streamed = run_streaming_command(
            [
                "claude", "-p", prompt, "--model", model,
                "--output-format", "stream-json", "--verbose",
                "--no-session-persistence", "--plugin-dir", str(destination_plugin),
                "--setting-sources", "project,local", "--allowedTools", ALLOWED,
            ],
            cwd,
            skill,
            stop_on_skill=route_only and kind in {"skill_tool", "skill_or_contract"},
            timeout_seconds=timeout_seconds,
        )

        if kind == "skill_tool":
            fired = streamed["fired"]
        elif kind == "contract_file":
            relative = detector.get("path")
            if not relative:
                raise ValueError("contract_file detector requires a path")
            fired = (cwd / relative).is_file()
        elif kind == "skill_or_contract":
            relative = detector.get("path")
            if not relative:
                raise ValueError("skill_or_contract detector requires a path")
            fired = streamed["fired"] or (cwd / relative).is_file()
        else:
            raise ValueError(f"unknown detector type: {kind}")
        return {
            "fired": fired,
            "stopped_early": streamed["stopped_early"],
            "duration_ms": streamed["duration_ms"],
            "total_cost_usd": streamed["total_cost_usd"],
            "num_turns": streamed["num_turns"],
        }


def quality_metrics(rows: list[dict]) -> dict:
    """Return routing confusion counts and stable rate metrics."""
    true_positive = sum(
        1 for row in rows if row["kind"] == "should" and row["fired"]
    )
    false_negative = sum(
        1 for row in rows if row["kind"] == "should" and not row["fired"]
    )
    true_negative = sum(
        1 for row in rows if row["kind"] == "should_not" and not row["fired"]
    )
    false_positive = sum(
        1 for row in rows if row["kind"] == "should_not" and row["fired"]
    )

    def rate(numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator else 1.0

    total = len(rows)
    return {
        "true_positive": true_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
        "false_positive": false_positive,
        "accuracy": rate(true_positive + true_negative, total),
        "precision": rate(true_positive, true_positive + false_positive),
        "recall": rate(true_positive, true_positive + false_negative),
        "specificity": rate(true_negative, true_negative + false_positive),
    }


def threshold_failures(metrics: dict, thresholds: dict) -> list[str]:
    """Describe any configured minimum quality rates the result misses."""
    allowed = {"accuracy", "precision", "recall", "specificity"}
    failures = []
    for name, minimum in thresholds.items():
        if name not in allowed:
            raise ValueError(f"unknown routing threshold: {name}")
        if not isinstance(minimum, (int, float)) or not 0 <= minimum <= 1:
            raise ValueError(f"threshold {name} must be a number from 0 to 1")
        actual = metrics[name]
        if actual < minimum:
            failures.append(f"{name} {actual:.1%} < {minimum:.1%}")
    return failures


def score(skill_dir: Path, skill: str, description: str, battery: dict, model: str,
          samples: int = 1, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
          route_only: bool = True, progress: Callable[[dict], None] | None = None) -> dict:
    if samples <= 0:
        raise ValueError("samples must be greater than zero")
    detector = battery.get("detector", {"type": "skill_tool"})
    rows = []
    for sample in range(1, samples + 1):
        for kind, prompts in (("should", battery["should_trigger"]),
                              ("should_not", battery["should_not"])):
            for prompt in prompts:
                result = run_prompt(
                    skill_dir, skill, description, prompt, model, detector, battery,
                    timeout_seconds=timeout_seconds, route_only=route_only,
                )
                row = {"sample": sample, "kind": kind, "prompt": prompt, **result}
                rows.append(row)
                if progress:
                    progress(row)
    correct = sum(1 for row in rows if (row["kind"] == "should") == row["fired"])
    return {
        "correct": correct,
        "total": len(rows),
        "duration_ms": sum(row["duration_ms"] for row in rows),
        "total_cost_usd": sum(row["total_cost_usd"] for row in rows),
        "num_turns": sum(row["num_turns"] for row in rows),
        "metrics": quality_metrics(rows),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("battery", type=Path)
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--samples", type=int)
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument(
        "--full-session", action="store_true",
        help="let positive cases finish instead of stopping at the observed Skill route",
    )
    for metric in ("accuracy", "precision", "recall", "specificity"):
        parser.add_argument(f"--min-{metric}", type=float)
    args = parser.parse_args()

    battery = json.loads(args.battery.read_text(encoding="utf-8"))
    samples = args.samples if args.samples is not None else battery.get("samples", 1)
    timeout_seconds = (
        args.timeout_seconds
        if args.timeout_seconds is not None
        else battery.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    )
    if samples <= 0:
        parser.error("--samples must be greater than zero")
    if timeout_seconds <= 0:
        parser.error("--timeout-seconds must be greater than zero")
    route_only = not args.full_session and battery.get("route_only", True)
    thresholds = dict(battery.get("thresholds", {}))
    for metric in ("accuracy", "precision", "recall", "specificity"):
        override = getattr(args, f"min_{metric}")
        if override is not None:
            thresholds[metric] = override
    threshold_failures(
        {name: 1.0 for name in ("accuracy", "precision", "recall", "specificity")},
        thresholds,
    )
    skill = battery["skill"]
    skill_dir = locate_skill(battery)
    variants = battery.get("variants") or {"current": current_description(skill_dir)}
    output_dir = REPO / "qa" / "_work" / "trigger-battery"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Trigger battery for {skill} (model={args.model})")
    print(f"Source: {skill_dir.relative_to(REPO)}")
    print(
        f"{len(battery['should_trigger'])} should-trigger + "
        f"{len(battery['should_not'])} should-not x {samples} sample(s) "
        f"x {len(variants)} variant(s)"
    )
    print(
        f"Mode: {'route-only' if route_only else 'full-session'} | "
        f"timeout={timeout_seconds:g}s"
    )
    if thresholds:
        print(
            "Thresholds: "
            + ", ".join(f"{name}>={value:.0%}" for name, value in thresholds.items())
        )
    print()

    scores = {}
    for label, description in variants.items():
        print(f"-- scoring variant: {label}")

        def print_progress(row: dict) -> None:
            kind, prompt, fired = row["kind"], row["prompt"], row["fired"]
            passed = (kind == "should") == fired
            early = " route-only" if row["stopped_early"] else ""
            print(
                f"     [{'OK ' if passed else 'MISS'}] "
                f"sample {row['sample']}/{samples} "
                f"want {'fire' if kind == 'should' else 'silent':6} "
                f"got {'fired' if fired else 'silent':6} | {prompt[:58]} "
                f"| {row['duration_ms']/1000:.1f}s ${row['total_cost_usd']:.4f}{early}",
                flush=True,
            )

        result = score(
            skill_dir, skill, description, battery, args.model,
            samples=samples, timeout_seconds=timeout_seconds,
            route_only=route_only, progress=print_progress,
        )
        scores[label] = result
        metrics = result["metrics"]
        print(
            f"   => {label}: {result['correct']}/{result['total']} | "
            f"precision={metrics['precision']:.1%} recall={metrics['recall']:.1%} "
            f"specificity={metrics['specificity']:.1%} | "
            f"{result['duration_ms']/1000:.1f}s ${result['total_cost_usd']:.4f}\n"
        )

    artifact = {
        "skill": skill,
        "source": str(skill_dir.relative_to(REPO)),
        "model": args.model,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "samples": samples,
        "timeout_seconds": timeout_seconds,
        "route_only": route_only,
        "thresholds": thresholds,
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

    gate_label = "current" if "current" in scores else baseline_label
    failures = threshold_failures(scores[gate_label]["metrics"], thresholds)
    if failures:
        print(f"\nGATE FAILED ({gate_label}): " + "; ".join(failures))
        return 1
    if thresholds:
        print(f"\nGATE PASSED ({gate_label}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
