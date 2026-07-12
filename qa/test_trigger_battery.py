from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trigger_battery import (  # noqa: E402
    materialize_fixture,
    quality_metrics,
    result_metadata,
    run_streaming_command,
    selected_skill,
    swap_description,
    threshold_failures,
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

    def test_route_only_stream_stops_at_skill_selection(self) -> None:
        event = json.dumps({
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use",
                "name": "Skill",
                "input": {"skill": "demo:test-discipline"},
            }]},
        })
        command = [
            sys.executable,
            "-u",
            "-c",
            f"import time; print({event!r}, flush=True); time.sleep(5)",
        ]
        with tempfile.TemporaryDirectory() as temp:
            result = run_streaming_command(
                command, Path(temp), "test-discipline", True, 2
            )
        self.assertTrue(result["fired"])
        self.assertTrue(result["stopped_early"])
        self.assertLess(result["duration_ms"], 2000)

    def test_stream_timeout_is_infrastructure_error(self) -> None:
        command = [sys.executable, "-u", "-c", "import time; time.sleep(5)"]
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                run_streaming_command(command, Path(temp), "demo", False, 0.05)

    def test_quality_metrics_and_thresholds(self) -> None:
        rows = [
            {"kind": "should", "fired": True},
            {"kind": "should", "fired": False},
            {"kind": "should_not", "fired": False},
            {"kind": "should_not", "fired": True},
        ]
        metrics = quality_metrics(rows)
        self.assertEqual(metrics["true_positive"], 1)
        self.assertEqual(metrics["false_negative"], 1)
        self.assertEqual(metrics["true_negative"], 1)
        self.assertEqual(metrics["false_positive"], 1)
        self.assertEqual(metrics["precision"], 0.5)
        self.assertEqual(metrics["recall"], 0.5)
        self.assertEqual(
            threshold_failures(metrics, {"precision": 0.6, "recall": 0.5}),
            ["precision 50.0% < 60.0%"],
        )
        with self.assertRaisesRegex(ValueError, "unknown routing threshold"):
            threshold_failures(metrics, {"f1": 0.9})


if __name__ == "__main__":
    unittest.main()
