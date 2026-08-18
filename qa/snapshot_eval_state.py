#!/usr/bin/env python3
"""Capture bounded post-eval evidence without following fixture-controlled links."""

from __future__ import annotations

import argparse
import json
import os
import resource
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

MAX_FILES = 256
MAX_DEPTH = 10
MAX_FILE_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024
MAX_GIT_BYTES = 2 * 1024 * 1024
DIR_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_NOFOLLOW", 0)
)
FILE_FLAGS = (
    os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
)


class SnapshotError(RuntimeError):
    pass


def _state(details: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        stat.S_IFMT(details.st_mode),
        details.st_dev,
        details.st_ino,
        details.st_size,
        details.st_mtime_ns,
        details.st_ctime_ns,
        details.st_nlink,
    )


def _root(path: Path) -> tuple[Path, int]:
    root = Path(os.path.abspath(os.fspath(path)))
    details = root.lstat()
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
        raise SnapshotError("work root must be a real directory")
    fd = os.open(root, DIR_FLAGS)
    opened = os.fstat(fd)
    if (details.st_dev, details.st_ino) != (opened.st_dev, opened.st_ino):
        os.close(fd)
        raise SnapshotError("work root changed while it was opened")
    return root, fd


def _read_file_at(parent_fd: int, name: str) -> tuple[str | None, str]:
    try:
        before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as exc:
        return None, f"unreadable metadata: {type(exc).__name__}"
    if stat.S_ISLNK(before.st_mode):
        return None, "blocked symlink"
    if not stat.S_ISREG(before.st_mode):
        return None, "blocked non-regular file"
    if before.st_nlink != 1:
        return None, "blocked hard-linked file"
    if before.st_size > MAX_FILE_BYTES:
        return None, f"blocked file larger than {MAX_FILE_BYTES} bytes"
    try:
        fd = os.open(name, FILE_FLAGS, dir_fd=parent_fd)
    except OSError as exc:
        return None, f"unreadable file: {type(exc).__name__}"
    try:
        opened = os.fstat(fd)
        if _state(before) != _state(opened):
            return None, "file changed while it was opened"
        chunks: list[bytes] = []
        remaining = MAX_FILE_BYTES + 1
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        finished = os.fstat(fd)
        if (
            len(data) > MAX_FILE_BYTES
            or _state(opened) != _state(finished)
            or len(data) != finished.st_size
        ):
            return None, "file changed or exceeded its limit while read"
    finally:
        os.close(fd)
    return data.decode("utf-8", errors="replace"), "captured"


def _open_relative_parent(root_fd: int, relative: PurePosixPath) -> tuple[int, str]:
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise SnapshotError("unsafe relative path")
    current = os.dup(root_fd)
    try:
        for part in relative.parts[:-1]:
            following = os.open(part, DIR_FLAGS, dir_fd=current)
            os.close(current)
            current = following
        return current, relative.parts[-1]
    except Exception:
        os.close(current)
        raise


def _capture_relative(root_fd: int, relative: str) -> tuple[str | None, str]:
    path = PurePosixPath(relative)
    try:
        parent, name = _open_relative_parent(root_fd, path)
    except (OSError, SnapshotError) as exc:
        return None, f"blocked path: {type(exc).__name__}"
    try:
        return _read_file_at(parent, name)
    finally:
        os.close(parent)


def _walk_memory(root_fd: int) -> str:
    try:
        ai_fd = os.open(".ai", DIR_FLAGS, dir_fd=root_fd)
        memory_fd = os.open("memory", DIR_FLAGS, dir_fd=ai_fd)
    except FileNotFoundError:
        try:
            os.close(ai_fd)
        except (NameError, OSError):
            pass
        return ""
    except OSError as exc:
        try:
            os.close(ai_fd)
        except (NameError, OSError):
            pass
        return f"[memory directory blocked: {type(exc).__name__}]\n"

    lines: list[str] = []
    count = 0
    total = 0

    def visit(directory_fd: int, prefix: PurePosixPath, depth: int) -> None:
        nonlocal count, total
        if depth > MAX_DEPTH:
            lines.append(f"[blocked depth beyond {MAX_DEPTH}: {json.dumps(str(prefix))}]")
            return
        try:
            names = sorted(os.listdir(directory_fd))
        except OSError as exc:
            lines.append(
                f"[directory unreadable: {json.dumps(str(prefix))}: {type(exc).__name__}]"
            )
            return
        for name in names:
            relative = prefix / name
            if count >= MAX_FILES or total >= MAX_TOTAL_BYTES:
                lines.append("[memory snapshot budget exhausted]")
                return
            count += 1
            try:
                details = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except OSError as exc:
                lines.append(
                    f"[blocked {json.dumps(str(relative))}: {type(exc).__name__}]"
                )
                continue
            if stat.S_ISDIR(details.st_mode) and not stat.S_ISLNK(details.st_mode):
                try:
                    child = os.open(name, DIR_FLAGS, dir_fd=directory_fd)
                except OSError as exc:
                    lines.append(
                        f"[blocked directory {json.dumps(str(relative))}: "
                        f"{type(exc).__name__}]"
                    )
                    continue
                try:
                    visit(child, relative, depth + 1)
                finally:
                    os.close(child)
                continue
            text, status = _read_file_at(directory_fd, name)
            lines.append(f"\n--- {json.dumps(str(relative))} ({status}) ---")
            if text is not None:
                encoded = text.encode("utf-8", errors="replace")
                if total + len(encoded) > MAX_TOTAL_BYTES:
                    lines.append("[content omitted: total snapshot budget exhausted]")
                    total = MAX_TOTAL_BYTES
                else:
                    total += len(encoded)
                    lines.append(text)

    try:
        visit(memory_fd, PurePosixPath("memory"), 0)
    finally:
        os.close(memory_fd)
        os.close(ai_fd)
    return "\n".join(lines).rstrip() + ("\n" if lines else "")


