#!/usr/bin/env python3
"""Read an explicit, bounded set of text artifacts without following links."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path


DEFAULT_MAX_ARTIFACTS = 8
DEFAULT_MAX_BYTES = 64 * 1024
INSTRUCTION_NAMES = {
    "agents.md",
    "claude.md",
    "claude.local.md",
}
RESTRICTED_NAMES = {
    ".env",
    ".env.local",
    "credentials",
    "credentials.json",
    "id_dsa",
    "id_ed25519",
    "id_rsa",
}


def lexical_root(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def relative_artifact(path: Path, root: Path) -> Path:
    if path.is_absolute():
        candidate = Path(os.path.abspath(os.fspath(path.expanduser())))
        try:
            relative = candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"artifact is outside the authorized root: {candidate}") from exc
    else:
        relative = path
    if not relative.parts or relative == Path("."):
        raise ValueError("artifact must name a file below the authorized root")
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"artifact path must be normalized and relative: {path}")
    return relative


def open_parent(root: Path, relative: Path) -> tuple[int, str]:
    required = {os.open, os.stat}
    if not required.issubset(os.supports_dir_fd):
        raise RuntimeError("this platform lacks required dir-fd operations")
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
        raise ValueError(f"{label} must be a regular file; links and special files are refused")
    if details.st_nlink != 1:
        raise ValueError(f"{label} has {details.st_nlink} hard links; provenance is ambiguous")


def restricted(relative: Path, allowed: set[str]) -> bool:
    normalized = relative.as_posix()
    if normalized in allowed:
        return False
    lowered = relative.name.casefold()
    lowered_parts = tuple(part.casefold() for part in relative.parts)
    if (
        lowered in INSTRUCTION_NAMES
        or lowered in RESTRICTED_NAMES
        or lowered.startswith(".env")
        or lowered.endswith((".key", ".pem", ".p12", ".pfx"))
    ):
        return True
    if ".claude" in lowered_parts and "rules" in lowered_parts:
        return True
    return False


def read_one(root: Path, relative: Path, *, remaining: int) -> dict[str, object]:
    parent_fd, name = open_parent(root, relative)
    source_fd: int | None = None
    try:
        before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        regular_single_link(before, label=relative.as_posix())
        if before.st_size > remaining:
            raise ValueError(
                f"content budget exceeded by {relative.as_posix()}: "
                f"{before.st_size} bytes exceeds {remaining} remaining"
            )
        source_fd = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        opened = os.fstat(source_fd)
        regular_single_link(opened, label=relative.as_posix())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"artifact changed while opening: {relative.as_posix()}")

        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(source_fd, min(1024 * 1024, remaining - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > remaining:
                raise ValueError(f"content budget exceeded while reading {relative.as_posix()}")
            chunks.append(chunk)

        after = os.fstat(source_fd)
        identity_before = (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
        )
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        )
        if identity_before != identity_after:
            raise RuntimeError(f"artifact changed while reading: {relative.as_posix()}")

        payload = b"".join(chunks)
        if b"\x00" in payload:
            raise ValueError(f"artifact is not text: {relative.as_posix()}")
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"artifact is not valid UTF-8 text: {relative.as_posix()}") from exc
        return {
            "path": relative.as_posix(),
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "text": text,
        }
    finally:
        if source_fd is not None:
            os.close(source_fd)
        os.close(parent_fd)


def inspect(
    root: Path,
    paths: list[Path],
    *,
    max_artifacts: int = DEFAULT_MAX_ARTIFACTS,
    max_bytes: int = DEFAULT_MAX_BYTES,
    allow_restricted: set[str] | None = None,
) -> dict[str, object]:
    root = lexical_root(root)
    root_details = os.stat(root, follow_symlinks=False)
    if not stat.S_ISDIR(root_details.st_mode):
        raise ValueError("authorized root must be a real directory, not a link or special file")
    if len(paths) > max_artifacts:
        raise ValueError(f"artifact budget exceeded: {len(paths)} requested, limit is {max_artifacts}")

    allowed = allow_restricted or set()
    relatives: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        relative = relative_artifact(path, root)
        normalized = relative.as_posix()
        if normalized in seen:
            continue
        if restricted(relative, allowed):
            raise ValueError(
                f"restricted artifact refused: {normalized}; explicitly allow this exact subject"
            )
        seen.add(normalized)
        relatives.append(relative)
    if len(relatives) > max_artifacts:
        raise ValueError(
            f"artifact budget exceeded: {len(relatives)} unique paths, limit is {max_artifacts}"
        )

    artifacts: list[dict[str, object]] = []
    used_bytes = 0
    for relative in relatives:
        artifact = read_one(root, relative, remaining=max_bytes - used_bytes)
        used_bytes += int(artifact["bytes"])
        artifacts.append(artifact)
    return {
        "root": os.fspath(root),
        "limits": {"artifacts": max_artifacts, "bytes": max_bytes},
        "used": {"artifacts": len(artifacts), "bytes": used_bytes},
        "artifacts": artifacts,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--max-artifacts", type=int, default=DEFAULT_MAX_ARTIFACTS)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument(
        "--allow-restricted",
        action="append",
        default=[],
        metavar="RELATIVE_PATH",
        help="allow an exact restricted artifact when it is the research subject",
    )
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args(argv[1:])
    if not 1 <= args.max_artifacts <= DEFAULT_MAX_ARTIFACTS:
        parser.error(f"--max-artifacts must be between 1 and {DEFAULT_MAX_ARTIFACTS}")
    if not 1 <= args.max_bytes <= DEFAULT_MAX_BYTES:
        parser.error(f"--max-bytes must be between 1 and {DEFAULT_MAX_BYTES}")
    root = lexical_root(args.root)
    try:
        allowed = {
            relative_artifact(Path(path), root).as_posix()
            for path in args.allow_restricted
        }
        result = inspect(
            root,
            args.paths,
            max_artifacts=args.max_artifacts,
            max_bytes=args.max_bytes,
            allow_restricted=allowed,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"bounded inspection refused: {exc}", file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
