#!/usr/bin/env python3
"""Materialize semantic contract-gap claims and assemble an append-only delta."""

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
CLAIM_RE = re.compile(r"^C[1-9][0-9]*$")
MAX_REVIEW_BYTES = 4 * 1024 * 1024
PRIORITIES = {"P0", "P1", "P2"}
CONFIDENCES = {"high", "medium"}
COVERAGE_STATUSES = {"covered", "uncovered", "unclear"}
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
MIN_FRAGMENT_LENGTH = 16


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
    raw.decode("utf-8")
    return {
        "review": str(resolved),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def safe_path(value: Any) -> str | None:
    if not nonempty(value) or any(ord(character) < 32 for character in str(value)):
        return None
    path = PurePosixPath(str(value))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return None
    return path.as_posix()


def normalized_line(value: str) -> str:
    return " ".join(value.strip().split())


def snippet_fragments(snippet: str) -> list[str]:
    """Return distinctive normalized hints, ignoring generic or ellipsis-only scaffolding."""
    fragments = []
    for raw in snippet.splitlines():
        fragment = normalized_line(raw)
        fragment = re.sub(r"^\.\.\.\s*", "", fragment)
        fragment = re.sub(r"\s*\.\.\.$", "", fragment)
        fragment = normalized_line(fragment)
        if not fragment or "..." in fragment:
            continue
        identifiers = set(IDENTIFIER_RE.findall(fragment))
        if len(fragment) < MIN_FRAGMENT_LENGTH or len(identifiers) < 2:
            continue
        fragments.append(fragment)
    return fragments


def line_match_quality(source: str, fragment: str) -> tuple[int, int] | None:
    if source == fragment:
        return (2, len(fragment))
    if fragment in source and len(fragment) / max(len(source), 1) >= 0.65:
        return (1, len(fragment))
    return None


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


def string_list(value: Any, field: str, errors: list[str], minimum: int = 0) -> list[str]:
    if not isinstance(value, list) or any(not nonempty(item) for item in value):
        errors.append(f"{field} must be an array of non-empty strings")
        return []
    items = [str(item).strip() for item in value]
    if len(items) < minimum:
        errors.append(f"{field} must contain at least {minimum} item(s)")
    return items


def source_lines(root: Path, ref: str, path: str) -> list[str]:
    result = git(root, "show", f"{ref}:{path}")
    if result.returncode != 0:
        raise ValueError(f"cannot read {path} at {ref}")
    return result.stdout.splitlines()


def changed_line_sets(root: Path, merge_base: str, head: str, path: str) -> dict[str, set[int]]:
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
    changed = {"LEFT": set(), "RIGHT": set()}
    for line in result.stdout.splitlines():
        match = HUNK_RE.match(line)
        if not match:
            continue
        old_start, old_count, new_start, new_count = match.groups()
        old_length = int(old_count) if old_count is not None else 1
        new_length = int(new_count) if new_count is not None else 1
        if old_length:
            changed["LEFT"].update(range(int(old_start), int(old_start) + old_length))
        if new_length:
            changed["RIGHT"].update(range(int(new_start), int(new_start) + new_length))
    return changed


def choose_line(lines: list[str], snippet: str, line_hint: int, allowed: set[int] | None) -> int:
    fragments = snippet_fragments(snippet)
    if not fragments:
        raise ValueError("snippet must preserve at least one distinctive source line")
    matches: dict[int, tuple[int, int]] = {}
    for line, raw_source in enumerate(lines, start=1):
        source = normalized_line(raw_source)
        qualities = [
            quality
            for fragment in fragments
            if (quality := line_match_quality(source, fragment)) is not None
        ]
        if qualities:
            matches[line] = max(qualities)
    if not matches:
        raise ValueError("no distinctive snippet fragment matches a source line")
    if line_hint in matches:
        selected = line_hint
    else:
        ranked = sorted(
            (abs(line - line_hint), -quality[0], -quality[1], line)
            for line, quality in matches.items()
        )
        if len(ranked) > 1 and ranked[0][:-1] == ranked[1][:-1]:
            raise ValueError("snippet matches multiple equally near source lines")
        selected = ranked[0][-1]
    if allowed is not None and selected not in allowed:
        raise ValueError("intended source line is not a changed line on the requested side")
    return selected


def resolve_evidence_hint(
    raw: Any,
    field: str,
    root: Path,
    merge_base: str,
    head: str,
    errors: list[str],
    *,
    contract: bool = False,
) -> dict[str, Any] | None:
    required = {"path", "line_hint", "snippet", "ref", "role"}
    if contract:
        required.add("statement")
    value = exact_keys(raw, field, required, errors)
    if value is None:
        return None
    path = safe_path(value.get("path"))
    line_hint = value.get("line_hint")
    snippet = value.get("snippet")
    symbolic_ref = value.get("ref")
    if path is None:
        errors.append(f"{field}.path must be a safe repository-relative path")
    if type(line_hint) is not int or line_hint <= 0:
        errors.append(f"{field}.line_hint must be a positive integer")
    if not nonempty(snippet):
        errors.append(f"{field}.snippet must be a non-empty string")
    if symbolic_ref not in {"base", "head"}:
        errors.append(f"{field}.ref must be base or head")
    if contract and symbolic_ref != "base":
        errors.append(f"{field}.ref must be base")
    if not nonempty(value.get("role")):
        errors.append(f"{field}.role must be a non-empty string")
    if contract and not nonempty(value.get("statement")):
        errors.append(f"{field}.statement must be a non-empty string")
    if path is None or type(line_hint) is not int or not nonempty(snippet):
        return None
    if symbolic_ref not in {"base", "head"}:
        return None
    ref = merge_base if symbolic_ref == "base" else head
    try:
        lines = source_lines(root, ref, path)
        line = choose_line(lines, str(snippet), line_hint, None)
    except ValueError as exc:
        errors.append(f"{field}: {exc}")
        return None
    result = {
        "path": path,
        "line": line,
        "ref": ref,
        "line_text": lines[line - 1],
        "role": str(value["role"]).strip(),
    }
    if contract:
        result["statement"] = str(value["statement"]).strip()
    return result


def resolve_changed_hint(
    raw: Any,
    field: str,
    root: Path,
    merge_base: str,
    head: str,
    errors: list[str],
    range_cache: dict[str, dict[str, set[int]]],
) -> dict[str, Any] | None:
    required = {"path", "line_hint", "snippet", "side", "role"}
    value = exact_keys(raw, field, required, errors)
    if value is None:
        return None
    path = safe_path(value.get("path"))
    line_hint = value.get("line_hint")
    snippet = value.get("snippet")
    side = value.get("side")
    if path is None:
        errors.append(f"{field}.path must be a safe repository-relative path")
    if type(line_hint) is not int or line_hint <= 0:
        errors.append(f"{field}.line_hint must be a positive integer")
    if not nonempty(snippet):
        errors.append(f"{field}.snippet must be a non-empty string")
    if side not in {"LEFT", "RIGHT"}:
        errors.append(f"{field}.side must be LEFT or RIGHT")
    if not nonempty(value.get("role")):
        errors.append(f"{field}.role must be a non-empty string")
    if path is None or type(line_hint) is not int or not nonempty(snippet):
        return None
    if side not in {"LEFT", "RIGHT"}:
        return None
    ref = merge_base if side == "LEFT" else head
    try:
        changed = range_cache.setdefault(path, changed_line_sets(root, merge_base, head, path))
        lines = source_lines(root, ref, path)
        line = choose_line(lines, str(snippet), line_hint, changed[side])
    except ValueError as exc:
        errors.append(f"{field}: {exc}")
        return None
    return {
        "path": path,
        "line": line,
        "ref": ref,
        "line_text": lines[line - 1],
        "role": str(value["role"]).strip(),
        "side": side,
    }


def materialize_claims(
    payload: Any,
    root: Path,
    base: str,
    head: str,
    review: Path | None = None,
) -> dict[str, Any]:
    root = root.expanduser().resolve(strict=True)
    base = resolve_exact_commit(root, base, "base")
    head = resolve_exact_commit(root, head, "head")
    merge_base = unique_merge_base(root, base, head)
    review_sha = str(review_digest(review)["sha256"]) if review is not None else None
    top_errors: list[str] = []
    top = exact_keys(
        payload,
        "payload",
        {"schema_version", "claims", "inspected_surfaces", "blind_spots"},
        top_errors,
    )
    if top is None:
        return {"schema_version": 2, "status": "error", "errors": top_errors}
    if top.get("schema_version") != 2:
        top_errors.append("schema_version must equal 2")
    claims = top.get("claims")
    if not isinstance(claims, list):
        top_errors.append("claims must be an array")
        claims = []
    inspected = string_list(top.get("inspected_surfaces"), "inspected_surfaces", top_errors)
    blind_spots = string_list(top.get("blind_spots"), "blind_spots", top_errors)
    if top_errors:
        return {"schema_version": 2, "status": "error", "errors": top_errors}

    ids = Counter(str(item.get("id", "")) for item in claims if isinstance(item, dict))
    roots = Counter(
        str(item.get("root_cause_key", "")).strip().lower()
        for item in claims
        if isinstance(item, dict)
    )
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    range_cache: dict[str, dict[str, set[int]]] = {}
    claim_fields = {
        "id",
        "decision",
        "root_cause_key",
        "changed_anchor",
        "contract",
        "producer",
        "consumers",
        "guards_checked",
        "scenario",
        "priority",
        "confidence",
        "title",
        "failure_path",
        "impact",
        "suggested_comment",
    }
    for index, raw in enumerate(claims):
        field = f"claims[{index}]"
        errors: list[str] = []
        claim = exact_keys(raw, field, claim_fields, errors)
        if claim is None:
            rejected.append({"claim_id": f"index-{index}", "root_cause_key": "", "errors": errors})
            continue
        claim_id = claim.get("id")
        root_key = str(claim.get("root_cause_key", "")).strip()
        if not isinstance(claim_id, str) or not CLAIM_RE.fullmatch(claim_id):
            errors.append(f"{field}.id must match C1, C2, ...")
        elif ids[claim_id] != 1:
            errors.append(f"duplicate claim id: {claim_id}")
        if not root_key:
            errors.append(f"{field}.root_cause_key must be a non-empty string")
        elif roots[root_key.lower()] != 1:
            errors.append(f"duplicate root_cause_key: {root_key}")
        for name in ("decision", "title", "failure_path", "impact", "suggested_comment"):
            if not nonempty(claim.get(name)):
                errors.append(f"{field}.{name} must be a non-empty string")
        if claim.get("priority") not in PRIORITIES:
            errors.append(f"{field}.priority must be P0, P1, or P2")
        if claim.get("confidence") not in CONFIDENCES:
            errors.append(f"{field}.confidence must be high or medium")
        guards = string_list(claim.get("guards_checked"), f"{field}.guards_checked", errors, 1)
        scenario = exact_keys(
            claim.get("scenario"),
            f"{field}.scenario",
            {"precondition", "action", "observable_failure"},
            errors,
        )
        if scenario:
            for name in ("precondition", "action", "observable_failure"):
                if not nonempty(scenario.get(name)):
                    errors.append(f"{field}.scenario.{name} must be a non-empty string")
        changed = resolve_changed_hint(
            claim.get("changed_anchor"),
            f"{field}.changed_anchor",
            root,
            merge_base,
            head,
            errors,
            range_cache,
        )
        contract = resolve_evidence_hint(
            claim.get("contract"),
            f"{field}.contract",
            root,
            merge_base,
            head,
            errors,
            contract=True,
        )
        producer = resolve_evidence_hint(
            claim.get("producer"),
            f"{field}.producer",
            root,
            merge_base,
            head,
            errors,
        )
        consumers_raw = claim.get("consumers")
        consumers: list[dict[str, Any]] = []
        if not isinstance(consumers_raw, list) or not consumers_raw:
            errors.append(f"{field}.consumers must contain at least one evidence hint")
        else:
            for consumer_index, consumer_raw in enumerate(consumers_raw):
                consumer = resolve_evidence_hint(
                    consumer_raw,
                    f"{field}.consumers[{consumer_index}]",
                    root,
                    merge_base,
                    head,
                    errors,
                )
                if consumer is not None:
                    consumers.append(consumer)
        if errors:
            rejected.append(
                {
                    "claim_id": claim_id if isinstance(claim_id, str) else f"index-{index}",
                    "root_cause_key": root_key,
                    "errors": errors,
                }
            )
            continue
        assert changed is not None and contract is not None and producer is not None and scenario
        accepted.append(
            {
                "id": claim_id,
                "decision": str(claim["decision"]).strip(),
                "root_cause_key": root_key,
                "changed_anchor": changed,
                "contract": contract,
                "producer": producer,
                "consumers": consumers,
                "guards_checked": guards,
                "scenario": {name: str(scenario[name]).strip() for name in scenario},
                "priority": claim["priority"],
                "confidence": claim["confidence"],
                "title": str(claim["title"]).strip(),
                "failure_path": str(claim["failure_path"]).strip(),
                "impact": str(claim["impact"]).strip(),
                "suggested_comment": str(claim["suggested_comment"]).strip(),
            }
        )
    return {
        "schema_version": 2,
        "status": "materialized",
        "base": base,
        "head": head,
        "merge_base": merge_base,
        "base_review_sha256": review_sha,
        "accepted_claims": accepted,
        "rejected_claims": rejected,
        "coverage_context": {
            "inspected_surfaces": inspected,
            "blind_spots": blind_spots,
        },
        "metrics": {
            "submitted_claims": len(claims),
            "accepted_claims": len(accepted),
            "rejected_claims": len(rejected),
            "fully_materialized": not rejected,
        },
    }


def finalize_claims(
    materialized: Any,
    coverage: Any | None,
    review: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(materialized, dict) or materialized.get("status") != "materialized":
        raise ValueError("materialized artifact is unavailable or invalid")
    expected_digest = materialized.get("base_review_sha256")
    if review is not None:
        actual_digest = str(review_digest(review)["sha256"])
        if expected_digest != actual_digest:
            raise ValueError("frozen review digest changed after materialization")
    elif expected_digest is not None:
        raise ValueError("review is required for a review-bound materialized artifact")
    claims = materialized.get("accepted_claims")
    if not isinstance(claims, list):
        raise ValueError("accepted_claims must be an array")

    standalone = coverage is None
    decisions_by_id: dict[str, dict[str, str]] = {}
    invalid_decisions: list[dict[str, Any]] = []
    if coverage is not None:
        errors: list[str] = []
        top = exact_keys(coverage, "coverage", {"schema_version", "decisions"}, errors)
        if top is None or top.get("schema_version") != 1 or not isinstance(top.get("decisions"), list):
            if top is not None and top.get("schema_version") != 1:
                errors.append("coverage.schema_version must equal 1")
            if top is not None and not isinstance(top.get("decisions"), list):
                errors.append("coverage.decisions must be an array")
            invalid_decisions.append({"claim_id": "*", "errors": errors})
            decisions_raw: list[Any] = []
        else:
            decisions_raw = top["decisions"]
        counts = Counter(
            str(item.get("claim_id", ""))
            for item in decisions_raw
            if isinstance(item, dict)
        )
        for index, raw in enumerate(decisions_raw):
            item_errors: list[str] = []
            decision = exact_keys(
                raw,
                f"decisions[{index}]",
                {"claim_id", "status", "reason"},
                item_errors,
            )
            claim_id = str(raw.get("claim_id", "")) if isinstance(raw, dict) else f"index-{index}"
            if decision is not None:
                if not CLAIM_RE.fullmatch(claim_id):
                    item_errors.append(f"decisions[{index}].claim_id is invalid")
                if counts[claim_id] != 1:
                    item_errors.append(f"duplicate coverage decision for {claim_id}")
                if decision.get("status") not in COVERAGE_STATUSES:
                    item_errors.append(f"decisions[{index}].status is invalid")
                if not nonempty(decision.get("reason")):
                    item_errors.append(f"decisions[{index}].reason must be non-empty")
            if item_errors:
                invalid_decisions.append({"claim_id": claim_id, "errors": item_errors})
            elif decision is not None:
                decisions_by_id[claim_id] = {
                    "claim_id": claim_id,
                    "status": str(decision["status"]),
                    "reason": str(decision["reason"]).strip(),
                }

    claim_ids = {str(claim.get("id")) for claim in claims if isinstance(claim, dict)}
    unknown_decisions = sorted(set(decisions_by_id) - claim_ids)
    findings: list[dict[str, Any]] = []
    decisions: list[dict[str, str]] = []
    missing: list[str] = []
    disposition_counts: Counter[str] = Counter()
    for claim in claims:
        claim_id = str(claim["id"])
        if standalone:
            decision = {
                "claim_id": claim_id,
                "status": "uncovered",
                "reason": "Standalone mode did not subtract a primary review.",
            }
        else:
            decision = decisions_by_id.get(claim_id)
            if decision is None:
                missing.append(claim_id)
                disposition_counts["missing"] += 1
                continue
        decisions.append(decision)
        disposition_counts[decision["status"]] += 1
        if decision["status"] != "uncovered":
            continue
        changed = claim["changed_anchor"]
        findings.append(
            {
                "claim_id": claim_id,
                "root_cause_key": claim["root_cause_key"],
                "priority": claim["priority"],
                "confidence": claim["confidence"],
                "title": claim["title"],
                "file": changed["path"],
                "line": changed["line"],
                "side": changed["side"],
                "changed_line": changed["line_text"],
                "failure_path": claim["failure_path"],
                "impact": claim["impact"],
                "suggested_comment": claim["suggested_comment"],
                "scenario": claim["scenario"],
                "contract": claim["contract"],
                "producer": claim["producer"],
                "consumers": claim["consumers"],
                "guards_checked": claim["guards_checked"],
                "coverage_reason": decision["reason"],
            }
        )
    coverage_context = materialized.get("coverage_context", {})
    coverage_complete = standalone or (
        not missing
        and not invalid_decisions
        and not unknown_decisions
        and set(decisions_by_id) == claim_ids
    )
    return {
        "schema_version": 2,
        "status": "valid",
        "mode": "standalone" if standalone else "review-delta",
        "base": materialized["base"],
        "head": materialized["head"],
        "merge_base": materialized["merge_base"],
        "base_review_sha256": expected_digest,
        "findings": findings,
        "coverage_decisions": decisions,
        "rejections": {
            "materialization": materialized.get("rejected_claims", []),
            "invalid_coverage_decisions": invalid_decisions,
            "missing_coverage_decisions": missing,
            "unknown_coverage_decisions": unknown_decisions,
        },
        "coverage": {
            "submitted_claims": int(materialized.get("metrics", {}).get("submitted_claims", 0)),
            "materialized_claims": len(claims),
            "admitted_findings": len(findings),
            "covered": disposition_counts["covered"],
            "uncovered": disposition_counts["uncovered"],
            "unclear": disposition_counts["unclear"],
            "missing": disposition_counts["missing"],
            "inspected_surfaces": coverage_context.get("inspected_surfaces", []),
            "blind_spots": coverage_context.get("blind_spots", []),
            "fully_materialized": bool(materialized.get("metrics", {}).get("fully_materialized")),
            "coverage_complete": coverage_complete,
        },
    }


def render_delta(artifact: dict[str, Any]) -> bytes:
    findings = artifact.get("findings", [])
    if not findings:
        return b""
    heading = (
        "## Standalone semantic contract gaps"
        if artifact.get("mode") == "standalone"
        else "## Semantic contract-gap additions"
    )
    lines = ["", "---", "", heading, ""]
    for finding in findings:
        lines.extend(
            [
                f"### [{finding['priority']}] {finding['title']}",
                "",
                f"**Location:** `{finding['file']}:{finding['line']}`",
                "",
                finding["failure_path"],
                "",
                f"**Impact:** {finding['impact']}",
                "",
                f"**Suggested comment:** {finding['suggested_comment']}",
                "",
            ]
        )
    return ("\n".join(lines).rstrip() + "\n").encode("utf-8")


def read_json_argument(value: str | None) -> Any:
    return json.loads(value if value is not None else sys.stdin.read())


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser()
    subparsers = command_parser.add_subparsers(dest="command", required=True)
    index = subparsers.add_parser("index-review")
    index.add_argument("--review", required=True, type=Path)
    materialize = subparsers.add_parser("materialize")
    materialize.add_argument("--repo", required=True, type=Path)
    materialize.add_argument("--base", required=True)
    materialize.add_argument("--head", required=True)
    materialize.add_argument("--review", type=Path)
    materialize.add_argument("--claims-json")
    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--materialized", required=True, type=Path)
    finalize.add_argument("--coverage", type=Path)
    finalize.add_argument("--review", type=Path)
    render = subparsers.add_parser("render")
    render.add_argument("--artifact", required=True, type=Path)
    return command_parser


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "index-review":
            print(json.dumps(review_digest(args.review), indent=2, sort_keys=True))
        elif args.command == "materialize":
            payload = read_json_argument(args.claims_json)
            result = materialize_claims(payload, args.repo, args.base, args.head, args.review)
            print(json.dumps(result, indent=2, sort_keys=True))
            if result.get("status") != "materialized":
                return 2
        elif args.command == "finalize":
            materialized = json.loads(args.materialized.read_text(encoding="utf-8"))
            coverage = (
                json.loads(args.coverage.read_text(encoding="utf-8"))
                if args.coverage is not None
                else None
            )
            print(json.dumps(finalize_claims(materialized, coverage, args.review), indent=2, sort_keys=True))
        else:
            artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
            sys.stdout.buffer.write(render_delta(artifact))
        return 0
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
