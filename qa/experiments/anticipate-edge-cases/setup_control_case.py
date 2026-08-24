#!/usr/bin/env python3
"""Materialize one Anticipate Edge Cases control on a main/feature history."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path, PurePosixPath


CASES_PATH = Path(__file__).with_name("behavioral-controls.json")


def git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(
            completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        )
    return completed.stdout.strip()


def safe_relative(value: str) -> Path:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe fixture path: {value}")
    return Path(*path.parts)


def load_case(case_id: str) -> dict[str, object]:
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    matches = [case for case in data.get("cases", []) if case.get("id") == case_id]
    if len(matches) != 1:
        raise ValueError(f"unknown or duplicate control case: {case_id}")
    return matches[0]


def write_files(root: Path, files: list[dict[str, str]], field: str) -> None:
    for item in files:
        if field not in item:
            continue
        relative = safe_relative(item["path"])
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item[field], encoding="utf-8")
        git(root, "add", "--", relative.as_posix())


def materialize(case_id: str, output: Path) -> dict[str, str]:
    if output.exists():
        raise ValueError("output path already exists; choose a new directory")
    output.mkdir(parents=True)
    case = load_case(case_id)
    files = case.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("control case has no files")

    git(output, "init", "-q")
    git(output, "config", "user.email", "anticipate-edge-cases@example.com")
    git(output, "config", "user.name", "Anticipate Edge Cases Control")
    git(output, "checkout", "-qb", "main")
    write_files(output, files, "base")
    git(output, "commit", "-qm", "control base")
    base = git(output, "rev-parse", "HEAD")

    git(output, "checkout", "-qb", f"control/{case_id}")
    write_files(output, files, "head")
    changed = subprocess.run(
        ["git", "-C", str(output), "diff", "--cached", "--quiet"],
        check=False,
    )
    if changed.returncode == 0:
        raise ValueError("control case head makes no change")
    git(output, "commit", "-qm", "hidden implementation")
    head = git(output, "rev-parse", "HEAD")
    return {
        "case_id": case_id,
        "repository": str(output),
        "base": base,
        "head": head,
        "branch": git(output, "branch", "--show-current"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        result = materialize(args.case_id, args.output)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
