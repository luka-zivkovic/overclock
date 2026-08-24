#!/usr/bin/env python3
"""Collect exact head-side changed lines for a pinned Git comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HUNK_RE = re.compile(
    r"^@@ -[0-9]+(?:,[0-9]+)? \+([0-9]+)(?:,([0-9]+))? @@"
)


def run_git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(message or f"git {' '.join(args)} failed")
    return result.stdout


def validate_commit(repo: Path, sha: str, label: str) -> None:
    if SHA_RE.fullmatch(sha) is None:
        raise ValueError(f"{label} must be a full lowercase 40-character SHA")
    run_git(repo, "cat-file", "-e", f"{sha}^{{commit}}")


def decode_diff_path(raw: bytes) -> str | None:
    if raw == b"/dev/null":
        return None
    if raw.startswith(b"b/"):
        raw = raw[2:]
    try:
        path = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("diff contains a non-UTF-8 path") from exc
    if not path or path.startswith("/") or any(part in {"", ".", ".."} for part in path.split("/")):
        raise ValueError(f"unsafe diff path: {path!r}")
    return path


def parse_changed_lines(diff: bytes) -> list[dict[str, object]]:
    changed: dict[str, set[int]] = {}
    current_path: str | None = None
    for raw_line in diff.splitlines():
        if raw_line.startswith(b"+++ "):
            current_path = decode_diff_path(raw_line[4:])
            if current_path is not None:
                changed.setdefault(current_path, set())
            continue
        if not raw_line.startswith(b"@@ ") or current_path is None:
            continue
        line = raw_line.decode("ascii", errors="strict")
        match = HUNK_RE.match(line)
        if match is None:
            raise ValueError(f"could not parse diff hunk: {line}")
        start = int(match.group(1))
        count = 1 if match.group(2) is None else int(match.group(2))
        if count > 0:
            changed[current_path].update(range(start, start + count))
    return [
        {"path": path, "lines": sorted(lines)}
        for path, lines in sorted(changed.items())
        if lines
    ]


def collect(repo: Path, base_sha: str, head_sha: str) -> dict[str, object]:
    validate_commit(repo, base_sha, "base SHA")
    validate_commit(repo, head_sha, "head SHA")
    diff = run_git(
        repo,
        "diff",
        "--unified=0",
        "--no-ext-diff",
        "--no-color",
        base_sha,
        head_sha,
        "--",
    )
    return {
        "schema_version": 1,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "diff_sha256": hashlib.sha256(diff).hexdigest(),
        "changed_lines": parse_changed_lines(diff),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        payload = collect(args.repo.resolve(), args.base, args.head)
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
