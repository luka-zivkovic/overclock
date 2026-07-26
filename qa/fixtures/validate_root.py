#!/usr/bin/env python3
"""Validate a fresh eval-fixture root without trusting marker files."""

from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path


def _contains(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def validate_root(candidate: Path, repository: Path) -> Path:
    root = candidate.expanduser().resolve(strict=False)
    repo = repository.expanduser().resolve(strict=True)
    home = Path.home().resolve(strict=True)

    if root == Path("/") or root == home or root == repo:
        raise ValueError("fixture root may not be /, the home directory, or the repository")
    if _contains(root, home) or _contains(root, repo):
        raise ValueError("fixture root may not contain the home directory or repository")

    temp_roots = {
        Path(value).expanduser().resolve(strict=False)
        for value in (
            tempfile.gettempdir(),
            os.environ.get("TMPDIR", ""),
            "/tmp",
            "/private/tmp",
            "/var/tmp",
        )
        if value
    }
    temp_roots = {
        candidate
        for candidate in temp_roots
        if candidate != Path("/")
        and candidate != home
        and not _contains(home, candidate)
        and not _contains(repo, candidate)
    }
    if not any(_contains(temp_root, root) for temp_root in temp_roots):
        raise ValueError("fixture root must be below a recognized temporary directory")

    # Fixtures must not inherit a surrounding repository. Skills deliberately use
    # nearest-repository discovery, so nesting would also make eval writes escape.
    for ancestor in (root, *root.parents):
        git_entry = ancestor / ".git"
        if git_entry.exists() or git_entry.is_symlink():
            raise ValueError(f"fixture root is inside a git repository: {ancestor}")

    if root.exists() or root.is_symlink():
        details = root.lstat()
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
            raise ValueError("fixture root must be a real directory")
        if details.st_uid != os.geteuid():
            raise ValueError("fixture root must be owned by the current user")
        try:
            next(root.iterdir())
        except StopIteration:
            pass
        else:
            raise ValueError("fixture root must be empty; refusing to wipe existing data")
    else:
        root.mkdir(parents=True, mode=0o700)
    return root


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: validate_root.py FIXTURE_ROOT REPOSITORY", file=sys.stderr)
        return 2
    try:
        print(validate_root(Path(argv[1]), Path(argv[2])))
    except (OSError, ValueError) as exc:
        print(f"unsafe fixture root: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
