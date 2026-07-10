#!/usr/bin/env python3
"""Build a safe, self-contained natural-writing revision report."""
from __future__ import annotations

import argparse
import base64
import json
import os
import stat
import uuid
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


def relative_under_root(path: Path, root: Path) -> Path:
    boundary = Path(os.path.abspath(os.fspath(root.expanduser())))
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = boundary / candidate
    candidate = Path(os.path.abspath(os.fspath(candidate)))
    try:
        relative = candidate.relative_to(boundary)
    except ValueError as exc:
        raise ValueError(f"path escapes authorized root: {path}") from exc
    if not relative.parts:
        raise ValueError("path must name a file below the authorized root")
    return relative


def open_parent(root: Path, relative: Path, *, create: bool) -> int:
    required = {os.open, os.mkdir, os.stat, os.unlink, os.rename}
    if not required.issubset(os.supports_dir_fd):
        raise RuntimeError("secure report paths require dir_fd support")
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    current_fd = os.open(root, directory_flags)
    try:
        for part in relative.parts[:-1]:
            if create:
                try:
                    os.mkdir(part, mode=0o755, dir_fd=current_fd)
                except FileExistsError:
                    pass
            next_fd = os.open(part, directory_flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except Exception:
        os.close(current_fd)
        raise


def read_project_text(path: Path, *, root: Path) -> str:
    relative = relative_under_root(path, root)
    parent_fd = open_parent(root, relative, create=False)
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(relative.name, flags, dir_fd=parent_fd)
        details = os.fstat(fd)
        if not stat.S_ISREG(details.st_mode):
            os.close(fd)
            raise ValueError(f"input is not a regular file: {path}")
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            return handle.read()
    finally:
        os.close(parent_fd)


def write_project_text(
    path: Path, text: str, *, root: Path, replace: bool = False
) -> None:
    relative = relative_under_root(path, root)
    parent_fd = open_parent(root, relative, create=True)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    temporary_name: str | None = None
    try:
        if not replace:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow
            fd = os.open(relative.name, flags, 0o644, dir_fd=parent_fd)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(text)
            except Exception:
                try:
                    os.unlink(relative.name, dir_fd=parent_fd)
                except OSError:
                    pass
                raise
            return

        try:
            existing = os.stat(relative.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            existing = None
        if existing is not None and not stat.S_ISREG(existing.st_mode):
            raise ValueError(f"refusing to replace linked or non-regular output: {path}")
        temporary_name = f".{relative.name}.tmp-{uuid.uuid4().hex}"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow
        fd = os.open(temporary_name, flags, 0o644, dir_fd=parent_fd)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.rename(
            temporary_name,
            relative.name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
        temporary_name = None
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name, dir_fd=parent_fd)
            except OSError:
                pass
        os.close(parent_fd)


def build(
    data_path: Path,
    output_path: Path,
    *,
    root: Path | None = None,
    replace: bool = False,
) -> None:
    authorized_root = Path.cwd() if root is None else root
    authorized_root = Path(os.path.abspath(os.fspath(authorized_root.expanduser())))
    data = validate(json.loads(read_project_text(data_path, root=authorized_root)))
    template_path = Path(__file__).resolve().parent.parent / "assets" / "revision-report.html"
    template = template_path.read_text(encoding="utf-8")
    marker = "__DATA_BASE64__"
    if template.count(marker) != 1:
        raise ValueError(f"template must contain exactly one {marker} marker")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded = base64.b64encode(payload).decode("ascii")
    write_project_text(
        output_path,
        template.replace(marker, encoded),
        root=authorized_root,
        replace=replace,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path, help="JSON file containing revision report data")
    parser.add_argument("output", type=Path, help="HTML report to create")
    parser.add_argument(
        "--root", type=Path, default=Path.cwd(), help="authorized project output root"
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="replace an existing regular output file after explicit approval",
    )
    args = parser.parse_args()
    build(args.data, args.output, root=args.root, replace=args.replace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
