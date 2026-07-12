from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class RepoDocsTest(unittest.TestCase):
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

        hero = REPO / "assets/overclock-hero.jpg"
        self.assertIn('src="assets/overclock-hero.jpg"', readme)
        self.assertTrue(hero.is_file())
        self.assertLess(hero.stat().st_size, 500_000)

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
        self.assertIn("precedent_citations", required)
        blind_options = schema["properties"]["blind_key"]["oneOf"]
        self.assertEqual(
            {tuple(sorted(option["const"].items())) for option in blind_options},
            {
                (("A", "baseline"), ("B", "candidate")),
                (("A", "candidate"), ("B", "baseline")),
            },
        )


if __name__ == "__main__":
    unittest.main()
