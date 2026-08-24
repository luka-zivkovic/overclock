from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "qa" / "experiments" / "pr-edge-role-matrix-phase0"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


assemble_review = load_module("pr_edge_role_assemble", EXPERIMENT / "assemble_review.py")
collect_changed_lines = load_module(
    "pr_edge_role_changed_lines", EXPERIMENT / "collect_changed_lines.py"
)


def edge_bytes(*, second_high: bool = False) -> bytes:
    payload = {
        "schema_version": 1,
        "analysis_base": "a" * 40,
        "risks": [
            {
                "id": "R1",
                "title": "Persisted identity can become stale",
                "scenario": "A saved consumer replays the old id after reconciliation.",
                "impact_signal": "high",
                "evidence": ["src/base.ts:4 @ " + "a" * 40],
                "probe": "Check migration or aliasing of the saved id.",
            },
            {
                "id": "R2",
                "title": "Fallback may hide an error",
                "scenario": "A missing value takes the fallback path.",
                "impact_signal": "high" if second_high else "medium",
                "evidence": ["src/base.ts:9 @ " + "a" * 40],
                "probe": "Check explicit absence separately from invalid input.",
            },
        ],
    }
    return (json.dumps(payload, indent=2) + "\n").encode()


def changed_lines() -> dict[str, object]:
    return {
        "schema_version": 1,
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "diff_sha256": "c" * 64,
        "changed_lines": [
            {"path": "src/change.ts", "lines": [12, 13]},
            {"path": "src/other.ts", "lines": [7]},
        ],
    }


def finding(root: str, *, path: str = "src/change.ts", line: int = 12) -> dict[str, object]:
    return {
        "root_cause_key": root,
        "priority": "P1",
        "title": "Saved references are not migrated",
        "location": {"path": path, "line": line},
        "failure_path": "A saved consumer sends an old id that no longer resolves.",
        "impact": "Existing workflows fail after reconciliation.",
        "change_causality": "The changed reconciliation path replaces the id without an alias.",
        "reachable_producer": "Workflow execution reads and sends the persisted raw id.",
        "guards_checked": ["No migration runs before lookup", "Stable-key fallback is absent"],
        "evidence": ["src/change.ts:12 replaces the id", "src/consumer.ts:8 reads the raw id"],
        "suggested_comment": "Please preserve or migrate persisted references when replacing the id.",
    }


def candidate(
    base: bytes,
    edge: bytes,
    *,
    approach: str = "late-per-risk-confirmed",
    decisions: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "approach_id": approach,
        "base_review_sha256": hashlib.sha256(base).hexdigest(),
        "edge_index_sha256": hashlib.sha256(edge).hexdigest(),
        "decisions": decisions,
    }


def rejected(risk_id: str, disposition: str = "defeated") -> dict[str, object]:
    return {
        "risk_id": risk_id,
        "disposition": disposition,
        "reason": "The implementation preserves the invariant.",
        "finding": None,
    }


class PrEdgeRoleMatrixExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.approaches = json.loads(
            (EXPERIMENT / "approaches.json").read_text(encoding="utf-8")
        )
        self.cases = json.loads((EXPERIMENT / "cases.json").read_text(encoding="utf-8"))

    def test_role_matrix_covers_distinct_placements_and_lanes(self) -> None:
        approaches = self.approaches["approaches"]
        ids = {approach["id"] for approach in approaches}
        self.assertEqual(self.approaches["schema_version"], 1)
        self.assertEqual(len(approaches), 15)
        self.assertEqual(len(ids), len(approaches))
        self.assertEqual(
            {approach["lane"] for approach in approaches},
            {"automatic-final-review", "reviewer-support", "diagnostic"},
        )
        self.assertTrue(
            {
                "upfront-probes-only",
                "parallel-independent-challenger",
                "late-batch-confirmed",
                "late-per-risk-confirmed",
                "coverage-filtered-per-risk",
                "test-scenario-confirmed",
                "conditional-no-findings-challenger",
                "conditional-high-impact-challenger",
                "raw-human-sidecar",
                "coverage-map-human-sidecar",
                "test-scenario-human-sidecar",
                "risk-router-only",
                "author-preflight",
            }.issubset(ids)
        )

    def test_append_approaches_are_strict_and_after_control_freeze(self) -> None:
        append_approaches = [
            approach
            for approach in self.approaches["approaches"]
            if approach["output_policy"].startswith("append-confirmed")
        ]
        self.assertGreaterEqual(len(append_approaches), 7)
        self.assertTrue(all(approach["admission"] == "strict" for approach in append_approaches))
        self.assertTrue(
            all(approach["family"] in {"parallel", "after-review", "conditional"} for approach in append_approaches)
        )
        historical = [
            approach["id"]
            for approach in self.approaches["approaches"]
            if approach["screening_action"] == "historical-only"
        ]
        self.assertEqual(historical, ["upfront-full-brief"])

    def test_cases_keep_historical_screening_and_confirmation_separate(self) -> None:
        self.assertEqual(self.cases["schema_version"], 1)
        historical = self.cases["historical_calibration"]
        screening = self.cases["screening_cases"]
        self.assertEqual({case["number"] for case in historical}, {33820, 33867, 33960, 33970})
        self.assertEqual({case["number"] for case in screening}, {33762, 33897})
        self.assertFalse({case["number"] for case in historical} & {case["number"] for case in screening})
        self.assertEqual(self.cases["confirmation"]["case_count"], 3)
        self.assertEqual(self.cases["confirmation"]["cases"], [])
        self.assertEqual(self.cases["human_support_study"]["case_count"], 4)
        self.assertEqual(
            len(self.cases["human_support_study"]["packet_rotation"]), 4
        )
        for case in [*historical, *screening]:
            self.assertRegex(case["base_sha"], r"^[0-9a-f]{40}$")
            self.assertRegex(case["head_sha"], r"^[0-9a-f]{40}$")
            self.assertNotEqual(case["base_sha"], case["head_sha"])

    def test_protocol_prevents_cross_lane_and_contamination_errors(self) -> None:
        protocol = (EXPERIMENT / "README.md").read_text(encoding="utf-8")
        protocol_flat = " ".join(protocol.split())
        for required in (
            "Do not rank outputs from different lanes",
            "one clean-room edge artifact per case",
            "before any implementation access",
            "same sealed artifacts in every matched approach",
            "one fresh verifier per risk",
            "returns the frozen review byte-for-byte",
            "Advance at most three automatic approaches",
            "three untouched cases",
            "no matched losses",
            "A win in one lane does not authorize behavior in another",
        ):
            self.assertIn(required, protocol_flat)

    def test_json_contracts_are_closed(self) -> None:
        for filename in (
            "edge-index-schema.json",
            "review-index-schema.json",
            "coverage-map-schema.json",
            "candidate-schema.json",
            "changed-lines-schema.json",
            "judge-output-schema.json",
            "risk-audit-schema.json",
            "support-session-schema.json",
            "router-output-schema.json",
        ):
            schema = json.loads((EXPERIMENT / filename).read_text(encoding="utf-8"))
            self.assertFalse(schema["additionalProperties"], filename)
        edge_schema = json.loads(
            (EXPERIMENT / "edge-index-schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(edge_schema["properties"]["risks"]["minItems"], 0)

    def test_live_runner_is_resumable_and_keeps_generated_state_under_qa_work(self) -> None:
        runner = (EXPERIMENT / "run_screen.py").read_text(encoding="utf-8")
        self.assertIn('choices=["setup", "prep", "reviews", "approaches", "assemble", "judge", "audit", "all"]', runner)
        self.assertIn("experiment sources changed after the run was frozen", runner)
        self.assertIn("--run-root must be a child of qa/_work", runner)
        self.assertIn("accepted_permission_denials", runner)
        self.assertIn("all_worktrees_clean", runner)
        self.assertIn('if key == "$schema"', runner)
        self.assertIn('"definitions" if key == "$defs"', runner)
        self.assertIn('args.extend(["--", spec.prompt])', runner)

    def test_changed_line_parser_collects_only_head_ranges(self) -> None:
        diff = b"""diff --git a/src/a.ts b/src/a.ts
index 111..222 100644
--- a/src/a.ts
+++ b/src/a.ts
@@ -2,2 +2,3 @@
+new one
 same
+new two
diff --git a/src/deleted.ts b/src/deleted.ts
deleted file mode 100644
--- a/src/deleted.ts
+++ /dev/null
@@ -1 +0,0 @@
-gone
"""
        self.assertEqual(
            collect_changed_lines.parse_changed_lines(diff),
            [{"path": "src/a.ts", "lines": [2, 3, 4]}],
        )

    def test_assembler_appends_only_confirmed_changed_line_findings(self) -> None:
        base = b"# Frozen review\n\nExisting finding.\n"
        edge = edge_bytes()
        decisions = [
            {
                "risk_id": "R1",
                "disposition": "confirmed-new-finding",
                "reason": "Reachable and introduced by the changed reconciliation path.",
                "finding": finding("stale-persisted-reference"),
            },
            rejected("R2", "unreachable"),
        ]
        output, audit = assemble_review.assemble(
            base,
            edge,
            changed_lines(),
            [candidate(base, edge, decisions=decisions)],
            "late-per-risk-confirmed",
        )
        self.assertTrue(output.startswith(base))
        self.assertIn(b"Additional verified findings", output)
        self.assertIn(b"Saved references are not migrated", output)
        self.assertTrue(audit["base_bytes_preserved"])
        self.assertFalse(audit["output_equals_base"])
        self.assertEqual(audit["confirmed_risk_ids"], ["R1"])

    def test_empty_confirmation_returns_exact_frozen_bytes(self) -> None:
        base = b"No actionable findings"
        edge = edge_bytes()
        decisions = [rejected("R1"), rejected("R2", "already-covered")]
        output, audit = assemble_review.assemble(
            base,
            edge,
            changed_lines(),
            [candidate(base, edge, decisions=decisions)],
            "late-per-risk-confirmed",
        )
        self.assertEqual(output, base)
        self.assertTrue(audit["output_equals_base"])
        self.assertEqual(audit["confirmed_risk_ids"], [])

    def test_assembler_rejects_stale_hash_nonchanged_line_and_missing_risk(self) -> None:
        base = b"Frozen review\n"
        edge = edge_bytes()
        decisions = [
            {
                "risk_id": "R1",
                "disposition": "confirmed-new-finding",
                "reason": "Claimed confirmed.",
                "finding": finding("bad-anchor", line=99),
            },
            rejected("R2"),
        ]
        with self.assertRaisesRegex(ValueError, "exact changed line"):
            assemble_review.assemble(
                base,
                edge,
                changed_lines(),
                [candidate(base, edge, decisions=decisions)],
                "late-per-risk-confirmed",
            )

        stale = candidate(base, edge, decisions=[rejected("R1"), rejected("R2")])
        stale["base_review_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "different frozen review"):
            assemble_review.assemble(
                base, edge, changed_lines(), [stale], "late-per-risk-confirmed"
            )

        incomplete = candidate(base, edge, decisions=[rejected("R1")])
        with self.assertRaisesRegex(ValueError, "expected risks"):
            assemble_review.assemble(
                base, edge, changed_lines(), [incomplete], "late-per-risk-confirmed"
            )

    def test_assembler_rejects_edge_evidence_from_another_base(self) -> None:
        base = b"Frozen review\n"
        raw = json.loads(edge_bytes())
        raw["risks"][0]["evidence"] = ["src/base.ts:4 @ " + "d" * 40]
        edge = (json.dumps(raw) + "\n").encode()
        payload = candidate(base, edge, decisions=[rejected("R1"), rejected("R2")])
        with self.assertRaisesRegex(ValueError, "exact analysis base"):
            assemble_review.assemble(
                base, edge, changed_lines(), [payload], "late-per-risk-confirmed"
            )

    def test_empty_edge_index_is_a_valid_exact_base_result(self) -> None:
        base = b"Frozen review\n"
        edge = json.dumps(
            {"schema_version": 1, "analysis_base": "a" * 40, "risks": []}
        ).encode()
        payload = candidate(base, edge, decisions=[])
        output, audit = assemble_review.assemble(
            base, edge, changed_lines(), [payload], "late-per-risk-confirmed"
        )
        self.assertEqual(output, base)
        self.assertEqual(audit["decisions"], 0)

    def test_assembler_rejects_duplicate_root_causes_across_isolated_verifiers(self) -> None:
        base = b"Frozen review\n"
        edge = edge_bytes(second_high=True)
        first = candidate(
            base,
            edge,
            decisions=[
                {
                    "risk_id": "R1",
                    "disposition": "confirmed-new-finding",
                    "reason": "Confirmed.",
                    "finding": finding("same-root"),
                }
            ],
        )
        second = candidate(
            base,
            edge,
            decisions=[
                {
                    "risk_id": "R2",
                    "disposition": "confirmed-new-finding",
                    "reason": "Also confirmed.",
                    "finding": finding("same-root", path="src/other.ts", line=7),
                }
            ],
        )
        with self.assertRaisesRegex(ValueError, "duplicate confirmed root cause"):
            assemble_review.assemble(
                base,
                edge,
                changed_lines(),
                [first, second],
                "late-per-risk-confirmed",
            )

    def test_high_impact_conditional_requires_only_sealed_high_risks(self) -> None:
        base = b"Frozen review\n"
        edge = edge_bytes()
        high_only = candidate(
            base,
            edge,
            approach="conditional-high-impact-challenger",
            decisions=[rejected("R1")],
        )
        output, audit = assemble_review.assemble(
            base,
            edge,
            changed_lines(),
            [high_only],
            "conditional-high-impact-challenger",
        )
        self.assertEqual(output, base)
        self.assertEqual(audit["decisions"], 1)

    def test_assembler_cli_contract_uses_repeatable_candidates(self) -> None:
        base = b"Frozen review\n"
        edge = edge_bytes()
        decisions = [rejected("R1"), rejected("R2")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_path = root / "base.md"
            edge_path = root / "edge.json"
            changed_path = root / "changed.json"
            candidate_path = root / "candidate.json"
            base_path.write_bytes(base)
            edge_path.write_bytes(edge)
            changed_path.write_text(json.dumps(changed_lines()), encoding="utf-8")
            candidate_path.write_text(
                json.dumps(candidate(base, edge, decisions=decisions)), encoding="utf-8"
            )
            output, audit = assemble_review.assemble(
                base_path.read_bytes(),
                edge_path.read_bytes(),
                json.loads(changed_path.read_text()),
                [json.loads(candidate_path.read_text())],
                "late-per-risk-confirmed",
            )
            self.assertEqual(output, base)
            self.assertEqual(audit["candidate_files"], 1)


if __name__ == "__main__":
    unittest.main()
