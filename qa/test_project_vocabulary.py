from __future__ import annotations

import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = (
    Path(__file__).resolve().parent.parent
    / "plugins/project-vocabulary/skills/project-vocabulary/scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))
import glossary_file  # noqa: E402


class GlossaryFileTest(unittest.TestCase):
    def _proposal(
        self,
        root: Path,
    ) -> tuple[Path, Path, dict[str, object]]:
        target = root / "CONCEPTS.md"
        target.write_text("# Concepts\n\n## A\nApproved prior text.\n", encoding="utf-8")
        candidate = root / ".CONCEPTS.md.proposed"
        candidate.write_text(
            "# Concepts\n\n## A\nApproved candidate text.\n",
            encoding="utf-8",
        )
        return target, candidate, glossary_file.proposal(root, candidate)

    def _apply_with_hook(
        self,
        root: Path,
        candidate: Path,
        shown: dict[str, object],
        hook,
    ) -> None:
        glossary_file.apply(
            root,
            candidate,
            expected_current=str(shown["current_sha256"]),
            expected_candidate=str(shown["candidate_sha256"]),
            phase_hook=hook,
        )

    def test_proposal_and_apply_are_bound_to_both_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "CONCEPTS.md"
            target.write_text("# Concepts\n\n## Workspace\nA boundary.\n", encoding="utf-8")
            candidate = root / ".CONCEPTS.md.proposed"
            candidate.write_text(
                "# Concepts\n\n## Workspace\nThe billing boundary.\n",
                encoding="utf-8",
            )

            shown = glossary_file.proposal(root, candidate)
            self.assertIn("-A boundary.", shown["diff"])
            self.assertIn("+The billing boundary.", shown["diff"])
            result = glossary_file.apply(
                root,
                candidate,
                expected_current=str(shown["current_sha256"]),
                expected_candidate=str(shown["candidate_sha256"]),
            )

            self.assertTrue(result["changed"])
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                "# Concepts\n\n## Workspace\nThe billing boundary.\n",
            )

    def test_apply_refuses_changed_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "CONCEPTS.md"
            target.write_text("# Concepts\n\n## A\nFirst.\n", encoding="utf-8")
            candidate = root / ".CONCEPTS.md.proposed"
            candidate.write_text("# Concepts\n\n## A\nSecond.\n", encoding="utf-8")
            shown = glossary_file.proposal(root, candidate)
            target.write_text("# Concepts\n\n## A\nThird.\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "changed"):
                glossary_file.apply(
                    root,
                    candidate,
                    expected_current=str(shown["current_sha256"]),
                    expected_candidate=str(shown["candidate_sha256"]),
                )

            self.assertIn("Third", target.read_text(encoding="utf-8"))

    def test_apply_refuses_changed_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "CONCEPTS.md").write_text(
                "# Concepts\n\n## A\nFirst.\n", encoding="utf-8"
            )
            candidate = root / ".CONCEPTS.md.proposed"
            candidate.write_text("# Concepts\n\n## A\nSecond.\n", encoding="utf-8")
            shown = glossary_file.proposal(root, candidate)
            candidate.write_text("# Concepts\n\n## A\nThird.\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "candidate changed"):
                glossary_file.apply(
                    root,
                    candidate,
                    expected_current=str(shown["current_sha256"]),
                    expected_candidate=str(shown["candidate_sha256"]),
                )

    def test_refuses_linked_target_and_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "repo"
            root.mkdir()
            outside = base / "outside.md"
            outside.write_text("# Concepts\n\n## Outside\nNo.\n", encoding="utf-8")
            (root / "CONCEPTS.md").symlink_to(outside)
            candidate = root / ".CONCEPTS.md.proposed"
            candidate.write_text("# Concepts\n\n## Safe\nYes.\n", encoding="utf-8")

            with self.assertRaises(OSError):
                glossary_file.proposal(root, candidate)

            (root / "CONCEPTS.md").unlink()
            (root / "CONCEPTS.md").write_text(
                "# Concepts\n\n## Safe\nOld.\n", encoding="utf-8"
            )
            candidate.unlink()
            candidate.symlink_to(outside)
            with self.assertRaises(OSError):
                glossary_file.proposal(root, candidate)

    def test_refuses_hardlinked_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "CONCEPTS.md"
            target.write_text("# Concepts\n\n## A\nOne.\n", encoding="utf-8")
            os.link(target, root / "other.md")
            candidate = root / ".CONCEPTS.md.proposed"
            candidate.write_text("# Concepts\n\n## A\nTwo.\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "hard links"):
                glossary_file.proposal(root, candidate)

    def test_new_glossary_uses_missing_precondition(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = root / ".CONCEPTS.md.proposed"
            candidate.write_text("# Concepts\n\n## Draft\nNever published.\n", encoding="utf-8")
            shown = glossary_file.proposal(root, candidate)
            self.assertEqual(shown["current_sha256"], glossary_file.MISSING)
            result = glossary_file.apply(
                root,
                candidate,
                expected_current=glossary_file.MISSING,
                expected_candidate=str(shown["candidate_sha256"]),
            )
            self.assertTrue(result["changed"])
            self.assertTrue((root / "CONCEPTS.md").is_file())

    def test_apply_preserves_same_inode_edit_between_check_and_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, candidate, shown = self._proposal(root)
            concurrent = "# Concepts\n\n## A\nConcurrent same-inode edit.\n"

            def edit(phase: str, _state: dict[str, Path]) -> None:
                if phase == "before_claim":
                    target.write_text(concurrent, encoding="utf-8")

            with self.assertRaisesRegex(
                glossary_file.ConcurrentGlossaryChange,
                "content changed during claim",
            ):
                self._apply_with_hook(root, candidate, shown, edit)

            self.assertEqual(target.read_text(encoding="utf-8"), concurrent)
            self.assertFalse(any(root.glob(".CONCEPTS.md.claim-*")))

    def test_apply_preserves_regular_path_replacement_before_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, candidate, shown = self._proposal(root)
            concurrent = "# Concepts\n\n## A\nConcurrent replacement.\n"

            def replace(phase: str, _state: dict[str, Path]) -> None:
                if phase == "before_claim":
                    replacement = root / "replacement.md"
                    replacement.write_text(concurrent, encoding="utf-8")
                    os.replace(replacement, target)

            with self.assertRaisesRegex(
                glossary_file.ConcurrentGlossaryChange,
                "content changed during claim",
            ):
                self._apply_with_hook(root, candidate, shown, replace)

            self.assertEqual(target.read_text(encoding="utf-8"), concurrent)
            self.assertFalse(any(root.glob(".CONCEPTS.md.claim-*")))

    def test_apply_preserves_symlink_swap_before_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, candidate, shown = self._proposal(root)
            outside = root / "outside.md"
            outside.write_text("outside stays untouched\n", encoding="utf-8")

            def replace_with_symlink(
                phase: str,
                _state: dict[str, Path],
            ) -> None:
                if phase == "before_claim":
                    target.unlink()
                    target.symlink_to(outside)

            with self.assertRaisesRegex(
                glossary_file.ConcurrentGlossaryChange,
                "changed during claim",
            ):
                self._apply_with_hook(root, candidate, shown, replace_with_symlink)

            self.assertTrue(target.is_symlink())
            self.assertEqual(target.readlink(), outside)
            self.assertEqual(
                outside.read_text(encoding="utf-8"),
                "outside stays untouched\n",
            )

    def test_apply_preserves_special_file_swap_before_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, candidate, shown = self._proposal(root)

            def replace_with_fifo(
                phase: str,
                _state: dict[str, Path],
            ) -> None:
                if phase == "before_claim":
                    target.unlink()
                    os.mkfifo(target)

            with self.assertRaisesRegex(
                glossary_file.ConcurrentGlossaryChange,
                "changed during claim",
            ):
                self._apply_with_hook(root, candidate, shown, replace_with_fifo)

            self.assertTrue(stat.S_ISFIFO(target.lstat().st_mode))

    def test_apply_preserves_hardlink_swap_before_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, candidate, shown = self._proposal(root)
            concurrent = root / "concurrent.md"
            concurrent.write_text(
                "# Concepts\n\n## A\nConcurrent hardlinked replacement.\n",
                encoding="utf-8",
            )

            def replace_with_hardlink(
                phase: str,
                _state: dict[str, Path],
            ) -> None:
                if phase == "before_claim":
                    target.unlink()
                    os.link(concurrent, target)

            with self.assertRaisesRegex(
                glossary_file.ConcurrentGlossaryChange,
                "changed during claim",
            ):
                self._apply_with_hook(root, candidate, shown, replace_with_hardlink)

            self.assertEqual(target.stat().st_ino, concurrent.stat().st_ino)
            self.assertEqual(target.stat().st_nlink, 2)
            self.assertIn(
                "Concurrent hardlinked replacement",
                target.read_text(encoding="utf-8"),
            )

    def test_apply_never_overwrites_target_created_after_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, candidate, shown = self._proposal(root)
            concurrent = "# Concepts\n\n## A\nAppeared after claim.\n"

            def occupy_target(
                phase: str,
                _state: dict[str, Path],
            ) -> None:
                if phase == "after_claim":
                    target.write_text(concurrent, encoding="utf-8")

            with self.assertRaisesRegex(
                glossary_file.ConcurrentGlossaryChange,
                "concurrent CONCEPTS.md was preserved",
            ):
                self._apply_with_hook(root, candidate, shown, occupy_target)

            self.assertEqual(target.read_text(encoding="utf-8"), concurrent)
            claims = list(root.glob(".CONCEPTS.md.claim-*"))
            self.assertEqual(len(claims), 1)
            self.assertIn(
                "Approved prior text",
                claims[0].read_text(encoding="utf-8"),
            )
            self.assertFalse(any(root.glob(".CONCEPTS.md.tmp-*")))

    def test_apply_preserves_all_versions_when_target_replaced_after_install(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, candidate, shown = self._proposal(root)
            concurrent = "# Concepts\n\n## A\nReplacement after install.\n"

            def replace_after_install(
                phase: str,
                _state: dict[str, Path],
            ) -> None:
                if phase == "after_install":
                    replacement = root / "replacement.md"
                    replacement.write_text(concurrent, encoding="utf-8")
                    os.replace(replacement, target)

            with self.assertRaisesRegex(
                glossary_file.ConcurrentGlossaryChange,
                "recovery files",
            ):
                self._apply_with_hook(root, candidate, shown, replace_after_install)

            self.assertEqual(target.read_text(encoding="utf-8"), concurrent)
            claims = list(root.glob(".CONCEPTS.md.claim-*"))
            temporaries = list(root.glob(".CONCEPTS.md.tmp-*"))
            self.assertEqual(len(claims), 1)
            self.assertEqual(len(temporaries), 1)
            self.assertIn("Approved prior text", claims[0].read_text(encoding="utf-8"))
            self.assertIn(
                "Approved candidate text",
                temporaries[0].read_text(encoding="utf-8"),
            )

    def test_stale_crashed_claim_is_recovered_before_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stranded_content = "# Concepts\n\n## A\nStranded prior text.\n"
            stranded = root / ".CONCEPTS.md.claim-deadbeefdeadbeef"
            stranded.write_text(stranded_content, encoding="utf-8")
            # Age the claim past the staleness threshold so recovery treats it
            # as a dead writer's leftovers, not a live claim.
            old = 1_000_000_000
            os.utime(stranded, (old, old))
            candidate = root / ".CONCEPTS.md.proposed"
            candidate.write_text("# Concepts\n\n## B\nNew text.\n", encoding="utf-8")
            shown = glossary_file.proposal(root, candidate)
            # The proposal was computed against an apparently-missing glossary;
            # apply must first restore the stranded claim and then refuse the
            # now-stale expected-current digest instead of overwriting.
            with self.assertRaises(ValueError):
                glossary_file.apply(
                    root,
                    candidate,
                    expected_current=str(shown["current_sha256"]),
                    expected_candidate=str(shown["candidate_sha256"]),
                )
            target = root / "CONCEPTS.md"
            self.assertEqual(target.read_text(encoding="utf-8"), stranded_content)
            self.assertFalse(stranded.exists())
            # Re-proposing against the recovered glossary applies cleanly.
            shown = glossary_file.proposal(root, candidate)
            glossary_file.apply(
                root,
                candidate,
                expected_current=str(shown["current_sha256"]),
                expected_candidate=str(shown["candidate_sha256"]),
            )
            self.assertIn("New text", target.read_text(encoding="utf-8"))

    def test_fresh_claims_are_not_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            live = root / ".CONCEPTS.md.claim-livewriter"
            live.write_text("# Concepts\n\n## A\nLive claim.\n", encoding="utf-8")
            glossary_file._recover_stale_claims(root)
            self.assertTrue(live.exists())
            self.assertFalse((root / "CONCEPTS.md").exists())


if __name__ == "__main__":
    unittest.main()
