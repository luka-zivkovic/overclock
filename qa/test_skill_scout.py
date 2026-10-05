from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO / "plugins/skill-scout/skills/skill-scout"
SCRIPT = SKILL_DIR / "scripts/skill_scout.py"
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(REPO / "qa/fixtures"))
import harness_fixtures  # noqa: E402
import skill_scout  # noqa: E402


def snapshot(root: Path) -> dict[str, str]:
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "dir"
            for path in sorted(root.rglob("*"))}


def run_scan(home: Path, *extra: str) -> dict:
    result = subprocess.run([sys.executable, str(SCRIPT), "scan", "--home", str(home), *extra],
                            capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def cluster_with(report: dict, term: str) -> dict | None:
    return next((item for item in report["clusters"] if term in item["terms"]), None)


class PlantedHistoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.home = Path(cls.tmp.name) / "home"
        cls.home.mkdir()
        harness_fixtures.build_history(cls.home)
        cls.before = snapshot(cls.home)
        cls.report = run_scan(cls.home)
        cls.raw = json.dumps(cls.report)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_recurring_request_spans_three_harnesses(self) -> None:
        notes = cluster_with(self.report, "release")
        self.assertIsNotNone(notes)
        self.assertEqual(notes["kind"], "request")
        self.assertEqual(notes["harnesses"], ["claude-code", "codex", "pi"])
        # Two interactive Claude sessions, one interactive Codex rollout, one Pi session, plus the
        # release-notes prompt inside the gadget session. Contaminated copies never count.
        self.assertEqual(notes["sessions"], 5)
        self.assertEqual(notes["prompts"], 5)
        self.assertEqual(notes["id"], "C1")

    def test_contamination_is_dropped(self) -> None:
        dropped = self.report["coverage"]["dropped"]
        for reason in ("injected", "tool_result", "command_output", "automated_session", "approval"):
            self.assertGreater(dropped.get(reason, 0), 0, reason)
        claude = self.report["coverage"]["harnesses"]["claude-code"]
        self.assertEqual(claude["automated"], 2)
        self.assertEqual(claude["subagent_files"], 2)
        self.assertEqual(claude["outside_window"], 1)
        self.assertEqual(self.report["coverage"]["harnesses"]["codex"]["automated"], 1)
        self.assertNotIn("internal context", self.raw)
        self.assertNotIn("Long skill body", self.raw)

    def test_under_triggering_skill_is_matched(self) -> None:
        description = cluster_with(self.report, "description")
        self.assertIsNotNone(description)
        self.assertEqual([match["name"] for match in description["installed_matches"]][:1], ["pr-description"])
        self.assertNotIn("pr-description", description["skills_used_in_these_sessions"])

    def test_repeated_correction_is_its_own_cluster(self) -> None:
        corrections = [item for item in self.report["clusters"] if item["kind"] == "correction"]
        self.assertEqual(len(corrections), 1)
        self.assertIn("pnpm", corrections[0]["terms"])
        self.assertEqual(corrections[0]["sessions"], 3)

    def test_one_offs_never_cluster(self) -> None:
        for prompt in harness_fixtures.ONE_OFFS:
            self.assertNotIn(prompt[:40], self.raw)

    def test_usage_signals(self) -> None:
        self.assertIn({"name": "compact", "count": 1}, self.report["usage"]["slash_commands"])
        invoked = {row["name"] for row in self.report["usage"]["skills_invoked"]}
        self.assertLessEqual({"lessons-learned", "pr-description", "pdf-tools"}, invoked)

    def test_secrets_are_redacted(self) -> None:
        self.assertNotIn(harness_fixtures.FAKE_GITHUB_TOKEN, self.raw)
        self.assertNotIn("Fixture0Token0", self.raw)
        self.assertIn("GITHUB_TOKEN=[REDACTED]", self.raw)

    def test_unknown_records_are_counted_not_fatal(self) -> None:
        self.assertEqual(self.report["coverage"]["harnesses"]["codex"]["unknown_records"], {"brand_new_record_type": 2})

    def test_scan_never_writes(self) -> None:
        self.assertEqual(snapshot(self.home), self.before)

    def test_samples_are_bounded_and_spread_across_sessions(self) -> None:
        notes = cluster_with(self.report, "release")
        self.assertLessEqual(len(notes["samples"]), skill_scout.MAX_SAMPLES)
        self.assertEqual(len({sample["session"] for sample in notes["samples"]}), len(notes["samples"]))
        for sample in notes["samples"]:
            self.assertLessEqual(len(sample["text"]), skill_scout.MAX_SAMPLE_CHARS + 1)


class ScopeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_sparse_history_yields_no_cluster(self) -> None:
        harness_fixtures.build_sparse_history(self.home)
        report = run_scan(self.home)
        self.assertEqual(report["clusters"], [])
        self.assertGreater(report["coverage"]["prompts_kept"], 0)

    def test_thresholds_and_filters(self) -> None:
        harness_fixtures.build_history(self.home)
        strict = run_scan(self.home, "--min-sessions", "6")
        self.assertEqual(strict["clusters"], [])
        only_pi = run_scan(self.home, "--harness", "pi")
        self.assertEqual(list(only_pi["coverage"]["harnesses"]), ["pi"])
        gadget = run_scan(self.home, "--project", "/Users/dev/gadget", "--min-sessions", "1", "--min-count", "1")
        self.assertTrue(all(item["projects"] == ["/Users/dev/gadget"] for item in gadget["clusters"]))
        everything = run_scan(self.home, "--days", "0", "--include-automated")
        notes = cluster_with(everything, "release")
        self.assertGreater(notes["sessions"], 5)

    def test_unsupported_harness_is_named(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPT), "scan", "--home", str(self.home), "--harness", "cursor"],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SQLite", result.stderr)

    def test_missing_history_is_an_empty_report(self) -> None:
        report = run_scan(self.home)
        self.assertEqual(report["clusters"], [])
        self.assertEqual(report["coverage"]["prompts_kept"], 0)


