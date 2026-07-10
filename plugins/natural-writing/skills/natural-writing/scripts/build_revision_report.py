#!/usr/bin/env python3
"""Build a safe, self-contained natural-writing revision report."""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

ALLOWED_TYPES = {"keep", "delete", "rewrite"}


def validate(data: object) -> dict:
    if not isinstance(data, dict):
        raise ValueError("report data must be a JSON object")
    for field in ("original", "revised"):
        if not isinstance(data.get(field), str):
            raise ValueError(f"{field} must be a string")
    if "title" in data and not isinstance(data["title"], str):
        raise ValueError("title must be a string when present")
    changes = data.get("changes")
    if not isinstance(changes, list):
        raise ValueError("changes must be a list")
    for index, change in enumerate(changes):
        if not isinstance(change, dict) or change.get("type") not in ALLOWED_TYPES:
            raise ValueError(f"changes[{index}] needs type keep, delete, or rewrite")
        kind = change["type"]
        required = ("text",) if kind in {"keep", "delete"} else ("before", "after")
        for field in required:
            if not isinstance(change.get(field), str):
                raise ValueError(f"changes[{index}].{field} must be a string")
        if kind != "keep" and not isinstance(change.get("reason"), str):
            raise ValueError(f"changes[{index}].reason must be a string")
    return data


def build(data_path: Path, output_path: Path) -> None:
    data = validate(json.loads(data_path.read_text(encoding="utf-8")))
    template_path = Path(__file__).resolve().parent.parent / "assets" / "revision-report.html"
    template = template_path.read_text(encoding="utf-8")
    marker = "__DATA_BASE64__"
    if template.count(marker) != 1:
        raise ValueError(f"template must contain exactly one {marker} marker")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded = base64.b64encode(payload).decode("ascii")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(template.replace(marker, encoded), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path, help="JSON file containing revision report data")
    parser.add_argument("output", type=Path, help="HTML report to create")
    args = parser.parse_args()
    build(args.data, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
