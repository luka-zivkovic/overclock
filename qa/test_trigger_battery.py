from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trigger_battery import (  # noqa: E402
    materialize_fixture,
    result_metadata,
    selected_skill,
    swap_description,
)


class TriggerBatteryTest(unittest.TestCase):
    def test_description_is_yaml_safe(self) -> None:
        source = "---\nname: demo\ndescription: old\n---\nbody\n"
        updated = swap_description(source, "Use when prose contains: a risky colon")
        self.assertIn('description: "Use when prose contains: a risky colon"', updated)

    def test_detects_namespaced_skill_tool_call(self) -> None:
        event = {
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use",
                "name": "Skill",
                "input": {"skill": "natural-writing:natural-writing"},
            }]},
        }
        self.assertTrue(selected_skill(json.dumps(event), "natural-writing"))
        self.assertFalse(selected_skill(json.dumps(event), "test-discipline"))

    def test_extracts_result_cost_and_latency(self) -> None:
        events = "\n".join([
            json.dumps({"type": "assistant", "message": {"content": []}}),
            json.dumps({
                "type": "result",
                "duration_ms": 1234,
                "total_cost_usd": 0.0125,
                "num_turns": 3,
            }),
        ])
        self.assertEqual(result_metadata(events), {
            "duration_ms": 1234,
            "total_cost_usd": 0.0125,
            "num_turns": 3,
        })

    def test_materializes_safe_fixture_and_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            materialize_fixture(root, {"fixture_files": {"src/demo.js": "ok\n"}})
            self.assertEqual((root / "src/demo.js").read_text(), "ok\n")
            with self.assertRaisesRegex(ValueError, "unsafe fixture path"):
                materialize_fixture(root, {"fixture_files": {"../escape": "bad"}})


if __name__ == "__main__":
    unittest.main()
