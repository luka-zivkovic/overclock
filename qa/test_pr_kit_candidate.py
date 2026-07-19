from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
CANDIDATE = REPO / "qa" / "experiments" / "pr-reviewer-phase0" / "candidate" / "pr-kit"
INITIALIZER = CANDIDATE / "skills" / "initialize-pr-kit"
REVIEWER = CANDIDATE / "skills" / "review-pr"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


profile_inputs = load_module("profile_inputs", INITIALIZER / "scripts" / "profile_inputs.py")
inventory = load_module("pr_kit_inventory", INITIALIZER / "scripts" / "inventory.py")
profile_validator = load_module(
    "validate_profile", INITIALIZER / "scripts" / "validate_profile.py"
)
write_profile_module = load_module(
    "pr_kit_write_profile", INITIALIZER / "scripts" / "write_profile.py"
)
review_scope = load_module("pr_kit_review_scope", REVIEWER / "scripts" / "review_scope.py")
findings_validator = load_module(
    "pr_kit_validate_findings", REVIEWER / "scripts" / "validate_findings.py"
)
review_inspector = load_module(
    "pr_kit_inspect_review", REVIEWER / "scripts" / "inspect_review.py"
)
control_setup = load_module(
    "pr_kit_control_setup",
    REPO / "qa" / "experiments" / "pr-reviewer-phase0" / "setup_control_case.py",
)


def valid_profile(sha: str = "1" * 40, digest: str = "a" * 64) -> str:
    return f"""---
schema_version: 2
repository: example/project
base_commit: {sha}
profile_inputs_digest: {digest}
generated_at: 2026-07-17T12:00:00Z
---

# PR Kit Repository Profile

## Review scope

- The CLI is a shipped surface. [source: README.md:10]

## Architecture and ownership

- Commands delegate to the core package. [source: src/cli.py:22]

## Critical invariants

- Tenant identifiers remain scoped through storage calls. [source: src/store.py:44]

## Trust boundaries and sensitive paths

- Webhook payloads are untrusted until signature verification. [source: src/webhooks.py:18]

## Failure modes and edge cases

- Retried deliveries reuse the event id. [source: tests/test_webhooks.py:31]

## Verification map

- `python3 -m unittest` — discovered; covers the core package. [source: pyproject.toml]

## Local conventions

- Public behavior changes require a changelog entry. [source: CONTRIBUTING.md:12]

## Verified precedents

- PR #42 established tenant-scoped cache keys. [source: PR #42 @ {'2' * 40}]

## Source index

- `README.md` — shipped surfaces. [source: README.md]
"""


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout.strip()


def commit_files(root: Path, files: dict[str, str], message: str) -> str:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        git(root, "add", relative)
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD")


def initialize_repo(root: Path) -> None:
    git(root, "init", "-q")
    git(root, "config", "user.email", "eval@example.com")
    git(root, "config", "user.name", "Eval")


def profile_repo(root: Path) -> tuple[str, str]:
    initialize_repo(root)
    files = {
        "README.md": "# Example\n" + "surface\n" * 12,
        "CONTRIBUTING.md": "# Contributing\n" + "rule\n" * 14,
        "pyproject.toml": "[project]\nname = 'example'\n",
        "src/cli.py": "command = 'run'\n" * 24,
        "src/store.py": "tenant = 'scoped'\n" * 46,
        "src/webhooks.py": "verified = True\n" * 20,
        "tests/test_webhooks.py": "assert True\n" * 34,
    }
    sha = commit_files(root, files, "base")
    digest = str(profile_inputs.digest_for_ref(root, sha)["profile_inputs_digest"])
    return sha, digest


