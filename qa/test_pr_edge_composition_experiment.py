from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "qa" / "experiments" / "pr-edge-composition-phase0"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


merge_delta = load_module("pr_edge_merge_delta", EXPERIMENT / "merge_delta.py")


def empty_delta(base: bytes) -> dict[str, object]:
    return {
        "base_review_sha256": hashlib.sha256(base).hexdigest(),
        "verified_additions": [],
        "strengthening_notes": [],
        "rejected_brief_risks": [],
    }


class PrEdgeCompositionExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads((EXPERIMENT / "cases.json").read_text(encoding="utf-8"))

    def test_delta_schema_matches_merge_contract(self) -> None:
        schema = json.loads((EXPERIMENT / "delta-schema.json").read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            set(schema["required"]),
            {
                "base_review_sha256",
                "verified_additions",
                "strengthening_notes",
                "rejected_brief_risks",
            },
        )

    def test_judge_schema_requires_all_blind_arms_and_pairs(self) -> None:
        schema = json.loads(
            (EXPERIMENT / "judge-output-schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(schema["properties"]["arms"]["required"], ["A", "B", "C", "D"])
        self.assertEqual(schema["properties"]["pairs"]["minItems"], 6)
        self.assertEqual(schema["properties"]["pairs"]["maxItems"], 6)

    def test_late_reveal_arms_are_complete_and_unique(self) -> None:
        self.assertEqual(self.manifest["schema_version"], 2)
        arms = self.manifest["arms"]
        self.assertEqual(len(arms), 4)
        self.assertEqual(len({arm["id"] for arm in arms}), 4)
        self.assertEqual(
            {(arm["reviewer"], arm["augmentation"]) for arm in arms},
            {
                ("built-in-code-review", "none"),
                ("built-in-code-review", "late-reveal-edge-delta"),
                ("pr-kit-review-pr", "none"),
                ("pr-kit-review-pr", "late-reveal-edge-delta"),
            },
        )

    def test_cases_separate_regression_from_generalization(self) -> None:
        self.assertEqual(len(self.manifest["cases"]), 4)
        phases = [case["evaluation_phase"] for case in self.manifest["cases"]]
        self.assertEqual(phases.count("regression"), 2)
        self.assertEqual(phases.count("generalization"), 2)
        self.assertEqual(
            {case["number"] for case in self.manifest["cases"] if case["evaluation_phase"] == "generalization"},
            {33960, 33970},
        )
        for case in self.manifest["cases"]:
            self.assertRegex(case["base_sha"], r"^[0-9a-f]{40}$")
            self.assertRegex(case["head_sha"], r"^[0-9a-f]{40}$")
            self.assertNotEqual(case["base_sha"], case["head_sha"])

    def test_protocol_freezes_review_before_late_reveal(self) -> None:
        protocol = (EXPERIMENT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Freeze each complete output and its", protocol)
        self.assertIn("before revealing the brief", protocol)
        self.assertIn("copies the base", protocol)
        self.assertIn("byte-for-byte", protocol)
        self.assertIn("Regression cases are diagnostic", protocol)
        self.assertIn("at least two augmented wins", protocol)
        self.assertIn("standalone skill may depend on its sibling", protocol)

    def test_merge_preserves_base_bytes_and_rejects_wrong_digest(self) -> None:
        base = b"# Frozen review\n\nOriginal finding.\n"
        delta = empty_delta(base)
        delta["verified_additions"] = [
            {
                "priority": "P1",
                "title": "Reference remains stale",
                "location": "src/example.ts:42",
                "failure_path": "A saved consumer replays the old identifier.",
                "impact": "The request targets a missing object.",
                "evidence": ["src/example.ts:42 reads the raw persisted id"],
                "suggested_comment": "Please migrate the saved reference.",
                "brief_origin": "identity-consumer propagation",
            }
        ]
        merged, audit = merge_delta.merge(base, delta)
        self.assertTrue(merged.startswith(base))
        self.assertTrue(audit["base_bytes_preserved"])
        self.assertEqual(audit["verified_additions"], 1)
        self.assertIn(b"## Verified edge delta", merged)
        self.assertIn(b"Reference remains stale", merged)

        delta["base_review_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "frozen base review"):
            merge_delta.merge(base, delta)

    def test_merge_cli_writes_audit_with_empty_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = b"No actionable findings\n"
            base_path = root / "base.md"
            delta_path = root / "delta.json"
            output_path = root / "merged.md"
            audit_path = root / "audit.json"
            base_path.write_bytes(base)
            delta_path.write_text(json.dumps(empty_delta(base)), encoding="utf-8")

            merged, audit = merge_delta.merge(base_path.read_bytes(), json.loads(delta_path.read_text()))
            output_path.write_bytes(merged)
            audit_path.write_text(json.dumps(audit), encoding="utf-8")

            self.assertTrue(output_path.read_bytes().startswith(base))
            self.assertEqual(json.loads(audit_path.read_text())["verified_additions"], 0)


if __name__ == "__main__":
    unittest.main()
