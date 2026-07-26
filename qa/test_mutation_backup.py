import importlib.util
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "plugins/discipline-gates/skills/test-discipline/scripts/mutation_backup.py"
)
SPEC = importlib.util.spec_from_file_location("mutation_backup", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MutationBackupTests(unittest.TestCase):
    def test_inode_guard_preserves_replacement_arriving_before_unlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            target = root / "published.txt"
            source.write_bytes(b"owned inode")
            os.link(source, target)
            parent_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            real_stat = MODULE.os.stat
            injected = False

            def stat_with_replacement(path, *args, **kwargs):
                nonlocal injected
                result = real_stat(path, *args, **kwargs)
                if path == "source.txt" and not injected:
                    injected = True
                    os.unlink("published.txt", dir_fd=parent_fd)
                    replacement_fd = os.open(
                        "published.txt",
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                        dir_fd=parent_fd,
                    )
                    os.write(replacement_fd, b"concurrent replacement")
                    os.close(replacement_fd)
                return result

            try:
                with mock.patch.object(MODULE.os, "stat", side_effect=stat_with_replacement):
                    removed = MODULE.unlink_if_same_inode(
                        parent_fd,
                        "published.txt",
                        "source.txt",
                    )
            finally:
                os.close(parent_fd)

            self.assertFalse(removed)
            self.assertEqual(target.read_bytes(), b"concurrent replacement")
            self.assertEqual(source.read_bytes(), b"owned inode")

    def test_dirty_file_round_trips_exact_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "src" / "module.bin"
            target.parent.mkdir()
            original = b"dirty\x00bytes\r\nwithout-final-newline"
            target.write_bytes(original)

            backup = MODULE.backup(target, root=root)
            metadata = MODULE.verify_backup(target, root=root)
            self.assertEqual(metadata["path"], "src/module.bin")
            self.assertEqual(metadata["size"], len(original))
            target.write_bytes(b"mutated")
            MODULE.restore(
                target,
                root=root,
                expected_current_sha256=hashlib.sha256(b"mutated").hexdigest(),
            )

            self.assertEqual(target.read_bytes(), original)
            self.assertFalse(backup.exists())

    def test_symlink_target_is_refused_without_touching_referent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            referent = root / "referent.txt"
            referent.write_text("outside of mutation", encoding="utf-8")
            target = root / "target.txt"
            target.symlink_to(referent)

            with self.assertRaisesRegex(ValueError, "regular file"):
                MODULE.backup(target, root=root)
            self.assertEqual(referent.read_text(encoding="utf-8"), "outside of mutation")

    def test_hardlink_target_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original.txt"
            original.write_text("shared", encoding="utf-8")
            linked = root / "linked.txt"
            os.link(original, linked)

            with self.assertRaisesRegex(ValueError, "hard links"):
                MODULE.backup(linked, root=root)
            self.assertEqual(original.read_text(encoding="utf-8"), "shared")

    def test_symlinked_parent_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"
            outside.mkdir()
            referent = outside / "target.txt"
            referent.write_text("do not copy", encoding="utf-8")
            (root / "linked-parent").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(OSError):
                MODULE.backup(root / "linked-parent" / "target.txt", root=root)
            self.assertEqual(referent.read_text(encoding="utf-8"), "do not copy")

    def test_restore_refuses_target_replaced_by_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.txt"
            target.write_text("original", encoding="utf-8")
            backup = MODULE.backup(target, root=root)
            referent = root / "referent.txt"
            referent.write_text("must stay unchanged", encoding="utf-8")
            target.unlink()
            target.symlink_to(referent)

            with self.assertRaisesRegex(ValueError, "regular file"):
                MODULE.restore(
                    target,
                    root=root,
                    expected_current_sha256="0" * 64,
                )
            self.assertEqual(referent.read_text(encoding="utf-8"), "must stay unchanged")
            self.assertTrue(target.is_symlink())
            self.assertEqual(list(root.glob(".target.txt.mutcurrent.*")), [])
            self.assertTrue(backup.exists())

    def test_restore_refuses_hardlink_replacement_without_hiding_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.txt"
            target.write_text("original", encoding="utf-8")
            backup = MODULE.backup(target, root=root)
            target.unlink()
            shared = root / "shared.txt"
            shared.write_text("concurrent", encoding="utf-8")
            os.link(shared, target)

            with self.assertRaisesRegex(ValueError, "hard links"):
                MODULE.restore(
                    target,
                    root=root,
                    expected_current_sha256=hashlib.sha256(b"concurrent").hexdigest(),
                )

            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(encoding="utf-8"), "concurrent")
            self.assertEqual(target.stat().st_ino, shared.stat().st_ino)
            self.assertEqual(list(root.glob(".target.txt.mutcurrent.*")), [])
            self.assertTrue(backup.exists())

    def test_preexisting_backup_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.txt"
            target.write_text("original", encoding="utf-8")
            backup = root / "target.txt.mutbak"
            backup.write_text("keep me", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                MODULE.backup(target, root=root)
            self.assertEqual(backup.read_text(encoding="utf-8"), "keep me")
            self.assertEqual(target.read_text(encoding="utf-8"), "original")

    def test_partial_backup_is_never_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.txt"
            target.write_text("original", encoding="utf-8")

            with mock.patch.object(MODULE, "copy_and_hash", side_effect=OSError("write failed")):
                with self.assertRaisesRegex(OSError, "write failed"):
                    MODULE.backup(target, root=root)

            self.assertFalse((root / "target.txt.mutbak").exists())
            self.assertEqual(list(root.glob(".target.txt.mutbak.tmp.*")), [])
            self.assertEqual(target.read_text(encoding="utf-8"), "original")

    def test_failed_published_backup_cleanup_preserves_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.txt"
            target.write_text("original", encoding="utf-8")
            backup = root / "target.txt.mutbak"
            real_unlink = MODULE.os.unlink
            injected = False

            def unlink_with_backup_replacement(path, *args, **kwargs):
                nonlocal injected
                if (
                    not injected
                    and ".mutbak.tmp." in os.fspath(path)
                    and backup.exists()
                ):
                    injected = True
                    parent_fd = kwargs["dir_fd"]
                    real_unlink("target.txt.mutbak", dir_fd=parent_fd)
                    replacement_fd = os.open(
                        "target.txt.mutbak",
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                        dir_fd=parent_fd,
                    )
                    os.write(replacement_fd, b"concurrent backup replacement")
                    os.close(replacement_fd)
                    raise OSError("injected temporary cleanup failure")
                return real_unlink(path, *args, **kwargs)

            with mock.patch.object(
                MODULE.os,
                "unlink",
                side_effect=unlink_with_backup_replacement,
            ):
                supported_dir_fd = set(MODULE.os.supports_dir_fd)
                supported_dir_fd.add(MODULE.os.unlink)
                with mock.patch.object(MODULE.os, "supports_dir_fd", supported_dir_fd):
                    with self.assertRaisesRegex(OSError, "injected temporary cleanup failure"):
                        MODULE.backup(target, root=root)

            self.assertEqual(backup.read_bytes(), b"concurrent backup replacement")
            self.assertEqual(target.read_text(encoding="utf-8"), "original")

    def test_corrupt_backup_is_refused_without_replacing_mutated_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.txt"
            target.write_text("original", encoding="utf-8")
            backup = MODULE.backup(target, root=root)
            target.write_text("mutated", encoding="utf-8")
            with backup.open("r+b") as stream:
                stream.seek(0)
                stream.write(b"X")

            with self.assertRaisesRegex(ValueError, "integrity verification"):
                MODULE.restore(
                    target,
                    root=root,
                    expected_current_sha256=hashlib.sha256(b"mutated").hexdigest(),
                )

            self.assertEqual(target.read_text(encoding="utf-8"), "mutated")
            self.assertTrue(backup.exists())

    def test_restore_recovers_original_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "tool.sh"
            target.write_text("#!/bin/sh\n", encoding="utf-8")
            target.chmod(0o750)
            MODULE.backup(target, root=root)
            target.write_text("mutated\n", encoding="utf-8")
            target.chmod(0o600)

            MODULE.restore(
                target,
                root=root,
                expected_current_sha256=hashlib.sha256(b"mutated\n").hexdigest(),
            )

            self.assertEqual(target.stat().st_mode & 0o777, 0o750)

    def test_restore_refuses_to_clobber_concurrent_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.txt"
            target.write_text("original", encoding="utf-8")
            backup = MODULE.backup(target, root=root)
            expected_mutant = b"mutant"
            target.write_bytes(expected_mutant)
            captured_mutant_digest = hashlib.sha256(expected_mutant).hexdigest()

            target.write_text("user edit during test", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "changed after the mutant"):
                MODULE.restore(
                    target,
                    root=root,
                    expected_current_sha256=captured_mutant_digest,
                )

            self.assertEqual(target.read_text(encoding="utf-8"), "user edit during test")
            self.assertTrue(backup.exists())

    def test_restore_does_not_replace_target_created_during_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.txt"
            target.write_text("original", encoding="utf-8")
            backup = MODULE.backup(target, root=root)
            target.write_text("mutant", encoding="utf-8")
            mutant_digest = hashlib.sha256(b"mutant").hexdigest()
            original_publish = MODULE.publish_no_replace
            injected = False

            def publish_with_concurrent_target(parent_fd, source_name, target_name):
                nonlocal injected
                if target_name == "target.txt" and not injected:
                    injected = True
                    fd = os.open(
                        target_name,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                        dir_fd=parent_fd,
                    )
                    os.write(fd, b"user file created during publish")
                    os.close(fd)
                return original_publish(parent_fd, source_name, target_name)

            with mock.patch.object(
                MODULE,
                "publish_no_replace",
                side_effect=publish_with_concurrent_target,
            ):
                with self.assertRaisesRegex(RuntimeError, "appeared during restore publication"):
                    MODULE.restore(
                        target,
                        root=root,
                        expected_current_sha256=mutant_digest,
                    )

            self.assertEqual(target.read_bytes(), b"user file created during publish")
            self.assertTrue(backup.exists())
            claims = list(root.glob(".target.txt.mutcurrent.*"))
            self.assertEqual(len(claims), 1)
            self.assertEqual(claims[0].read_bytes(), b"mutant")

    def test_restore_claim_cleanup_preserves_concurrent_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.txt"
            target.write_bytes(b"original")
            backup = MODULE.backup(target, root=root)
            target.write_bytes(b"mutant")
            real_digest = MODULE.current_sha256

            def digest_then_replace_claim(path, *, root):
                digest = real_digest(path, root=root)
                claim = next(root.glob(".target.txt.mutcurrent.*"))
                claim.unlink()
                claim.write_bytes(b"concurrent claim replacement")
                return digest

            with mock.patch.object(
                MODULE,
                "current_sha256",
                side_effect=digest_then_replace_claim,
            ):
                with self.assertRaisesRegex(RuntimeError, "claim changed during cleanup"):
                    MODULE.restore(
                        target,
                        root=root,
                        expected_current_sha256=hashlib.sha256(b"mutant").hexdigest(),
                    )

            claims = list(root.glob(".target.txt.mutcurrent.*"))
            self.assertEqual(len(claims), 1)
            self.assertEqual(claims[0].read_bytes(), b"concurrent claim replacement")
            self.assertEqual(target.read_bytes(), b"original")
            self.assertTrue(backup.exists())

    def test_restore_backup_cleanup_preserves_concurrent_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.txt"
            target.write_bytes(b"original")
            backup = MODULE.backup(target, root=root)
            target.write_bytes(b"mutant")
            real_digest = MODULE.current_sha256

            def digest_then_replace_backup(path, *, root):
                digest = real_digest(path, root=root)
                backup.unlink()
                backup.write_bytes(b"concurrent backup replacement")
                return digest

            with mock.patch.object(
                MODULE,
                "current_sha256",
                side_effect=digest_then_replace_backup,
            ):
                with self.assertRaisesRegex(RuntimeError, "backup changed during cleanup"):
                    MODULE.restore(
                        target,
                        root=root,
                        expected_current_sha256=hashlib.sha256(b"mutant").hexdigest(),
                    )

            self.assertEqual(backup.read_bytes(), b"concurrent backup replacement")
            self.assertEqual(target.read_bytes(), b"original")
            self.assertEqual(list(root.glob(".target.txt.mutcurrent.*")), [])


if __name__ == "__main__":
    unittest.main()
