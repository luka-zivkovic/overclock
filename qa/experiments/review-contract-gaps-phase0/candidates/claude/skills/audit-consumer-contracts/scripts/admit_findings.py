#!/usr/bin/env python3
"""Fail-closed admission for consumer-contract review findings."""

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
SURFACE_RE = re.compile(r"^S[1-9][0-9]*$")
REMOTE_CLAIM_RE = re.compile(r"(?:\bPR\s*#?\d+|\bissue\s*#?\d+|(?<![A-Za-z0-9])#\d+)", re.I)
DISPOSITIONS = (
    "confirmed-new-finding",
    "already-covered",
    "defeated",
    "unreachable",
    "unresolved",
)
PRIORITIES = ("P0", "P1", "P2")
CONFIDENCES = ("high", "medium")


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def resolve(root: Path, value: str, label: str) -> str:
    if not SHA_RE.fullmatch(value):
        raise ValueError(f"{label} must be an exact 40-character lowercase SHA")
    result = git(root, "rev-parse", "--verify", "--quiet", f"{value}^{{commit}}")
    if result.returncode != 0 or result.stdout.strip() != value:
        raise ValueError(f"{label} commit is unavailable")
    return value


def merge_base(root: Path, base: str, head: str) -> str:
    result = git(root, "merge-base", "--all", base, head)
    values = [line for line in result.stdout.splitlines() if line]
    if result.returncode != 0 or len(values) != 1:
        raise ValueError("merge base is unavailable or ambiguous")
    return values[0]


def review_sha(path: Path | None) -> str | None:
    if path is None:
        return None
    resolved = path.expanduser().resolve(strict=True)
    metadata = resolved.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError("review must be a regular non-symlink file")
    raw = resolved.read_bytes()
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError("review exceeds the 4 MiB limit")
    raw.decode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def safe_path(value: Any) -> str | None:
    if not nonempty(value) or any(ord(character) < 32 for character in value):
        return None
    path = PurePosixPath(str(value))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return None
    return path.as_posix()


