#!/usr/bin/env python3
"""Run one exact-replacement mutation trial and restore in a finally block.

Exit codes: 0 = mutated run exited nonzero and the clean rerun passed; 1 = trial
refused or errored; 2 = clean rerun failed after restore; 3 = trial completed and
the mutation survived (target test stayed green with the mutant installed).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import signal
import stat
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from mutation_backup import (
    backup,
    claim_target,
    current_sha256,
    inode_identity,
    open_sha256_at,
    open_parent,
    publish_no_replace,
    regular_single_link,
    relink_claim,
    relative_under_root,
    return_claim_if_target_absent,
    restore,
    sha256_at,
    unlink_if_identity,
    unlink_if_same_inode,
    verify_backup,
    write_all,
)


class TerminationRequested(RuntimeError):
    """Raised so SIGTERM still executes Python cleanup."""


def request_termination(signum: int, _frame: object) -> None:
    raise TerminationRequested(f"received signal {signum}")


def read_target(root: Path, relative: Path) -> tuple[bytes, int, tuple[int, int]]:
    parent_fd, name = open_parent(root, relative)
    source_fd: int | None = None
    try:
        details = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        regular_single_link(details, label="mutation target")
        source_fd = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        opened = os.fstat(source_fd)
        regular_single_link(opened, label="opened mutation target")
        if (opened.st_dev, opened.st_ino) != (details.st_dev, details.st_ino):
            raise RuntimeError("mutation target changed while opening")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(source_fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(source_fd)
        identity = (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
        if identity != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise RuntimeError("mutation target changed while reading")
        return b"".join(chunks), stat.S_IMODE(opened.st_mode), (opened.st_dev, opened.st_ino)
    finally:
        if source_fd is not None:
            os.close(source_fd)
        os.close(parent_fd)


def atomic_replace(
    root: Path,
    relative: Path,
    payload: bytes,
    *,
    mode: int,
    expected_original_sha256: str,
    expected_mutant_sha256: str,
    on_publish: Callable[[], None] | None = None,
) -> None:
    parent_fd, name = open_parent(root, relative)
    temporary_name = f".{name}.muttrial.tmp.{os.getpid()}.{secrets.token_hex(8)}"
    temporary_fd: int | None = None
    temporary_identity: tuple[int, int] | None = None
    original_claim: str | None = None
    original_claim_identity: tuple[int, int] | None = None
    original_claim_fd: int | None = None
    try:
        temporary_fd = os.open(
            temporary_name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_fd,
        )
        temporary_identity = inode_identity(os.fstat(temporary_fd))
        write_all(temporary_fd, payload)
        os.fchmod(temporary_fd, mode)
        os.fsync(temporary_fd)

        original_claim = claim_target(parent_fd, name, label="mutorigin")
        original_claim_identity = inode_identity(
            os.stat(original_claim, dir_fd=parent_fd, follow_symlinks=False)
        )
        claimed_digest, hashed_claim_identity, original_claim_fd = open_sha256_at(
            parent_fd,
            original_claim,
            label="claimed original mutation target",
        )
        if hashed_claim_identity != original_claim_identity:
            raise RuntimeError("claimed original mutation target changed while being verified")
        if claimed_digest != expected_original_sha256:
            try:
                relink_claim(
                    parent_fd,
                    original_claim,
                    name,
                    expected_identity=original_claim_identity,
                )
                original_claim = None
            except FileExistsError:
                pass
            raise RuntimeError(
                "mutation target changed after backup and before mutant installation; "
                "the changed target was preserved"
            )

        if on_publish is not None:
            # Fires before the link so the caller treats the mutant as possibly
            # installed on every failure path from here on.
            on_publish()
        try:
            publish_no_replace(parent_fd, temporary_name, name)
        except FileExistsError as exc:
            raise RuntimeError(
                "a new target appeared during mutant publication; it was not overwritten and "
                f"the original claim remains at {root / relative.parent / original_claim}"
            ) from exc

        latest_claim_digest, _latest_claim_identity = sha256_at(
            parent_fd,
            original_claim,
            label="claimed original mutation target",
        )
        if latest_claim_digest != expected_original_sha256:
            if unlink_if_same_inode(parent_fd, name, temporary_name):
                try:
                    relink_claim(
                        parent_fd,
                        original_claim,
                        name,
                        expected_identity=original_claim_identity,
                    )
                    original_claim = None
                except FileExistsError:
                    pass
            raise RuntimeError(
                "original target changed while the mutant was being published; "
                "the concurrent edit was preserved"
            )

        if not unlink_if_identity(
            parent_fd,
            temporary_name,
            temporary_identity,
            label="temporary mutant cleanup",
        ):
            raise RuntimeError("temporary mutant inode changed during cleanup")
        temporary_identity = None
        if current_sha256(root / relative, root=root) != expected_mutant_sha256:
            raise RuntimeError(
                "published mutant changed during installation; preserving the current target, "
                f"original claim, and backup at {root / relative.parent}"
            )
        if not unlink_if_identity(
            parent_fd,
            original_claim,
            original_claim_identity,
            label="original mutation claim cleanup",
        ):
            raise RuntimeError("original mutation claim changed during cleanup; it was preserved")
        original_claim = None
        os.close(original_claim_fd)
        original_claim_fd = None
    except Exception:
        if (
            original_claim is not None
            and original_claim_identity is not None
            and return_claim_if_target_absent(
                parent_fd,
                original_claim,
                name,
                expected_identity=original_claim_identity,
            )
        ):
            original_claim = None
        if temporary_identity is not None:
            try:
                unlink_if_identity(
                    parent_fd,
                    temporary_name,
                    temporary_identity,
                    label="failed temporary mutant cleanup",
                )
            except (OSError, RuntimeError):
                pass
        raise
    finally:
        if original_claim_fd is not None:
            os.close(original_claim_fd)
        if temporary_fd is not None:
            os.close(temporary_fd)
        os.close(parent_fd)


def run_trial(
    path: Path,
    *,
    root: Path,
    old: bytes,
    new: bytes,
    test_command: list[str],
) -> dict[str, object]:
    root = Path(os.path.abspath(os.fspath(root.expanduser())))
    relative = relative_under_root(path, root)
    if not old:
        raise ValueError("original mutation text must not be empty")
    if not test_command:
        raise ValueError("target test command is required")

    original, mode, _identity = read_target(root, relative)
    occurrences = original.count(old)
    if occurrences != 1:
        raise ValueError(
            f"exact original mutation text must occur once; found {occurrences} occurrences"
        )
    mutated = original.replace(old, new, 1)
    original_digest = hashlib.sha256(original).hexdigest()
    mutated_digest = hashlib.sha256(mutated).hexdigest()

    backup(path, root=root)
    mutated_result: subprocess.CompletedProcess[bytes] | None = None
    mutant_installed = False

    def mark_mutant_installed() -> None:
        nonlocal mutant_installed
        mutant_installed = True

    try:
        metadata = verify_backup(path, root=root)
        if metadata["sha256"] != original_digest:
            raise RuntimeError("backup digest does not match the target selected for mutation")
        atomic_replace(
            root,
            relative,
            mutated,
            mode=mode,
            expected_original_sha256=original_digest,
            expected_mutant_sha256=mutated_digest,
            on_publish=mark_mutant_installed,
        )
        if hashlib.sha256(read_target(root, relative)[0]).hexdigest() != mutated_digest:
            raise RuntimeError("installed mutant digest does not match the selected mutation")
        mutated_result = subprocess.run(test_command, cwd=root, check=False)
    finally:
        if mutant_installed:
            restore(path, root=root, expected_current_sha256=mutated_digest)

    restored, _restored_mode, _restored_identity = read_target(root, relative)
    if hashlib.sha256(restored).hexdigest() != original_digest:
        raise RuntimeError("restored target digest does not match the original")
    clean_result = subprocess.run(test_command, cwd=root, check=False)
    return {
        "target": relative.as_posix(),
        "mutation_test_exit": mutated_result.returncode,
        "mutation_outcome": "nonzero" if mutated_result.returncode != 0 else "survived",
        "interpretation": (
            "inspect the target-test failure output before deciding whether the intended "
            "regression was detected"
            if mutated_result.returncode != 0
            else "the selected mutation survived the target test"
        ),
        "restored_test_exit": clean_result.returncode,
        "restored_sha256": original_digest,
    }


def main(argv: list[str]) -> int:
    try:
        separator = argv.index("--")
    except ValueError:
        separator = -1
    option_arguments = argv[1:separator] if separator >= 0 else argv[1:]
    command = argv[separator + 1 :] if separator >= 0 else []
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--old", required=True)
    parser.add_argument("--new", required=True)
    args = parser.parse_args(option_arguments)
    previous_term = signal.signal(signal.SIGTERM, request_termination)
    try:
        result = run_trial(
            args.file,
            root=args.root,
            old=args.old.encode("utf-8"),
            new=args.new.encode("utf-8"),
            test_command=command,
        )
    except (OSError, RuntimeError, ValueError, TerminationRequested) as exc:
        print(f"mutation trial refused: {exc}", file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous_term)
    print(json.dumps(result, sort_keys=True))
    if result["restored_test_exit"] != 0:
        return 2
    return 3 if result["mutation_outcome"] == "survived" else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