def base_review_payload(changed_line: str = "    return 2") -> dict[str, object]:
    finding = {
        "priority": "P1",
        "title": "Preserve the prior result",
        "file": "src/worker.py",
        "line": 2,
        "side": "RIGHT",
        "changed_line": changed_line,
        "failure_path": "Calling work() now returns the wrong durable value.",
        "impact": "Callers persist an incorrect result.",
        "evidence": ["tests expect the prior value"],
        "introduced_by_diff": True,
        "confidence": "high",
        "suggested_comment": "Please preserve the prior result or update the contract explicitly.",
    }
    return {
        "findings": [finding],
        "coverage": {
            "activated_lenses": [
                "correctness", "failure-handling", "regression-coverage"
            ],
            "inspected_surfaces": ["src/worker.py and its direct callers"],
            "blind_spots": [],
            "testing_gaps": ["No failure-path test was present."],
        },
    }


class ProfileValidationTests(unittest.TestCase):
    def write_profile(self, root: Path, text: str) -> Path:
        path = root / ".ai" / "pr-kit" / "REPOSITORY.md"
        path.parent.mkdir(parents=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_accepts_source_grounded_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha, digest = profile_repo(root)
            path = self.write_profile(root, valid_profile(sha, digest))
            messages = profile_validator.validate(path, root)
            self.assertTrue(any("source-grounded bullets" in message for message in messages))
            self.assertTrue(any("profile_inputs_digest" in message for message in messages))

    def test_rejects_unsourced_bullet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = valid_profile().replace(
                "- Commands delegate to the core package. [source: src/cli.py:22]",
                "- Commands delegate to the core package.",
            )
            path = self.write_profile(root, text)
            with self.assertRaisesRegex(ValueError, "source tag"):
                profile_validator.validate(path, root)

    def test_rejects_traversal_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = valid_profile().replace(
                "[source: src/cli.py:22]",
                "[source: ../private/notes.md]",
            )
            path = self.write_profile(root, text)
            with self.assertRaisesRegex(ValueError, "source tag"):
                profile_validator.validate(path, root)

    def test_rejects_secret_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = valid_profile().replace(
                "The CLI is a shipped surface.",
                "The CLI uses api_key=super-secret-production-value.",
            )
            path = self.write_profile(root, text)
            with self.assertRaisesRegex(ValueError, "secret material"):
                profile_validator.validate(path, root)

    def test_rejects_profile_digest_that_does_not_match_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha, _ = profile_repo(root)
            path = self.write_profile(root, valid_profile(sha, "f" * 64))
            with self.assertRaisesRegex(ValueError, "digest does not match"):
                profile_validator.validate(path, root)

    def test_profile_check_marks_profile_input_change_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha, digest = profile_repo(root)
            path = self.write_profile(root, valid_profile(sha, digest))
            head = commit_files(
                root,
                {"pyproject.toml": "[project]\nname = 'changed'\n"},
                "change manifest",
            )
            result = profile_inputs.check_profile(root, path, head)
            self.assertEqual(result["status"], "stale")
            self.assertIn("profile inputs changed", " ".join(result["reasons"]))

    def test_profile_check_marks_changed_cited_source_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha, digest = profile_repo(root)
            path = self.write_profile(root, valid_profile(sha, digest))
            head = commit_files(root, {"src/store.py": "tenant = 'global'\n"}, "change source")
            result = profile_inputs.check_profile(root, path, head)
            self.assertEqual(result["status"], "stale")
            self.assertIn("src/store.py", result["changed_source_paths"])

    def test_profile_check_allows_unrelated_source_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha, digest = profile_repo(root)
            path = self.write_profile(root, valid_profile(sha, digest))
            head = commit_files(root, {"src/unrelated.py": "value = 2\n"}, "unrelated")
            result = profile_inputs.check_profile(root, path, head)
            self.assertEqual(result["status"], "fresh")

    def test_rejects_linked_profile_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "outside.md"
            target.write_text(valid_profile(), encoding="utf-8")
            profile = root / ".ai" / "pr-kit" / "REPOSITORY.md"
            profile.parent.mkdir(parents=True)
            profile.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "linked profile path"):
                profile_validator.validate(profile, root)

    def test_atomic_writer_preserves_valid_existing_profile_on_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha, digest = profile_repo(root)
            original = valid_profile(sha, digest)
            path, action = write_profile_module.write_profile(root, original)
            self.assertEqual(action, "created")
            with self.assertRaisesRegex(ValueError, "template placeholders"):
                write_profile_module.write_profile(
                    root,
                    original.replace("The CLI is a shipped surface.", "Replace with a surface."),
                )
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_atomic_writer_preserves_existing_profile_on_digest_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha, digest = profile_repo(root)
            original = valid_profile(sha, digest)
            path, _ = write_profile_module.write_profile(root, original)
            with self.assertRaisesRegex(ValueError, "digest does not match"):
                write_profile_module.write_profile(root, valid_profile(sha, "f" * 64))
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_atomic_writer_rejects_linked_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"
            outside.mkdir()
            (root / ".ai").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "linked profile parent"):
                write_profile_module.write_profile(root, valid_profile())

    def test_atomic_writer_rejects_hard_linked_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.write_profile(root, valid_profile())
            os.link(path, root / "second-link.md")
            with self.assertRaisesRegex(ValueError, "hard-linked profile target"):
                write_profile_module.write_profile(root, valid_profile())