def _git_binary() -> str:
    path = shutil.which(
        "git",
        path="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin",
    )
    if not path:
        raise SnapshotError("trusted git executable was not found")
    return path


def _limit_output() -> None:
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_GIT_BYTES, MAX_GIT_BYTES))


def _git(root: Path, arguments: list[str]) -> tuple[int, bytes]:
    environment = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin",
        "HOME": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_PAGER": "cat",
        "PAGER": "cat",
        "GIT_OPTIONAL_LOCKS": "0",
        "LC_ALL": "C",
    }
    common = [
        _git_binary(),
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        "-c",
        "core.attributesFile=/dev/null",
        "-c",
        "core.excludesFile=/dev/null",
        "-c",
        "submodule.recurse=false",
        "--no-pager",
    ]
    with tempfile.TemporaryFile() as output:
        try:
            completed = subprocess.run(
                [*common, *arguments],
                cwd=root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=15,
                check=False,
                preexec_fn=_limit_output,
            )
        except subprocess.TimeoutExpired:
            return 124, b"[git evidence command timed out]\n"
        output.seek(0)
        data = output.read(MAX_GIT_BYTES)
    if len(data) >= MAX_GIT_BYTES:
        data = data[:MAX_GIT_BYTES] + b"\n[git evidence truncated]\n"
    return completed.returncode, data


def _git_evidence(root: Path, root_fd: int) -> dict[str, str]:
    git_entry = root / ".git"
    try:
        details = git_entry.lstat()
    except OSError:
        return {}
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
        return {"git_status.txt": "[blocked unsafe .git directory]\n"}

    commands = {
        "git_status.txt": ["status", "--porcelain", "--untracked-files=all"],
        "git_log.txt": ["log", "--no-show-signature", "--oneline", "-n", "8"],
        "git_diff.txt": ["diff", "--no-ext-diff", "--no-textconv", "HEAD"],
        "git_log_full.txt": [
            "log",
            "--no-show-signature",
            "--no-ext-diff",
            "--no-textconv",
            "-p",
            "-n",
            "8",
        ],
    }
    evidence: dict[str, str] = {}
    for name, command in commands.items():
        code, output = _git(root, command)
        text = output.decode("utf-8", errors="replace")
        if code and not text:
            text = f"[git command exited {code}]\n"
        evidence[name] = text

    code, output = _git(root, ["ls-files", "-z", "--others", "--exclude-standard"])
    lines: list[str] = []
    if code == 0:
        for raw in output.split(b"\0"):
            if not raw:
                continue
            relative = raw.decode("utf-8", errors="surrogateescape")
            text, status = _capture_relative(root_fd, relative)
            lines.append(f"\n=== untracked: {json.dumps(relative)} ({status}) ===")
            if text is not None:
                lines.append(text)
    else:
        lines.append(f"[git untracked listing exited {code}]")
    evidence["untracked.txt"] = "\n".join(lines).rstrip() + ("\n" if lines else "")
    return evidence


def capture(work: Path, output: Path) -> None:
    root, root_fd = _root(work)
    try:
        output.mkdir(parents=True, exist_ok=False)
        (output / "memory.txt").write_text(_walk_memory(root_fd), encoding="utf-8")
        for name, text in _git_evidence(root, root_fd).items():
            (output / name).write_text(text, encoding="utf-8")
    finally:
        os.close(root_fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        capture(args.work, args.output)
    except (OSError, SnapshotError) as exc:
        print(f"eval state snapshot refused: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
