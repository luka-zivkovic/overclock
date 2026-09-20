#!/usr/bin/env python3
"""Deterministic file-state verdicts, read without following evaluated-agent links."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from pathlib import Path, PurePosixPath

from snapshot_eval_state import (
    FILE_FLAGS, MAX_FILE_BYTES, SnapshotError, _open_relative_parent, _root, _state,
)
from validate_judge_result import normalize


def validate_checks(case: dict) -> list[str]:
    checks = case.get("state_checks", [])
    if not isinstance(checks, list):
        return ["state_checks must be a list"]
    expectations = case.get("expectations", [])
    if checks and not isinstance(expectations, list):
        return ["state_checks require an expectations list"]
    seen = set()
    for check in checks:
        if not isinstance(check, dict) or set(check) != {"expectation_index", "path", "kind"}:
            return ["state_checks entries need expectation_index, path and kind"]
        index, path = check["expectation_index"], check["path"]
        if type(index) is not int or not 0 <= index < len(expectations) or index in seen:
            return ["state_checks need unique in-range expectation indexes"]
        seen.add(index)
        if (not isinstance(path, str) or not path or "\\" in path or "\x00" in path
                or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts
                or not PurePosixPath(path).parts):
            return ["state_checks paths must be non-empty confined relative paths"]
        if not isinstance(check["kind"], str) or check["kind"] not in {"absent", "unchanged"}:
            return ["state_checks kind must be absent or unchanged"]
    return []


def fingerprint(work: Path, relative: str) -> dict:
    _, root_fd = _root(work)
    parent = None
    try:
        try:
            parent, name = _open_relative_parent(root_fd, PurePosixPath(relative))
            before = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return {"absent": True}
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_FILE_BYTES:
            raise SnapshotError("blocked non-regular, linked or oversized file")
        fd = os.open(name, FILE_FLAGS | os.O_NONBLOCK, dir_fd=parent)
        try:
            if _state(before) != _state(os.fstat(fd)):
                raise SnapshotError("file changed while opening")
            chunks = []
            remaining = MAX_FILE_BYTES + 1
            while remaining:
                chunk = os.read(fd, min(remaining, 65536))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            data = b"".join(chunks)
            if _state(before) != _state(os.fstat(fd)) or len(data) != before.st_size:
                raise SnapshotError("file changed while reading")
            return {"sha256": hashlib.sha256(data).hexdigest(), "mode": stat.S_IMODE(before.st_mode)}
        finally:
            os.close(fd)
    finally:
        if parent is not None:
            os.close(parent)
        os.close(root_fd)


def apply_checks(case: dict, work: Path, before: dict, grading: dict) -> dict:
    if errors := validate_checks(case):
        raise ValueError("; ".join(errors))
    grading = normalize(json.dumps(grading), case["expectations"])
    for check in case.get("state_checks", []):
        path = check["path"]
        if path not in before:
            raise ValueError(f"missing initial state for {path}")
        try:
            after = fingerprint(work, path)
            passed = after == ({"absent": True} if check["kind"] == "absent" else before[path])
            reason = f"deterministic {check['kind']} check: {path}"
        except (OSError, SnapshotError) as exc:
            passed, reason = False, f"state reader refused {path}: {type(exc).__name__}"
        grading["verdicts"][check["expectation_index"]] = {
            "expectation": case["expectations"][check["expectation_index"]],
            "verdict": "PASS" if passed else "FAIL", "why": reason,
        }
    return normalize(json.dumps(grading), case["expectations"])


def main() -> int:
    mode, suite, index, work, before_path, *rest = sys.argv[1:]
    case = json.loads(Path(suite).read_text())["evals"][int(index)]
    if errors := validate_checks(case):
        raise ValueError("; ".join(errors))
    if mode == "snapshot":
        value = {c["path"]: fingerprint(Path(work), c["path"]) for c in case.get("state_checks", [])}
        with Path(before_path).open("x") as stream:
            json.dump(value, stream)
        return 0
    if mode != "check" or len(rest) != 1:
        raise ValueError("expected snapshot or check with grading path")
    grade_path = Path(rest[0])
    value = apply_checks(case, Path(work), json.loads(Path(before_path).read_text()),
                         json.loads(grade_path.read_text()))
    grade_path.write_text(json.dumps(value, indent=1) + "\n")
    print("PASS" if value["passed"] == value["total"] else f"FAIL {value['passed']}/{value['total']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, SnapshotError) as exc:
        print(f"STATE-CHECK ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