class InventoryTests(unittest.TestCase):
    def test_skips_secrets_memory_dependencies_and_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Example\n", encoding="utf-8")
            (root / ".env").write_text("API_KEY=secret\n", encoding="utf-8")
            memory = root / ".ai" / "memory"
            memory.mkdir(parents=True)
            (memory / "LESSONS.md").write_text("private\n", encoding="utf-8")
            dependency = root / "node_modules" / "example"
            dependency.mkdir(parents=True)
            (dependency / "README.md").write_text("dependency\n", encoding="utf-8")
            outside = root / "outside"
            outside.mkdir()
            (outside / "SECURITY.md").write_text("outside\n", encoding="utf-8")
            (root / "linked").symlink_to(outside, target_is_directory=True)

            files, truncated = inventory.walk(root)
            paths = {item["path"] for item in files}
            self.assertFalse(truncated)
            self.assertIn("README.md", paths)
            self.assertNotIn(".env", paths)
            self.assertNotIn(".ai/memory/LESSONS.md", paths)
            self.assertNotIn("node_modules/example/README.md", paths)
            self.assertNotIn("linked/SECURITY.md", paths)

    def test_sanitizes_remote_credentials(self) -> None:
        self.assertEqual(
            inventory.sanitize_remote("https://token@example.com/owner/repo.git?secret=yes"),
            "https://example.com/owner/repo.git",
        )


class ReviewScopeTests(unittest.TestCase):
    def test_activates_silent_pass_lens_for_ci_that_can_false_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_repo(root)
            base = commit_files(
                root,
                {
                    "package.json": '{"scripts":{"test":"node --test"}}\n',
                    ".github/workflows/ci.yml": "steps:\n  - run: npm test\n",
                },
                "base",
            )
            head = commit_files(
                root,
                {".github/workflows/ci.yml": "steps:\n  - run: npm test || true\n"},
                "weaken gate",
            )
            result = review_scope.derive_scope(root, base, head)
            self.assertEqual(result["status"], "complete")
            self.assertTrue(result["silent_pass_verification"])
            self.assertIn("silent-pass-verification", result["activated_lenses"])

    def test_ordinary_feature_test_does_not_activate_silent_pass_lens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_repo(root)
            base = commit_files(root, {"tests/math.test.js": "assert.equal(sum(1, 1), 2)\n"}, "base")
            head = commit_files(
                root,
                {"tests/math.test.js": "assert.equal(sum(0, 0), 0)\n"},
                "add assertion",
            )
            result = review_scope.derive_scope(root, base, head)
            self.assertFalse(result["silent_pass_verification"])
            self.assertNotIn("silent-pass-verification", result["activated_lenses"])

    def test_invalid_endpoint_fails_closed_with_all_lenses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_repo(root)
            commit_files(root, {"README.md": "example\n"}, "base")
            result = review_scope.derive_scope(root, "missing", "HEAD")
            self.assertEqual(result["status"], "unknown")
            self.assertTrue(result["silent_pass_verification"])
            self.assertIn("security", result["activated_lenses"])


