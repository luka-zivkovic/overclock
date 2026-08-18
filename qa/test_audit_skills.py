from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from audit_skills import (  # noqa: E402
    audit_openai_metadata,
    audit_routing_battery_contract,
    discover,
)
from validate_skill import parse_frontmatter  # noqa: E402


MODEL_METADATA = """\
interface:
  display_name: "Example Skill"
  short_description: "Perform one example workflow safely"
  default_prompt: "Use $example-skill to complete this example workflow."
"""


class AuditOpenAIMetadataTest(unittest.TestCase):
    def write_metadata(self, skill_dir: Path, text: str) -> None:
        path = skill_dir / "agents" / "openai.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_missing_metadata_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            findings = audit_openai_metadata(
                Path(temp), "example-skill", user_invoked=False
            )
        self.assertIn(("FAIL", "Codex metadata is missing: agents/openai.yaml"), findings)

    def test_model_invoked_metadata_passes_without_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_dir = Path(temp)
            self.write_metadata(skill_dir, MODEL_METADATA)
            findings = audit_openai_metadata(
                skill_dir, "example-skill", user_invoked=False
            )
        self.assertEqual(findings, [])

    def test_user_invoked_skill_requires_matching_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_dir = Path(temp)
            self.write_metadata(skill_dir, MODEL_METADATA)
            findings = audit_openai_metadata(
                skill_dir, "example-skill", user_invoked=True
            )
            self.assertIn(
                (
                    "FAIL",
                    "user-invoked skill must set "
                    "policy.allow_implicit_invocation: false",
                ),
                findings,
            )

            self.write_metadata(
                skill_dir,
                MODEL_METADATA
                + """\
policy:
  allow_implicit_invocation: false
""",
            )
            findings = audit_openai_metadata(
                skill_dir, "example-skill", user_invoked=True
            )
        self.assertEqual(findings, [])

    def test_model_invoked_skill_rejects_false_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_dir = Path(temp)
            self.write_metadata(
                skill_dir,
                MODEL_METADATA
                + """\
policy:
  allow_implicit_invocation: false
""",
            )
            findings = audit_openai_metadata(
                skill_dir, "example-skill", user_invoked=False
            )
        self.assertIn(
            (
                "FAIL",
                "model-invoked skill must not disable implicit invocation in openai.yaml",
            ),
            findings,
        )

    def test_required_interface_fields_are_quoted_and_constrained(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_dir = Path(temp)
            self.write_metadata(
                skill_dir,
                """\
interface:
  display_name: Example Skill
  short_description: "Too short"
  default_prompt: "Run the example workflow."
""",
            )
            findings = audit_openai_metadata(
                skill_dir, "example-skill", user_invoked=False
            )

        messages = {message for severity, message in findings if severity == "FAIL"}
        self.assertTrue(
            any(
                "interface.display_name must be a quoted string" in message
                for message in messages
            )
        )
        self.assertTrue(
            any(
                "interface.short_description must contain 25–64 characters" in message
                for message in messages
            )
        )
        self.assertIn(
            "interface.default_prompt must mention $example-skill",
            messages,
        )

    def test_all_repository_distributions_have_valid_metadata(self) -> None:
        failures = []
        for skill_md in discover(REPO / "plugins"):
            frontmatter, _ = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            name = frontmatter.get("name", skill_md.parent.name)
            user_invoked = (
                frontmatter.get("disable-model-invocation", "").lower() == "true"
            )
            findings = audit_openai_metadata(
                skill_md.parent, name, user_invoked=user_invoked
            )
            failures.extend(
                f"{skill_md.relative_to(REPO)}: {message}"
                for severity, message in findings
                if severity == "FAIL"
            )
        self.assertEqual(failures, [])

    def test_routing_audit_directly_rejects_missing_install_matrix(self) -> None:
        skill_dir = REPO / "plugins/natural-writing/skills/natural-writing"
        findings = audit_routing_battery_contract(
            {
                "skill": "natural-writing",
                "thresholds": {"precision": 0.9},
                "should_trigger": ["Polish this essay."],
                "should_not": ["Fix this bug."],
            },
            skill_dir,
        )
        messages = [message for severity, message in findings if severity == "FAIL"]
        self.assertTrue(
            any("routing battery install matrix" in message for message in messages)
        )


if __name__ == "__main__":
    unittest.main()
