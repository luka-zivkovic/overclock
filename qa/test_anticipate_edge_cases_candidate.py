from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parent.parent
EXPERIMENT = REPO / "qa" / "experiments" / "anticipate-edge-cases"
CANDIDATE = EXPERIMENT / "candidate" / "anticipate-edge-cases"
SKILL = CANDIDATE / "skills" / "anticipate-edge-cases"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


inspector = load_module(
    "anticipate_edge_cases_inspector",
    SKILL / "scripts" / "inspect_base.py",
)
control_setup = load_module(
    "anticipate_edge_cases_control_setup",
    EXPERIMENT / "setup_control_case.py",
)


def git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout)
    return completed.stdout.strip()


class CandidateStructureTests(unittest.TestCase):
    def test_candidate_is_one_standalone_skill(self) -> None:
        skills = sorted(
            path.parent.name for path in (CANDIDATE / "skills").glob("*/SKILL.md")
        )
        self.assertEqual(skills, ["anticipate-edge-cases"])
        manifest = json.loads(
            (CANDIDATE / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["name"], "anticipate-edge-cases")
        self.assertIn("phase0", manifest["version"])

    def test_skill_has_fresh_explicit_read_only_boundary(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("disable-model-invocation: true", text)
        self.assertIn("context: fork", text)
        self.assertIn("agent: Explore", text)
        self.assertIn('Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/inspect_base.py" *)', text)
        self.assertIn("disallowed-tools: Write Edit NotebookEdit Read Grep Glob", text)
        self.assertIn("Never inspect a diff", text)
        self.assertIn('inspect_base.py\" lenses', text)
        self.assertIn("Do not open the linked path with `cat`", text)
        self.assertIn("Do not prefix it with shell variable assignments", text)
        self.assertIn("exactly one helper invocation", text)
        self.assertIn("identity-consumer lens", text)
        self.assertIn("outside the producing subsystem", text)
        self.assertIn("do not count, parse, or revalidate the SHA", text)
        self.assertIn("Before resolving an analysis base or running any helper", text)
        self.assertLess(
            text.index("Before resolving an analysis base or running any helper"),
            text.index("## Resolve the intent and analysis base"),
        )
        self.assertIn("complete `analysis_base` in every evidence citation", text)
        self.assertIn("Implementation not inspected", text)
        self.assertNotIn("TODO", text)

    def test_openai_metadata_matches_explicit_invocation(self) -> None:
        text = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "Anticipate Edge Cases"', text)
        self.assertIn('$anticipate-edge-cases', text)
        self.assertIn("allow_implicit_invocation: false", text)

    def test_controls_declare_target_only_skill_evidence(self) -> None:
        controls = json.loads(
            (EXPERIMENT / "behavioral-controls.json").read_text(encoding="utf-8")
        )
        self.assertEqual(controls["skill_name"], "anticipate-edge-cases")
        self.assertEqual(controls["invocation"], "explicit")
        self.assertEqual(controls["install_modes"], ["skill"])
        self.assertEqual(
            {case["kind"] for case in controls["cases"]},
            {"positive", "negative"},
        )
        for case in controls["cases"]:
            self.assertIn("$anticipate-edge-cases", case["prompt"])


class BaseOnlyInspectorTests(unittest.TestCase):
    def materialize(self, root: Path, case_id: str = "webhook-retry-positive") -> dict[str, str]:
        return control_setup.materialize(case_id, root)

    def test_auto_resolution_uses_main_feature_merge_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "case"
            case = self.materialize(root)
            resolved = inspector.resolve_local(root, base_ref=None, head_ref=None)
            self.assertEqual(resolved["analysis_base"], case["base"])
            self.assertEqual(resolved["resolution"], "detected-default-merge-base")
            serialized = json.dumps(resolved)
            self.assertNotIn(case["head"], serialized)
            self.assertNotIn("IMPLEMENTATION_SENTINEL_SHOULD_NEVER_APPEAR", serialized)

    def test_show_and_search_return_base_content_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "case"
            case = self.materialize(root)
            shown = inspector.show_file(
                root,
                case["base"],
                "src/webhook_delivery.py",
                start=1,
                end=None,
            )
            searched = inspector.search_base(
                root,
                case["base"],
                "IMPLEMENTATION_SENTINEL_SHOULD_NEVER_APPEAR",
                prefix=None,
                limit=10,
            )
            self.assertIn("X-Delivery-ID", shown["text"])
            self.assertNotIn("IMPLEMENTATION_SENTINEL_SHOULD_NEVER_APPEAR", shown["text"])
            self.assertEqual(searched["matches"], [])

    def test_pr_resolution_uses_local_repo_and_does_not_return_head_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = parent / "case"
            case = self.materialize(root)
            fake_bin = parent / "bin"
            fake_bin.mkdir()
            capture = parent / "gh-cwd.txt"
            gh = fake_bin / "gh"
            gh.write_text(
                "#!/bin/sh\npwd > \"$GH_CWD_CAPTURE\"\nprintf '%s' \"$GH_PAYLOAD\"\n",
                encoding="utf-8",
            )
            gh.chmod(0o700)
            payload = json.dumps(
                {
                    "number": 42,
                    "title": "Retry timed-out webhook deliveries",
                    "body": "Retry outgoing webhooks up to three times.",
                    "url": "https://example.test/repo/pull/42",
                    "baseRefName": "main",
                    "headRefName": case["branch"],
                    "baseRefOid": case["base"],
                    "headRefOid": case["head"],
                    "closingIssuesReferences": [],
                }
            )
            environment = {
                "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
                "GH_CWD_CAPTURE": str(capture),
                "GH_PAYLOAD": payload,
            }
            with mock.patch.dict(os.environ, environment, clear=False):
                result = inspector.resolve_pr(root, "42")

            self.assertEqual(result["analysis_base"], case["base"])
            self.assertNotIn(case["head"], json.dumps(result))
            self.assertEqual(capture.read_text(encoding="utf-8").strip(), str(root.resolve()))

    def test_inspection_does_not_change_repository_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "case"
            case = self.materialize(root)
            before = (
                git(root, "rev-parse", "HEAD"),
                git(root, "branch", "--show-current"),
                git(root, "status", "--porcelain=v1", "--untracked-files=all"),
            )
            inspector.list_paths(root, case["base"], prefix="src", limit=20)
            inspector.search_base(
                root, case["base"], "delivery_id", prefix="src", limit=20
            )
            inspector.show_file(root, case["base"], "docs/webhooks.md", start=1, end=20)
            inspector.history(root, case["base"], path="src/webhook_delivery.py", limit=10)
            after = (
                git(root, "rev-parse", "HEAD"),
                git(root, "branch", "--show-current"),
                git(root, "status", "--porcelain=v1", "--untracked-files=all"),
            )
            self.assertEqual(after, before)

    def test_restricted_generated_and_link_paths_are_hidden(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-q")
            git(root, "config", "user.email", "test@example.com")
            git(root, "config", "user.name", "Test")
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / ".env").write_text("TOKEN=fake\n", encoding="utf-8")
            dependency = root / "node_modules" / "demo"
            dependency.mkdir(parents=True)
            (dependency / "index.js").write_text("secret = true\n", encoding="utf-8")
            (root / "linked.py").symlink_to("src/app.py")
            git(root, "add", ".")
            git(root, "commit", "-qm", "base")
            base = git(root, "rev-parse", "HEAD")

            listed = inspector.list_paths(root, base, prefix=None, limit=100)
            self.assertEqual(listed["paths"], ["src/app.py"])
            with self.assertRaisesRegex(ValueError, "restricted"):
                inspector.show_file(root, base, ".env", start=1, end=None)
            with self.assertRaisesRegex(ValueError, "absent|ambiguous"):
                inspector.show_file(root, base, "linked.py", start=1, end=None)

    def test_inspector_exposes_no_diff_or_worktree_command(self) -> None:
        command_parser = inspector.parser()
        subparsers = next(
            action
            for action in command_parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        self.assertEqual(
            set(subparsers.choices),
            {"resolve", "issue", "list", "search", "show", "log", "lenses"},
        )

    def test_inspection_requires_exact_commit_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "case"
            self.materialize(root)
            with self.assertRaisesRegex(ValueError, "40-character"):
                inspector.list_paths(root, "HEAD", prefix=None, limit=20)

    def test_bundled_lenses_have_stable_provenance(self) -> None:
        result = inspector.lenses()
        self.assertEqual(result["source"], "references/risk-lenses.md")
        self.assertEqual(len(result["sha256"]), 64)
        self.assertIn("Timeout after the remote side has succeeded", result["text"])
        self.assertIn("Identity and reference propagation", result["text"])

    def test_search_prefix_limits_results_and_rejects_restricted_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "case"
            case = self.materialize(root)
            result = inspector.search_base(
                root,
                case["base"],
                "delivery",
                prefix="src",
                limit=20,
            )
            self.assertEqual(result["prefix"], "src")
            self.assertTrue(result["matches"])
            self.assertTrue(
                all(match["path"].startswith("src/") for match in result["matches"])
            )
            with self.assertRaisesRegex(ValueError, "restricted"):
                inspector.search_base(
                    root,
                    case["base"],
                    "delivery",
                    prefix="node_modules",
                    limit=20,
                )


class ControlSetupTests(unittest.TestCase):
    def test_each_control_materializes_clean_main_feature_history(self) -> None:
        controls = json.loads(
            (EXPERIMENT / "behavioral-controls.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            for case in controls["cases"]:
                root = parent / case["id"]
                result = control_setup.materialize(case["id"], root)
                self.assertNotEqual(result["base"], result["head"])
                self.assertEqual(git(root, "status", "--porcelain"), "")
                self.assertEqual(git(root, "branch", "--show-current"), f"control/{case['id']}")
                self.assertEqual(
                    inspector.resolve_local(root, base_ref=None, head_ref=None)["analysis_base"],
                    result["base"],
                )


if __name__ == "__main__":
    unittest.main()
