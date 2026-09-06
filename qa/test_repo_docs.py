from __future__ import annotations

import json
import re
import unittest
import struct
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class RepoDocsTest(unittest.TestCase):
    def test_agent_instructions_use_one_shared_source(self) -> None:
        agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
        claude = (REPO / "CLAUDE.md").read_text(encoding="utf-8")

        self.assertEqual(claude, "@AGENTS.md\n")
        self.assertIn("## Skill and plugin invariants", agents)
        self.assertIn("## Publication invariants", agents)
        self.assertIn("## Validation", agents)

    def test_readme_local_links_and_hero_are_valid(self) -> None:
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        targets = re.findall(r"]\(([^)]+)\)", readme)
        missing = []
        for target in targets:
            if target.startswith(("http://", "https://", "#")):
                continue
            relative = target.split("#", 1)[0]
            if relative and not (REPO / relative).exists():
                missing.append(target)
        self.assertEqual(missing, [])

        hero = REPO / "assets/overclock-agent-powerup.png"
        self.assertIn('src="assets/overclock-agent-powerup.png"', readme)
        self.assertTrue(hero.is_file())
        self.assertLess(hero.stat().st_size, 2_000_000)
        header = hero.read_bytes()[:24]
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(header[12:16], b"IHDR")
        width, height = struct.unpack(">II", header[16:24])
        self.assertGreaterEqual(width, 1200)
        self.assertGreater(height, 0)
        self.assertGreaterEqual(width / height, 1.5)

    def test_pr_reviewer_corpus_is_pinned_and_unique(self) -> None:
        path = REPO / "qa/experiments/pr-reviewer-phase0/cases.json"
        cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
        self.assertEqual(len(cases), 6)
        self.assertEqual(len({case["number"] for case in cases}), len(cases))
        sha = re.compile(r"^[0-9a-f]{40}$")
        for case in cases:
            self.assertEqual(
                case["url"], f"https://github.com/n8n-io/n8n/pull/{case['number']}"
            )
            for field in ("base_sha", "head_sha", "merge_sha"):
                self.assertRegex(case[field], sha)

    def test_pr_reviewer_result_schema_requires_blind_arms(self) -> None:
        path = REPO / "qa/experiments/pr-reviewer-phase0/result.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        required = set(schema["required"])
        self.assertIn("blind_key", required)
        self.assertIn("profile_audit", required)
        self.assertIn("precedent_audit", required)
        self.assertIn("safety", required)
        self.assertEqual(
            set(schema["properties"]["precedent_audit"]["required"]),
            {"real", "material", "fabricated"},
        )
        self.assertEqual(
            set(schema["properties"]["profile_audit"]["required"]),
            {"material", "decorative", "unsupported", "leaked", "secret_entries"},
        )
        self.assertEqual(
            set(schema["properties"]["safety"]["required"]),
            {
                "unsupported_high_confidence_security_claims",
                "generic_required_profile",
                "remote_mutations",
                "unauthorized_local_state_mutations",
            },
        )
        blind_options = schema["properties"]["blind_key"]["oneOf"]
        decoded = [option["const"] for option in blind_options]
        self.assertEqual(len(decoded), 6)
        for option in decoded:
            self.assertEqual(set(option), {"A", "B", "C"})
            self.assertEqual(set(option.values()), {"baseline", "generic", "initialized"})
        self.assertEqual(
            schema["properties"]["pairwise"]["prefixItems"],
            [
                {"$ref": "#/$defs/pair_a_b"},
                {"$ref": "#/$defs/pair_a_c"},
                {"$ref": "#/$defs/pair_b_c"},
            ],
        )

    def test_pr_reviewer_docs_do_not_embed_a_developer_home(self) -> None:
        path = REPO / "qa/experiments/pr-reviewer-phase0/README.md"
        self.assertNotIn("/Users/", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
