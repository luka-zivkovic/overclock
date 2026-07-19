#!/usr/bin/env python3
"""Atomically write the one PR Kit profile after validating stdin."""

from __future__ import annotations

import argparse
import os
import stat
import sys
import tempfile
from pathlib import Path

import profile_inputs
from validate_profile import MAX_BYTES, validate_text


def ensure_directory(path: Path) -> None:
    if path.is_symlink():
        raise ValueError(f"linked profile parent is forbidden: {path}")
    if path.exists():
        if not path.is_dir():
            raise ValueError(f"profile parent is not a directory: {path}")
        return
    path.mkdir(mode=0o755)


def write_profile(project_root: Path, text: str) -> tuple[Path, str]:
    if project_root.is_symlink():
        raise ValueError("project root must not be a symlink")
    root = project_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("project root is not a directory")

    profile_dir = root / ".ai" / "pr-kit"
    ensure_directory(root / ".ai")
    ensure_directory(profile_dir)
    target = profile_dir / "REPOSITORY.md"

    if target.is_symlink():
        raise ValueError("linked profile target is forbidden")
    action = "created"
    if target.exists():
        metadata = target.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("profile target must be a regular file")
        if metadata.st_nlink != 1:
            raise ValueError("hard-linked profile target is forbidden")
        action = "replaced"

    validate_text(text)
    profile_inputs.validate_profile_content(root, text)
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_BYTES:
        raise ValueError(f"profile exceeds {MAX_BYTES} bytes")

    fd, temporary_name = tempfile.mkstemp(
        prefix=".REPOSITORY.md.tmp.",
        dir=profile_dir,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, target)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    return target, action


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root", type=Path)
    args = parser.parse_args()
    raw = sys.stdin.buffer.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        print(f"ERROR: profile exceeds {MAX_BYTES} bytes", file=sys.stderr)
        return 1
    try:
        text = raw.decode("utf-8")
        target, action = write_profile(args.project_root, text)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"{action} valid profile: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
