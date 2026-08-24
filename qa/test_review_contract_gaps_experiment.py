from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT = ROOT / "qa" / "experiments" / "review-contract-gaps-phase0"
SKILL = EXPERIMENT / "candidates" / "codex" / "skills" / "review-contract-gaps"
V2_SKILL = EXPERIMENT / "candidates" / "codex-v2" / "skills" / "review-contract-gaps"
V3_SKILL = EXPERIMENT / "candidates" / "codex-v3" / "skills" / "review-contract-gaps"
V4_SKILL = EXPERIMENT / "candidates" / "codex-v4" / "skills" / "review-contract-gaps"
V5_SKILL = EXPERIMENT / "candidates" / "codex-v5" / "skills" / "review-contract-gaps"
CLAUDE_SKILL = (
    EXPERIMENT / "candidates" / "claude" / "skills" / "audit-consumer-contracts"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


validator = load_module("review_contract_gap_validator", SKILL / "scripts" / "validate_delta.py")
v2_assembler = load_module(
    "review_contract_gap_v2_assembler", V2_SKILL / "scripts" / "assemble_delta.py"
)
v3_assembler = load_module(
    "review_contract_gap_v3_assembler", V3_SKILL / "scripts" / "assemble_delta.py"
)
v4_assembler = load_module(
    "review_contract_gap_v4_assembler", V4_SKILL / "scripts" / "assemble_delta.py"
)
v5_assembler = load_module(
    "review_contract_gap_v5_assembler", V5_SKILL / "scripts" / "assemble_delta.py"
)
surface_extractor = load_module(
    "consumer_contract_surface_extractor", CLAUDE_SKILL / "scripts" / "extract_surface.py"
)
consumer_admitter = load_module(
    "consumer_contract_admitter", CLAUDE_SKILL / "scripts" / "admit_findings.py"
)
control_setup = load_module(
    "consumer_contract_control_setup", EXPERIMENT / "setup_control_case.py"
)


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


def commit(root: Path, files: dict[str, str], message: str) -> str:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        git(root, "add", relative)
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD")


def fixture(root: Path) -> tuple[str, str, Path]:
    git(root, "init", "-q")
    git(root, "config", "user.email", "eval@example.com")
    git(root, "config", "user.name", "Eval")
    base = commit(
        root,
        {
            "src/options.py": (
                'OPTIONS = {"auto": {"description": "Standard behavior"}}\n'
                "\n"
                "def render_option(option):\n"
                '    return option["description"]\n'
            )
        },
        "base",
    )
    head = commit(
        root,
        {
            "src/options.py": (
                'OPTIONS = {"auto": {"description": "Standard behavior"}}\n'
                "\n"
                "def render_option(option):\n"
                '    return option.get("description") or "Requires chat trigger"\n'
            )
        },
        "add fallback hint",
    )
    review = root / "frozen-review.md"
    review.write_text("No actionable findings.\n", encoding="utf-8")
    return base, head, review


def valid_payload(root: Path, base: str, head: str, review: Path) -> dict[str, object]:
    base_line = 'OPTIONS = {"auto": {"description": "Standard behavior"}}'
    changed_line = '    return option.get("description") or "Requires chat trigger"'
    digest = hashlib.sha256(review.read_bytes()).hexdigest()
    return {
        "schema_version": 1,
        "base": base,
        "head": head,
        "base_review_sha256": digest,
        "rows": [
            {
                "id": "C1",
                "decision": "Use the existing description before the new fallback hint.",
                "changed_anchor": {
                    "path": "src/options.py",
                    "line": 4,
                    "ref": head,
                    "line_text": changed_line,
                    "role": "new fallback",
                    "side": "RIGHT",
                },
                "contract": {
                    "path": "src/options.py",
                    "line": 1,
                    "ref": base,
                    "line_text": base_line,
                    "role": "production option definition",
                    "statement": "The auto option already supplies a non-empty description.",
                },
                "producer": {
                    "path": "src/options.py",
                    "line": 1,
                    "ref": base,
                    "line_text": base_line,
                    "role": "real option producer",
                },
                "consumers": [
                    {
                        "path": "src/options.py",
                        "line": 4,
                        "ref": head,
                        "line_text": changed_line,
                        "role": "description renderer",
                    }
                ],
                "guards_checked": [
                    "The production value is non-empty, so Python's `or` does not reach the fallback."
                ],
                "scenario": {
                    "precondition": "Render the real auto option.",
                    "action": "Evaluate render_option with its production object.",
                    "observable_failure": "The new chat-trigger hint is never displayed.",
                },
                "review_coverage": {
                    "status": "uncovered",
                    "reason": "The frozen review contains no finding about description precedence.",
                },
                "disposition": "confirmed-gap",
                "root_cause_key": "existing-description-shadows-new-fallback",
                "reason": "A reachable production value defeats the behavior added on the changed line.",
            }
        ],
        "findings": [
            {
                "row_id": "C1",
                "priority": "P2",
                "confidence": "high",
                "title": "Existing description makes the new hint unreachable",
                "file": "src/options.py",
                "line": 4,
                "side": "RIGHT",
                "changed_line": changed_line,
                "failure_path": "The production auto option has a truthy description, so the fallback is skipped.",
                "impact": "Users never see the explanation added by this change.",
                "evidence": [
                    "The base producer supplies Standard behavior.",
                    "The changed renderer evaluates the old description first.",
                    "The value is truthy.",
                    "The frozen review does not cover this root cause.",
                ],
                "suggested_comment": "Use the new hint deliberately instead of placing it behind the existing description.",
            }
        ],
        "coverage": {
            "changed_decisions": 1,
            "rows": 1,
            "confirmed_gaps": 1,
            "handled": 0,
            "covered": 0,
            "unreachable": 0,
            "unresolved": 0,
            "inspected_surfaces": ["src/options.py producer and renderer"],
            "blind_spots": [],
        },
    }


def v2_payload() -> dict[str, object]:
    return {
        "schema_version": 2,
        "claims": [
            {
                "id": "C1",
                "decision": "Use the existing description before the new fallback hint.",
                "root_cause_key": "existing-description-shadows-new-fallback",
                "changed_anchor": {
                    "path": "src/options.py",
                    "line_hint": 99,
                    "snippet": 'return   option.get("description") or "Requires chat trigger"',
                    "side": "RIGHT",
                    "role": "new fallback",
                },
                "contract": {
                    "path": "src/options.py",
                    "line_hint": 1,
                    "snippet": 'OPTIONS = {"auto": {"description": "Standard behavior"}}',
                    "ref": "base",
                    "role": "production option definition",
                    "statement": "The auto option already supplies a non-empty description.",
                },
                "producer": {
                    "path": "src/options.py",
                    "line_hint": 1,
                    "snippet": 'OPTIONS = {"auto": {"description": "Standard behavior"}}',
                    "ref": "base",
                    "role": "real option producer",
                },
                "consumers": [
                    {
                        "path": "src/options.py",
                        "line_hint": 4,
                        "snippet": 'return option.get("description") or "Requires chat trigger"',
                        "ref": "head",
                        "role": "description renderer",
                    }
                ],
                "guards_checked": [
                    "The production value is non-empty, so the fallback is unreachable."
                ],
                "scenario": {
                    "precondition": "Render the real auto option.",
                    "action": "Evaluate render_option with its production object.",
                    "observable_failure": "The new chat-trigger hint is never displayed.",
                },
                "priority": "P2",
                "confidence": "high",
                "title": "Existing description makes the new hint unreachable",
                "failure_path": "The truthy production description wins before the fallback.",
                "impact": "Users never see the explanation added by this change.",
                "suggested_comment": "Make the new explanation reachable for the production option.",
            }
        ],
        "inspected_surfaces": ["src/options.py producer and renderer"],
        "blind_spots": [],
    }


def consumer_fixture(root: Path) -> tuple[str, str, Path]:
    git(root, "init", "-q")
    git(root, "config", "user.email", "eval@example.com")
    git(root, "config", "user.name", "Eval")
    base = commit(
        root,
        {
            "src/definitions.py": 'AUTO = {"description": "Standard behavior"}\n',
            "src/renderer.py": (
                "def render_option(option):\n"
                '    return option["description"]\n'
            ),
        },
        "base",
    )
    head = commit(
        root,
        {
            "src/renderer.py": (
                "def render_option(option):\n"
                '    return option.get("description") or "Requires chat trigger"\n'
            )
        },
        "add fallback hint",
    )
    review = root / "consumer-review.md"
    review.write_text("No actionable findings.\n", encoding="utf-8")
    return base, head, review


class SkillShapeTests(unittest.TestCase):
    def test_metadata_is_explicit_and_collision_averse(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        metadata = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("disable-model-invocation: true", skill)
        self.assertIn("Do not use as the primary PR review", skill)
        self.assertIn("allow_implicit_invocation: false", metadata)
        self.assertIn("$review-contract-gaps", metadata)

    def test_skill_is_append_only_and_requires_actual_implementation(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("implementation mechanisms actually present", text)
        self.assertIn("Return an append-only delta", text)
        self.assertIn("Do not repeat the base review", text)
        self.assertIn("No verified contract gaps beyond the frozen review.", text)
        self.assertNotIn("TODO", text)

    def test_schema_is_valid_json(self) -> None:
        schema = json.loads(
            (SKILL / "references" / "contract-gap-output-schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(schema["properties"]["schema_version"], {"const": 1})

    def test_claude_candidate_is_explicit_and_consumer_scoped(self) -> None:
        skill = (CLAUDE_SKILL / "SKILL.md").read_text(encoding="utf-8")
        metadata = (CLAUDE_SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("disable-model-invocation: true", skill)
        self.assertIn("pre-existing producer or consumer contracts", skill)
        self.assertIn("base tree outside changed files", skill)
        self.assertIn("never consumes an implementation-blind edge brief", skill)
        self.assertIn("allow_implicit_invocation: false", metadata)
        self.assertIn("$audit-consumer-contracts", metadata)
        self.assertNotIn("TODO", skill)

    def test_claude_machine_output_schema_is_valid_json(self) -> None:
        schema = json.loads(
            (
                CLAUDE_SKILL
                / "references"
                / "contract-audit-output-schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(schema["properties"]["schema_version"], {"const": 1})
        self.assertEqual(
            schema["$defs"]["decision"]["properties"]["disposition"]["enum"],
            [
                "confirmed-new-finding",
                "already-covered",
                "defeated",
                "unreachable",
                "unresolved",
            ],
        )


class ValidatorTests(unittest.TestCase):
    def test_indexes_review_without_modifying_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            review = Path(tmp) / "review.md"
            review.write_text("### [P1] Preserve the contract\n", encoding="utf-8")
            before = review.read_bytes()
            result = validator.review_digest(review)
            self.assertEqual(result["sha256"], hashlib.sha256(before).hexdigest())
            self.assertEqual(result["actionable_heading_count"], 1)
            self.assertEqual(review.read_bytes(), before)

    def test_accepts_one_confirmed_contract_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, review = fixture(root)
            payload = valid_payload(root, base, head, review)
            result, errors = validator.validate_payload(
                payload,
                root,
                base,
                head,
                validator.unique_merge_base(root, base, head),
                hashlib.sha256(review.read_bytes()).hexdigest(),
            )
            self.assertEqual(errors, [])
            self.assertEqual(result["findings"], 1)

    def test_rejects_confirmed_row_already_covered_by_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, review = fixture(root)
            payload = valid_payload(root, base, head, review)
            payload["rows"][0]["review_coverage"]["status"] = "covered"
            _, errors = validator.validate_payload(
                payload,
                root,
                base,
                head,
                validator.unique_merge_base(root, base, head),
                hashlib.sha256(review.read_bytes()).hexdigest(),
            )
            self.assertTrue(any("requires uncovered" in error for error in errors))

    def test_rejects_non_changed_finding_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, review = fixture(root)
            payload = valid_payload(root, base, head, review)
            payload["rows"][0]["changed_anchor"]["line"] = 1
            payload["rows"][0]["changed_anchor"]["line_text"] = payload["rows"][0]["contract"][
                "line_text"
            ]
            payload["findings"][0]["line"] = 1
            payload["findings"][0]["changed_line"] = payload["rows"][0]["contract"]["line_text"]
            _, errors = validator.validate_payload(
                payload,
                root,
                base,
                head,
                validator.unique_merge_base(root, base, head),
                hashlib.sha256(review.read_bytes()).hexdigest(),
            )
            self.assertTrue(any("not anchored to a changed" in error for error in errors))

    def test_rejects_stale_review_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, review = fixture(root)
            payload = valid_payload(root, base, head, review)
            payload["base_review_sha256"] = "f" * 64
            _, errors = validator.validate_payload(
                payload,
                root,
                base,
                head,
                validator.unique_merge_base(root, base, head),
                hashlib.sha256(review.read_bytes()).hexdigest(),
            )
            self.assertIn("base_review_sha256 does not match the frozen review", errors)

    def test_rejects_duplicate_root_causes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, review = fixture(root)
            payload = valid_payload(root, base, head, review)
            duplicate = json.loads(json.dumps(payload["rows"][0]))
            duplicate["id"] = "C2"
            duplicate["disposition"] = "handled"
            duplicate["review_coverage"]["status"] = "uncovered"
            payload["rows"].append(duplicate)
            payload["coverage"]["changed_decisions"] = 2
            payload["coverage"]["rows"] = 2
            payload["coverage"]["handled"] = 1
            _, errors = validator.validate_payload(
                payload,
                root,
                base,
                head,
                validator.unique_merge_base(root, base, head),
                hashlib.sha256(review.read_bytes()).hexdigest(),
            )
            self.assertTrue(any("duplicate root_cause_key" in error for error in errors))


class V2AssemblerTests(unittest.TestCase):
    def test_v2_skill_separates_discovery_from_review_and_forbids_repairs(self) -> None:
        skill = (V2_SKILL / "SKILL.md").read_text(encoding="utf-8")
        metadata = (V2_SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("Do not read or summarize the frozen review while discovering", skill)
        self.assertIn("Never launch a model repair session", skill)
        self.assertIn("rejects only the malformed claim", skill)
        self.assertIn("disable-model-invocation: true", skill)
        self.assertIn("allow_implicit_invocation: false", metadata)
        self.assertIn("$review-contract-gaps", metadata)

    def test_v2_schemas_remove_model_authored_hashes_lines_and_counts(self) -> None:
        claims = json.loads(
            (V2_SKILL / "references" / "semantic-claims-output-schema.json").read_text(
                encoding="utf-8"
            )
        )
        coverage = json.loads(
            (V2_SKILL / "references" / "review-coverage-output-schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(claims["properties"]["schema_version"], {"const": 2})
        serialized = json.dumps(claims)
        self.assertNotIn("line_text", serialized)
        self.assertNotIn("base_review_sha256", serialized)
        self.assertNotIn("changed_decisions", serialized)
        self.assertEqual(coverage["properties"]["schema_version"], {"const": 1})

    def test_materializer_resolves_approximate_hints_and_authors_exact_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, review = fixture(root)
            result = v2_assembler.materialize_claims(
                v2_payload(), root, base, head, review
            )
            self.assertEqual(result["status"], "materialized")
            self.assertEqual(result["metrics"]["accepted_claims"], 1)
            self.assertTrue(result["metrics"]["fully_materialized"])
            claim = result["accepted_claims"][0]
            self.assertEqual(claim["changed_anchor"]["line"], 4)
            self.assertEqual(claim["changed_anchor"]["ref"], head)
            self.assertEqual(claim["contract"]["ref"], base)
            self.assertEqual(
                result["base_review_sha256"], hashlib.sha256(review.read_bytes()).hexdigest()
            )

    def test_materializer_rejects_one_bad_claim_without_erasing_a_valid_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, review = fixture(root)
            payload = v2_payload()
            bad = json.loads(json.dumps(payload["claims"][0]))
            bad["id"] = "C2"
            bad["root_cause_key"] = "unresolvable-second-claim"
            bad["changed_anchor"]["snippet"] = "this source line does not exist"
            payload["claims"].append(bad)
            result = v2_assembler.materialize_claims(payload, root, base, head, review)
            self.assertEqual(result["metrics"]["accepted_claims"], 1)
            self.assertEqual(result["metrics"]["rejected_claims"], 1)
            self.assertFalse(result["metrics"]["fully_materialized"])
            self.assertEqual(result["rejected_claims"][0]["claim_id"], "C2")

    def test_finalizer_admits_only_uncovered_and_fails_missing_decisions_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, review = fixture(root)
            materialized = v2_assembler.materialize_claims(
                v2_payload(), root, base, head, review
            )
            uncovered = {
                "schema_version": 1,
                "decisions": [
                    {
                        "claim_id": "C1",
                        "status": "uncovered",
                        "reason": "The frozen review does not describe this precedence defect.",
                    }
                ],
            }
            admitted = v2_assembler.finalize_claims(materialized, uncovered, review)
            self.assertEqual(len(admitted["findings"]), 1)
            self.assertTrue(admitted["coverage"]["coverage_complete"])
            rendered = v2_assembler.render_delta(admitted)
            self.assertIn(b"Existing description makes the new hint unreachable", rendered)

            missing = v2_assembler.finalize_claims(
                materialized, {"schema_version": 1, "decisions": []}, review
            )
            self.assertEqual(missing["findings"], [])
            self.assertEqual(missing["rejections"]["missing_coverage_decisions"], ["C1"])
            self.assertFalse(missing["coverage"]["coverage_complete"])

    def test_finalizer_rejects_review_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, review = fixture(root)
            materialized = v2_assembler.materialize_claims(
                v2_payload(), root, base, head, review
            )
            review.write_text("Changed review.\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest changed"):
                v2_assembler.finalize_claims(
                    materialized,
                    {"schema_version": 1, "decisions": []},
                    review,
                )


class V3AssemblerTests(unittest.TestCase):
    def test_v3_preserves_semantic_workflow_and_documents_bounded_hints(self) -> None:
        skill = (V3_SKILL / "SKILL.md").read_text(encoding="utf-8")
        contract = (V3_SKILL / "references" / "admission-contract.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Do not read or summarize the frozen review while discovering", skill)
        self.assertIn("one or more source lines", skill)
        self.assertIn("abbreviate surrounding text with `...`", skill)
        self.assertIn("never accepted without lexical overlap", contract)

    def test_multiline_hints_resolve_to_concrete_source_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, review = fixture(root)
            payload = v2_payload()
            claim = payload["claims"][0]
            claim["changed_anchor"]["snippet"] = (
                "def render_option(option):\n"
                '    return option.get("description") or "Requires chat trigger"\n'
                "..."
            )
            claim["contract"]["snippet"] = (
                'OPTIONS = {"auto": {"description": "Standard behavior"}}\n'
                "\n"
                "def render_option(option):"
            )
            result = v3_assembler.materialize_claims(payload, root, base, head, review)
            self.assertEqual(result["status"], "materialized")
            self.assertEqual(result["metrics"]["accepted_claims"], 1)
            self.assertEqual(result["accepted_claims"][0]["changed_anchor"]["line"], 4)
            self.assertEqual(result["accepted_claims"][0]["contract"]["line"], 1)

    def test_abbreviated_hint_resolves_when_it_contains_a_real_source_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, review = fixture(root)
            payload = v2_payload()
            payload["claims"][0]["changed_anchor"]["snippet"] = (
                'return option.get("description") or "Requires chat trigger"  ...'
            )
            result = v3_assembler.materialize_claims(payload, root, base, head, review)
            self.assertEqual(result["metrics"]["accepted_claims"], 1)
            self.assertEqual(result["accepted_claims"][0]["changed_anchor"]["line"], 4)

    def test_line_hint_without_lexical_overlap_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, review = fixture(root)
            payload = v2_payload()
            payload["claims"][0]["changed_anchor"].update(
                {"line_hint": 4, "snippet": "...\nthis source line does not exist\n..."}
            )
            result = v3_assembler.materialize_claims(payload, root, base, head, review)
            self.assertEqual(result["metrics"]["accepted_claims"], 0)
            self.assertIn(
                "no concrete snippet fragment matches an allowed source line",
                result["rejected_claims"][0]["errors"][0],
            )

    def test_changed_hint_still_cannot_anchor_an_unchanged_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, review = fixture(root)
            payload = v2_payload()
            payload["claims"][0]["changed_anchor"].update(
                {
                    "line_hint": 1,
                    "snippet": 'OPTIONS = {"auto": {"description": "Standard behavior"}}',
                }
            )
            result = v3_assembler.materialize_claims(payload, root, base, head, review)
            self.assertEqual(result["metrics"]["accepted_claims"], 0)


class V4AssemblerTests(unittest.TestCase):
    def test_v4_contract_requires_real_changed_and_base_evidence(self) -> None:
        skill = (V4_SKILL / "SKILL.md").read_text(encoding="utf-8")
        schema = json.loads(
            (V4_SKILL / "references" / "semantic-claims-output-schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn("Do not use unchanged code", skill)
        self.assertIn("Contract evidence must exist in the base tree", skill)
        changed_description = schema["$defs"]["changed_hint"]["properties"]["snippet"][
            "description"
        ]
        contract_description = schema["$defs"]["contract_hint"]["properties"]["snippet"][
            "description"
        ]
        self.assertIn("genuinely added or removed", changed_description)
        self.assertIn("base tree", contract_description)

    def test_v4_resolves_the_intended_line_before_changed_membership(self) -> None:
        lines = [
            "const unrelated = buildRequest(",
            "    workflowId,",
            ");",
            "",
            "async archiveIfAiTemporary(workflowId: string) {",
            "    assertNotReadOnly();",
            "    await workflowService.archive(user, workflowId, { skipArchived: true });",
            "}",
        ]
        snippet = (
            "async archiveIfAiTemporary(workflowId: string) {\n"
            "    assertNotReadOnly();\n"
            "    ...\n"
            "    await workflowService.archive(user, workflowId, { skipArchived: true });"
        )
        with self.assertRaisesRegex(ValueError, "intended source line is not a changed line"):
            v4_assembler.choose_line(lines, snippet, 5, {2})

    def test_v4_discards_short_generic_fragments(self) -> None:
        with self.assertRaisesRegex(ValueError, "distinctive source line"):
            v4_assembler.choose_line(["workflowId,"], "workflowId,", 1, {1})

    def test_v4_accepts_multiline_hint_when_intended_line_is_changed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, review = fixture(root)
            payload = v2_payload()
            payload["claims"][0]["changed_anchor"]["snippet"] = (
                "def render_option(option):\n"
                '    return option.get("description") or "Requires chat trigger"\n'
                "..."
            )
            result = v4_assembler.materialize_claims(payload, root, base, head, review)
            self.assertEqual(result["metrics"]["accepted_claims"], 1)
            self.assertEqual(result["accepted_claims"][0]["changed_anchor"]["line"], 4)

    def test_v4_accepts_trailing_ellipsis_only_after_strong_source_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, review = fixture(root)
            payload = v2_payload()
            payload["claims"][0]["changed_anchor"]["snippet"] = (
                'return option.get("description") or "Requires chat trigger" ...'
            )
            result = v4_assembler.materialize_claims(payload, root, base, head, review)
            self.assertEqual(result["metrics"]["accepted_claims"], 1)


class V5AssemblerTests(unittest.TestCase):
    def test_v5_accepts_distinctive_one_identifier_source_lines(self) -> None:
        lines = ["<NodeToolSettingsContent", "...promptTypeOptions,"]
        self.assertEqual(
            v5_assembler.choose_line(lines, "<NodeToolSettingsContent", 1, None), 1
        )
        self.assertEqual(v5_assembler.choose_line(lines, "...promptTypeOptions,", 2, None), 2)

    def test_v5_keeps_the_v3_generic_fragment_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "distinctive source line"):
            v5_assembler.choose_line(["workflowId,"], "workflowId,", 1, {1})

    def test_v5_still_rejects_unchanged_intended_blocks(self) -> None:
        lines = [
            "const unrelated = buildRequest(",
            "    workflowId,",
            ");",
            "async archiveIfAiTemporary(workflowId: string) {",
            "    await workflowService.archive(user, workflowId, { skipArchived: true });",
            "}",
        ]
        snippet = (
            "async archiveIfAiTemporary(workflowId: string) {\n"
            "...\n"
            "await workflowService.archive(user, workflowId, { skipArchived: true });"
        )
        with self.assertRaisesRegex(ValueError, "intended source line is not a changed line"):
            v5_assembler.choose_line(lines, snippet, 4, {2})


class ConsumerCandidateTests(unittest.TestCase):
    def test_extractor_finds_external_description_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, _ = consumer_fixture(root)
            result = surface_extractor.extract(root, base, head, 20, 20)
            matches = [item for item in result["surfaces"] if item["token"] == "description"]
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["base_matches"][0]["path"], "src/definitions.py")
            self.assertNotIn("src/renderer.py", {hit["path"] for hit in matches[0]["base_matches"]})

    def test_extractor_noops_when_change_has_no_external_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-q")
            git(root, "config", "user.email", "eval@example.com")
            git(root, "config", "user.name", "Eval")
            base = commit(root, {"README.md": "Old wording.\n"}, "base")
            head = commit(root, {"README.md": "Clearer prose.\n"}, "wording")
            result = surface_extractor.extract(root, base, head, 20, 20)
            self.assertEqual(result["surface_count"], 0)

    def candidate_payload(
        self,
        surface: dict[str, object],
        surface_json: str,
        review: Path,
    ) -> dict[str, object]:
        item = next(entry for entry in surface["surfaces"] if entry["token"] == "description")
        consumer = item["base_matches"][0]
        anchor = next(entry for entry in item["changed_anchors"] if entry["side"] == "RIGHT")
        return {
            "schema_version": 1,
            "base": surface["base"],
            "head": surface["head"],
            "surface_sha256": hashlib.sha256(surface_json.encode("utf-8")).hexdigest(),
            "base_review_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
            "decisions": [
                {
                    "surface_id": item["surface_id"],
                    "disposition": "confirmed-new-finding",
                    "root_cause_key": "existing-description-shadows-new-fallback",
                    "reason": "The production consumer supplies a truthy value before the fallback.",
                    "external_endpoint": {
                        **consumer,
                        "role": "production option definition",
                        "direction": "producer",
                        "expectation": "The option description is already non-empty.",
                    },
                    "head_evidence": {
                        "path": anchor["path"],
                        "line": anchor["line"],
                        "ref": surface["head"],
                        "line_text": anchor["text"],
                        "role": "fallback expression",
                    },
                    "reachable_sequence": "A real option reaches render_option with its existing description.",
                    "guards_checked": ["The existing description is truthy."],
                    "finding": {
                        "priority": "P2",
                        "confidence": "high",
                        "title": "Existing description makes the new hint unreachable",
                        "file": anchor["path"],
                        "line": anchor["line"],
                        "side": anchor["side"],
                        "changed_line": anchor["text"],
                        "failure_path": "The existing description wins before the fallback.",
                        "impact": "Users do not see the added hint.",
                        "evidence": [
                            "The base consumer supplies a description.",
                            "The changed expression evaluates it first.",
                            "The value is truthy.",
                            "The frozen review omits this root cause.",
                        ],
                        "suggested_comment": "Make the new explanation reachable for the production option.",
                    },
                }
            ],
            "coverage": {
                "surfaced": len(surface["surfaces"]),
                "verified": 1,
                "confirmed": 1,
                "already_covered": 0,
                "defeated": 0,
                "unreachable": 0,
                "unresolved": 0,
                "skipped": len(surface["surfaces"]) - 1,
                "blind_spots": [],
            },
        }

    def test_admitter_accepts_extractor_listed_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, review = consumer_fixture(root)
            surface = surface_extractor.extract(root, base, head, 20, 20)
            surface_json = json.dumps(surface, sort_keys=True)
            payload = self.candidate_payload(surface, surface_json, review)
            result, errors = consumer_admitter.validate(
                payload,
                surface,
                hashlib.sha256(surface_json.encode("utf-8")).hexdigest(),
                root,
                surface["base"],
                surface["head"],
                hashlib.sha256(review.read_bytes()).hexdigest(),
            )
            self.assertEqual(errors, [])
            self.assertEqual(result["admitted_findings"], 1)

    def test_admitter_cli_accepts_frozen_surface_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, review = consumer_fixture(root)
            surface = surface_extractor.extract(root, base, head, 20, 20)
            surface_path = root / ".eval-surface.json"
            surface_path.write_text(
                json.dumps(surface, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            surface_raw = surface_path.read_bytes()
            payload = self.candidate_payload(
                surface,
                surface_raw.decode("utf-8"),
                review,
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLAUDE_SKILL / "scripts" / "admit_findings.py"),
                    "--repo",
                    str(root),
                    "--base",
                    base,
                    "--head",
                    head,
                    "--surface-file",
                    str(surface_path),
                    "--review",
                    str(review),
                ],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["admitted_findings"], 1)

    def test_admitter_rejects_unsupplied_issue_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head, review = consumer_fixture(root)
            surface = surface_extractor.extract(root, base, head, 20, 20)
            surface_json = json.dumps(surface, sort_keys=True)
            payload = self.candidate_payload(surface, surface_json, review)
            payload["decisions"][0]["finding"]["evidence"].append("Issue #27417 requires this.")
            _, errors = consumer_admitter.validate(
                payload,
                surface,
                hashlib.sha256(surface_json.encode("utf-8")).hexdigest(),
                root,
                surface["base"],
                surface["head"],
                hashlib.sha256(review.read_bytes()).hexdigest(),
            )
            self.assertTrue(any("external PR/issue claim" in error for error in errors))


class ControlTests(unittest.TestCase):
    def test_controls_are_explicit_target_only_evidence(self) -> None:
        payload = json.loads((EXPERIMENT / "behavioral-controls.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["skill_name"], "audit-consumer-contracts")
        self.assertEqual(payload["invocation"], "explicit")
        self.assertEqual(payload["install_modes"], ["skill"])
        self.assertEqual(
            {case["kind"] for case in payload["cases"]},
            {"positive", "negative"},
        )
        for case in payload["cases"]:
            self.assertIn("$audit-consumer-contracts", case["prompt"])

    def test_routing_controls_include_sibling_and_fix_negatives(self) -> None:
        payload = json.loads((EXPERIMENT / "routing-controls.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["invocation"], "explicit")
        negatives = "\n".join(payload["should_not_trigger"])
        self.assertIn("anticipate edge cases", negatives)
        self.assertIn("Fix the findings", negatives)

    def test_control_surfaces_match_registered_shapes(self) -> None:
        expected = {
            "shadowed-fallback-positive": "description",
            "persisted-key-positive": "dataTableId",
            "alias-handled-negative": "dataTableId",
            "wording-no-surface-negative": None,
        }
        for case_id, token in expected.items():
            with self.subTest(case_id=case_id), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "case"
                case = control_setup.materialize(case_id, root)
                surface = surface_extractor.extract(
                    root,
                    case["base"],
                    case["head"],
                    20,
                    20,
                )
                tokens = {item["token"] for item in surface["surfaces"]}
                if token is None:
                    self.assertEqual(surface["surface_count"], 0)
                else:
                    self.assertIn(token, tokens)
                self.assertEqual(git(root, "status", "--porcelain=v1"), "")


class LiveMatrixShapeTests(unittest.TestCase):
    def test_matrix_freezes_five_cases_and_three_samples(self) -> None:
        payload = json.loads((EXPERIMENT / "live-cases.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["samples"], 3)
        self.assertEqual(len(payload["cases"]), 5)
        self.assertEqual(
            {case["role"] for case in payload["cases"]},
            {"calibration-negative", "calibration-contract", "fresh-metadata-only"},
        )
        self.assertEqual(payload["promotion_gate"]["losses"], 0)

    def test_matrix_uses_post_review_append_only_composition(self) -> None:
        source = (EXPERIMENT / "run_live_matrix.py").read_text(encoding="utf-8")
        self.assertIn('(\"built-in\", \"prkit\")', source)
        self.assertIn("base = review.read_bytes()", source)
        self.assertIn('(target / "augmented.md").write_bytes(base + delta)', source)
        self.assertIn("augmented.startswith(base)", source)
        self.assertIn('"--surface-file"', source)
        self.assertNotIn("edge-brief", source)

    def test_blind_judge_schema_has_neutral_labels(self) -> None:
        schema = json.loads((EXPERIMENT / "live-judge-schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["winner"]["enum"], ["A", "B", "tie"])
        rubric = (EXPERIMENT / "live-judge-rubric.md").read_text(encoding="utf-8")
        self.assertIn("review is the experimental arm", rubric)

    def test_live_pilot_stops_on_zero_signal_and_known_miss(self) -> None:
        result = json.loads(
            (
                EXPERIMENT
                / "results"
                / "live-matrix-pilot-2026-08-17.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(result["status"], "stopped-after-pilot")
        self.assertEqual(result["completed_samples"], 1)
        self.assertEqual(result["composition_outcomes"]["wins"], 0)
        self.assertEqual(result["composition_outcomes"]["ties"], 10)
        self.assertEqual(result["audit_coverage"]["confirmed"], 0)
        self.assertFalse(result["known_contract_case"]["built_in_base_found_known_description_bug"])
        self.assertFalse(result["known_contract_case"]["built_in_audit_added_known_description_bug"])
        self.assertEqual(result["known_contract_case"]["description_surface_rank"], 11)
        self.assertFalse(result["promotion"])


class CandidateTournamentShapeTests(unittest.TestCase):
    def test_broad_candidate_is_loadable_as_an_isolated_plugin(self) -> None:
        manifest = json.loads(
            (
                EXPERIMENT
                / "candidates"
                / "codex"
                / ".claude-plugin"
                / "plugin.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["name"], "review-contract-gaps-candidate")
        self.assertEqual(manifest["version"], "0.0.0")

    def test_tournament_reuses_matched_reviews_for_both_reviewer_families(self) -> None:
        source = (EXPERIMENT / "run_candidate_tournament.py").read_text(encoding="utf-8")
        self.assertIn('for reviewer in ("built-in", "prkit")', source)
        self.assertIn("source_review(case, reviewer)", source)
        self.assertIn("sha256_file(source)", source)
        self.assertIn("other candidates", source)

    def test_broad_arm_is_semantic_append_only_and_fail_closed(self) -> None:
        source = (EXPERIMENT / "run_candidate_tournament.py").read_text(encoding="utf-8")
        self.assertIn("without using a lexical surface file", source)
        self.assertIn('delta = self.render_delta(payload) if eligible else b""', source)
        self.assertIn('(target / "augmented.md").write_bytes(base + delta)', source)
        self.assertIn("invalid payload failed closed", source)
        self.assertIn("Preserve every disposition", source)

    def test_tournament_records_matched_semantic_lift_without_promotion(self) -> None:
        result = json.loads(
            (
                EXPERIMENT
                / "results"
                / "candidate-tournament-2026-08-17.json"
            ).read_text(encoding="utf-8")
        )
        broad = result["arms"]["review-contract-gaps"]
        narrow = result["arms"]["audit-consumer-contracts"]
        self.assertEqual((broad["wins"], broad["ties"], broad["losses"]), (3, 7, 0))
        self.assertEqual((narrow["wins"], narrow["ties"], narrow["losses"]), (0, 10, 0))
        self.assertEqual(broad["valid_ledgers"], 8)
        self.assertTrue(broad["negative_case_passed"])
        self.assertFalse(broad["known_description_miss_recovered_over_built_in"])
        self.assertFalse(result["decision"]["publish"])
        self.assertFalse(result["decision"]["automatic_composition"])


class CandidateReplicationShapeTests(unittest.TestCase):
    def test_replication_gate_freezes_two_new_samples_and_separate_gates(self) -> None:
        gate = json.loads((EXPERIMENT / "replication-gate.json").read_text(encoding="utf-8"))
        self.assertEqual(gate["samples"], [2, 3])
        self.assertEqual(gate["per_sample_behavior_gate"]["minimum_wins"], 1)
        self.assertEqual(gate["per_sample_behavior_gate"]["maximum_losses"], 0)
        self.assertEqual(
            gate["combined_behavior_gate"]["required_win_reviewers"],
            ["built-in", "prkit"],
        )
        self.assertEqual(gate["mechanics_gate"]["minimum_valid_ledger_rate"], 0.9)
        self.assertEqual(gate["mechanics_gate"]["maximum_repair_dependency_rate"], 0.25)
        self.assertIn("diagnostic_only", gate)

    def test_replication_harness_locks_candidate_and_reuses_base_reviews(self) -> None:
        source = (EXPERIMENT / "run_candidate_replication.py").read_text(encoding="utf-8")
        self.assertIn("candidate tree differs from the sample-1 tournament", source)
        self.assertIn("self.tournament.source_review(case, reviewer)", source)
        self.assertIn('for reviewer in ("built-in", "prkit")', source)
        self.assertIn("other candidates, replication sessions", source)
        self.assertIn("maximum_transport_attempts_per_analysis", source)
        self.assertIn("invalid payload failed closed", source)

    def test_replication_summary_keeps_behavior_and_mechanics_independent(self) -> None:
        source = (EXPERIMENT / "run_candidate_replication.py").read_text(encoding="utf-8")
        self.assertIn('decision = "park"', source)
        self.assertIn('decision = "redesign-mechanics"', source)
        self.assertIn('decision = "advance-fresh-ab"', source)
        self.assertIn('"behavior_passed": behavior_passed', source)
        self.assertIn('"mechanics_passed": mechanics_passed', source)

    def test_replication_records_behavior_pass_and_mechanics_failure(self) -> None:
        result = json.loads(
            (
                EXPERIMENT
                / "results"
                / "replication-2026-08-17.json"
            ).read_text(encoding="utf-8")
        )
        replication = result["replication"]
        self.assertEqual(
            (
                replication["aggregate"]["wins"],
                replication["aggregate"]["ties"],
                replication["aggregate"]["losses"],
            ),
            (6, 14, 0),
        )
        self.assertTrue(replication["aggregate"]["behavior_passed"])
        self.assertEqual(replication["mechanics"]["valid_ledger_rate"], 0.75)
        self.assertEqual(replication["mechanics"]["repair_dependency_rate"], 0.75)
        self.assertFalse(replication["mechanics"]["mechanics_passed"])
        self.assertTrue(
            replication["known_description_case"][
                "sample_2_recovered_over_built_in"
            ]
        )
        self.assertTrue(
            replication["known_description_case"][
                "sample_3_recovered_over_built_in"
            ]
        )
        combined = result["combined_three_sample_result"]
        self.assertEqual((combined["wins"], combined["ties"], combined["losses"]), (9, 21, 0))
        self.assertEqual(result["decision"]["next"], "redesign deterministic parent-side evidence assembly")
        self.assertFalse(result["decision"]["publish"])


class MechanicsRedesignShapeTests(unittest.TestCase):
    def test_gate_reuses_frozen_blocks_and_separates_behavior_from_mechanics(self) -> None:
        gate = json.loads(
            (EXPERIMENT / "mechanics-redesign-gate.json").read_text(encoding="utf-8")
        )
        self.assertEqual(gate["sample"], "mechanics-v2-1")
        self.assertIn("ten frozen sample-1 base reviews", gate["input_policy"])
        self.assertEqual(gate["behavior_gate"]["maximum_losses"], 0)
        self.assertEqual(gate["mechanics_gate"]["maximum_model_repair_sessions"], 0)
        self.assertEqual(
            gate["mechanics_gate"]["minimum_fully_materialized_discovery_rate"], 0.9
        )
        self.assertEqual(gate["mechanics_gate"]["minimum_coverage_complete_block_rate"], 0.9)

    def test_runner_uses_one_blind_discovery_and_separate_coverage(self) -> None:
        source = (EXPERIMENT / "run_mechanics_redesign.py").read_text(encoding="utf-8")
        self.assertIn("for case in self.runner.cases", source)
        self.assertIn("Do not read any frozen review", source)
        self.assertIn("narrow root-cause coverage subtractor", source)
        self.assertIn("Return exactly one", source)
        self.assertIn("decision per candidate", source)
        self.assertIn("repair_sessions\": 0", source)
        self.assertIn("api_error_status", source)
        self.assertIn("run is invalid and must not be summarized", source)
        self.assertNotIn("repair_spec", source)

    def test_runner_installs_only_the_v2_target_plugin(self) -> None:
        source = (EXPERIMENT / "run_mechanics_redesign.py").read_text(encoding="utf-8")
        self.assertIn('plugins=(self.plugin_copy(),)', source)
        self.assertIn('"--candidate-plugin"', source)
        self.assertIn('"--gate"', source)
        self.assertNotIn("PRKIT_PLUGIN", source)
        self.assertNotIn("candidates/claude", source)

    def test_v3_gate_changes_only_bounded_hint_resolution(self) -> None:
        gate = json.loads(
            (EXPERIMENT / "mechanics-redesign-v3-gate.json").read_text(encoding="utf-8")
        )
        self.assertEqual(gate["candidate"], "review-contract-gaps-v3")
        self.assertEqual(gate["sample"], "mechanics-v3-1")
        self.assertIn("Preserve V2 semantic discovery", gate["candidate_policy"])
        self.assertIn("never accept a line without lexical overlap", gate["candidate_policy"])
        self.assertEqual(
            gate["mechanics_gate"]["minimum_fully_materialized_discovery_rate"], 0.9
        )
        self.assertEqual(gate["mechanics_gate"]["maximum_rejected_claim_rate"], 0.1)

    def test_v4_gate_preregisters_strict_intended_line_resolution(self) -> None:
        gate = json.loads(
            (EXPERIMENT / "mechanics-redesign-v4-gate.json").read_text(encoding="utf-8")
        )
        self.assertEqual(gate["candidate"], "review-contract-gaps-v4")
        self.assertEqual(gate["sample"], "mechanics-v4-1")
        self.assertIn("complete file before changed-line membership", gate["candidate_policy"])
        self.assertIn("genuinely added or removed", gate["candidate_policy"])
        self.assertIn("must never materialize", gate["diagnostic_only"]["v3_false_anchor"])
        self.assertEqual(gate["behavior_gate"]["maximum_losses"], 0)
        self.assertEqual(gate["mechanics_gate"]["maximum_rejected_claim_rate"], 0.1)

    def test_v5_gate_changes_only_the_identifier_count_floor(self) -> None:
        gate = json.loads(
            (EXPERIMENT / "mechanics-redesign-v5-gate.json").read_text(encoding="utf-8")
        )
        self.assertEqual(gate["candidate"], "review-contract-gaps-v5")
        self.assertEqual(gate["sample"], "mechanics-v5-1")
        self.assertIn("Preserve V4", gate["candidate_policy"])
        self.assertIn("Remove only the two-distinct-identifier requirement", gate["candidate_policy"])
        self.assertIn("16-character floor", gate["diagnostic_only"]["v4_one_identifier_rejections"])
        self.assertEqual(gate["behavior_gate"]["maximum_losses"], 0)

    def test_runner_fails_claims_closed_individually_and_retains_review_bytes(self) -> None:
        source = (EXPERIMENT / "run_mechanics_redesign.py").read_text(encoding="utf-8")
        self.assertIn('"rejected_claims"', source)
        self.assertIn('(target / "augmented.md").write_bytes(base + delta)', source)
        self.assertIn(".startswith(base)", source)
        self.assertIn('decision = "advance-fresh-ab"', source)

    def test_v2_result_passes_behavior_and_fails_multiline_hint_mechanics(self) -> None:
        result = json.loads(
            (
                EXPERIMENT
                / "results"
                / "mechanics-redesign-v2-2026-08-17.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(result["status"], "behavior-passed-mechanics-failed")
        self.assertEqual(
            (
                result["behavior"]["wins"],
                result["behavior"]["ties"],
                result["behavior"]["losses"],
            ),
            (2, 8, 0),
        )
        self.assertTrue(result["behavior"]["passed"])
        self.assertEqual(result["mechanics"]["fully_materialized_discovery_rate"], 0.4)
        self.assertEqual(result["mechanics"]["rejected_claim_rate"], 0.75)
        self.assertFalse(result["mechanics"]["passed"])
        known = result["semantic_discovery"]["known_description_case"]
        self.assertTrue(known["discovered_review_blind"])
        self.assertFalse(known["materialized"])
        self.assertEqual(result["decision"]["next"], "preserve semantic discovery and add deterministic multi-line/path-plus-line-hint resolution before another frozen replay")
        self.assertFalse(result["decision"]["publish"])

    def test_v3_result_improves_yield_but_fails_unsafe_anchor_and_behavior(self) -> None:
        result = json.loads(
            (
                EXPERIMENT
                / "results"
                / "mechanics-redesign-v3-2026-08-18.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(result["status"], "behavior-failed-mechanics-failed")
        self.assertEqual(
            (
                result["behavior"]["wins"],
                result["behavior"]["ties"],
                result["behavior"]["losses"],
            ),
            (4, 5, 1),
        )
        self.assertEqual(result["behavior"]["unsupported_candidate_findings"], 2)
        self.assertFalse(result["behavior"]["passed"])
        self.assertEqual(result["mechanics"]["fully_materialized_discovery_rate"], 0.8)
        self.assertEqual(result["mechanics"]["rejected_claim_rate"], 0.25)
        self.assertFalse(result["mechanics"]["passed"])
        write_lock = next(
            claim
            for claim in result["semantic_discovery"]["claims"]
            if claim["case_id"] == "instance-ai-write-lock"
        )
        self.assertEqual(write_lock["unsafe_anchor"]["resolved_line"], 643)
        self.assertEqual(write_lock["unsafe_anchor"]["resolved_text"], "workflowId,")
        self.assertFalse(result["decision"]["publish"])
        self.assertFalse(result["decision"]["advance_fresh_pr_ab"])

    def test_v4_result_passes_behavior_but_rejects_one_identifier_evidence(self) -> None:
        result = json.loads(
            (
                EXPERIMENT
                / "results"
                / "mechanics-redesign-v4-2026-08-18.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(result["status"], "behavior-passed-mechanics-failed")
        self.assertEqual(
            (
                result["behavior"]["wins"],
                result["behavior"]["ties"],
                result["behavior"]["losses"],
            ),
            (1, 9, 0),
        )
        self.assertEqual(result["behavior"]["unsupported_candidate_findings"], 0)
        self.assertTrue(result["behavior"]["passed"])
        self.assertEqual(result["mechanics"]["fully_materialized_discovery_rate"], 0.6)
        self.assertEqual(result["mechanics"]["rejected_claim_rate"], 0.5)
        self.assertFalse(result["mechanics"]["passed"])
        self.assertFalse(
            result["semantic_discovery"]["v3_false_anchor_case"][
                "unsafe_anchor_materialized"
            ]
        )
        self.assertFalse(result["decision"]["publish"])

    def test_v5_result_passes_mechanics_but_fails_causal_admission(self) -> None:
        result = json.loads(
            (
                EXPERIMENT
                / "results"
                / "mechanics-redesign-v5-2026-08-18.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(result["status"], "behavior-failed-mechanics-passed")
        self.assertEqual(
            (
                result["behavior"]["wins"],
                result["behavior"]["ties"],
                result["behavior"]["losses"],
            ),
            (2, 6, 2),
        )
        self.assertEqual(result["behavior"]["unsupported_candidate_findings"], 2)
        self.assertFalse(result["behavior"]["passed"])
        self.assertEqual(result["mechanics"]["fully_materialized_discovery_rate"], 1.0)
        self.assertEqual(result["mechanics"]["rejected_claim_rate"], 0.0)
        self.assertTrue(result["mechanics"]["passed"])
        restore = next(
            claim
            for claim in result["semantic_discovery"]["claims"]
            if claim["case_id"] == "instance-ai-write-lock"
        )
        self.assertEqual(restore["blind_judgments"], ["loss", "loss"])
        self.assertFalse(result["decision"]["publish"])
        self.assertFalse(result["decision"]["advance_fresh_pr_ab"])


if __name__ == "__main__":
    unittest.main()
