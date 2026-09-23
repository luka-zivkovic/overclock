from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "plugins" / "api-bench" / "skills" / "api-bench"
SCRIPT = SKILL / "scripts" / "api_bench.py"


def load_module():
    spec = importlib.util.spec_from_file_location("api_bench", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


bench = load_module()


def base_spec(**overrides) -> dict:
    spec = {
        "name": "unit",
        "provider": "anthropic",
        "model": "claude-opus-5",
        "system": "Use the tools.",
        "messages": [{"role": "user", "content": "Look up ada@example.com"}],
        "tools": [
            {
                "name": "lookup_customer",
                "description": "Fetch a customer by email.",
                "input_schema": {"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]},
            },
            {
                "name": "list_charges",
                "description": "List charges.",
                "input_schema": {"type": "object", "properties": {"customer_id": {"type": "string"}}},
            },
        ],
        "tool_results": {
            "lookup_customer": {
                "cases": [{"when": {"email": "ada@example.com"}, "result": {"customer_id": "cus_1"}}],
                "error": "not found",
            }
        },
        "budget": {"max_requests": 6},
    }
    spec.update(overrides)
    return spec


def response(stop_reason: str, content: list[dict], input_tokens: int = 100, output_tokens: int = 10, **extra) -> dict:
    return {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5",
        "stop_reason": stop_reason, "content": content,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        **extra,
    }


def tool_use(name: str, tool_input: dict, call_id: str = "toolu_1") -> dict:
    return {"type": "tool_use", "id": call_id, "name": name, "input": tool_input}


class FakePost:
    """Canned HTTP transport that records every call and never touches the network."""

    def __init__(self, replies: list[tuple[int, dict[str, str], dict]]):
        self.replies = list(replies)
        self.calls: list[tuple[str, dict[str, str], dict]] = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, dict(headers), json.loads(body)))
        status, reply_headers, payload = self.replies.pop(0)
        return status, reply_headers, json.dumps(payload).encode("utf-8")


class SpecValidationTest(unittest.TestCase):
    def assert_invalid(self, spec: dict, fragment: str) -> None:
        with self.assertRaises(bench.BenchError) as caught:
            bench.validate_spec(spec)
        self.assertEqual(caught.exception.status, "invalid_spec")
        self.assertIn(fragment, str(caught.exception))

    def test_defaults_are_applied(self) -> None:
        resolved = bench.validate_spec(base_spec())
        self.assertEqual(resolved["base_url"], "https://api.anthropic.com")
        self.assertEqual(resolved["max_turns"], bench.DEFAULT_MAX_TURNS)
        self.assertEqual(resolved["max_tokens"], bench.DEFAULT_MAX_TOKENS)
        self.assertEqual(resolved["user_turns"], [])

    def test_budget_is_required(self) -> None:
        spec = base_spec()
        del spec["budget"]
        self.assert_invalid(spec, "budget is required")

    def test_unknown_field_is_rejected(self) -> None:
        self.assert_invalid(base_spec(max_reqests=3), "unknown spec fields")

    def test_http_base_url_only_for_loopback(self) -> None:
        self.assert_invalid(
            base_spec(provider="openai-compatible", base_url="http://example.com/v1"),
            "https",
        )
        resolved = bench.validate_spec(
            base_spec(provider="openai-compatible", base_url="http://localhost:11434/v1/")
        )
        self.assertEqual(resolved["base_url"], "http://localhost:11434/v1")

    def test_openai_compatible_needs_base_url(self) -> None:
        self.assert_invalid(base_spec(provider="openai-compatible"), "base_url")

    def test_stub_for_unknown_tool_is_rejected(self) -> None:
        self.assert_invalid(base_spec(tool_results={"ghost": "x"}), "unknown tool")

    def test_conversation_must_end_with_user_turn(self) -> None:
        spec = base_spec(messages=[
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ])
        self.assert_invalid(spec, "end with a user turn")

    def test_max_usd_requires_pricing(self) -> None:
        self.assert_invalid(base_spec(budget={"max_requests": 2, "max_usd": 1}), "pricing")

    def test_turn_ceiling_is_hard(self) -> None:
        self.assert_invalid(base_spec(max_turns=bench.HARD_MAX_TURNS + 1), "max_turns")


class MockRunTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name) / "out"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_mock(self, spec: dict, replies: list[dict]) -> tuple[dict, list[dict]]:
        resolved = bench.validate_spec(spec)
        transport = bench.Transport(resolved, credential=None, timeout=5, mock=replies)
        self.runs = getattr(self, "runs", 0) + 1
        out = bench.prepare_out_dir(self.out / str(self.runs), False)
        summary = bench.run_bench(resolved, "digest", out, transport=transport)
        events = [json.loads(line) for line in (out / "transcript.jsonl").read_text().splitlines()]
        return summary, events

    def test_tool_loop_returns_all_results_in_one_user_message(self) -> None:
        summary, events = self.run_mock(base_spec(), [
            response("tool_use", [
                {"type": "thinking", "thinking": "", "signature": "sig"},
                tool_use("lookup_customer", {"email": "ada@example.com"}, "toolu_a"),
                tool_use("list_charges", {"customer_id": "cus_1"}, "toolu_b"),
            ]),
            response("end_turn", [{"type": "text", "text": "done"}]),
        ])
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["requests"], 2)
        self.assertEqual(summary["tool_sequence"], ["lookup_customer", "list_charges"])
        self.assertEqual(summary["missing_stubs"], ["list_charges"])
        second_request = [event for event in events if event["event"] == "request"][1]["body"]
        assistant_turn = second_request["messages"][1]
        self.assertEqual(assistant_turn["content"][0]["type"], "thinking")
        tool_turn = second_request["messages"][2]
        self.assertEqual(tool_turn["role"], "user")
        self.assertEqual([block["type"] for block in tool_turn["content"]], ["tool_result", "tool_result"])
        self.assertEqual(tool_turn["content"][0]["content"], json.dumps({"customer_id": "cus_1"}))
        self.assertNotIn("is_error", tool_turn["content"][0])
        self.assertTrue(tool_turn["content"][1]["is_error"])
        self.assertIn("no stub result", tool_turn["content"][1]["content"])
        self.assertEqual(second_request["system"], "Use the tools.")
        self.assertEqual(len(second_request["messages"]), 3)
        self.assertEqual(summary["final_text"], "done")

    def test_stub_error_case_and_fallback(self) -> None:
        summary, events = self.run_mock(base_spec(), [
            response("tool_use", [tool_use("lookup_customer", {"email": "nobody@example.com"})]),
            response("end_turn", [{"type": "text", "text": "no such customer"}]),
        ])
        call = next(event for event in events if event["event"] == "tool_call")
        self.assertEqual(call["stub"], "default")
        self.assertTrue(call["is_error"])
        self.assertEqual(call["result"], "not found")
        self.assertEqual(summary["missing_stubs"], [])

    def test_request_cap_stops_the_loop(self) -> None:
        loop = [response("tool_use", [tool_use("lookup_customer", {"email": "ada@example.com"})])] * 5
        summary, _ = self.run_mock(base_spec(budget={"max_requests": 2}), loop)
        self.assertEqual(summary["status"], "budget_exceeded")
        self.assertEqual(summary["requests"], 2)

    def test_token_cap_stops_the_loop(self) -> None:
        summary, _ = self.run_mock(
            base_spec(budget={"max_requests": 6, "max_total_tokens": 150}),
            [
                response("tool_use", [tool_use("lookup_customer", {"email": "ada@example.com"})], 100, 100),
                response("end_turn", [{"type": "text", "text": "x"}]),
            ],
        )
        self.assertEqual(summary["status"], "budget_exceeded")
        self.assertIn("max_total_tokens", summary["detail"])

    def test_usd_cap_uses_pricing(self) -> None:
        summary, _ = self.run_mock(
            base_spec(
                budget={"max_requests": 6, "max_usd": 0.001},
                pricing={"input_per_mtok": 5, "output_per_mtok": 25},
            ),
            [response("end_turn", [{"type": "text", "text": "x"}], 100_000, 100_000)],
        )
        self.assertEqual(summary["status"], "budget_exceeded")
        self.assertEqual(summary["estimated_usd"], 3.0)

    def test_turn_limit(self) -> None:
        loop = [response("tool_use", [tool_use("lookup_customer", {"email": "ada@example.com"})])] * 5
        summary, _ = self.run_mock(base_spec(max_turns=3, budget={"max_requests": 10}), loop)
        self.assertEqual(summary["status"], "turn_limit")
        self.assertEqual(summary["turns"], 3)

    def test_truncation_refusal_and_pause_turn(self) -> None:
        summary, _ = self.run_mock(base_spec(), [response("max_tokens", [{"type": "text", "text": "partial"}])])
        self.assertEqual(summary["status"], "truncated")

        summary, events = self.run_mock(base_spec(), [
            response("refusal", [], stop_details={"type": "refusal", "category": "cyber"}),
        ])
        self.assertEqual(summary["status"], "refusal")
        self.assertIn("cyber", summary["detail"])
        self.assertEqual(events[2]["stop_details"]["category"], "cyber")

        summary, events = self.run_mock(base_spec(), [
            response("pause_turn", [{"type": "text", "text": "working"}]),
            response("end_turn", [{"type": "text", "text": "finished"}]),
        ])
        self.assertEqual(summary["status"], "completed")
        self.assertIn("pause_turn", [event["event"] for event in events])
        self.assertEqual(summary["requests"], 2)

    def test_scripted_user_turns_continue_the_conversation(self) -> None:
        summary, events = self.run_mock(base_spec(user_turns=["and then?", "never used"]), [
            response("end_turn", [{"type": "text", "text": "first"}]),
            response("end_turn", [{"type": "text", "text": "second"}]),
            response("end_turn", [{"type": "text", "text": "third"}]),
        ])
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["requests"], 3)
        self.assertEqual(summary["unused_user_turns"], [])
        third_request = [event for event in events if event["event"] == "request"][2]["body"]
        self.assertEqual(third_request["messages"][2], {"role": "user", "content": "and then?"})

    def test_mock_exhaustion_is_reported(self) -> None:
        summary, events = self.run_mock(base_spec(), [
            response("tool_use", [tool_use("lookup_customer", {"email": "ada@example.com"})]),
        ])
        self.assertEqual(summary["status"], "mock_exhausted")
        self.assertEqual(events[-2]["event"], "error")

    def test_tool_use_without_blocks_is_a_protocol_error(self) -> None:
        summary, _ = self.run_mock(base_spec(), [response("tool_use", [{"type": "text", "text": "?"}])])
        self.assertEqual(summary["status"], "protocol_error")

    def test_anthropic_request_carries_generation_parameters(self) -> None:
        spec = base_spec(effort="low", thinking={"type": "adaptive"}, tool_choice={"type": "auto"})
        spec["tools"][0]["strict"] = True
        _, events = self.run_mock(spec, [response("end_turn", [{"type": "text", "text": "x"}])])
        body = events[1]["body"]
        self.assertEqual(body["output_config"], {"effort": "low"})
        self.assertEqual(body["thinking"], {"type": "adaptive"})
        self.assertEqual(body["tool_choice"], {"type": "auto"})
        self.assertTrue(body["tools"][0]["strict"])
        self.assertNotIn("strict", body["tools"][1])
        self.assertNotIn("temperature", body)


class LiveTransportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name) / "out"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_live(self, spec: dict, post: FakePost, credential: tuple[str, str]) -> tuple[dict, list[dict]]:
        resolved = bench.validate_spec(spec)
        transport = bench.Transport(resolved, credential=credential, timeout=5, post=post)
        out = bench.prepare_out_dir(self.out, False)
        with mock.patch.object(bench.time, "sleep", lambda _seconds: None):
            summary = bench.run_bench(resolved, "digest", out, transport=transport)
        events = [json.loads(line) for line in (out / "transcript.jsonl").read_text().splitlines()]
        return summary, events

    def test_api_key_header_and_credential_redaction(self) -> None:
        secret = "sk-ant-unit-secret-value"
        post = FakePost([(200, {}, response("end_turn", [{"type": "text", "text": f"echo {secret}"}]))])
        summary, events = self.run_live(base_spec(), post, ("api-key", secret))
        url, headers, body = post.calls[0]
        self.assertEqual(url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(headers["x-api-key"], secret)
        self.assertEqual(headers["anthropic-version"], bench.ANTHROPIC_VERSION)
        self.assertNotIn("authorization", headers)
        artifacts = (self.out / "transcript.jsonl").read_text() + (self.out / "summary.json").read_text()
        self.assertNotIn(secret, artifacts)
        self.assertIn("[redacted-credential]", summary["final_text"])
        self.assertNotIn("headers", json.dumps(events))

    def test_bearer_token_is_sent_plain(self) -> None:
        post = FakePost([(200, {}, response("end_turn", [{"type": "text", "text": "ok"}]))])
        self.run_live(base_spec(), post, ("bearer", "gateway-token"))
        headers = post.calls[0][1]
        self.assertEqual(headers["authorization"], "Bearer gateway-token")
        self.assertNotIn("x-api-key", headers)
        self.assertNotIn("anthropic-beta", headers)

    def test_retry_once_on_rate_limit_then_succeed(self) -> None:
        post = FakePost([
            (429, {"retry-after": "0"}, {"error": {"type": "rate_limit_error", "message": "slow down"}}),
            (200, {}, response("end_turn", [{"type": "text", "text": "ok"}])),
        ])
        summary, _ = self.run_live(base_spec(), post, ("api-key", "k"))
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["requests"], 2)

    def test_persistent_error_becomes_provider_error(self) -> None:
        post = FakePost([
            (500, {}, {"error": {"type": "api_error", "message": "boom"}}),
            (500, {}, {"error": {"type": "api_error", "message": "boom"}}),
            (500, {}, {"error": {"type": "api_error", "message": "boom"}}),
        ])
        summary, events = self.run_live(base_spec(), post, ("api-key", "k"))
        self.assertEqual(summary["status"], "provider_error")
        self.assertIn("HTTP 500", summary["detail"])
        self.assertIn("api_error", summary["detail"])
        self.assertEqual(events[-2]["event"], "error")

    def test_non_retryable_error_is_not_retried(self) -> None:
        post = FakePost([(400, {}, {"error": {"type": "invalid_request_error", "message": "bad"}})])
        summary, _ = self.run_live(base_spec(), post, ("api-key", "k"))
        self.assertEqual(summary["status"], "provider_error")
        self.assertEqual(len(post.calls), 1)

    def test_openai_compatible_request_and_tool_results(self) -> None:
        spec = base_spec(provider="openai-compatible", base_url="https://models.example.com/v1", temperature=0.2)
        post = FakePost([
            (200, {}, {
                "choices": [{
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant", "content": None,
                        "tool_calls": [{
                            "id": "call_1", "type": "function",
                            "function": {"name": "lookup_customer", "arguments": json.dumps({"email": "ada@example.com"})},
                        }],
                    },
                }],
                "usage": {"prompt_tokens": 50, "completion_tokens": 5},
            }),
            (200, {}, {
                "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "all good"}}],
                "usage": {"prompt_tokens": 80, "completion_tokens": 4},
            }),
        ])
        summary, _ = self.run_live(spec, post, ("bearer", "oa-key"))
        self.assertEqual(summary["status"], "completed")
        first_url, first_headers, first_body = post.calls[0]
        self.assertEqual(first_url, "https://models.example.com/v1/chat/completions")
        self.assertEqual(first_headers["authorization"], "Bearer oa-key")
        self.assertNotIn("anthropic-version", first_headers)
        self.assertEqual(first_body["messages"][0], {"role": "system", "content": "Use the tools."})
        self.assertEqual(first_body["tools"][0]["type"], "function")
        self.assertEqual(first_body["tools"][0]["function"]["name"], "lookup_customer")
        self.assertIn("parameters", first_body["tools"][0]["function"])
        self.assertEqual(first_body["temperature"], 0.2)
        second_body = post.calls[1][2]
        self.assertEqual(second_body["messages"][-1]["role"], "tool")
        self.assertEqual(second_body["messages"][-1]["tool_call_id"], "call_1")
        self.assertEqual(second_body["messages"][-2]["role"], "assistant")
        self.assertEqual(summary["usage"]["input_tokens"], 130)
        self.assertEqual(summary["tool_sequence"], ["lookup_customer"])
        self.assertEqual(summary["final_text"], "all good")


