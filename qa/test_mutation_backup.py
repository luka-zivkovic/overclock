import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "plugins/discipline-gates/skills/test-discipline/scripts/mutation_backup.py"
)
SPEC = importlib.util.spec_from_file_location("mutation_backup", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MutationBackupTests(unittest.TestCase):
    def test_dirty_file_round_trips_exact_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "src" / "module.bin"
            target.parent.mkdir()
            original = b"dirty\x00bytes\r\nwithout-final-newline"
            target.write_bytes(original)

            backup = MODULE.backup(target, root=root)
            target.write_bytes(b"mutated")
            MODULE.restore(target, root=root)

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
                MODULE.restore(target, root=root)
            self.assertEqual(referent.read_text(encoding="utf-8"), "must stay unchanged")
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


if __name__ == "__main__":
    unittest.main()
