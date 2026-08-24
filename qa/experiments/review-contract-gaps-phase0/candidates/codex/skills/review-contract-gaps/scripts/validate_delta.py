#!/usr/bin/env python3
"""Validate a contract-gap review delta against immutable Git endpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ROW_RE = re.compile(r"^C[1-9][0-9]*$")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
DISPOSITIONS = ("confirmed-gap", "handled", "covered", "unreachable", "unresolved")
PRIORITIES = ("P0", "P1", "P2")
CONFIDENCES = ("high", "medium")
MAX_REVIEW_BYTES = 4 * 1024 * 1024


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def resolve_exact_commit(root: Path, value: str, label: str) -> str:
    if not SHA_RE.fullmatch(value):
        raise ValueError(f"{label} must be an exact 40-character lowercase SHA")
    result = git(root, "rev-parse", "--verify", "--quiet", f"{value}^{{commit}}")
    resolved = result.stdout.strip() if result.returncode == 0 else ""
    if resolved != value:
        raise ValueError(f"{label} commit is unavailable: {value}")
    return resolved


def unique_merge_base(root: Path, base: str, head: str) -> str:
    result = git(root, "merge-base", "--all", base, head)
    values = [line for line in result.stdout.splitlines() if line]
    if result.returncode != 0 or len(values) != 1:
        raise ValueError("base/head merge base is unavailable or ambiguous")
    return values[0]


def review_digest(path: Path) -> dict[str, object]:
    resolved = path.expanduser().resolve(strict=True)
    metadata = resolved.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError("review must be a regular non-symlink file")
    if metadata.st_size > MAX_REVIEW_BYTES:
        raise ValueError("review exceeds the 4 MiB limit")
    raw = resolved.read_bytes()
    text = raw.decode("utf-8")
    headings = [
        line.strip()
        for line in text.splitlines()
        if re.match(r"^#{1,6}\s+(?:\[P[0-2]\]|P[0-2]\b)", line.strip())
    ]
    return {
        "review": str(resolved),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "actionable_heading_count": len(headings),
        "actionable_headings": headings,
    }


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def safe_path(value: Any) -> str | None:
    if not nonempty(value) or any(ord(character) < 32 for character in value):
        return None
    path = PurePosixPath(str(value))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return None
    return path.as_posix()


def exact_keys(
    value: Any,
    field: str,
    required: set[str],
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return None
    missing = sorted(required - set(value))
    extra = sorted(set(value) - required)
    if missing:
        errors.append(f"{field} missing fields: {', '.join(missing)}")
    if extra:
        errors.append(f"{field} has unknown fields: {', '.join(extra)}")
    return value


def source_line(root: Path, ref: str, path: str, line: int) -> str:
    result = git(root, "show", f"{ref}:{path}")
    if result.returncode != 0:
        raise ValueError(f"cannot read {path} at {ref}")
    lines = result.stdout.splitlines()
    if line > len(lines):
        raise ValueError(f"line {line} is outside {path} at {ref}")
    return lines[line - 1]


def changed_ranges(
    root: Path,
    merge_base: str,
    head: str,
    path: str,
) -> dict[str, list[range]]:
    result = git(
        root,
        "diff",
        "--unified=0",
        "--no-color",
        "--no-ext-diff",
        "--no-renames",
        merge_base,
        head,
        "--",
        path,
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


def validate_anchor(
    raw: Any,
    field: str,
    root: Path,
    refs: set[str],
    errors: list[str],
    *,
    require_statement: bool = False,
) -> dict[str, Any] | None:
    required = {"path", "line", "ref", "line_text", "role"}
    if require_statement:
        required.add("statement")
    value = exact_keys(raw, field, required, errors)
    if value is None:
        return None
    path = safe_path(value.get("path"))
    line = value.get("line")
    ref = value.get("ref")
    if path is None:
        errors.append(f"{field}.path must be a safe repository-relative path")
    if type(line) is not int or line <= 0:
        errors.append(f"{field}.line must be a positive integer")
    if ref not in refs:
        errors.append(f"{field}.ref must equal an exact allowed endpoint")
    for name in ("role", "statement") if require_statement else ("role",):
        if not nonempty(value.get(name)):
            errors.append(f"{field}.{name} must be a non-empty string")
    if not isinstance(value.get("line_text"), str):
        errors.append(f"{field}.line_text must be a string")
    if path is not None and type(line) is int and line > 0 and ref in refs:
        try:
            actual = source_line(root, str(ref), path, line)
            if str(value.get("line_text", "")).strip() != actual.strip():
                errors.append(f"{field}.line_text does not match {path}:{line} at {ref}")
        except ValueError as exc:
            errors.append(f"{field}: {exc}")
    return value


def validate_changed_anchor(
    raw: Any,
    field: str,
    root: Path,
    merge_base: str,
    head: str,
    range_cache: dict[str, dict[str, list[range]]],
    errors: list[str],
) -> dict[str, Any] | None:
    required = {"path", "line", "ref", "line_text", "role", "side"}
    value = exact_keys(raw, field, required, errors)
    if value is None:
        return None
    side = value.get("side")
    expected_ref = merge_base if side == "LEFT" else head if side == "RIGHT" else None
    if expected_ref is None:
        errors.append(f"{field}.side must be LEFT or RIGHT")
    anchor = {key: item for key, item in value.items() if key != "side"}
    validate_anchor(anchor, field, root, {expected_ref} if expected_ref else set(), errors)
    path = safe_path(value.get("path"))
    line = value.get("line")
    if path is not None and type(line) is int and line > 0 and side in {"LEFT", "RIGHT"}:
        try:
            ranges = range_cache.setdefault(
                path,
                changed_ranges(root, merge_base, head, path),
            )
            if not any(line in changed_range for changed_range in ranges[side]):
                errors.append(f"{field} is not anchored to a changed {side} line")
        except ValueError as exc:
            errors.append(f"{field}: {exc}")
    return value


def validate_string_list(
    value: Any,
    field: str,
    errors: list[str],
    *,
    minimum: int = 0,
) -> list[str]:
    if not isinstance(value, list) or any(not nonempty(item) for item in value):
        errors.append(f"{field} must be an array of non-empty strings")
        return []
    normalized = [str(item).strip() for item in value]
    if len(normalized) < minimum:
        errors.append(f"{field} must contain at least {minimum} item(s)")
    return normalized


def validate_payload(
    payload: Any,
    root: Path,
    base: str,
    head: str,
    merge_base: str,
    digest: str,
) -> tuple[dict[str, object] | None, list[str]]:
    errors: list[str] = []
    top_fields = {
        "schema_version",
        "base",
        "head",
        "base_review_sha256",
        "rows",
        "findings",
        "coverage",
    }
    top = exact_keys(payload, "payload", top_fields, errors)
    if top is None:
        return None, errors
    if top.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if top.get("base") != base:
        errors.append("payload.base does not match the requested base")
    if top.get("head") != head:
        errors.append("payload.head does not match the requested head")
    if top.get("base_review_sha256") != digest:
        errors.append("base_review_sha256 does not match the frozen review")

    rows_raw = top.get("rows")
    findings_raw = top.get("findings")
    if not isinstance(rows_raw, list):
        errors.append("rows must be an array")
        rows_raw = []
    if not isinstance(findings_raw, list):
        errors.append("findings must be an array")
        findings_raw = []

    row_fields = {
        "id",
        "decision",
        "changed_anchor",
        "contract",
        "producer",
        "consumers",
        "guards_checked",
        "scenario",
        "review_coverage",
        "disposition",
        "root_cause_key",
        "reason",
    }
    rows: dict[str, dict[str, Any]] = {}
    root_causes: set[str] = set()
    range_cache: dict[str, dict[str, list[range]]] = {}
    counts: Counter[str] = Counter()
    for index, raw in enumerate(rows_raw):
        field = f"rows[{index}]"
        row = exact_keys(raw, field, row_fields, errors)
        if row is None:
            continue
        row_id = row.get("id")
        if not isinstance(row_id, str) or not ROW_RE.fullmatch(row_id):
            errors.append(f"{field}.id must match C1, C2, ...")
            continue
        if row_id in rows:
            errors.append(f"duplicate row id: {row_id}")
        rows[row_id] = row
        for name in ("decision", "root_cause_key", "reason"):
            if not nonempty(row.get(name)):
                errors.append(f"{field}.{name} must be a non-empty string")
        root_key = str(row.get("root_cause_key", "")).strip().lower()
        if root_key in root_causes:
            errors.append(f"duplicate root_cause_key: {row.get('root_cause_key')}")
        root_causes.add(root_key)
        validate_changed_anchor(
            row.get("changed_anchor"),
            f"{field}.changed_anchor",
            root,
            merge_base,
            head,
            range_cache,
            errors,
        )
        contract = validate_anchor(
            row.get("contract"),
            f"{field}.contract",
            root,
            {merge_base},
            errors,
            require_statement=True,
        )
        if contract is not None and contract.get("ref") != merge_base:
            errors.append(f"{field}.contract.ref must equal the resolved merge base")
        validate_anchor(
            row.get("producer"),
            f"{field}.producer",
            root,
            {merge_base, head},
            errors,
        )
        consumers = row.get("consumers")
        if not isinstance(consumers, list) or not consumers:
            errors.append(f"{field}.consumers must contain at least one anchor")
        else:
            for consumer_index, consumer in enumerate(consumers):
                validate_anchor(
                    consumer,
                    f"{field}.consumers[{consumer_index}]",
                    root,
                    {merge_base, head},
                    errors,
                )
        validate_string_list(row.get("guards_checked"), f"{field}.guards_checked", errors, minimum=1)
        scenario = exact_keys(
            row.get("scenario"),
            f"{field}.scenario",
            {"precondition", "action", "observable_failure"},
            errors,
        )
        if scenario:
            for name in ("precondition", "action", "observable_failure"):
                if not nonempty(scenario.get(name)):
                    errors.append(f"{field}.scenario.{name} must be a non-empty string")
        review_coverage = exact_keys(
            row.get("review_coverage"),
            f"{field}.review_coverage",
            {"status", "reason"},
            errors,
        )
        coverage_status = review_coverage.get("status") if review_coverage else None
        if coverage_status not in {"covered", "uncovered", "unclear"}:
            errors.append(f"{field}.review_coverage.status is invalid")
        if review_coverage and not nonempty(review_coverage.get("reason")):
            errors.append(f"{field}.review_coverage.reason must be non-empty")
        disposition = row.get("disposition")
        if disposition not in DISPOSITIONS:
            errors.append(f"{field}.disposition is invalid")
        else:
            counts[str(disposition)] += 1
        if disposition == "confirmed-gap" and coverage_status != "uncovered":
            errors.append(f"{field}: confirmed-gap requires uncovered review coverage")
        if disposition == "covered" and coverage_status != "covered":
            errors.append(f"{field}: covered disposition requires covered review coverage")

    finding_fields = {
        "row_id",
        "priority",
        "confidence",
        "title",
        "file",
        "line",
        "side",
        "changed_line",
        "failure_path",
        "impact",
        "evidence",
        "suggested_comment",
    }
    findings: list[dict[str, Any]] = []
    seen_finding_rows: set[str] = set()
    for index, raw in enumerate(findings_raw):
        field = f"findings[{index}]"
        finding = exact_keys(raw, field, finding_fields, errors)
        if finding is None:
            continue
        row_id = finding.get("row_id")
        row = rows.get(str(row_id))
        if row is None:
            errors.append(f"{field}.row_id does not identify a known row")
            continue
        if row_id in seen_finding_rows:
            errors.append(f"more than one finding uses row {row_id}")
        seen_finding_rows.add(str(row_id))
        if row.get("disposition") != "confirmed-gap":
            errors.append(f"{field} belongs to a non-confirmed row")
        if finding.get("priority") not in PRIORITIES:
            errors.append(f"{field}.priority must be P0, P1, or P2")
        if finding.get("confidence") not in CONFIDENCES:
            errors.append(f"{field}.confidence must be high or medium")
        for name in ("title", "failure_path", "impact", "suggested_comment"):
            if not nonempty(finding.get(name)):
                errors.append(f"{field}.{name} must be a non-empty string")
        validate_string_list(finding.get("evidence"), f"{field}.evidence", errors, minimum=4)
        changed = row.get("changed_anchor")
        if isinstance(changed, dict):
            expected = (
                changed.get("path"),
                changed.get("line"),
                changed.get("side"),
                str(changed.get("line_text", "")).strip(),
            )
            actual = (
                finding.get("file"),
                finding.get("line"),
                finding.get("side"),
                str(finding.get("changed_line", "")).strip(),
            )
            if actual != expected:
                errors.append(f"{field} must use its row's exact changed anchor")
        findings.append(finding)

    confirmed_ids = {
        row_id for row_id, row in rows.items() if row.get("disposition") == "confirmed-gap"
    }
    if seen_finding_rows != confirmed_ids:
        missing = sorted(confirmed_ids - seen_finding_rows)
        extra = sorted(seen_finding_rows - confirmed_ids)
        if missing:
            errors.append(f"confirmed rows missing findings: {', '.join(missing)}")
        if extra:
            errors.append(f"findings from non-confirmed rows: {', '.join(extra)}")

    coverage_fields = {
        "changed_decisions",
        "rows",
        "confirmed_gaps",
        "handled",
        "covered",
        "unreachable",
        "unresolved",
        "inspected_surfaces",
        "blind_spots",
    }
    coverage = exact_keys(top.get("coverage"), "coverage", coverage_fields, errors)
    if coverage:
        expected_counts = {
            "rows": len(rows_raw),
            "confirmed_gaps": counts["confirmed-gap"],
            "handled": counts["handled"],
            "covered": counts["covered"],
            "unreachable": counts["unreachable"],
            "unresolved": counts["unresolved"],
        }
        for name, expected in expected_counts.items():
            if coverage.get(name) != expected:
                errors.append(f"coverage.{name} must equal {expected}")
        changed_decisions = coverage.get("changed_decisions")
        if type(changed_decisions) is not int or changed_decisions < len(rows_raw):
            errors.append("coverage.changed_decisions must be an integer at least as large as rows")
        validate_string_list(coverage.get("inspected_surfaces"), "coverage.inspected_surfaces", errors)
        validate_string_list(coverage.get("blind_spots"), "coverage.blind_spots", errors)

    if errors:
        return None, errors
    return {
        "status": "valid",
        "base": base,
        "head": head,
        "merge_base": merge_base,
        "base_review_sha256": digest,
        "rows": len(rows),
        "findings": len(findings),
        "dispositions": {name: counts[name] for name in DISPOSITIONS},
    }, []


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser()
    subparsers = command_parser.add_subparsers(dest="command", required=True)
    index = subparsers.add_parser("index-review")
    index.add_argument("--review", required=True, type=Path)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--repo", required=True, type=Path)
    validate.add_argument("--base", required=True)
    validate.add_argument("--head", required=True)
    validate.add_argument("--review", required=True, type=Path)
    validate.add_argument("--payload-json")
    return command_parser


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "index-review":
            print(json.dumps(review_digest(args.review), indent=2, sort_keys=True))
            return 0
        root = args.repo.expanduser().resolve(strict=True)
        base = resolve_exact_commit(root, args.base, "base")
        head = resolve_exact_commit(root, args.head, "head")
        merge_base = unique_merge_base(root, base, head)
        digest = str(review_digest(args.review)["sha256"])
        raw_payload = args.payload_json if args.payload_json is not None else sys.stdin.read()
        payload = json.loads(raw_payload)
        result, errors = validate_payload(payload, root, base, head, merge_base, digest)
        if errors:
            print(json.dumps({"status": "invalid", "errors": errors}, indent=2, sort_keys=True))
            return 2
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
