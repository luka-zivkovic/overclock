#!/usr/bin/env python3
"""Fail if any byte-identical file group in tools/shared-files.txt has drifted.

Some reference files are duplicated across skills by design (skills install
independently, so they cannot share a path at runtime). The duplication is only
safe while the copies stay byte-identical; this check makes drift a CI failure
instead of a silent format incompatibility.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "tools" / "shared-files.txt"


def main() -> int:
    failures = 0
    groups = 0
    for raw in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        paths = [REPO / p.strip() for p in line.split(",")]
        if len(paths) < 2:
            print(f"ERROR: manifest line needs >=2 paths: {line}", file=sys.stderr)
            failures += 1
            continue
        groups += 1
        missing = [p for p in paths if not p.exists()]
        if missing:
            for p in missing:
                print(f"ERROR: shared file missing: {p.relative_to(REPO)}", file=sys.stderr)
            failures += 1
            continue
        contents = {p: p.read_bytes() for p in paths}
        first = paths[0]
        for p in paths[1:]:
            if contents[p] != contents[first]:
                print(
                    f"ERROR: shared files drifted: {p.relative_to(REPO)} != "
                    f"{first.relative_to(REPO)} (edit one, copy to the other)",
                    file=sys.stderr,
                )
                failures += 1
    if failures:
        return 1
    print(f"OK: {groups} shared-file group(s) byte-identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
