#!/usr/bin/env python3
"""Shared validation for live-eval suites and their generated fixtures."""

from __future__ import annotations

import json
import re
from pathlib import Path

from eval_packaging import INSTALL_MODES, resolve_install_modes
from eval_invocation import EXPLICIT_INVOCATION


def _install_modes_error(value: object) -> str | None:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item in INSTALL_MODES for item in value)
        or len(set(value)) != len(value)
    ):
        return (
            "install_modes must be a non-empty unique list drawn from "
            + ", ".join(INSTALL_MODES)
        )
    return None


def resolve_suite(path: Path, eval_root: Path) -> Path:
    """Resolve an eval ``extends`` chain without allowing it to escape qa/evals."""
    current = path.resolve()
    boundary = eval_root.resolve()
    seen: set[Path] = set()
    while True:
        try:
            current.relative_to(boundary)
        except ValueError as exc:
            raise ValueError(f"eval extends path escapes qa/evals: {current}") from exc
        if current in seen:
            raise ValueError(f"cyclic eval extends chain at {current}")
        seen.add(current)
        try:
            data = json.loads(current.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ValueError(f"extended eval suite is missing: {current}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid eval JSON in {current}: {exc}") from exc
        parent = data.get("extends")
        if not parent:
            cases = data.get("evals")
            if not isinstance(cases, list) or not cases:
                raise ValueError(f"eval suite has no cases: {current}")
            return current
        if not isinstance(parent, str) or not parent:
            raise ValueError(f"invalid eval extends value in {current}")
        current = (current.parent / parent).resolve()


def load_suite(path: Path, eval_root: Path) -> tuple[Path, dict]:
    resolved = resolve_suite(path, eval_root)
    data = json.loads(resolved.read_text(encoding="utf-8"))
    return resolved, data


def validate_case(case: object, index: int, suite: Path) -> list[str]:
    """Return deterministic schema errors for one case."""
    prefix = f"{suite}: eval-{index}"
    if not isinstance(case, dict):
        return [f"{prefix} must be an object"]
    errors: list[str] = []
    case_id = case.get("id")
    if case_id is not None and (
        not isinstance(case_id, (str, int))
        or isinstance(case_id, bool)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", str(case_id)) is None
    ):
        errors.append(f"{prefix} id must be a safe string or integer")
    if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
        errors.append(f"{prefix} needs a non-empty prompt")
    expectations = case.get("expectations")
    if (
        not isinstance(expectations, list)
        or not expectations
        or not all(isinstance(item, str) and item.strip() for item in expectations)
    ):
        errors.append(f"{prefix} needs non-empty string expectations")
    files = case.get("files", [])
    if not isinstance(files, list):
        errors.append(f"{prefix} files must be a list")
    else:
        for file_index, item in enumerate(files):
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                errors.append(f"{prefix} files[{file_index}] needs a string name")
                continue
            relative = Path(item["name"])
            if relative.is_absolute() or not relative.parts or ".." in relative.parts:
                errors.append(f"{prefix} has unsafe fixture file {item['name']!r}")
    plugins = case.get("plugins")
    if plugins is not None and (
        not isinstance(plugins, list)
        or not plugins
        or not all(
            isinstance(plugin, str)
            and re.fullmatch(r"[a-z0-9][a-z0-9-]*", plugin) is not None
            for plugin in plugins
        )
    ):
        errors.append(f"{prefix} plugins must be non-empty safe plugin names")
    if "install_modes" in case:
        detail = _install_modes_error(case["install_modes"])
        if detail is not None:
            errors.append(f"{prefix} {detail}")
    if "setup_with_plugins" in case and not isinstance(
        case["setup_with_plugins"], bool
    ):
        errors.append(f"{prefix} setup_with_plugins must be boolean")
    setup_turns = case.get("setup_turns", [])
    if (
        not isinstance(setup_turns, list)
        or not all(isinstance(turn, str) and turn.strip() for turn in setup_turns)
    ):
        errors.append(f"{prefix} setup_turns must be non-empty strings")
    if case.get("setup_with_plugins") and not setup_turns:
        errors.append(f"{prefix} setup_with_plugins requires setup_turns")
    return errors


def validate_suite(path: Path, eval_root: Path) -> list[str]:
    resolved, data = load_suite(path, eval_root)
    raw_data = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    skill_name = data.get("skill_name")
    if (
        not isinstance(skill_name, str)
        or re.fullmatch(r"[a-z0-9][a-z0-9-]*", skill_name) is None
    ):
        errors.append(f"{resolved}: skill_name must be a safe non-empty name")
    if data.get("invocation") != EXPLICIT_INVOCATION:
        errors.append(
            f"{resolved}: behavioral suites must set invocation to "
            f"{EXPLICIT_INVOCATION!r}"
        )
    if raw_data.get("invocation") != EXPLICIT_INVOCATION:
        errors.append(
            f"{path}: every distribution suite must explicitly declare invocation "
            f"as {EXPLICIT_INVOCATION!r}"
        )
    if "install_modes" in data:
        detail = _install_modes_error(data["install_modes"])
        if detail is not None:
            errors.append(f"{resolved}: {detail}")
    declared_matrix = raw_data.get("install_modes")
    detail = _install_modes_error(declared_matrix)
    if detail is not None:
        errors.append(
            f"{path}: every distribution suite must explicitly declare {detail}"
        )
    elif "skill" not in declared_matrix:
        errors.append(
            f"{path}: every distribution suite install_modes must contain skill"
        )
    if raw_data.get("extends") and declared_matrix != data.get("install_modes"):
        errors.append(
            f"{path}: extending distributions must repeat the resolved suite's "
            "install_modes exactly"
        )
    value_gate = data.get("value_gate")
    if value_gate is not None:
        allowed = {
            "min_case_wins",
            "max_case_losses",
            "min_total_expectation_lift",
        }
        if not isinstance(value_gate, dict):
            errors.append(f"{resolved}: value_gate must be an object")
        else:
            unknown = set(value_gate) - allowed
            if unknown:
                errors.append(
                    f"{resolved}: unknown value_gate fields: {sorted(unknown)}"
                )
            for key, value in value_gate.items():
                if not isinstance(value, int) or value < 0:
                    errors.append(
                        f"{resolved}: value_gate.{key} must be a non-negative integer"
                    )
    effective_mode_union: set[str] = set()
    for index, case in enumerate(data["evals"]):
        errors.extend(validate_case(case, index, resolved))
        if not isinstance(case, dict) or not isinstance(skill_name, str):
            continue
        plugins = case.get("plugins")
        has_external_plugins = (
            isinstance(plugins, list)
            and any(plugin != path.parent.name for plugin in plugins)
        )
        try:
            modes = resolve_install_modes(
                case,
                path.parent.name,
                suite=data,
            )
        except ValueError:
            continue
        effective_mode_union.update(modes)
        if has_external_plugins and "stack" not in modes:
            errors.append(
                f"{resolved}: eval-{index} declares external plugins but its "
                "install_modes omit stack"
            )
    if "skill" not in effective_mode_union:
        errors.append(
            f"{resolved}: suite has no case that actually runs in skill mode"
        )

    # Multi-skill and hook-bearing packages must also exercise their full plugin.
    # A case override cannot substitute for a suite-wide standalone matrix.
    distribution = eval_root.parent.parent / "plugins" / path.parent.name
    skills_root = distribution / "skills"
    if skills_root.is_dir():
        shipped_skills = [
            child
            for child in skills_root.iterdir()
            if child.is_dir() and (child / "SKILL.md").is_file()
        ]
        has_hooks = (distribution / "hooks").exists()
        if len(shipped_skills) > 1 or has_hooks:
            if not isinstance(declared_matrix, list) or "plugin" not in declared_matrix:
                errors.append(
                    f"{path}: multi-skill or hook-bearing plugin "
                    f"{path.parent.name} requires suite install_modes containing "
                    "plugin"
                )
            if "plugin" not in effective_mode_union:
                errors.append(
                    f"{resolved}: multi-skill or hook-bearing suite has no case "
                    "that actually runs in plugin mode"
                )
    return errors


def fixture_errors(
    fixture_root: Path,
    suite_path: Path,
    eval_root: Path,
) -> list[str]:
    """Require a work directory and every declared source artifact for each case."""
    resolved, data = load_suite(suite_path, eval_root)
    skill = data.get("skill_name")
    if not isinstance(skill, str) or not skill:
        return [f"{resolved}: missing skill_name"]
    errors: list[str] = []
    for index, case in enumerate(data["evals"]):
        work = fixture_root / skill / f"eval-{index}"
        if not work.is_dir():
            errors.append(f"{skill}/eval-{index}: fixture directory is missing")
            continue
        if not isinstance(case, dict):
            continue
        for item in case.get("files", []):
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            target = work / item["name"]
            if not target.exists() and not target.is_symlink():
                errors.append(
                    f"{skill}/eval-{index}: declared fixture file is missing: "
                    f"{item['name']}"
                )
    return errors


def all_suite_paths(eval_root: Path) -> list[Path]:
    return sorted(eval_root.glob("*/*.evals.json"))
