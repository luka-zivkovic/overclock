#!/usr/bin/env python3
"""Mechanically audit repository skills before behavioral evaluation.

The audit checks loading structure, routing metadata, bundled-resource links,
progressive-disclosure size, and whether each plugin distribution has a live eval
suite. It deliberately avoids subjective prose/style grading: behavioral quality is
owned by qa/run_evals.sh and the committed eval cases. Evidence tiers belong to a
specific change and are never inferred from words in a skill body.

Usage:
  python3 tools/audit_skills.py plugins
  python3 tools/audit_skills.py plugins --json
  python3 tools/audit_skills.py plugins --out audit.md --fail-on fail
"""
from __future__ import annotations

import argparse
import atexit
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "qa"))
from eval_contract import fixture_errors, resolve_suite, validate_suite  # noqa: E402
from validate_skill import parse_frontmatter, validate as structural_validate  # noqa: E402
from trigger_battery import (  # noqa: E402
    validate_battery_install_modes,
    validate_battery_prompt_contracts,
)

SKIP_DIRS = {
    ".git", ".impeccable", ".venv", "_work", "__pycache__", "build", "dist",
    "node_modules", "venv",
}
RESOURCE_RE = re.compile(
    r"(?<![\w/])((?:references|templates|scripts|assets)/[A-Za-z0-9._/-]+)"
)
OPENAI_INTERFACE_FIELDS = ("display_name", "short_description", "default_prompt")
_FIXTURE_TEMP: tempfile.TemporaryDirectory[str] | None = None
_FIXTURE_FAILURE: str | None = None


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def discover(root: Path) -> list[Path]:
    """Find each real SKILL.md once while pruning generated/heavy directories."""
    by_real: dict[Path, Path] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if "SKILL.md" not in filenames:
            continue
        path = Path(dirpath) / "SKILL.md"
        try:
            by_real.setdefault(path.resolve(), path)
        except OSError:
            continue
    return sorted(by_real.values())


def audit_openai_metadata(
    skill_dir: Path,
    skill_name: str,
    *,
    user_invoked: bool,
) -> list[tuple[str, str]]:
    """Check Codex picker metadata and cross-harness invocation parity.

    The repository keeps this parser deliberately small and dependency-free. It
    validates only the direct `interface` and `policy` fields that Overclock
    requires, while tolerating unrelated top-level Codex metadata.
    """
    findings: list[tuple[str, str]] = []
    path = skill_dir / "agents" / "openai.yaml"
    if not path.is_file():
        return [("FAIL", "Codex metadata is missing: agents/openai.yaml")]

    values: dict[str, tuple[str, int]] = {}
    section: str | None = None
    lines = path.read_text(encoding="utf-8").splitlines()
    for lineno, raw_line in enumerate(lines, start=1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        top_level = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):\s*", raw_line)
        if top_level:
            section = top_level.group(1)
            continue
        direct_field = re.fullmatch(
            r"  ([A-Za-z_][A-Za-z0-9_-]*):(?:\s+(.*))?", raw_line
        )
        if direct_field and section in {"interface", "policy"}:
            key = f"{section}.{direct_field.group(1)}"
            if key in values:
                findings.append(("FAIL", f"{path.name}:{lineno}: duplicate {key}"))
            values[key] = ((direct_field.group(2) or "").strip(), lineno)

    decoded: dict[str, str] = {}
    for field in OPENAI_INTERFACE_FIELDS:
        key = f"interface.{field}"
        raw_value, lineno = values.get(key, ("", 0))
        if not raw_value:
            findings.append(("FAIL", f"Codex metadata is missing required field {key}"))
            continue
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            findings.append(
                ("FAIL", f"{path.name}:{lineno}: {key} must be a quoted string")
            )
            continue
        if not isinstance(value, str) or not value.strip():
            findings.append(("FAIL", f"{path.name}:{lineno}: {key} must be non-empty"))
            continue
        decoded[field] = value

    short_description = decoded.get("short_description")
    if short_description and not 25 <= len(short_description) <= 64:
        findings.append(
            (
                "FAIL",
                "interface.short_description must contain 25–64 characters "
                f"(got {len(short_description)})",
            )
        )

    default_prompt = decoded.get("default_prompt")
    invocation_name = skill_name.split(":")[-1]
    if default_prompt and f"${invocation_name}" not in default_prompt:
        findings.append(
            (
                "FAIL",
                f"interface.default_prompt must mention ${invocation_name}",
            )
        )

    policy_raw, policy_line = values.get("policy.allow_implicit_invocation", ("", 0))
    policy: bool | None = None
    if policy_raw:
        if policy_raw == "true":
            policy = True
        elif policy_raw == "false":
            policy = False
        else:
            findings.append(
                (
                    "FAIL",
                    f"{path.name}:{policy_line}: policy.allow_implicit_invocation "
                    "must be true or false",
                )
            )

    if user_invoked and policy is not False:
        findings.append(
            (
                "FAIL",
                "user-invoked skill must set policy.allow_implicit_invocation: false",
            )
        )
    if not user_invoked and policy is False:
        findings.append(
            (
                "FAIL",
                "model-invoked skill must not disable implicit invocation in openai.yaml",
            )
        )

    return findings