class FindingValidationTests(unittest.TestCase):
    def review_repo(self, root: Path) -> tuple[str, str]:
        initialize_repo(root)
        base = commit_files(root, {"src/worker.py": "def work():\n    return 1\n"}, "base")
        head = commit_files(root, {"src/worker.py": "def work():\n    return 2\n"}, "change")
        return base, head

    def test_accepts_exact_changed_line_and_assigns_stable_number(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head = self.review_repo(root)
            result, errors = findings_validator.validate_payload(
                base_review_payload(), root, base, head
            )
            self.assertEqual(errors, [])
            self.assertEqual(result["findings"][0]["number"], 1)
            self.assertEqual(result["findings"][0]["changed_line"], "return 2")

    def test_rejects_mismatched_source_quote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head = self.review_repo(root)
            result, errors = findings_validator.validate_payload(
                base_review_payload("return 999"), root, base, head
            )
            self.assertIsNone(result)
            self.assertTrue(any("does not match" in error for error in errors))

    def test_rejects_anchor_on_unchanged_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head = self.review_repo(root)
            payload = base_review_payload()
            payload["findings"][0]["line"] = 1
            payload["findings"][0]["changed_line"] = "def work():"
            result, errors = findings_validator.validate_payload(payload, root, base, head)
            self.assertIsNone(result)
            self.assertTrue(any("not anchored" in error for error in errors))

    def test_exact_duplicates_are_removed_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head = self.review_repo(root)
            payload = base_review_payload()
            payload["findings"].append(dict(payload["findings"][0]))
            result, errors = findings_validator.validate_payload(payload, root, base, head)
            self.assertEqual(errors, [])
            self.assertEqual(len(result["findings"]), 1)
            self.assertEqual(result["duplicates_removed"], 1)


class ReviewInspectionTests(unittest.TestCase):
    def review_repo(self, root: Path) -> tuple[str, str]:
        initialize_repo(root)
        base = commit_files(root, {"src/worker.py": "def work():\n    return 1\n"}, "base")
        head = commit_files(root, {"src/worker.py": "def work():\n    return 2\n"}, "head")
        return base, head

    def test_local_inspection_operations_preserve_repository_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head = self.review_repo(root)
            before_head = git(root, "rev-parse", "HEAD")
            before_status = git(root, "status", "--porcelain=v1", "--untracked-files=all")

            status = review_inspector.local_status(root)
            diff = review_inspector.local_diff(root, base, head, None)
            shown = review_inspector.local_show(root, head, "src/worker.py", 1, 2)
            history = review_inspector.local_log(root, head, "src/worker.py", 10)
            blame = review_inspector.local_blame(root, head, "src/worker.py", 1, 2)

            self.assertIn(head, status)
            self.assertIn("+    return 2", diff)
            self.assertIn("return 2", shown)
            self.assertIn("head", history)
            self.assertIn("filename src/worker.py", blame)
            self.assertEqual(git(root, "rev-parse", "HEAD"), before_head)
            self.assertEqual(
                git(root, "status", "--porcelain=v1", "--untracked-files=all"),
                before_status,
            )

    def test_inspector_cli_has_no_mutating_operation(self) -> None:
        script = REVIEWER / "scripts" / "inspect_review.py"
        result = subprocess.run(
            [sys.executable, str(script), "commit"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        source = script.read_text()
        for command in ('["gh", "pr", "review"', '["gh", "pr", "comment"', '["gh", "pr", "merge"'):
            self.assertNotIn(command, source)

    def test_inspector_rejects_paths_outside_repository(self) -> None:
        with self.assertRaisesRegex(ValueError, "repository-relative"):
            review_inspector.safe_path("../outside")


class BehavioralControlTests(unittest.TestCase):
    def test_controls_include_positive_and_negative_routes(self) -> None:
        controls = json.loads(
            (
                REPO
                / "qa"
                / "experiments"
                / "pr-reviewer-phase0"
                / "behavioral-controls.json"
            ).read_text()
        )
        self.assertEqual(
            {case["kind"] for case in controls["cases"]},
            {"positive", "negative"},
        )

    def test_materialized_controls_drive_expected_scope_routing(self) -> None:
        expectations = {
            "silent-pass-positive": True,
            "silent-pass-negative": False,
        }
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            for case_id, expected in expectations.items():
                result = control_setup.materialize(case_id, parent / case_id)
                scope = review_scope.derive_scope(
                    Path(result["repository"]), result["base"], result["head"]
                )
                self.assertEqual(scope["silent_pass_verification"], expected)
        self.assertEqual(
            inventory.sanitize_remote("git@example.com:owner/repo.git"),
            "example.com:owner/repo.git",
        )


class CandidateContractTests(unittest.TestCase):
    def test_candidate_is_not_published(self) -> None:
        marketplace = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())
        self.assertNotIn("pr-kit", {plugin["name"] for plugin in marketplace["plugins"]})

    def test_experiment_declares_three_arms(self) -> None:
        readme = (
            REPO / "qa" / "experiments" / "pr-reviewer-phase0" / "README.md"
        ).read_text()
        for arm in ("**Baseline:**", "**Generic:**", "**Initialized:**"):
            self.assertIn(arm, readme)
        cases = json.loads(
            (REPO / "qa" / "experiments" / "pr-reviewer-phase0" / "cases.json").read_text()
        )
        self.assertEqual(cases["schema_version"], 2)

    def test_review_skill_is_explicit_and_read_only(self) -> None:
        skill = (CANDIDATE / "skills" / "review-pr" / "SKILL.md").read_text()
        self.assertIn("disable-model-invocation: true", skill)
        self.assertIn("disallowed-tools: Write Edit", skill)
        self.assertIn("post a comment or review", skill.lower())
        self.assertIn("There is no writeful mode", skill)
        self.assertIn("scripts/inspect_review.py", skill)
        self.assertNotIn("Bash(git *)", skill)
        self.assertNotIn("Bash(gh *)", skill)
        self.assertIn("silent-pass-verification", skill)
        self.assertIn("scripts/validate_findings.py", skill)
        self.assertIn("compact coverage ledger", skill)

    def test_initializer_names_its_only_write_target(self) -> None:
        skill = (INITIALIZER / "SKILL.md").read_text()
        self.assertIn("`.ai/pr-kit/REPOSITORY.md`", skill)
        self.assertIn("Do not write any other file", skill)
        self.assertIn("never auto-commit", skill.lower())
        self.assertIn("disallowed-tools: Write Edit", skill)
        self.assertIn("profile_inputs_digest", skill)

    def test_explicit_invocation_policy_matches_both_skills(self) -> None:
        for skill_name in ("review-pr", "initialize-pr-kit"):
            metadata = (
                CANDIDATE / "skills" / skill_name / "agents" / "openai.yaml"
            ).read_text()
            self.assertIn(f"${skill_name}", metadata)
            self.assertIn("allow_implicit_invocation: false", metadata)

    def test_finding_schema_is_valid_json_and_requires_exact_source_text(self) -> None:
        schema = json.loads((REVIEWER / "references" / "finding-schema.json").read_text())
        required = schema["properties"]["findings"]["items"]["required"]
        self.assertIn("changed_line", required)
        self.assertIn("introduced_by_diff", required)


if __name__ == "__main__":
    unittest.main()
