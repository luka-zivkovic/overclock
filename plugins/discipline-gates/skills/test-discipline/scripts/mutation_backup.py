#!/usr/bin/env python3
"""Atomically back up and restore one mutation target without following links."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import stat
import sys
from pathlib import Path
from typing import BinaryIO


MAGIC = b"OVERCLOCK_MUTBAK_V2"
LENGTH_BYTES = 8
COPY_CHUNK = 1024 * 1024
InodeIdentity = tuple[int, int]


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
    required = {os.link, os.open, os.rename, os.stat, os.unlink}
    if not required.issubset(os.supports_dir_fd):
        raise RuntimeError("this platform lacks the dir-fd operations required for safe backup")
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


def write_all(destination_fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(destination_fd, view)
        view = view[written:]


def copy_and_hash(
    source_fd: int,
    destination_fd: int,
    *,
    limit: int | None = None,
) -> tuple[int, str]:
    digest = hashlib.sha256()
    copied = 0
    while limit is None or copied < limit:
        amount = COPY_CHUNK if limit is None else min(COPY_CHUNK, limit - copied)
        chunk = os.read(source_fd, amount)
        if not chunk:
            break
        write_all(destination_fd, chunk)
        digest.update(chunk)
        copied += len(chunk)
    return copied, digest.hexdigest()


def valid_digest(value: str) -> bool:
    return (
        len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def current_sha256(path: Path, *, root: Path) -> str:
    """Hash one no-follow regular target and reject changes during the read."""
    relative = relative_under_root(path, root)
    parent_fd, name = open_parent(root, relative)
    source_fd: int | None = None
    sink: BinaryIO | None = None
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
            raise RuntimeError("mutation target changed while being opened")
        sink = open(os.devnull, "wb")
        copied, digest = copy_and_hash(source_fd, sink.fileno())
        after = os.fstat(source_fd)
        before_identity = (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if before_identity != after_identity or copied != opened.st_size:
            raise RuntimeError("mutation target changed while its digest was being captured")
        return digest
    finally:
        if sink is not None:
            sink.close()
        if source_fd is not None:
            os.close(source_fd)
        os.close(parent_fd)


def inode_identity(details: os.stat_result) -> InodeIdentity:
    return details.st_dev, details.st_ino


def sha256_at(parent_fd: int, name: str, *, label: str) -> tuple[str, InodeIdentity]:
    """Hash a no-follow adjacent file and return its stable device/inode identity."""
    source_fd: int | None = None
    sink: BinaryIO | None = None
    try:
        details = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        regular_single_link(details, label=label)
        source_fd = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        opened = os.fstat(source_fd)
        regular_single_link(opened, label=f"opened {label}")
        if (opened.st_dev, opened.st_ino) != (details.st_dev, details.st_ino):
            raise RuntimeError(f"{label} changed while being opened")
        sink = open(os.devnull, "wb")
        copied, digest = copy_and_hash(source_fd, sink.fileno())
        after = os.fstat(source_fd)
        identity_before = (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        )
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if identity_before != identity_after or copied != opened.st_size:
            raise RuntimeError(f"{label} changed while being hashed")
        return digest, inode_identity(opened)
    finally:
        if sink is not None:
            sink.close()
        if source_fd is not None:
            os.close(source_fd)


def claim_target(parent_fd: int, name: str, *, label: str) -> str:
    """Atomically move the current path to a unique adjacent recovery claim."""
    claim = f".{name}.{label}.{os.getpid()}.{secrets.token_hex(8)}"
    os.rename(name, claim, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
    os.fsync(parent_fd)
    return claim


def publish_no_replace(parent_fd: int, source_name: str, target_name: str) -> None:
    """Publish a prepared inode only if no concurrent path occupies the target."""
    os.link(
        source_name,
        target_name,
        src_dir_fd=parent_fd,
        dst_dir_fd=parent_fd,
        follow_symlinks=False,
    )
    os.fsync(parent_fd)


def return_private_claim(
    parent_fd: int,
    private_name: str,
    original_name: str,
) -> None:
    """Put a private claim back without replacing a concurrently-created path."""
    publish_no_replace(parent_fd, private_name, original_name)
    os.unlink(private_name, dir_fd=parent_fd)
    os.fsync(parent_fd)


def claim_path_if_identity(
    parent_fd: int,
    name: str,
    expected_identity: InodeIdentity,
    *,
    label: str,
) -> str | None:
    """Move a path to a private claim, returning it only when its inode is expected."""
    try:
        private_name = claim_target(parent_fd, name, label=label)
    except FileNotFoundError:
        return None
    try:
        claimed = os.stat(private_name, dir_fd=parent_fd, follow_symlinks=False)
    except Exception:
        try:
            return_private_claim(parent_fd, private_name, name)
        except OSError:
            pass
        raise
    if inode_identity(claimed) == expected_identity:
        return private_name
    try:
        return_private_claim(parent_fd, private_name, name)
    except OSError as exc:
        raise RuntimeError(
            f"{name} changed during {label}; the replacement was preserved as {private_name}"
        ) from exc
    return None


def unlink_if_identity(
    parent_fd: int,
    name: str,
    expected_identity: InodeIdentity,
    *,
    label: str,
) -> bool:
    """Remove a path only after atomically claiming and verifying its inode."""
    private_name = claim_path_if_identity(
        parent_fd,
        name,
        expected_identity,
        label=label,
    )
    if private_name is None:
        return False
    try:
        os.unlink(private_name, dir_fd=parent_fd)
        os.fsync(parent_fd)
    except Exception:
        try:
            return_private_claim(parent_fd, private_name, name)
        except OSError:
            pass
        raise
    return True


def relink_claim(
    parent_fd: int,
    claim_name: str,
    target_name: str,
    *,
    expected_identity: InodeIdentity,
) -> None:
    """Return an expected claimed inode without replacing a concurrent target."""
    private_name = claim_path_if_identity(
        parent_fd,
        claim_name,
        expected_identity,
        label="claim rollback",
    )
    if private_name is None:
        raise RuntimeError(f"{claim_name} changed before claim rollback")
    try:
        publish_no_replace(parent_fd, private_name, target_name)
    except Exception:
        try:
            return_private_claim(parent_fd, private_name, claim_name)
        except OSError:
            pass
        raise
    try:
        os.unlink(private_name, dir_fd=parent_fd)
        os.fsync(parent_fd)
    except Exception:
        # Both names refer to the expected inode. Preserve the private recovery
        # link rather than risk deleting a path that could have been replaced.
        raise


def return_claim_if_target_absent(
    parent_fd: int,
    claim_name: str,
    target_name: str,
    *,
    expected_identity: InodeIdentity,
) -> bool:
    """Best-effort rollback after claiming a path; never replaces a new target."""
    try:
        relink_claim(
            parent_fd,
            claim_name,
            target_name,
            expected_identity=expected_identity,
        )
    except (FileExistsError, OSError, RuntimeError):
        return False
    return True


def unlink_if_same_inode(
    parent_fd: int,
    target_name: str,
    source_name: str,
) -> bool:
    """Remove target only when a private claim still matches the source inode."""
    try:
        source = os.stat(source_name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return unlink_if_identity(
        parent_fd,
        target_name,
        inode_identity(source),
        label="published inode cleanup",
    )


def backup_metadata(backup_fd: int) -> tuple[dict[str, object], int]:
    details = os.fstat(backup_fd)
    regular_single_link(details, label="opened mutation backup")
    footer_size = LENGTH_BYTES + len(MAGIC)
    if details.st_size < footer_size:
        raise ValueError("mutation backup is truncated")

    os.lseek(backup_fd, details.st_size - len(MAGIC), os.SEEK_SET)
    if os.read(backup_fd, len(MAGIC)) != MAGIC:
        raise ValueError("mutation backup has invalid integrity marker")
    os.lseek(backup_fd, details.st_size - footer_size, os.SEEK_SET)
    encoded_length = os.read(backup_fd, LENGTH_BYTES)
    if len(encoded_length) != LENGTH_BYTES:
        raise ValueError("mutation backup is truncated")
    header_length = int.from_bytes(encoded_length, "big")
    header_start = details.st_size - footer_size - header_length
    if header_length <= 0 or header_length > 64 * 1024 or header_start < 0:
        raise ValueError("mutation backup has invalid metadata length")
    os.lseek(backup_fd, header_start, os.SEEK_SET)
    encoded_header = os.read(backup_fd, header_length)
    if len(encoded_header) != header_length:
        raise ValueError("mutation backup metadata is truncated")
    try:
        metadata = json.loads(encoded_header.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("mutation backup metadata is invalid") from exc
    if not isinstance(metadata, dict):
        raise ValueError("mutation backup metadata is invalid")
    required = {"version", "path", "size", "sha256", "mode"}
    if set(metadata) != required or metadata.get("version") != 2:
        raise ValueError("mutation backup metadata schema is invalid")
    if not isinstance(metadata["path"], str) or not metadata["path"]:
        raise ValueError("mutation backup path metadata is invalid")
    if not isinstance(metadata["size"], int) or metadata["size"] < 0:
        raise ValueError("mutation backup size metadata is invalid")
    if not isinstance(metadata["mode"], int) or not 0 <= metadata["mode"] <= 0o7777:
        raise ValueError("mutation backup mode metadata is invalid")
    digest = metadata["sha256"]
    if not isinstance(digest, str) or not valid_digest(digest):
        raise ValueError("mutation backup digest metadata is invalid")
    if metadata["size"] != header_start:
        raise ValueError("mutation backup payload size does not match metadata")
    return metadata, header_start


def open_backup(parent_fd: int, backup_name: str) -> int:
    details = os.stat(backup_name, dir_fd=parent_fd, follow_symlinks=False)
    regular_single_link(details, label="mutation backup")
    backup_fd = os.open(
        backup_name,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=parent_fd,
    )
    opened = os.fstat(backup_fd)
    regular_single_link(opened, label="opened mutation backup")
    if (opened.st_dev, opened.st_ino) != (details.st_dev, details.st_ino):
        os.close(backup_fd)
        raise RuntimeError("mutation backup changed while being opened")
    return backup_fd


def backup(path: Path, *, root: Path) -> Path:
    relative = relative_under_root(path, root)
    parent_fd, name = open_parent(root, relative)
    source_fd: int | None = None
    temporary_fd: int | None = None
    temporary_identity: InodeIdentity | None = None
    temporary_name = f".{name}.mutbak.tmp.{os.getpid()}.{secrets.token_hex(8)}"
    backup_name = f"{name}.mutbak"
    published = False
    try:
        try:
            os.stat(backup_name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError(f"mutation backup already exists: {backup_name}")

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
            raise RuntimeError("mutation target changed while backup was being opened")

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
        copied, digest = copy_and_hash(source_fd, temporary_fd)
        after = os.fstat(source_fd)
        source_identity = (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
        after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        if source_identity != after_identity or copied != opened.st_size:
            raise RuntimeError("mutation target changed while backup was being created")
        metadata = {
            "version": 2,
            "path": relative.as_posix(),
            "size": copied,
            "sha256": digest,
            "mode": stat.S_IMODE(opened.st_mode),
        }
        encoded = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")
        write_all(temporary_fd, encoded)
        write_all(temporary_fd, len(encoded).to_bytes(LENGTH_BYTES, "big"))
        write_all(temporary_fd, MAGIC)
        os.fsync(temporary_fd)
        os.close(temporary_fd)
        temporary_fd = None

        os.link(
            temporary_name,
            backup_name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
            follow_symlinks=False,
        )
        published = True
        if not unlink_if_identity(
            parent_fd,
            temporary_name,
            temporary_identity,
            label="temporary backup cleanup",
        ):
            raise RuntimeError("temporary mutation backup changed during cleanup")
        temporary_identity = None
    except Exception:
        if temporary_fd is not None:
            os.close(temporary_fd)
        if temporary_identity is not None:
            try:
                unlink_if_identity(
                    parent_fd,
                    temporary_name,
                    temporary_identity,
                    label="failed temporary backup cleanup",
                )
            except (OSError, RuntimeError):
                pass
        if published and temporary_identity is not None:
            try:
                unlink_if_identity(
                    parent_fd,
                    backup_name,
                    temporary_identity,
                    label="failed published backup cleanup",
                )
            except (OSError, RuntimeError):
                pass
        raise
    finally:
        if source_fd is not None:
            os.close(source_fd)
        os.close(parent_fd)
    return Path(root) / relative.parent / backup_name


def verify_backup(path: Path, *, root: Path) -> dict[str, object]:
    relative = relative_under_root(path, root)
    parent_fd, name = open_parent(root, relative)
    backup_fd: int | None = None
    try:
        backup_fd = open_backup(parent_fd, f"{name}.mutbak")
        metadata, payload_size = backup_metadata(backup_fd)
        if metadata["path"] != relative.as_posix():
            raise ValueError("mutation backup belongs to a different target")
        os.lseek(backup_fd, 0, os.SEEK_SET)
        sink = open(os.devnull, "wb")
        try:
            copied, digest = copy_and_hash(backup_fd, sink.fileno(), limit=payload_size)
        finally:
            sink.close()
        if copied != payload_size or digest != metadata["sha256"]:
            raise ValueError("mutation backup payload failed integrity verification")
        return metadata
    finally:
        if backup_fd is not None:
            os.close(backup_fd)
        os.close(parent_fd)


def restore(path: Path, *, root: Path, expected_current_sha256: str) -> Path:
    if not valid_digest(expected_current_sha256):
        raise ValueError("expected current SHA-256 must be 64 lowercase hexadecimal characters")
    relative = relative_under_root(path, root)
    parent_fd, name = open_parent(root, relative)
    backup_name = f"{name}.mutbak"
    temporary_name = f".{name}.mutrestore.tmp.{os.getpid()}.{secrets.token_hex(8)}"
    backup_fd: int | None = None
    backup_identity: InodeIdentity | None = None
    temporary_fd: int | None = None
    temporary_identity: InodeIdentity | None = None
    current_claim: str | None = None
    current_claim_identity: InodeIdentity | None = None
    try:
        backup_fd = open_backup(parent_fd, backup_name)
        backup_identity = inode_identity(os.fstat(backup_fd))
        metadata, payload_size = backup_metadata(backup_fd)
        if metadata["path"] != relative.as_posix():
            raise ValueError("mutation backup belongs to a different target")

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
        os.lseek(backup_fd, 0, os.SEEK_SET)
        copied, digest = copy_and_hash(backup_fd, temporary_fd, limit=payload_size)
        if copied != payload_size or digest != metadata["sha256"]:
            raise ValueError("mutation backup payload failed integrity verification")
        os.fchmod(temporary_fd, int(metadata["mode"]))
        os.fsync(temporary_fd)
        os.close(temporary_fd)
        temporary_fd = None

        current_claim = claim_target(parent_fd, name, label="mutcurrent")
        current_claim_identity = inode_identity(
            os.stat(current_claim, dir_fd=parent_fd, follow_symlinks=False)
        )
        claimed_digest, hashed_claim_identity = sha256_at(
            parent_fd,
            current_claim,
            label="claimed mutation target",
        )
        if hashed_claim_identity != current_claim_identity:
            raise RuntimeError("claimed mutation target changed while being verified")
        if claimed_digest != expected_current_sha256:
            try:
                relink_claim(
                    parent_fd,
                    current_claim,
                    name,
                    expected_identity=current_claim_identity,
                )
                current_claim = None
            except FileExistsError:
                pass
            raise RuntimeError(
                "mutation target changed after the mutant was captured; refusing to overwrite "
                f"current digest {claimed_digest} (expected {expected_current_sha256}). "
                f"Backup retained at {Path(root) / relative.parent / backup_name}"
            )
        try:
            publish_no_replace(parent_fd, temporary_name, name)
        except FileExistsError as exc:
            raise RuntimeError(
                "a new target appeared during restore publication; it was not overwritten. "
                f"Claim retained as {Path(root) / relative.parent / current_claim}"
            ) from exc

        latest_claim_digest, _latest_claim_identity = sha256_at(
            parent_fd,
            current_claim,
            label="claimed mutation target",
        )
        if latest_claim_digest != expected_current_sha256:
            if unlink_if_same_inode(parent_fd, name, temporary_name):
                try:
                    relink_claim(
                        parent_fd,
                        current_claim,
                        name,
                        expected_identity=current_claim_identity,
                    )
                    current_claim = None
                except FileExistsError:
                    pass
            raise RuntimeError(
                "mutation target changed while the original was being published; "
                "the concurrent edit was preserved and the backup retained"
            )

        if not unlink_if_identity(
            parent_fd,
            temporary_name,
            temporary_identity,
            label="temporary restore cleanup",
        ):
            raise RuntimeError("temporary restore inode changed during cleanup")
        temporary_identity = None
        restored_digest = current_sha256(path, root=root)
        if restored_digest != metadata["sha256"]:
            raise RuntimeError(
                "published target changed during restore; preserving it and the recovery "
                f"claim at {Path(root) / relative.parent / current_claim}"
            )
        if not unlink_if_identity(
            parent_fd,
            current_claim,
            current_claim_identity,
            label="mutation claim cleanup",
        ):
            raise RuntimeError("mutation recovery claim changed during cleanup; it was preserved")
        current_claim = None
        if not unlink_if_identity(
            parent_fd,
            backup_name,
            backup_identity,
            label="mutation backup cleanup",
        ):
            raise RuntimeError("mutation backup changed during cleanup; it was preserved")
    except Exception:
        if temporary_fd is not None:
            os.close(temporary_fd)
        if (
            current_claim is not None
            and current_claim_identity is not None
            and return_claim_if_target_absent(
                parent_fd,
                current_claim,
                name,
                expected_identity=current_claim_identity,
            )
        ):
            current_claim = None
        if temporary_identity is not None:
            try:
                unlink_if_identity(
                    parent_fd,
                    temporary_name,
                    temporary_identity,
                    label="failed temporary restore cleanup",
                )
            except (OSError, RuntimeError):
                pass
        raise
    finally:
        if backup_fd is not None:
            os.close(backup_fd)
        os.close(parent_fd)
    return Path(root) / relative


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("backup", "digest", "verify", "restore"))
    parser.add_argument("file", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--expected-current-sha256")
    args = parser.parse_args(argv[1:])
    root = Path(os.path.abspath(os.fspath(args.root.expanduser())))
    try:
        if args.action == "backup":
            result: object = backup(args.file, root=root)
        elif args.action == "digest":
            result = current_sha256(args.file, root=root)
        elif args.action == "verify":
            result = verify_backup(args.file, root=root)
        else:
            if args.expected_current_sha256 is None:
                raise ValueError("restore requires --expected-current-sha256")
            result = restore(
                args.file,
                root=root,
                expected_current_sha256=args.expected_current_sha256,
            )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"mutation backup refused: {exc}", file=sys.stderr)
        return 1
    if isinstance(result, dict):
        print(json.dumps(result, sort_keys=True))
    else:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