def exact_keys(value: Any, field: str, keys: set[str], errors: list[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return None
    missing = sorted(keys - set(value))
    extra = sorted(set(value) - keys)
    if missing:
        errors.append(f"{field} missing fields: {', '.join(missing)}")
    if extra:
        errors.append(f"{field} has unknown fields: {', '.join(extra)}")
    return value


def strings(value: Any, field: str, errors: list[str], minimum: int = 0) -> list[str]:
    if not isinstance(value, list) or any(not nonempty(item) for item in value):
        errors.append(f"{field} must be an array of non-empty strings")
        return []
    result = [str(item).strip() for item in value]
    if len(result) < minimum:
        errors.append(f"{field} must contain at least {minimum} item(s)")
    return result


def source_line(root: Path, ref: str, path: str, line: int) -> str:
    result = git(root, "show", f"{ref}:{path}")
    if result.returncode != 0:
        raise ValueError(f"cannot read {path} at {ref}")
    lines = result.stdout.splitlines()
    if line > len(lines):
        raise ValueError(f"line {line} is outside {path} at {ref}")
    return lines[line - 1]


def verify_anchor(
    raw: Any,
    field: str,
    root: Path,
    allowed_refs: set[str],
    errors: list[str],
    *,
    expectation: bool = False,
) -> dict[str, Any] | None:
    keys = {"path", "line", "ref", "line_text", "role"}
    if expectation:
        keys.add("expectation")
    value = exact_keys(raw, field, keys, errors)
    if value is None:
        return None
    path = safe_path(value.get("path"))
    line = value.get("line")
    ref = value.get("ref")
    if path is None:
        errors.append(f"{field}.path must be safe and repository-relative")
    if type(line) is not int or line <= 0:
        errors.append(f"{field}.line must be a positive integer")
    if ref not in allowed_refs:
        errors.append(f"{field}.ref is not an allowed exact endpoint")
    for name in ("role", "expectation") if expectation else ("role",):
        if not nonempty(value.get(name)):
            errors.append(f"{field}.{name} must be non-empty")
    if not isinstance(value.get("line_text"), str):
        errors.append(f"{field}.line_text must be a string")
    if path is not None and type(line) is int and line > 0 and ref in allowed_refs:
        try:
            actual = source_line(root, str(ref), path, line)
            if actual.strip() != str(value.get("line_text", "")).strip():
                errors.append(f"{field}.line_text does not match {path}:{line} at {ref}")
        except ValueError as exc:
            errors.append(f"{field}: {exc}")
    return value


def validate(
    payload: Any,
    surface: Any,
    surface_digest: str,
    root: Path,
    base: str,
    head: str,
    digest: str | None,
) -> tuple[dict[str, object] | None, list[str]]:
    errors: list[str] = []
    top = exact_keys(
        payload,
        "payload",
        {"schema_version", "base", "head", "surface_sha256", "base_review_sha256", "decisions", "coverage"},
        errors,
    )
    if top is None:
        return None, errors
    if top.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if top.get("base") != base or top.get("head") != head:
        errors.append("payload endpoints do not match the requested endpoints")
    if top.get("surface_sha256") != surface_digest:
        errors.append("surface_sha256 does not match the supplied surface")
    if top.get("base_review_sha256") != digest:
        errors.append("base_review_sha256 does not match the supplied review state")
    if not isinstance(surface, dict) or surface.get("base") != base or surface.get("head") != head:
        errors.append("surface endpoints do not match the requested endpoints")
        surface = {}
    changed_files = set(surface.get("changed_files", []))
    surfaces = {
        item.get("surface_id"): item
        for item in surface.get("surfaces", [])
        if isinstance(item, dict) and SURFACE_RE.fullmatch(str(item.get("surface_id", "")))
    }

    decisions_raw = top.get("decisions")
    if not isinstance(decisions_raw, list):
        errors.append("decisions must be an array")
        decisions_raw = []
    decision_fields = {
        "surface_id", "disposition", "root_cause_key", "reason", "external_endpoint", "head_evidence",
        "reachable_sequence", "guards_checked", "finding",
    }
    seen_surfaces: set[str] = set()
    seen_causes: set[str] = set()
    counts: Counter[str] = Counter()
    admitted = 0
    for index, raw in enumerate(decisions_raw):
        field = f"decisions[{index}]"
        decision = exact_keys(raw, field, decision_fields, errors)
        if decision is None:
            continue
        surface_id = str(decision.get("surface_id", ""))
        item = surfaces.get(surface_id)
        if item is None:
            errors.append(f"{field}.surface_id is unknown")
            continue
        if surface_id in seen_surfaces:
            errors.append(f"duplicate decision for {surface_id}")
        seen_surfaces.add(surface_id)
        disposition = decision.get("disposition")
        if disposition not in DISPOSITIONS:
            errors.append(f"{field}.disposition is invalid")
        else:
            counts[str(disposition)] += 1
        for name in ("root_cause_key", "reason", "reachable_sequence"):
            if not nonempty(decision.get(name)):
                errors.append(f"{field}.{name} must be non-empty")
        cause = str(decision.get("root_cause_key", "")).strip().lower()
        if cause in seen_causes:
            errors.append(f"duplicate root cause: {decision.get('root_cause_key')}")
        seen_causes.add(cause)
        endpoint_raw = decision.get("external_endpoint")
        endpoint = None
        if isinstance(endpoint_raw, dict):
            direction = endpoint_raw.get("direction")
            endpoint = verify_anchor(
                {key: value for key, value in endpoint_raw.items() if key != "direction"},
                field + ".external_endpoint",
                root,
                {base},
                errors,
                expectation=True,
            )
            if direction not in {"producer", "consumer"}:
                errors.append(f"{field}.external_endpoint.direction must be producer or consumer")
        else:
            errors.append(f"{field}.external_endpoint must be an object")
        verify_anchor(decision.get("head_evidence"), field + ".head_evidence", root, {head}, errors)
        strings(decision.get("guards_checked"), field + ".guards_checked", errors, minimum=1)
        if endpoint:
            signature = (
                endpoint.get("path"), endpoint.get("line"), endpoint.get("ref"),
                str(endpoint.get("line_text", "")).strip(),
            )
            listed = {
                (hit.get("path"), hit.get("line"), hit.get("ref"), str(hit.get("line_text", "")).strip())
                for hit in item.get("base_matches", [])
                if isinstance(hit, dict)
            }
            if signature not in listed:
                errors.append(f"{field}.external_endpoint is not listed on {surface_id}")
            if endpoint.get("path") in changed_files:
                errors.append(f"{field}.external_endpoint must be outside the changed files")
        finding = decision.get("finding")
        if disposition == "confirmed-new-finding":
            admitted += 1
            finding_fields = {
                "priority", "confidence", "title", "file", "line", "side", "changed_line",
                "failure_path", "impact", "evidence", "suggested_comment",
            }
            finding_value = exact_keys(finding, field + ".finding", finding_fields, errors)
            if finding_value:
                if finding_value.get("priority") not in PRIORITIES:
                    errors.append(f"{field}.finding.priority is invalid")
                if finding_value.get("confidence") not in CONFIDENCES:
                    errors.append(f"{field}.finding.confidence is invalid")
                for name in ("title", "failure_path", "impact", "suggested_comment"):
                    if not nonempty(finding_value.get(name)):
                        errors.append(f"{field}.finding.{name} must be non-empty")
                evidence = strings(finding_value.get("evidence"), field + ".finding.evidence", errors, minimum=4)
                anchors = {
                    (a.get("path"), a.get("line"), a.get("side"), str(a.get("text", "")).strip())
                    for a in item.get("changed_anchors", [])
                    if isinstance(a, dict)
                }
                actual = (
                    finding_value.get("file"), finding_value.get("line"), finding_value.get("side"),
                    str(finding_value.get("changed_line", "")).strip(),
                )
                if actual not in anchors:
                    errors.append(f"{field}.finding is not anchored to {surface_id}")
                claim_text = " ".join(
                    [str(finding_value.get(name, "")) for name in ("title", "failure_path", "impact", "suggested_comment")]
                    + evidence
                )
                if REMOTE_CLAIM_RE.search(claim_text):
                    errors.append(f"{field}.finding contains an unsupplied external PR/issue claim")
        elif finding is not None:
            errors.append(f"{field}.finding must be null unless disposition is confirmed-new-finding")

    coverage = exact_keys(
        top.get("coverage"),
        "coverage",
        {"surfaced", "verified", "confirmed", "already_covered", "defeated", "unreachable", "unresolved", "skipped", "blind_spots"},
        errors,
    )
    if coverage:
        expected = {
            "surfaced": len(surfaces),
            "verified": len(decisions_raw),
            "confirmed": counts["confirmed-new-finding"],
            "already_covered": counts["already-covered"],
            "defeated": counts["defeated"],
            "unreachable": counts["unreachable"],
            "unresolved": counts["unresolved"],
            "skipped": max(0, len(surfaces) - len(decisions_raw)),
        }
        for name, value in expected.items():
            if coverage.get(name) != value:
                errors.append(f"coverage.{name} must equal {value}")
        strings(coverage.get("blind_spots"), "coverage.blind_spots", errors)
    if errors:
        return None, errors
    return {
        "status": "valid",
        "base": base,
        "head": head,
        "base_review_sha256": digest,
        "surface_sha256": surface_digest,
        "decisions": len(decisions_raw),
        "admitted_findings": admitted,
    }, []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    surface_group = parser.add_mutually_exclusive_group(required=True)
    surface_group.add_argument("--surface-json")
    surface_group.add_argument("--surface-file", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--payload-json")
    args = parser.parse_args()
    try:
        root = args.repo.expanduser().resolve(strict=True)
        base_endpoint = resolve(root, args.base, "base")
        head = resolve(root, args.head, "head")
        base = merge_base(root, base_endpoint, head)
        if args.surface_file is not None:
            surface_path = args.surface_file.expanduser().resolve(strict=True)
            metadata = surface_path.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                raise ValueError("surface file must be a regular non-symlink file")
            surface_raw = surface_path.read_bytes()
            if len(surface_raw) > 4 * 1024 * 1024:
                raise ValueError("surface file exceeds the 4 MiB limit")
            surface_text = surface_raw.decode("utf-8")
        else:
            surface_text = str(args.surface_json)
            surface_raw = surface_text.encode("utf-8")
        surface = json.loads(surface_text)
        surface_digest = hashlib.sha256(surface_raw).hexdigest()
        payload_raw = args.payload_json if args.payload_json is not None else sys.stdin.read()
        payload = json.loads(payload_raw)
        result, errors = validate(
            payload, surface, surface_digest, root, base, head, review_sha(args.review)
        )
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
