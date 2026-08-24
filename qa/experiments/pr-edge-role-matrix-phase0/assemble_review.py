#!/usr/bin/env python3
"""Strictly admit confirmed edge-originated findings into a frozen review."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RISK_ID_RE = re.compile(r"^R[1-9][0-9]*$")
ROOT_CAUSE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,80}$")
PRIORITIES = {"P0", "P1", "P2"}
DISPOSITIONS = {
    "confirmed-new-finding",
    "already-covered",
    "defeated",
    "unreachable",
    "unresolved",
}
ASSEMBLY_APPROACHES = {
    "parallel-independent-challenger",
    "late-batch-confirmed",
    "late-per-risk-confirmed",
    "coverage-filtered-per-risk",
    "test-scenario-confirmed",
    "conditional-no-findings-challenger",
    "conditional-high-impact-challenger",
}
CANDIDATE_FIELDS = {
    "schema_version",
    "approach_id",
    "base_review_sha256",
    "edge_index_sha256",
    "decisions",
}
DECISION_FIELDS = {"risk_id", "disposition", "reason", "finding"}
FINDING_FIELDS = {
    "root_cause_key",
    "priority",
    "title",
    "location",
    "failure_path",
    "impact",
    "change_causality",
    "reachable_producer",
    "guards_checked",
    "evidence",
    "suggested_comment",
}
EDGE_FIELDS = {"schema_version", "analysis_base", "risks"}
EDGE_RISK_FIELDS = {"id", "title", "scenario", "impact_signal", "evidence", "probe"}
CHANGED_FIELDS = {"schema_version", "base_sha", "head_sha", "diff_sha256", "changed_lines"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def exact_fields(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{label} fields must exactly match the contract")
    return value


def nonempty_strings(value: Any, label: str, *, minimum: int = 1) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) < minimum
        or any(not nonempty(item) for item in value)
    ):
        raise ValueError(f"{label} must contain at least {minimum} non-empty string(s)")
    return [item.strip() for item in value]


def safe_path(value: Any, label: str) -> str:
    if not nonempty(value):
        raise ValueError(f"{label} must be a non-empty repository-relative path")
    path = value.strip()
    pure = PurePosixPath(path)
    if (
        "\\" in path
        or "\x00" in path
        or pure.is_absolute()
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise ValueError(f"{label} must be a safe repository-relative path")
    return path


def validate_edge_index(raw: Any) -> tuple[str, dict[str, dict[str, Any]]]:
    edge = exact_fields(raw, EDGE_FIELDS, "edge index")
    if edge["schema_version"] != 1:
        raise ValueError("edge index schema_version must be 1")
    base = edge["analysis_base"]
    if not isinstance(base, str) or SHA_RE.fullmatch(base) is None:
        raise ValueError("edge index analysis_base must be a full lowercase SHA")
    risks = edge["risks"]
    if not isinstance(risks, list) or not 0 <= len(risks) <= 5:
        raise ValueError("edge index must contain between 0 and 5 risks")
    by_id: dict[str, dict[str, Any]] = {}
    for index, raw_risk in enumerate(risks):
        risk = exact_fields(raw_risk, EDGE_RISK_FIELDS, f"edge risk {index}")
        risk_id = risk["id"]
        if not isinstance(risk_id, str) or RISK_ID_RE.fullmatch(risk_id) is None:
            raise ValueError(f"edge risk {index} has an invalid id")
        if risk_id in by_id:
            raise ValueError(f"duplicate edge risk id: {risk_id}")
        for field in ("title", "scenario", "probe"):
            if not nonempty(risk[field]):
                raise ValueError(f"edge risk {risk_id}.{field} must be non-empty")
        if risk["impact_signal"] not in {"low", "medium", "high"}:
            raise ValueError(f"edge risk {risk_id} has an invalid impact signal")
        evidence = nonempty_strings(risk["evidence"], f"edge risk {risk_id}.evidence")
        if any(base not in item for item in evidence):
            raise ValueError(f"edge risk {risk_id} evidence must cite the exact analysis base")
        by_id[risk_id] = risk
    return base, by_id


def validate_changed_lines(raw: Any) -> tuple[str, str, dict[str, set[int]]]:
    changed = exact_fields(raw, CHANGED_FIELDS, "changed-line allowlist")
    if changed["schema_version"] != 1:
        raise ValueError("changed-line schema_version must be 1")
    base = changed["base_sha"]
    head = changed["head_sha"]
    diff_digest = changed["diff_sha256"]
    if not isinstance(base, str) or SHA_RE.fullmatch(base) is None:
        raise ValueError("changed-line base_sha must be a full lowercase SHA")
    if not isinstance(head, str) or SHA_RE.fullmatch(head) is None:
        raise ValueError("changed-line head_sha must be a full lowercase SHA")
    if not isinstance(diff_digest, str) or SHA256_RE.fullmatch(diff_digest) is None:
        raise ValueError("changed-line diff_sha256 must be lowercase hexadecimal")
    items = changed["changed_lines"]
    if not isinstance(items, list):
        raise ValueError("changed_lines must be an array")
    by_path: dict[str, set[int]] = {}
    for index, item in enumerate(items):
        entry = exact_fields(item, {"path", "lines"}, f"changed line entry {index}")
        path = safe_path(entry["path"], f"changed line entry {index}.path")
        if path in by_path:
            raise ValueError(f"duplicate changed-line path: {path}")
        lines = entry["lines"]
        if (
            not isinstance(lines, list)
            or not lines
            or any(not isinstance(line, int) or isinstance(line, bool) or line < 1 for line in lines)
        ):
            raise ValueError(f"changed line entry {path}.lines must contain positive integers")
        if len(set(lines)) != len(lines):
            raise ValueError(f"changed line entry {path}.lines contains duplicates")
        by_path[path] = set(lines)
    return base, head, by_path


def validate_finding(raw: Any, risk_id: str, changed: dict[str, set[int]]) -> dict[str, Any]:
    finding = exact_fields(raw, FINDING_FIELDS, f"finding for {risk_id}")
    root_cause = finding["root_cause_key"]
    if not isinstance(root_cause, str) or ROOT_CAUSE_RE.fullmatch(root_cause) is None:
        raise ValueError(f"finding for {risk_id} has an invalid root_cause_key")
    if finding["priority"] not in PRIORITIES:
        raise ValueError(f"finding for {risk_id} has an invalid priority")
    for field in (
        "title",
        "failure_path",
        "impact",
        "change_causality",
        "reachable_producer",
        "suggested_comment",
    ):
        if not nonempty(finding[field]):
            raise ValueError(f"finding for {risk_id}.{field} must be non-empty")
    location = exact_fields(finding["location"], {"path", "line"}, f"location for {risk_id}")
    path = safe_path(location["path"], f"location for {risk_id}.path")
    line = location["line"]
    if not isinstance(line, int) or isinstance(line, bool) or line < 1:
        raise ValueError(f"location for {risk_id}.line must be a positive integer")
    if path not in changed or line not in changed[path]:
        raise ValueError(f"finding for {risk_id} is not anchored to an exact changed line")
    return {
        "root_cause_key": root_cause,
        "priority": finding["priority"],
        "title": finding["title"].strip(),
        "location": {"path": path, "line": line},
        "failure_path": finding["failure_path"].strip(),
        "impact": finding["impact"].strip(),
        "change_causality": finding["change_causality"].strip(),
        "reachable_producer": finding["reachable_producer"].strip(),
        "guards_checked": nonempty_strings(
            finding["guards_checked"], f"finding for {risk_id}.guards_checked"
        ),
        "evidence": nonempty_strings(
            finding["evidence"], f"finding for {risk_id}.evidence", minimum=2
        ),
        "suggested_comment": finding["suggested_comment"].strip(),
    }


def normalize_candidates(
    raw_candidates: list[Any],
    *,
    approach_id: str,
    base_digest: str,
    edge_digest: str,
    risk_ids: set[str],
    changed: dict[str, set[int]],
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    seen_risks: set[str] = set()
    seen_roots: set[str] = set()
    for candidate_index, raw in enumerate(raw_candidates):
        candidate = exact_fields(raw, CANDIDATE_FIELDS, f"candidate {candidate_index}")
        if candidate["schema_version"] != 1:
            raise ValueError(f"candidate {candidate_index} schema_version must be 1")
        if candidate["approach_id"] != approach_id:
            raise ValueError(f"candidate {candidate_index} targets a different approach")
        if candidate["base_review_sha256"] != base_digest:
            raise ValueError(f"candidate {candidate_index} targets a different frozen review")
        if candidate["edge_index_sha256"] != edge_digest:
            raise ValueError(f"candidate {candidate_index} targets a different edge index")
        raw_decisions = candidate["decisions"]
        if not isinstance(raw_decisions, list):
            raise ValueError(f"candidate {candidate_index}.decisions must be an array")
        for decision_index, raw_decision in enumerate(raw_decisions):
            decision = exact_fields(
                raw_decision,
                DECISION_FIELDS,
                f"candidate {candidate_index} decision {decision_index}",
            )
            risk_id = decision["risk_id"]
            if risk_id not in risk_ids:
                raise ValueError(f"unknown edge risk id: {risk_id}")
            if risk_id in seen_risks:
                raise ValueError(f"duplicate candidate decision for risk: {risk_id}")
            seen_risks.add(risk_id)
            disposition = decision["disposition"]
            if disposition not in DISPOSITIONS:
                raise ValueError(f"invalid disposition for {risk_id}")
            if not nonempty(decision["reason"]):
                raise ValueError(f"decision reason for {risk_id} must be non-empty")
            if disposition == "confirmed-new-finding":
                if decision["finding"] is None:
                    raise ValueError(f"confirmed decision for {risk_id} requires a finding")
                finding = validate_finding(decision["finding"], risk_id, changed)
                root = finding["root_cause_key"]
                if root in seen_roots:
                    raise ValueError(f"duplicate confirmed root cause: {root}")
                seen_roots.add(root)
            else:
                if decision["finding"] is not None:
                    raise ValueError(f"non-confirmed decision for {risk_id} must not contain a finding")
                finding = None
            decisions.append(
                {
                    "risk_id": risk_id,
                    "disposition": disposition,
                    "reason": decision["reason"].strip(),
                    "finding": finding,
                }
            )
    return decisions


def render_findings(decisions: list[dict[str, Any]]) -> bytes:
    confirmed = [decision for decision in decisions if decision["finding"] is not None]
    if not confirmed:
        return b""
    lines = ["", "---", "", "## Additional verified findings", ""]
    for decision in confirmed:
        finding = decision["finding"]
        lines.extend(
            [
                f"### [{finding['priority']}] {finding['title']}",
                "",
                f"**Location:** `{finding['location']['path']}:{finding['location']['line']}`",
                "",
                f"**Failure path:** {finding['failure_path']}",
                "",
                f"**Impact:** {finding['impact']}",
                "",
                f"**Why this change causes it:** {finding['change_causality']}",
                "",
                f"**Reachable producer:** {finding['reachable_producer']}",
                "",
                "**Evidence:**",
                "",
                *[f"- {item}" for item in finding["evidence"]],
                "",
                f"**Suggested comment:** {finding['suggested_comment']}",
                "",
            ]
        )
    return ("\n".join(lines).rstrip() + "\n").encode("utf-8")


def assemble(
    base_bytes: bytes,
    edge_bytes: bytes,
    changed_raw: Any,
    candidate_raws: list[Any],
    approach_id: str,
) -> tuple[bytes, dict[str, Any]]:
    if approach_id not in ASSEMBLY_APPROACHES:
        raise ValueError("approach_id is not a strict-assembly approach")
    if not base_bytes:
        raise ValueError("frozen base review must not be empty")
    edge_raw = json.loads(edge_bytes.decode("utf-8"))
    analysis_base, risks = validate_edge_index(edge_raw)
    changed_base, head_sha, changed = validate_changed_lines(changed_raw)
    if analysis_base != changed_base:
        raise ValueError("edge analysis base does not match changed-line base")
    base_digest = digest(base_bytes)
    edge_digest = digest(edge_bytes)
    decisions = normalize_candidates(
        candidate_raws,
        approach_id=approach_id,
        base_digest=base_digest,
        edge_digest=edge_digest,
        risk_ids=set(risks),
        changed=changed,
    )
    seen_risks = {decision["risk_id"] for decision in decisions}
    if approach_id == "conditional-high-impact-challenger":
        expected_risks = {
            risk_id
            for risk_id, risk in risks.items()
            if risk["impact_signal"] == "high"
        }
    else:
        expected_risks = set(risks)
    if seen_risks != expected_risks:
        missing = sorted(expected_risks - seen_risks)
        extra = sorted(seen_risks - expected_risks)
        raise ValueError(
            f"candidate decisions do not cover the expected risks; missing={missing}, extra={extra}"
        )
    appendix = render_findings(decisions)
    if appendix:
        separator = b"" if base_bytes.endswith(b"\n") else b"\n"
        output = base_bytes + separator + appendix
    else:
        output = base_bytes
    counts = Counter(decision["disposition"] for decision in decisions)
    confirmed = [decision for decision in decisions if decision["finding"] is not None]
    audit = {
        "schema_version": 1,
        "approach_id": approach_id,
        "analysis_base": analysis_base,
        "head_sha": head_sha,
        "base_review_sha256": base_digest,
        "edge_index_sha256": edge_digest,
        "output_sha256": digest(output),
        "base_bytes_preserved": output.startswith(base_bytes),
        "output_equals_base": output == base_bytes,
        "candidate_files": len(candidate_raws),
        "decisions": len(decisions),
        "disposition_counts": {key: counts.get(key, 0) for key in sorted(DISPOSITIONS)},
        "confirmed_risk_ids": [decision["risk_id"] for decision in confirmed],
        "confirmed_root_causes": [
            decision["finding"]["root_cause_key"] for decision in confirmed
        ],
    }
    return output, audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-review", required=True, type=Path)
    parser.add_argument("--edge-index", required=True, type=Path)
    parser.add_argument("--changed-lines", required=True, type=Path)
    parser.add_argument("--approach-id", required=True)
    parser.add_argument("--candidate", required=True, action="append", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    args = parser.parse_args()
    try:
        base_bytes = args.base_review.read_bytes()
        edge_bytes = args.edge_index.read_bytes()
        changed_raw = json.loads(args.changed_lines.read_text(encoding="utf-8"))
        candidate_raws = [
            json.loads(path.read_text(encoding="utf-8")) for path in args.candidate
        ]
        output, audit = assemble(
            base_bytes,
            edge_bytes,
            changed_raw,
            candidate_raws,
            args.approach_id,
        )
        args.output.write_bytes(output)
        args.audit.write_text(
            json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