def distribution_for(skill_md: Path) -> tuple[str, str]:
    """Return (plugin, skill) for plugins/<plugin>/skills/<skill>/SKILL.md."""
    try:
        rel = skill_md.resolve().relative_to(REPO)
    except ValueError:
        return "(external)", skill_md.parent.name
    parts = rel.parts
    if len(parts) >= 5 and parts[0] == "plugins" and parts[2] == "skills":
        return parts[1], parts[3]
    return "(standalone)", skill_md.parent.name


def resolve_eval(path: Path) -> Path:
    """Resolve an eval suite through the shared, root-confined contract."""
    return resolve_suite(path, REPO / "qa" / "evals")


def materialized_fixture_root() -> Path:
    """Build the deterministic offline fixture tree once for this audit process."""
    global _FIXTURE_TEMP, _FIXTURE_FAILURE
    if _FIXTURE_TEMP is None and _FIXTURE_FAILURE is None:
        _FIXTURE_TEMP = tempfile.TemporaryDirectory(
            prefix="overclock-audit-fixtures."
        )
        atexit.register(_FIXTURE_TEMP.cleanup)
        root = Path(_FIXTURE_TEMP.name) / "fixtures"
        env = dict(os.environ)
        env["EVAL_FIXTURE_DIR"] = str(root)
        env["EVAL_FIXTURE_SKIP_REMOTE"] = "1"
        completed = subprocess.run(
            ["bash", str(REPO / "qa" / "fixtures" / "setup.sh")],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            _FIXTURE_FAILURE = (
                completed.stderr.strip()
                or completed.stdout.strip()
                or f"fixture generator exited {completed.returncode}"
            )
    if _FIXTURE_FAILURE is not None:
        raise ValueError(f"fixture generation failed: {_FIXTURE_FAILURE}")
    assert _FIXTURE_TEMP is not None
    return Path(_FIXTURE_TEMP.name) / "fixtures"


def routing_battery_for(plugin: str, skill: str) -> Path | None:
    root = REPO / "qa" / "trigger-battery"
    for path in (root / f"{plugin}-{skill}.json", root / f"{skill}.json"):
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return path
        if data.get("skill") != skill:
            continue
        declared_plugin = data.get("plugin")
        if declared_plugin is None:
            matches = list((REPO / "plugins").glob(f"*/skills/{skill}/SKILL.md"))
            if len(matches) != 1:
                continue
        elif declared_plugin != plugin:
            continue
        return path
    return None


def audit_routing_battery_contract(
    battery: dict,
    skill_dir: Path,
) -> list[tuple[str, str]]:
    """Mechanically validate one routing battery's matrix and row contracts."""
    findings: list[tuple[str, str]] = []
    findings.extend(
        ("FAIL", f"routing battery install matrix: {message}")
        for message in validate_battery_install_modes(battery, skill_dir)
    )
    findings.extend(
        ("FAIL", f"routing battery prompt contract: {message}")
        for message in validate_battery_prompt_contracts(battery)
    )
    thresholds = battery.get("thresholds")
    if not isinstance(thresholds, dict) or not thresholds:
        findings.append(
            ("FAIL", "routing battery must declare quality thresholds")
        )
    samples = battery.get("samples", 3)
    if not isinstance(samples, int) or samples < 3:
        findings.append(
            ("FAIL", "routing battery must use at least three samples")
        )
    return findings


def audit_one(skill_md: Path) -> dict:
    findings: list[tuple[str, str]] = []
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    skill_dir = skill_md.parent
    plugin, folder_name = distribution_for(skill_md)

    errors, warnings = structural_validate(skill_dir, max_body_lines=500, max_chars=30000)
    findings.extend(("FAIL", f"structural: {message}") for message in errors)
    findings.extend(("WARN", f"structural: {message}") for message in warnings)

    name, description, body, frontmatter = folder_name, "", text, {}
    try:
        frontmatter, body = parse_frontmatter(text)
        name = frontmatter.get("name", folder_name)
        description = frontmatter.get("description", "")
    except ValueError:
        pass

    user_invoked = frontmatter.get("disable-model-invocation", "").lower() == "true"
    findings.extend(
        audit_openai_metadata(skill_dir, name, user_invoked=user_invoked)
    )

    if description:
        if not re.search(r"\b(use when|when |before |after |for )\b", description, re.I):
            findings.append(("WARN", "routing description lacks a concrete positive trigger"))
        if not re.search(r"\b(do not|don't|never|stay silent|out of scope)\b", description, re.I):
            findings.append(("WARN", "routing description lacks an explicit anti-trigger"))

    if frontmatter.get("context") == "fork":
        agent = frontmatter.get("agent", "general-purpose")
        builtins = {"Explore", "Plan", "general-purpose"}
        if agent not in builtins and plugin not in {"(external)", "(standalone)"}:
            parts = agent.split(":")
            if parts and parts[0] == plugin:
                parts = parts[1:]
            agent_path = REPO / "plugins" / plugin / "agents" / Path(*parts).with_suffix(".md")
            if not agent_path.is_file():
                findings.append(("FAIL", f"forked skill agent is missing: {agent_path.relative_to(REPO)}"))

    tokens = estimate_tokens(body)
    if tokens > 4000:
        findings.append(("WARN", f"~{tokens} body tokens; split non-core detail into resources"))

    referenced = sorted({m.rstrip(".,);:`\"") for m in RESOURCE_RE.findall(body)})
    for relative in referenced:
        if not (skill_dir / relative).is_file():
            findings.append(("FAIL", f"referenced resource is missing: {relative}"))

    eval_path = REPO / "qa" / "evals" / plugin / f"{folder_name}.evals.json"
    if eval_path.is_file():
        try:
            resolved_eval = resolve_eval(eval_path)
            schema_errors = validate_suite(eval_path, REPO / "qa" / "evals")
            findings.extend(("FAIL", message) for message in schema_errors)
            resolved_data = json.loads(resolved_eval.read_text(encoding="utf-8"))
            if resolved_data.get("skill_name") != folder_name:
                findings.append(
                    (
                        "FAIL",
                        "eval skill_name "
                        f"{resolved_data.get('skill_name')!r} does not match "
                        f"distribution {folder_name!r}",
                    )
                )
            if not user_invoked and not isinstance(
                resolved_data.get("value_gate"), dict
            ):
                findings.append(
                    (
                        "FAIL",
                        "model-invoked skill eval suite must declare a paired "
                        "no-skill value_gate",
                    )
                )
            generated_root = materialized_fixture_root()
            findings.extend(
                ("FAIL", message)
                for message in fixture_errors(
                    generated_root, eval_path, REPO / "qa" / "evals"
                )
            )
            eval_status = str(eval_path.relative_to(REPO))
            if resolved_eval != eval_path.resolve():
                eval_status += f" -> {resolved_eval.relative_to(REPO)}"
        except ValueError as exc:
            eval_status = "invalid"
            findings.append(("FAIL", str(exc)))
    else:
        alternates = sorted((REPO / "qa" / "evals").glob(f"*/{folder_name}.evals.json"))
        if alternates:
            eval_status = f"shared via {alternates[0].relative_to(REPO)}"
            findings.append(("WARN", "this plugin distribution is not exercised directly by its own eval suite"))
        else:
            eval_status = "missing"
            findings.append(("WARN", "no live eval suite found for this skill"))

    if not user_invoked and plugin not in {"(external)", "(standalone)"}:
        battery_path = routing_battery_for(plugin, folder_name)
        if battery_path is None:
            findings.append(("FAIL", "model-invoked skill has no routing battery"))
        else:
            try:
                battery = json.loads(battery_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                findings.append(
                    ("FAIL", f"invalid routing battery JSON: {exc}")
                )
            else:
                findings.extend(
                    audit_routing_battery_contract(battery, skill_dir)
                )

    grade = (
        "FAIL" if any(level == "FAIL" for level, _ in findings)
        else "WARN" if any(level == "WARN" for level, _ in findings)
        else "PASS"
    )
    return {
        "name": name,
        "plugin": plugin,
        "path": str(skill_md),
        "grade": grade,
        "tokens": tokens,
        "eval": eval_status,
        "resources": referenced,
        "findings": [
            {"severity": severity, "message": message}
            for severity, message in findings
        ],
    }


def render_markdown(results: list[dict], root: Path) -> str:
    lines = [f"# Skill audit — `{root}`", ""]
    if not results:
        return "\n".join(lines + ["No `SKILL.md` files found."])

    counts = {grade: sum(r["grade"] == grade for r in results) for grade in ("PASS", "WARN", "FAIL")}
    lines.append(
        f"{len(results)} distribution(s): {counts['PASS']} PASS, "
        f"{counts['WARN']} WARN, {counts['FAIL']} FAIL"
    )
    lines.extend([
        "",
        "| Plugin | Skill | Grade | ~Tokens | Eval |",
        "|---|---|---:|---:|---|",
    ])
    for result in results:
        lines.append(
            f"| {result['plugin']} | {result['name']} | {result['grade']} | "
            f"{result['tokens']} | {result['eval']} |"
        )

    for result in results:
        if not result["findings"]:
            continue
        lines.extend(["", f"## {result['plugin']} / {result['name']}", ""])
        for finding in result["findings"]:
            lines.append(f"- **{finding['severity']}** {finding['message']}")

    lines.extend([
        "",
        "This report covers mechanical readiness only and does not assign a change-level "
        "evidence tier. Use the committed live evals and a manual trigger/safety review for "
        "behavioral conclusions.",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, nargs="?", default=Path("plugins"))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--fail-on", choices=["none", "warn", "fail"], default="none")
    args = parser.parse_args()

    results = [audit_one(path) for path in discover(args.root)]
    report = json.dumps(results, indent=2) if args.json else render_markdown(results, args.root)
    print(report)
    if args.out:
        args.out.write_text(report + "\n", encoding="utf-8")
        print(f"\nWROTE: {args.out}", file=sys.stderr)

    if args.fail_on == "warn" and any(r["grade"] in {"WARN", "FAIL"} for r in results):
        return 1
    if args.fail_on == "fail" and any(r["grade"] == "FAIL" for r in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
