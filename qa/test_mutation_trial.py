from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "plugins/discipline-gates/skills/test-discipline/scripts/mutation_trial.py"
)
SCRIPT_DIR = SCRIPT.parent
sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location("mutation_trial_under_test", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MutationTrialTests(unittest.TestCase):
    def test_trial_detects_mutation_restores_and_reruns_clean_test(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "value.txt"
            target.write_text("good\n", encoding="utf-8")
            check = root / "check.py"
            check.write_text(
                "from pathlib import Path\n"
                "raise SystemExit(0 if Path('value.txt').read_text() == 'good\\n' else 1)\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "value.txt",
                    "--root",
                    str(root),
                    "--old",
                    "good",
                    "--new",
                    "bad",
                    "--",
                    sys.executable,
                    "check.py",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(summary["mutation_outcome"], "nonzero")
            self.assertEqual(summary["restored_test_exit"], 0)
            self.assertEqual(target.read_text(encoding="utf-8"), "good\n")
            self.assertFalse((root / "value.txt.mutbak").exists())

    def test_trial_refuses_ambiguous_replacement_without_leaving_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "value.txt"
            target.write_text("same same\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "value.txt",
                    "--root",
                    str(root),
                    "--old",
                    "same",
                    "--new",
                    "other",
                    "--",
                    sys.executable,
                    "-c",
                    "raise SystemExit(0)",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("must occur once", result.stderr)
            self.assertEqual(target.read_text(encoding="utf-8"), "same same\n")
            self.assertFalse((root / "value.txt.mutbak").exists())

    def test_nonzero_test_is_not_labeled_as_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "value.txt"
            target.write_text("good\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "value.txt",
                    "--root",
                    str(root),
                    "--old",
                    "good",
                    "--new",
                    "bad",
                    "--",
                    sys.executable,
                    "-c",
                    "raise RuntimeError('fixture import failed before assertion')",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            summary = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(summary["mutation_outcome"], "nonzero")
            self.assertNotIn("detected", summary["mutation_outcome"])
            self.assertIn("inspect", summary["interpretation"])
            self.assertEqual(target.read_text(encoding="utf-8"), "good\n")

    def test_interruption_does_not_clobber_concurrent_edit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "value.txt"
            target.write_text("good\n", encoding="utf-8")
            interrupt = root / "interrupt.py"
            interrupt.write_text(
                "import os, signal\n"
                "from pathlib import Path\n"
                "Path('value.txt').write_text('user edit during interruption\\n')\n"
                "os.kill(os.getppid(), signal.SIGTERM)\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "value.txt",
                    "--root",
                    str(root),
                    "--old",
                    "good",
                    "--new",
                    "bad",
                    "--",
                    sys.executable,
                    "interrupt.py",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("changed after the mutant", result.stderr)
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                "user edit during interruption\n",
            )
            self.assertTrue((root / "value.txt.mutbak").exists())

    def test_edit_before_mutant_install_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "value.txt"
            original = b"good\n"
            target.write_bytes(original)
            MODULE.backup(target, root=root)
            target.write_text("user edit before install\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "changed after backup"):
                MODULE.atomic_replace(
                    root,
                    Path("value.txt"),
                    b"bad\n",
                    mode=0o644,
                    expected_original_sha256=hashlib.sha256(original).hexdigest(),
                    expected_mutant_sha256=hashlib.sha256(b"bad\n").hexdigest(),
                )

            self.assertEqual(target.read_text(encoding="utf-8"), "user edit before install\n")
            self.assertTrue((root / "value.txt.mutbak").exists())
            self.assertEqual(list(root.glob(".value.txt.mutorigin.*")), [])

    def test_new_target_during_mutant_publish_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "value.txt"
            original = b"good\n"
            target.write_bytes(original)
            MODULE.backup(target, root=root)
            original_publish = MODULE.publish_no_replace
            injected = False

            def publish_with_concurrent_target(parent_fd, source_name, target_name):
                nonlocal injected
                if target_name == "value.txt" and not injected:
                    injected = True
                    fd = os.open(
                        target_name,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                        dir_fd=parent_fd,
                    )
                    os.write(fd, b"user file during mutant publish\n")
                    os.close(fd)
                return original_publish(parent_fd, source_name, target_name)

            with mock.patch.object(
                MODULE,
                "publish_no_replace",
                side_effect=publish_with_concurrent_target,
            ):
                with self.assertRaisesRegex(RuntimeError, "appeared during mutant publication"):
                    MODULE.atomic_replace(
                        root,
                        Path("value.txt"),
                        b"bad\n",
                        mode=0o644,
                        expected_original_sha256=hashlib.sha256(original).hexdigest(),
                        expected_mutant_sha256=hashlib.sha256(b"bad\n").hexdigest(),
                    )

            self.assertEqual(target.read_bytes(), b"user file during mutant publish\n")
            claims = list(root.glob(".value.txt.mutorigin.*"))
            self.assertEqual(len(claims), 1)
            self.assertEqual(claims[0].read_bytes(), original)
            self.assertTrue((root / "value.txt.mutbak").exists())

    def test_original_claim_cleanup_preserves_concurrent_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "value.txt"
            original = b"good\n"
            mutant = b"bad\n"
            target.write_bytes(original)
            backup = MODULE.backup(target, root=root)
            real_digest = MODULE.current_sha256

            def digest_then_replace_claim(path, *, root):
                digest = real_digest(path, root=root)
                claim = next(root.glob(".value.txt.mutorigin.*"))
                claim.unlink()
                claim.write_bytes(b"concurrent claim replacement\n")
                return digest

            with mock.patch.object(
                MODULE,
                "current_sha256",
                side_effect=digest_then_replace_claim,
            ):
                with self.assertRaisesRegex(RuntimeError, "claim changed during cleanup"):
                    MODULE.atomic_replace(
                        root,
                        Path("value.txt"),
                        mutant,
                        mode=0o644,
                        expected_original_sha256=hashlib.sha256(original).hexdigest(),
                        expected_mutant_sha256=hashlib.sha256(mutant).hexdigest(),
                    )

            claims = list(root.glob(".value.txt.mutorigin.*"))
            self.assertEqual(len(claims), 1)
            self.assertEqual(claims[0].read_bytes(), b"concurrent claim replacement\n")
            self.assertEqual(target.read_bytes(), mutant)
            self.assertTrue(backup.exists())


if __name__ == "__main__":
    unittest.main()
