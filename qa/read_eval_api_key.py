#!/usr/bin/env python3
"""Read one private live-eval API key for Claude Code's apiKeyHelper."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path


def read_key(path: Path) -> str:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        details = os.fstat(fd)
        if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
            raise ValueError("eval API key must be a single-link regular file")
        if stat.S_IMODE(details.st_mode) & 0o077:
            raise ValueError("eval API key file must not be accessible by group or other")
        if details.st_size > 16_384:
            raise ValueError("eval API key is unexpectedly large")
        data = os.read(fd, 16_385)
    finally:
        os.close(fd)
    if len(data) > 16_384:
        raise ValueError("eval API key is unexpectedly large")
    value = data.decode("utf-8").strip()
    if not value or "\n" in value or "\r" in value:
        raise ValueError("eval API key must be one non-empty line")
    return value


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: read_eval_api_key.py KEY_FILE", file=sys.stderr)
        return 2
    try:
        print(read_key(Path(argv[1])))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"eval API key refused: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
