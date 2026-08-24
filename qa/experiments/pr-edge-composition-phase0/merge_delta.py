#!/usr/bin/env python3
"""Append a validated late-reveal delta without rewriting the frozen base review."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PRIORITIES = {"P0", "P1", "P2"}


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or any(not nonempty(item) for item in value):
        raise ValueError(f"{field} must be a list of non-empty strings")
    return [item.strip() for item in value]


def normalized_delta(raw: Any, expected_digest: str) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(raw, dict):
        raise ValueError("delta must be an object")
    allowed = {
        "base_review_sha256",
        "verified_additions",
        "strengthening_notes",
        "rejected_brief_risks",
    }
    if set(raw) != allowed:
        raise ValueError("delta fields must exactly match the late-reveal contract")
    digest = raw["base_review_sha256"]
    if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
        raise ValueError("base_review_sha256 must be 64 lowercase hexadecimal characters")
    if digest != expected_digest:
        raise ValueError("delta does not target the frozen base review")

    additions = raw["verified_additions"]
    strengthenings = raw["strengthening_notes"]
    rejections = raw["rejected_brief_risks"]
    if not all(isinstance(value, list) for value in (additions, strengthenings, rejections)):
        raise ValueError("delta collections must be arrays")

    normalized_additions: list[dict[str, Any]] = []
    addition_fields = {
        "priority",
        "title",
        "location",
        "failure_path",
        "impact",
        "evidence",
        "suggested_comment",
        "brief_origin",
    }
    for index, item in enumerate(additions):
        if not isinstance(item, dict) or set(item) != addition_fields:
            raise ValueError(f"verified_additions[{index}] has invalid fields")
        if item["priority"] not in PRIORITIES:
            raise ValueError(f"verified_additions[{index}].priority is invalid")
        for field in addition_fields - {"priority", "evidence"}:
            if not nonempty(item[field]):
                raise ValueError(f"verified_additions[{index}].{field} must be non-empty")
        normalized_additions.append(
            {
                **{field: item[field].strip() for field in addition_fields - {"evidence"}},
                "evidence": string_list(item["evidence"], f"verified_additions[{index}].evidence"),
            }
        )

    normalized_strengthenings: list[dict[str, str]] = []
    for index, item in enumerate(strengthenings):
        fields = {"base_finding", "note", "brief_origin"}
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError(f"strengthening_notes[{index}] has invalid fields")
        if any(not nonempty(item[field]) for field in fields):
            raise ValueError(f"strengthening_notes[{index}] fields must be non-empty")
        normalized_strengthenings.append({field: item[field].strip() for field in fields})

    normalized_rejections: list[dict[str, str]] = []
    for index, item in enumerate(rejections):
        fields = {"brief_origin", "reason"}
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError(f"rejected_brief_risks[{index}] has invalid fields")
        if any(not nonempty(item[field]) for field in fields):
            raise ValueError(f"rejected_brief_risks[{index}] fields must be non-empty")
        normalized_rejections.append({field: item[field].strip() for field in fields})

    return {
        "verified_additions": normalized_additions,
        "strengthening_notes": normalized_strengthenings,
        "rejected_brief_risks": normalized_rejections,
    }


def render_appendix(delta: dict[str, list[dict[str, Any]]]) -> str:
    lines = ["", "---", "", "## Verified edge delta", ""]
    additions = delta["verified_additions"]
    strengthenings = delta["strengthening_notes"]
    if not additions and not strengthenings:
        lines.append("No additional actionable findings survived implementation verification.")
        return "\n".join(lines) + "\n"

    for item in additions:
        lines.extend(
            [
                f"### [{item['priority']}] {item['title']}",
                "",
                f"**Location:** `{item['location']}`",
                "",
                f"**Failure path:** {item['failure_path']}",
                "",
                f"**Impact:** {item['impact']}",
                "",
                "**Evidence:**",
                "",
                *[f"- {evidence}" for evidence in item["evidence"]],
                "",
                f"**Suggested comment:** {item['suggested_comment']}",
                "",
                f"**Edge-brief origin:** {item['brief_origin']}",
                "",
            ]
        )
    for item in strengthenings:
        lines.extend(
            [
                f"### Strengthening note — {item['base_finding']}",
                "",
                item["note"],
                "",
                f"**Edge-brief origin:** {item['brief_origin']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def merge(base_bytes: bytes, raw_delta: Any) -> tuple[bytes, dict[str, Any]]:
    digest = hashlib.sha256(base_bytes).hexdigest()
    delta = normalized_delta(raw_delta, digest)
    separator = b"" if base_bytes.endswith(b"\n") else b"\n"
    merged = base_bytes + separator + render_appendix(delta).encode("utf-8")
    audit = {
        "base_review_sha256": digest,
        "merged_sha256": hashlib.sha256(merged).hexdigest(),
        "base_bytes_preserved": merged.startswith(base_bytes),
        "verified_additions": len(delta["verified_additions"]),
        "strengthening_notes": len(delta["strengthening_notes"]),
        "rejected_brief_risks": len(delta["rejected_brief_risks"]),
    }
    return merged, audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-review", required=True, type=Path)
    parser.add_argument("--delta", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    args = parser.parse_args()
    try:
        base_bytes = args.base_review.read_bytes()
        raw_delta = json.loads(args.delta.read_text(encoding="utf-8"))
        merged, audit = merge(base_bytes, raw_delta)
        args.output.write_bytes(merged)
        args.audit.write_text(
            json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
