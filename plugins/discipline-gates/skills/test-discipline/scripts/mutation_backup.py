#!/usr/bin/env python3
"""Safely back up and restore one mutation target without following links."""

from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path


def relative_under_root(path: Path, root: Path) -> Path:
    root = Path(os.path.abspath(os.fspath(root.expanduser())))
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = Path(os.path.abspath(os.fspath(candidate)))
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"mutation target is outside the authorized root: {candidate}") from exc
    if not relative.parts:
        raise ValueError("mutation target must be a file below the authorized root")
    return relative


def open_parent(root: Path, relative: Path) -> tuple[int, str]:
    required = {os.open, os.rename, os.stat, os.unlink}
    if not required.issubset(os.supports_dir_fd):
        raise RuntimeError("this platform lacks the dir-fd operations required for safe mutation backup")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    current = os.open(root, os.O_RDONLY | directory | nofollow)
    try:
        for component in relative.parts[:-1]:
            child = os.open(
                component,
                os.O_RDONLY | directory | nofollow,
                dir_fd=current,
            )
            os.close(current)
            current = child
        return current, relative.name
    except Exception:
        os.close(current)
        raise


def regular_single_link(details: os.stat_result, *, label: str) -> None:
    if not stat.S_ISREG(details.st_mode):
        raise ValueError(f"{label} must be a regular file; symlinks and special files are refused")
    if details.st_nlink != 1:
        raise ValueError(f"{label} has {details.st_nlink} hard links; refusing ambiguous restore")


def copy_all(source_fd: int, destination_fd: int) -> None:
    while True:
        chunk = os.read(source_fd, 1024 * 1024)
        if not chunk:
            break
        view = memoryview(chunk)
        while view:
            written = os.write(destination_fd, view)
            view = view[written:]


def backup(path: Path, *, root: Path) -> Path:
    relative = relative_under_root(path, root)
    parent_fd, name = open_parent(root, relative)
    source_fd = backup_fd = None
    backup_name = f"{name}.mutbak"
    try:
        details = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        regular_single_link(details, label="mutation target")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        source_fd = os.open(name, flags, dir_fd=parent_fd)
        opened = os.fstat(source_fd)
        regular_single_link(opened, label="opened mutation target")
        if (opened.st_dev, opened.st_ino) != (details.st_dev, details.st_ino):
            raise RuntimeError("mutation target changed while backup was being opened")

        backup_flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
        )
        backup_fd = os.open(backup_name, backup_flags, 0o600, dir_fd=parent_fd)
        copy_all(source_fd, backup_fd)
        os.fchmod(backup_fd, stat.S_IMODE(opened.st_mode))
        os.fsync(backup_fd)
    except Exception:
        if backup_fd is not None:
            os.close(backup_fd)
            backup_fd = None
            try:
                os.unlink(backup_name, dir_fd=parent_fd)
            except OSError:
                pass
        raise
    finally:
        if source_fd is not None:
            os.close(source_fd)
        if backup_fd is not None:
            os.close(backup_fd)
        os.close(parent_fd)
    return Path(root) / relative.parent / backup_name


def restore(path: Path, *, root: Path) -> Path:
    relative = relative_under_root(path, root)
    parent_fd, name = open_parent(root, relative)
    backup_name = f"{name}.mutbak"
    try:
        target_details = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        backup_details = os.stat(backup_name, dir_fd=parent_fd, follow_symlinks=False)
        regular_single_link(target_details, label="mutated target")
        regular_single_link(backup_details, label="mutation backup")
        os.rename(backup_name, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
    finally:
        os.close(parent_fd)
    return Path(root) / relative


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("backup", "restore"))
    parser.add_argument("file", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv[1:])
    root = Path(os.path.abspath(os.fspath(args.root.expanduser())))
    try:
        result = backup(args.file, root=root) if args.action == "backup" else restore(args.file, root=root)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"mutation backup refused: {exc}", file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
