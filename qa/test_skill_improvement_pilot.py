from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trigger_battery import validate_battery_install_modes, validate_battery_prompt_contracts

PILOT = Path(__file__).resolve().parent / "experiments/skill-improvement-pilot"


class SkillImprovementPilotTests(unittest.TestCase):
    def test_candidate_routing_contract_matches_the_native_runner(self):
        battery = json.loads((PILOT / "author-routing.json").read_text())
        candidate = PILOT / "candidate/skill-scenario-author/skills/skill-scenario-author"
        self.assertEqual(validate_battery_install_modes(battery, candidate), [])
        self.assertEqual(validate_battery_prompt_contracts(battery), [])
        self.assertEqual(battery["detector"]["type"], "skill_tool")
        for prompt in battery["should_trigger"]:
            self.assertEqual(prompt["allowed_skills"], ["skill-scenario-author"])
        for prompt in battery["should_not"]:
            self.assertEqual(prompt["allowed_skills"], [])

    def test_candidate_manifest_has_only_the_experimental_skill(self):
        plugin = PILOT / "candidate/skill-scenario-author"
        manifest = json.loads((plugin / ".claude-plugin/plugin.json").read_text())
        self.assertEqual(manifest["name"], "skill-scenario-author")
        self.assertEqual([p.name for p in (plugin / "skills").iterdir()], ["skill-scenario-author"])
        self.assertFalse((plugin / "hooks").exists())


if __name__ == "__main__":
    unittest.main()