class CredentialAndOutputTest(unittest.TestCase):
    def test_credential_resolution_order(self) -> None:
        spec = bench.validate_spec(base_spec())
        self.assertEqual(bench.resolve_credential(spec, {"ANTHROPIC_API_KEY": "a", "ANTHROPIC_AUTH_TOKEN": "t"}), ("api-key", "a"))
        self.assertEqual(bench.resolve_credential(spec, {"ANTHROPIC_AUTH_TOKEN": "t"}), ("bearer", "t"))
        with self.assertRaises(bench.BenchError) as caught:
            bench.resolve_credential(spec, {})
        self.assertEqual(caught.exception.status, "missing_credentials")
        custom = bench.validate_spec(base_spec(api_key_env="MY_PROVIDER_KEY"))
        self.assertEqual(bench.resolve_credential(custom, {"MY_PROVIDER_KEY": "c", "ANTHROPIC_API_KEY": "a"}), ("api-key", "c"))
        openai = bench.validate_spec(base_spec(provider="openai-compatible", base_url="https://x.example/v1"))
        self.assertEqual(bench.resolve_credential(openai, {"OPENAI_API_KEY": "o"}), ("bearer", "o"))

    def test_output_directory_must_be_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            busy = root / "busy"
            busy.mkdir()
            (busy / "old.txt").write_text("x")
            with self.assertRaises(bench.BenchError) as caught:
                bench.prepare_out_dir(busy, False)
            self.assertEqual(caught.exception.status, "invalid_output")
            self.assertEqual(bench.prepare_out_dir(busy, True), busy.resolve())
            link = root / "link"
            os.symlink(busy, link)
            with self.assertRaises(bench.BenchError):
                bench.prepare_out_dir(link, True)
            fresh = bench.prepare_out_dir(root / "fresh" / "nested", False)
            self.assertTrue(fresh.is_dir())
            self.assertEqual(fresh.stat().st_mode & 0o777, 0o700)

    def test_helper_never_shells_out_or_takes_a_key_argument(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("os.system", source)
        self.assertNotIn("shell=True", source)
        parser = bench.build_parser()
        for action in parser._subparsers._group_actions[0].choices.values():
            for option in action._option_string_actions:
                self.assertNotIn("key", option.lower())
                self.assertNotIn("token", option.lower())


class CompareAndCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.spec_path = self.root / "spec.json"
        self.spec_path.write_text(json.dumps(base_spec()))
        self.mock_path = self.root / "mock.json"
        self.mock_path.write_text(json.dumps([
            response("tool_use", [tool_use("lookup_customer", {"email": "ada@example.com"})]),
            response("end_turn", [{"type": "text", "text": "done"}]),
        ]))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def invoke(self, *argv: str) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = bench.main(list(argv))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_validate_reports_unstubbed_tools_without_network(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            code, out, _ = self.invoke("validate", "--spec", str(self.spec_path))
        self.assertEqual(code, 0)
        report = json.loads(out)
        self.assertEqual(report["unstubbed_tools"], ["list_charges"])
        self.assertTrue(report["credential_source"].startswith("none"))

    def test_run_with_mock_needs_no_credential_and_compare_works(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            code_a, out_a, _ = self.invoke("run", "--spec", str(self.spec_path), "--mock", str(self.mock_path), "--out", str(self.root / "a"))
            code_b, _, _ = self.invoke("run", "--spec", str(self.spec_path), "--mock", str(self.mock_path), "--out", str(self.root / "b"), "--max-requests", "1")
        self.assertEqual(code_a, 0)
        self.assertEqual(json.loads(out_a)["status"], "completed")
        self.assertEqual(code_b, 2)
        code, out, _ = self.invoke("compare", "--a", str(self.root / "a"), "--b", str(self.root / "b"), "--json")
        self.assertEqual(code, 0)
        report = json.loads(out)
        rows = {row["metric"]: row for row in report["rows"]}
        self.assertEqual(rows["status"]["a"], "completed")
        self.assertEqual(rows["status"]["b"], "budget_exceeded")
        self.assertFalse(rows["requests"]["same"])
        code, text, _ = self.invoke("compare", "--a", str(self.root / "a"), "--b", str(self.root / "b"))
        self.assertIn("api-bench compare", text)

    def test_live_run_without_credential_fails_closed(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            code, _, err = self.invoke("run", "--spec", str(self.spec_path), "--out", str(self.root / "live"))
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(err)["status"], "missing_credentials")
        self.assertFalse((self.root / "live").exists())

    def test_spec_chosen_credential_variable_needs_command_line_confirmation(self) -> None:
        """A spec must not be able to pick which secret is sent to its endpoint on its own."""
        spec = base_spec(provider="openai-compatible", base_url="http://127.0.0.1:9/v1", api_key_env="AWS_SECRET_ACCESS_KEY")
        path = self.root / "exfil.json"
        path.write_text(json.dumps(spec))
        env = {"AWS_SECRET_ACCESS_KEY": "aws-secret", "OPENAI_API_KEY": "o"}
        with mock.patch.dict(os.environ, env, clear=True):
            code, _, err = self.invoke("run", "--spec", str(path), "--out", str(self.root / "no-flag"))
            self.assertEqual((code, json.loads(err)["status"]), (1, "missing_credentials"))
            self.assertIn("--credential-env AWS_SECRET_ACCESS_KEY", json.loads(err)["message"])
            code, _, err = self.invoke("run", "--spec", str(path), "--out", str(self.root / "wrong-flag"), "--credential-env", "OPENAI_API_KEY")
            self.assertEqual((code, json.loads(err)["status"]), (1, "missing_credentials"))
            self.assertFalse((self.root / "no-flag").exists())
            self.assertFalse((self.root / "wrong-flag").exists())
            # The matching flag passes the gate; the unreachable loopback endpoint then fails as a provider error.
            code, out, _ = self.invoke("run", "--spec", str(path), "--out", str(self.root / "confirmed"), "--credential-env", "AWS_SECRET_ACCESS_KEY", "--timeout-seconds", "1")
            self.assertEqual((code, json.loads(out)["status"]), (2, "provider_error"))
            self.assertNotIn("aws-secret", (self.root / "confirmed" / "transcript.jsonl").read_text())
            # The flag without a spec-level api_key_env is a contradiction, not a silent override.
            code, _, err = self.invoke("run", "--spec", str(self.spec_path), "--out", str(self.root / "stray"), "--credential-env", "OPENAI_API_KEY")
            self.assertEqual((code, json.loads(err)["status"]), (1, "invalid_spec"))

    def test_invalid_spec_exits_one_with_json_on_stderr(self) -> None:
        bad = self.root / "bad.json"
        bad.write_text("{not json")
        code, _, err = self.invoke("validate", "--spec", str(bad))
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(err)["status"], "invalid_spec")

    def test_bundled_template_and_mock_run_end_to_end(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            code, out, _ = self.invoke(
                "run", "--spec", str(SKILL / "templates" / "bench-spec.json"),
                "--mock", str(SKILL / "templates" / "mock-responses.json"),
                "--out", str(self.root / "template"),
            )
        self.assertEqual(code, 0)
        summary = json.loads(out)
        self.assertEqual(summary["tool_sequence"], ["lookup_customer", "list_charges"])
        self.assertEqual(summary["missing_stubs"], [])
        self.assertIsNone(summary["estimated_usd"], "the bundled template must not ship a price table")


if __name__ == "__main__":
    unittest.main()
