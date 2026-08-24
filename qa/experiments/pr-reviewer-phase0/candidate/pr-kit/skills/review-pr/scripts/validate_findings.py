#!/usr/bin/env python3
"""Validate changed-line evidence and normalize PR Kit findings."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


PRIORITIES = ("P0", "P1", "P2")
CONFIDENCES = ("high", "medium")
COVERAGE_FIELDS = (
    "activated_lenses", "inspected_surfaces", "blind_spots", "testing_gaps",
)
ALLOWED_LENSES = {
    "api-contract", "compatibility", "concurrency", "correctness", "data-integrity",
    "failure-handling", "maintainability", "migration", "observability",
    "regression-coverage", "repository-profile", "security",
    "silent-pass-verification",
}
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def resolve_commit(root: Path, ref: str) -> str:
    result = git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    value = result.stdout.strip() if result.returncode == 0 else ""
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError(f"invalid commit endpoint: {ref}")
    return value


def unique_merge_base(root: Path, base: str, head: str) -> str:
    result = git(root, "merge-base", "--all", base, head)
    values = [line for line in result.stdout.splitlines() if line]
    if result.returncode != 0 or len(values) != 1:
        raise ValueError("merge base unavailable or ambiguous")
    return values[0]


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def safe_path(value: Any) -> str | None:
    if not nonempty(value):
        return None
    if any(ord(character) < 32 for character in value):
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return None
    return path.as_posix()


def changed_ranges(root: Path, merge_base: str, head: str, path: str) -> dict[str, list[range]]:
    result = git(
        root, "diff", "--unified=0", "--no-color", "--no-ext-diff", "--no-renames",
        merge_base, head, "--", path,
    )
    if result.returncode != 0:
        raise ValueError(f"git diff failed for {path}")
    ranges = {"LEFT": [], "RIGHT": []}
    for line in result.stdout.splitlines():
        match = HUNK_RE.match(line)
        if not match:
            continue
        old_start, old_count, new_start, new_count = match.groups()
        old_length = int(old_count) if old_count is not None else 1
        new_length = int(new_count) if new_count is not None else 1
        if old_length:
            ranges["LEFT"].append(range(int(old_start), int(old_start) + old_length))
        if new_length:
            ranges["RIGHT"].append(range(int(new_start), int(new_start) + new_length))
    return ranges


def source_line(root: Path, ref: str, path: str, line: int) -> str:
    result = git(root, "show", f"{ref}:{path}")
    if result.returncode != 0:
        raise ValueError(f"cannot read {path} at {ref}")
    lines = result.stdout.splitlines()
    if line > len(lines):
        raise ValueError(f"line {line} is outside {path} at {ref}")
    return lines[line - 1]


def validate_string_list(value: Any, field: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or any(not nonempty(item) for item in value):
        errors.append(f"{field} must be a list of non-empty strings")
        return []
    return [item.strip() for item in value]


def validate_payload(
    payload: Any, root: Path, base_ref: str, head_ref: str,
) -> tuple[dict[str, object] | None, list[str]]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return None, ["payload must be an object"]
    extra_top = sorted(set(payload) - {"findings", "coverage"})
    if extra_top:
        errors.append(f"payload has unknown fields: {', '.join(extra_top)}")
    findings = payload.get("findings")
    coverage = payload.get("coverage")
    if not isinstance(findings, list):
        errors.append("findings must be an array")
        findings = []
    if not isinstance(coverage, dict):
        errors.append("coverage must be an object")
        coverage = {}

    root = root.resolve(strict=True)
    base = resolve_commit(root, base_ref)
    head = resolve_commit(root, head_ref)
    merge_base = unique_merge_base(root, base, head)
    range_cache: dict[str, dict[str, list[range]]] = {}
    normalized: list[dict[str, object]] = []

    required = {
        "priority", "title", "file", "line", "side", "changed_line",
        "failure_path", "impact", "evidence", "introduced_by_diff",
        "confidence", "suggested_comment",
    }
    for index, raw in enumerate(findings):
        prefix = f"findings[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = sorted(required - raw.keys())
        if missing:
            errors.append(f"{prefix} missing fields: {', '.join(missing)}")
            continue
        extra = sorted(set(raw) - required)
        if extra:
            errors.append(f"{prefix} has unknown fields: {', '.join(extra)}")
        priority = raw.get("priority")
        confidence = raw.get("confidence")
        side = raw.get("side")
        path = safe_path(raw.get("file"))
        line = raw.get("line")
        if priority not in PRIORITIES:
            errors.append(f"{prefix}.priority must be P0, P1, or P2")
        if confidence not in CONFIDENCES:
            errors.append(f"{prefix}.confidence must be high or medium")
        if side not in {"LEFT", "RIGHT"}:
            errors.append(f"{prefix}.side must be LEFT or RIGHT")
        if path is None:
            errors.append(f"{prefix}.file must be a safe repository-relative path")
        if type(line) is not int or line <= 0:
            errors.append(f"{prefix}.line must be a positive integer")
        for field in ("title", "changed_line", "failure_path", "impact", "suggested_comment"):
            if not nonempty(raw.get(field)):
                errors.append(f"{prefix}.{field} must be a non-empty string")
        evidence = validate_string_list(raw.get("evidence"), f"{prefix}.evidence", errors)
        if not evidence:
            errors.append(f"{prefix}.evidence must contain at least one item")
        if raw.get("introduced_by_diff") is not True:
            errors.append(f"{prefix}.introduced_by_diff must be true")
        if path is None or type(line) is not int or line <= 0 or side not in {"LEFT", "RIGHT"}:
            continue
        try:
            ranges = range_cache.setdefault(path, changed_ranges(root, merge_base, head, path))
            if not any(line in item for item in ranges[side]):
                errors.append(f"{prefix} is not anchored to a changed {side} line")
                continue
            ref = merge_base if side == "LEFT" else head
            actual = source_line(root, ref, path, line)
            if raw["changed_line"].strip() != actual.strip():
                errors.append(f"{prefix}.changed_line does not match {path}:{line} at {side}")
                continue
        except ValueError as exc:
            errors.append(f"{prefix}: {exc}")
            continue
        normalized.append({
            "priority": priority,
            "title": raw["title"].strip(),
            "file": path,
            "line": line,
            "side": side,
            "changed_line": raw["changed_line"].strip(),
            "failure_path": raw["failure_path"].strip(),
            "impact": raw["impact"].strip(),
            "evidence": evidence,
            "introduced_by_diff": True,
            "confidence": confidence,
            "suggested_comment": raw["suggested_comment"].strip(),
        })

    normalized_coverage: dict[str, list[str]] = {}
    extra_coverage = sorted(set(coverage) - set(COVERAGE_FIELDS))
    if extra_coverage:
        errors.append(f"coverage has unknown fields: {', '.join(extra_coverage)}")
    for field in COVERAGE_FIELDS:
        normalized_coverage[field] = validate_string_list(
            coverage.get(field), f"coverage.{field}", errors
        )
        if field in {"activated_lenses", "inspected_surfaces"} and not normalized_coverage[field]:
            errors.append(f"coverage.{field} must contain at least one item")
    invalid_lenses = sorted(set(normalized_coverage.get("activated_lenses", [])) - ALLOWED_LENSES)
    if invalid_lenses:
        errors.append(f"coverage.activated_lenses contains unknown values: {', '.join(invalid_lenses)}")

    if errors:
        return None, errors

    deduplicated: dict[tuple[str, int, str, str], dict[str, object]] = {}
    for finding in normalized:
        key = (
            str(finding["file"]).lower(), int(finding["line"]), str(finding["side"]),
            " ".join(str(finding["title"]).lower().split()),
        )
        deduplicated.setdefault(key, finding)
    ordered = sorted(
        deduplicated.values(),
        key=lambda item: (
            PRIORITIES.index(str(item["priority"])),
            CONFIDENCES.index(str(item["confidence"])),
            str(item["file"]).lower(), int(item["line"]), str(item["title"]).lower(),
        ),
    )
    for number, finding in enumerate(ordered, 1):
        finding["number"] = number
    return {
        "status": "valid",
        "base": base,
        "head": head,
        "merge_base": merge_base,
        "findings": ordered,
        "coverage": normalized_coverage,
        "duplicates_removed": len(normalized) - len(ordered),
    }, []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument(
        "--payload-json",
        help="candidate JSON supplied as one argument; stdin remains available for compatibility",
    )
    args = parser.parse_args()
    try:
        payload = (
            json.loads(args.payload_json)
            if args.payload_json is not None
            else json.load(sys.stdin)
        )
        result, errors = validate_payload(payload, args.repo, args.base, args.head)
    except (json.JSONDecodeError, OSError, UnicodeError, ValueError) as exc:
        result, errors = None, [str(exc)]
    if errors:
        print(json.dumps({"status": "invalid", "errors": errors}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