class UnitTest(unittest.TestCase):
    def test_tokens_drop_noise(self) -> None:
        words = skill_scout.tokens("Please fix `src/app.ts` at https://x.dev/a and commit abc1234 now, thanks")
        self.assertEqual(words, ["fix", "commit"])

    def test_cluster_links_paraphrases_only(self) -> None:
        prompts = [{"tokens": skill_scout.tokens(text)} for text in (
            "draft release notes since the last tag grouped by features and fixes",
            "release notes since last tag, grouped features fixes",
            "rename the billing module to invoicing",
        )]
        groups = sorted(sorted(group) for group in skill_scout.cluster(prompts, 0.45))
        self.assertEqual(groups, [[0, 1], [2]])

    def test_different_opening_verbs_do_not_link(self) -> None:
        texts = ["fix the csv importer behind the proxy", "explain the csv importer behind the proxy",
                 "fix the csv importer behind the proxy with large files"]
        prompts = [{"tokens": skill_scout.tokens(text), "action": skill_scout.action(text)} for text in texts]
        groups = sorted(sorted(group) for group in skill_scout.cluster(prompts, 0.45))
        self.assertEqual(groups, [[0, 2], [1]])
        self.assertEqual(skill_scout.action("can you draft the release notes"), "produce")
        self.assertIsNone(skill_scout.action("release notes please"))

    def test_bridging_prompt_cannot_chain_unrelated_groups(self) -> None:
        texts = ["alpha bravo charlie delta", "alpha bravo charlie delta echo foxtrot golf hotel",
                 "echo foxtrot golf hotel"]
        prompts = [{"tokens": skill_scout.tokens(text)} for text in texts]
        groups = skill_scout.cluster(prompts, 0.45)
        self.assertFalse(any(len(group) == 3 for group in groups), groups)

    def test_secret_fragments_never_become_terms(self) -> None:
        secret = "ghp_" + "Zebra0Fixture0" + "K" * 24
        words = skill_scout.tokens(skill_scout.redact(f"release notes then push with GITHUB_TOKEN={secret}"))
        self.assertFalse(any("zebra0" in word for word in words), words)

    def test_parse_time_accepts_epoch_and_iso(self) -> None:
        self.assertEqual(skill_scout.parse_time(0).year, 1970)
        self.assertEqual(skill_scout.parse_time("2026-09-01T10:00:00Z"), dt.datetime(2026, 9, 1, 10, tzinfo=dt.timezone.utc))
        self.assertIsNone(skill_scout.parse_time("yesterday"))

    def test_correction_requires_a_preceding_assistant_turn(self) -> None:
        session = skill_scout.Session("claude-code", Path("x.jsonl"), {"home": Path("/nonexistent")})
        session.add_prompt("no, use pnpm for installs", None)
        session.last_was_assistant = True
        session.add_prompt("no, use pnpm for installs", None)
        self.assertEqual([prompt["kind"] for prompt in session.prompts], ["request", "correction"])


if __name__ == "__main__":
    unittest.main()
