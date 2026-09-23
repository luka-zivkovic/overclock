#!/usr/bin/env python3
"""Dry-run how an application would drive a model API, without writing the app.

One JSON spec describes the request an application would send: system prompt,
seed messages, tool definitions, stubbed tool results, and hard budgets. The
helper runs the tool-use loop against the Claude Messages API or an
OpenAI-compatible chat endpoint, records every request, response, and tool
call to a JSONL transcript, and stops at the first budget, provider, or
protocol boundary. A mock file replaces the network for wiring checks.

The helper never starts a shell, never reads credentials from arguments, never
writes outside the chosen output directory, and never prints a credential.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROVIDERS = ("anthropic", "openai-compatible")
ANTHROPIC_BASE_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_TIMEOUT_SECONDS = 600
MAX_TIMEOUT_SECONDS = 3600
DEFAULT_MAX_TURNS = 8
HARD_MAX_TURNS = 50
DEFAULT_MAX_TOKENS = 4096
MAX_REQUEST_BYTES = 4 * 1024 * 1024
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_STUB_RESULT_CHARS = 64 * 1024
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}
MAX_RETRIES = 2
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}
SPEC_FIELDS = {
    "name", "provider", "model", "base_url", "api_key_env", "system",
    "messages", "tools", "tool_results", "user_turns", "max_turns",
    "max_tokens", "thinking", "effort", "tool_choice", "temperature",
    "budget", "pricing", "notes",
}
BUDGET_FIELDS = {"max_requests", "max_total_tokens", "max_usd"}
PRICING_FIELDS = {
    "input_per_mtok", "output_per_mtok", "cache_read_per_mtok",
    "cache_write_per_mtok",
}
STUB_FIELDS = {"cases", "default", "error", "result"}

HttpPost = Callable[[str, dict[str, str], bytes, int], tuple[int, dict[str, str], bytes]]


class BenchError(RuntimeError):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


# --------------------------------------------------------------------------- spec


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BenchError("invalid_spec", message)


def _is_json_object(value: object) -> bool:
    return isinstance(value, dict)


def validate_spec(spec: object) -> dict[str, Any]:
    """Return the spec with defaults applied, or raise ``invalid_spec``."""
    _require(_is_json_object(spec), "spec must be a JSON object")
    assert isinstance(spec, dict)
    unknown = set(spec) - SPEC_FIELDS
    _require(not unknown, f"unknown spec fields: {sorted(unknown)}")

    name = spec.get("name", "bench")
    _require(
        isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", name) is not None,
        "name must be a short safe identifier",
    )
    provider = spec.get("provider", "anthropic")
    _require(provider in PROVIDERS, f"provider must be one of {', '.join(PROVIDERS)}")
    model = spec.get("model")
    _require(
        isinstance(model, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}", model) is not None,
        "model must be a non-empty model identifier",
    )

    base_url = spec.get("base_url")
    if provider == "anthropic":
        base_url = base_url or ANTHROPIC_BASE_URL
    else:
        _require(isinstance(base_url, str) and bool(base_url), "openai-compatible specs need base_url")
    _require(isinstance(base_url, str), "base_url must be a string")
    parsed = urllib.parse.urlsplit(base_url)
    _require(parsed.scheme in {"http", "https"} and bool(parsed.netloc), "base_url must be an absolute http(s) URL")
    host = parsed.hostname or ""
    _require(
        parsed.scheme == "https" or host in LOOPBACK_HOSTS,
        "base_url must use https unless it points at a loopback host",
    )
    _require(not parsed.query and not parsed.fragment, "base_url must not carry a query or fragment")

    api_key_env = spec.get("api_key_env")
    if api_key_env is not None:
        _require(
            isinstance(api_key_env, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", api_key_env) is not None,
            "api_key_env must name an environment variable",
        )

    system = spec.get("system")
    _require(system is None or isinstance(system, str), "system must be a string when present")

    messages = spec.get("messages")
    _require(isinstance(messages, list) and bool(messages), "messages must be a non-empty list")
    for index, message in enumerate(messages):
        _require(_is_json_object(message), f"messages[{index}] must be an object")
        _require(message.get("role") in {"user", "assistant"}, f"messages[{index}].role must be user or assistant")
        content = message.get("content")
        _require(
            (isinstance(content, str) and bool(content.strip())) or (isinstance(content, list) and bool(content)),
            f"messages[{index}].content must be non-empty text or content blocks",
        )
    _require(messages[0].get("role") == "user", "messages must start with a user turn")
    _require(messages[-1].get("role") == "user", "messages must end with a user turn")

    tools = spec.get("tools", [])
    _require(isinstance(tools, list), "tools must be a list")
    names: set[str] = set()
    for index, tool in enumerate(tools):
        _require(_is_json_object(tool), f"tools[{index}] must be an object")
        tool_name = tool.get("name")
        _require(
            isinstance(tool_name, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", tool_name) is not None,
            f"tools[{index}].name must match the API tool-name pattern",
        )
        _require(tool_name not in names, f"duplicate tool name {tool_name!r}")
        names.add(tool_name)
        _require(isinstance(tool.get("description"), str) and bool(tool["description"].strip()), f"tools[{index}] needs a description")
        schema = tool.get("input_schema")
        _require(_is_json_object(schema) and schema.get("type") == "object", f"tools[{index}].input_schema must be an object schema")

    stubs = spec.get("tool_results", {})
    _require(_is_json_object(stubs), "tool_results must map tool names to stub results")
    for stub_name, stub in stubs.items():
        _require(stub_name == "*" or stub_name in names, f"tool_results names unknown tool {stub_name!r}")
        if _is_json_object(stub) and (set(stub) & STUB_FIELDS) and set(stub) <= STUB_FIELDS:
            cases = stub.get("cases", [])
            _require(isinstance(cases, list), f"tool_results[{stub_name!r}].cases must be a list")
            for case_index, case in enumerate(cases):
                _require(
                    _is_json_object(case) and _is_json_object(case.get("when")) and ("result" in case or "error" in case),
                    f"tool_results[{stub_name!r}].cases[{case_index}] needs when plus result or error",
                )

    user_turns = spec.get("user_turns", [])
    _require(
        isinstance(user_turns, list) and all(isinstance(turn, str) and turn.strip() for turn in user_turns),
        "user_turns must be a list of non-empty strings",
    )

    max_turns = spec.get("max_turns", DEFAULT_MAX_TURNS)
    _require(
        isinstance(max_turns, int) and not isinstance(max_turns, bool) and 1 <= max_turns <= HARD_MAX_TURNS,
        f"max_turns must be an integer from 1 to {HARD_MAX_TURNS}",
    )
    max_tokens = spec.get("max_tokens", DEFAULT_MAX_TOKENS)
    _require(
        isinstance(max_tokens, int) and not isinstance(max_tokens, bool) and 1 <= max_tokens <= 128000,
        "max_tokens must be an integer from 1 to 128000",
    )
    thinking = spec.get("thinking")
    _require(thinking is None or _is_json_object(thinking), "thinking must be an object when present")
    effort = spec.get("effort")
    _require(effort is None or effort in EFFORT_LEVELS, f"effort must be one of {', '.join(EFFORT_LEVELS)}")
    tool_choice = spec.get("tool_choice")
    _require(tool_choice is None or _is_json_object(tool_choice), "tool_choice must be an object when present")
    temperature = spec.get("temperature")
    _require(
        temperature is None or (isinstance(temperature, (int, float)) and not isinstance(temperature, bool) and 0 <= temperature <= 2),
        "temperature must be a number from 0 to 2",
    )

    budget = spec.get("budget")
    _require(_is_json_object(budget), "budget is required: set max_requests and optionally max_total_tokens or max_usd")
    unknown_budget = set(budget) - BUDGET_FIELDS
    _require(not unknown_budget, f"unknown budget fields: {sorted(unknown_budget)}")
    max_requests = budget.get("max_requests")
    _require(
        isinstance(max_requests, int) and not isinstance(max_requests, bool) and 1 <= max_requests <= 500,
        "budget.max_requests must be an integer from 1 to 500",
    )
    for field in ("max_total_tokens", "max_usd"):
        value = budget.get(field)
        _require(
            value is None or (isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0),
            f"budget.{field} must be a positive number",
        )

    pricing = spec.get("pricing")
    if pricing is not None:
        _require(_is_json_object(pricing), "pricing must be an object")
        unknown_pricing = set(pricing) - PRICING_FIELDS
        _require(not unknown_pricing, f"unknown pricing fields: {sorted(unknown_pricing)}")
        for field, value in pricing.items():
            _require(
                isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0,
                f"pricing.{field} must be a non-negative number",
            )
        _require(
            "input_per_mtok" in pricing and "output_per_mtok" in pricing,
            "pricing needs input_per_mtok and output_per_mtok",
        )
    _require(
        budget.get("max_usd") is None or pricing is not None,
        "budget.max_usd needs pricing so spend can be estimated",
    )

    resolved = dict(spec)
    resolved.update(
        name=name,
        provider=provider,
        base_url=base_url.rstrip("/"),
        messages=messages,
        tools=tools,
        tool_results=stubs,
        user_turns=user_turns,
        max_turns=max_turns,
        max_tokens=max_tokens,
        budget=budget,
    )
    return resolved


def load_spec(path: Path) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise BenchError("invalid_spec", f"cannot read spec: {exc}") from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BenchError("invalid_spec", f"spec is not valid JSON: {exc}") from exc
    return validate_spec(data), sha256_bytes(raw)


# ---------------------------------------------------------------------- credentials


def confirm_credential_env(spec: dict[str, Any], confirmed: str | None) -> None:
    """A non-default credential variable named by the spec must be repeated on the command line.

    A spec is data the user may not have written. Without this gate a spec could name any
    secret-looking variable and have it sent as a bearer token to any https ``base_url``. The
    run command therefore refuses to read a spec-chosen variable unless ``--credential-env`` names
    the same variable, which puts the choice in the conversation where the user can see it.
    """
    override = spec.get("api_key_env")
    if override and confirmed != override:
        raise BenchError(
            "missing_credentials",
            f"spec names the non-default credential variable {override}; rerun with "
            f"--credential-env {override} to confirm it may be sent to {spec['base_url']}",
        )
    if confirmed and not override:
        raise BenchError("invalid_spec", f"--credential-env {confirmed} given but the spec sets no api_key_env")


def resolve_credential(spec: dict[str, Any], environ: dict[str, str]) -> tuple[str, str]:
    """Return (scheme, secret). Scheme is ``api-key`` or ``bearer``."""
    override = spec.get("api_key_env")
    if override:
        value = environ.get(override, "")
        if value.strip():
            return ("bearer" if spec["provider"] != "anthropic" else "api-key"), value.strip()
        raise BenchError("missing_credentials", f"environment variable {override} is empty or unset")
    if spec["provider"] == "anthropic":
        api_key = environ.get("ANTHROPIC_API_KEY", "").strip()
        if api_key:
            return "api-key", api_key
        token = environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
        if token:
            return "bearer", token
        raise BenchError(
            "missing_credentials",
            "set ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN, or run with --mock",
        )
    api_key = environ.get("OPENAI_API_KEY", "").strip()
    if api_key:
        return "bearer", api_key
    raise BenchError(
        "missing_credentials",
        "set OPENAI_API_KEY (or api_key_env in the spec), or run with --mock",
    )


# ------------------------------------------------------------------------ transport


def http_post(url: str, headers: dict[str, str], body: bytes, timeout: int) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
            return response.status, dict(response.headers.items()), payload
    except urllib.error.HTTPError as exc:
        payload = exc.read(MAX_RESPONSE_BYTES + 1)
        return exc.code, dict(exc.headers.items()), payload
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise BenchError("provider_error", f"request failed before a response arrived: {exc}") from exc


class Transport:
    """Serialize requests, enforce size and retry limits, and redact the credential."""

    def __init__(
        self,
        spec: dict[str, Any],
        *,
        credential: tuple[str, str] | None,
        timeout: int,
        post: HttpPost = http_post,
        mock: list[dict[str, Any]] | None = None,
    ) -> None:
        self.spec = spec
        self.credential = credential
        self.timeout = timeout
        self.post = post
        self.mock = mock
        self.mock_index = 0
        self.requests_made = 0

    @property
    def secret(self) -> str | None:
        return self.credential[1] if self.credential else None

    def redact(self, text: str) -> str:
        if self.secret and self.secret in text:
            return text.replace(self.secret, "[redacted-credential]")
        return text

    def endpoint(self) -> str:
        base = self.spec["base_url"]
        if self.spec["provider"] == "anthropic":
            return base + "/v1/messages"
        return base + "/chat/completions"

    def headers(self) -> dict[str, str]:
        headers = {
            "content-type": "application/json",
            "accept": "application/json",
            "user-agent": "overclock-api-bench/0.1",
        }
        if self.credential is None:
            return headers
        scheme, secret = self.credential
        if self.spec["provider"] == "anthropic":
            headers["anthropic-version"] = ANTHROPIC_VERSION
            if scheme == "api-key":
                headers["x-api-key"] = secret
            else:
                headers["authorization"] = f"Bearer {secret}"
        else:
            headers["authorization"] = f"Bearer {secret}"
        return headers

    def send(self, body: dict[str, Any]) -> tuple[dict[str, Any], float]:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        if len(encoded) > MAX_REQUEST_BYTES:
            raise BenchError("request_too_large", f"request body is {len(encoded)} bytes; limit is {MAX_REQUEST_BYTES}")
        if self.mock is not None:
            if self.mock_index >= len(self.mock):
                raise BenchError("mock_exhausted", f"mock file has only {len(self.mock)} responses")
            response = self.mock[self.mock_index]
            self.mock_index += 1
            self.requests_made += 1
            return response, 0.0
        attempt = 0
        while True:
            started = time.monotonic()
            status, headers, payload = self.post(self.endpoint(), self.headers(), encoded, self.timeout)
            elapsed = (time.monotonic() - started) * 1000.0
            self.requests_made += 1
            if len(payload) > MAX_RESPONSE_BYTES:
                raise BenchError("provider_error", "response exceeded the size limit")
            if status in RETRYABLE_STATUS and attempt < MAX_RETRIES:
                attempt += 1
                delay = _retry_delay(headers, attempt)
                time.sleep(delay)
                continue
            text = payload.decode("utf-8", errors="replace")
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise BenchError("provider_error", f"HTTP {status}: non-JSON response: {self.redact(text[:500])}") from exc
            if status >= 400:
                detail = _error_detail(data)
                raise BenchError("provider_error", f"HTTP {status}: {self.redact(detail)}")
            if not isinstance(data, dict):
                raise BenchError("provider_error", "response JSON is not an object")
            return data, elapsed


def _retry_delay(headers: dict[str, str], attempt: int) -> float:
    lowered = {key.lower(): value for key, value in headers.items()}
    retry_after = lowered.get("retry-after")
    if retry_after:
        try:
            return min(float(retry_after), 30.0)
        except ValueError:
            pass
    return min(2.0 ** attempt, 30.0)


def _error_detail(data: object) -> str:
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            kind = error.get("type") or error.get("code") or "error"
            return f"{kind}: {str(error.get('message', ''))[:500]}"
        if isinstance(error, str):
            return error[:500]
    return json.dumps(data)[:500]


# ------------------------------------------------------------------------- stubs


def _matches(when: dict[str, Any], tool_input: Any) -> bool:
    if not isinstance(tool_input, dict):
        return False
    return all(tool_input.get(key) == value for key, value in when.items())


def stub_result(spec: dict[str, Any], name: str, tool_input: Any) -> tuple[str, str, bool]:
    """Return (kind, content, is_error) for one tool call using the spec's stubs."""
    stubs = spec["tool_results"]
    stub = stubs.get(name, stubs.get("*"))
    if stub is None:
        return "missing", f"api-bench: no stub result configured for tool {name!r}", True
    if isinstance(stub, dict) and (set(stub) & STUB_FIELDS) and set(stub) <= STUB_FIELDS:
        for case in stub.get("cases", []):
            if _matches(case["when"], tool_input):
                if "error" in case:
                    return "matched", _stringify(case["error"]), True
                return "matched", _stringify(case["result"]), False
        if "error" in stub:
            return "default", _stringify(stub["error"]), True
        if "result" in stub:
            return "default", _stringify(stub["result"]), False
        if "default" in stub:
            return "default", _stringify(stub["default"]), False
        return "missing", f"api-bench: stub for {name!r} matched no case and has no default", True
    return "default", _stringify(stub), False


def _stringify(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    if len(text) > MAX_STUB_RESULT_CHARS:
        text = text[:MAX_STUB_RESULT_CHARS] + "\n[api-bench: stub result truncated]"
    return text


# ----------------------------------------------------------------------- providers


def anthropic_request(spec: dict[str, Any], messages: list[dict[str, Any]]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": spec["model"],
        "max_tokens": spec["max_tokens"],
        "messages": messages,
    }
    if spec.get("system"):
        body["system"] = spec["system"]
    if spec["tools"]:
        body["tools"] = [
            {"name": tool["name"], "description": tool["description"], "input_schema": tool["input_schema"]}
            | ({"strict": True} if tool.get("strict") else {})
            for tool in spec["tools"]
        ]
    if spec.get("tool_choice") is not None:
        body["tool_choice"] = spec["tool_choice"]
    if spec.get("thinking") is not None:
        body["thinking"] = spec["thinking"]
    if spec.get("effort") is not None:
        body["output_config"] = {"effort": spec["effort"]}
    if spec.get("temperature") is not None:
        body["temperature"] = spec["temperature"]
    return body


def openai_request(spec: dict[str, Any], messages: list[dict[str, Any]]) -> dict[str, Any]:
    chat: list[dict[str, Any]] = []
    if spec.get("system"):
        chat.append({"role": "system", "content": spec["system"]})
    chat.extend(messages)
    body: dict[str, Any] = {"model": spec["model"], "messages": chat, "max_tokens": spec["max_tokens"]}
    if spec["tools"]:
        body["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
            for tool in spec["tools"]
        ]
    if spec.get("temperature") is not None:
        body["temperature"] = spec["temperature"]
    return body


def parse_anthropic(response: dict[str, Any]) -> dict[str, Any]:
    content = response.get("content")
    if not isinstance(content, list):
        raise BenchError("provider_error", "anthropic response has no content list")
    text_parts = [block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"]
    tool_calls = [
        {"id": block.get("id"), "name": block.get("name"), "input": block.get("input")}
        for block in content
        if isinstance(block, dict) and block.get("type") == "tool_use"
    ]
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    return {
        "stop_reason": response.get("stop_reason"),
        "stop_details": response.get("stop_details"),
        "text": "".join(text_parts),
        "tool_calls": tool_calls,
        "assistant_message": {"role": "assistant", "content": content},
        "usage": {
            "input_tokens": int(usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or 0),
            "cache_read_input_tokens": int(usage.get("cache_read_input_tokens") or 0),
            "cache_creation_input_tokens": int(usage.get("cache_creation_input_tokens") or 0),
        },
        "raw_content": content,
    }


def parse_openai(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise BenchError("provider_error", "openai-compatible response has no choices")
    choice = choices[0]
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    tool_calls = []
    for call in message.get("tool_calls") or []:
        if not isinstance(call, dict):
            continue
        function = call.get("function") if isinstance(call.get("function"), dict) else {}
        arguments = function.get("arguments", "{}")
        try:
            parsed_input = json.loads(arguments) if isinstance(arguments, str) else arguments
        except json.JSONDecodeError:
            parsed_input = {"_unparsed_arguments": arguments}
        tool_calls.append({"id": call.get("id"), "name": function.get("name"), "input": parsed_input})
    finish = choice.get("finish_reason")
    stop_reason = {"stop": "end_turn", "tool_calls": "tool_use", "length": "max_tokens", "content_filter": "refusal"}.get(finish, finish)
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    content = message.get("content")
    return {
        "stop_reason": stop_reason,
        "stop_details": None,
        "text": content if isinstance(content, str) else "",
        "tool_calls": tool_calls,
        "assistant_message": {key: value for key, value in message.items() if key in {"role", "content", "tool_calls"}} | {"role": "assistant"},
        "usage": {
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
        "raw_content": message,
    }


def anthropic_tool_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """All tool results go back in ONE user message, preserving parallel calls."""
    blocks = [
        {"type": "tool_result", "tool_use_id": item["id"], "content": item["content"]}
        | ({"is_error": True} if item["is_error"] else {})
        for item in results
    ]
    return [{"role": "user", "content": blocks}]


def openai_tool_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"role": "tool", "tool_call_id": item["id"], "content": item["content"]}
        for item in results
    ]


# ------------------------------------------------------------------------------ run


def estimate_usd(spec: dict[str, Any], usage: dict[str, int]) -> float | None:
    pricing = spec.get("pricing")
    if not pricing:
        return None
    uncached_input = max(usage["input_tokens"] - usage["cache_read_input_tokens"], 0)
    total = uncached_input * pricing["input_per_mtok"]
    total += usage["output_tokens"] * pricing["output_per_mtok"]
    total += usage["cache_read_input_tokens"] * pricing.get("cache_read_per_mtok", pricing["input_per_mtok"])
    total += usage["cache_creation_input_tokens"] * pricing.get("cache_write_per_mtok", pricing["input_per_mtok"])
    return round(total / 1_000_000.0, 6)


class Recorder:
    def __init__(self, path: Path, redact: Callable[[str], str]) -> None:
        self.path = path
        self.redact = redact
        self.handle = path.open("w", encoding="utf-8")

    def write(self, event: dict[str, Any]) -> None:
        line = json.dumps(event, ensure_ascii=False)
        self.handle.write(self.redact(line) + "\n")
        self.handle.flush()

    def close(self) -> None:
        self.handle.close()


def prepare_out_dir(out: Path, force: bool) -> Path:
    out = out.expanduser()
    if out.is_symlink():
        raise BenchError("invalid_output", "output directory must not be a symlink")
    if out.exists():
        if not out.is_dir():
            raise BenchError("invalid_output", "output path exists and is not a directory")
        if any(out.iterdir()) and not force:
            raise BenchError("invalid_output", f"output directory {out} is not empty; choose a fresh directory or pass --force")
    else:
        out.mkdir(parents=True, mode=0o700)
    return out.resolve()


def run_bench(
    spec: dict[str, Any],
    spec_digest: str,
    out: Path,
    *,
    transport: Transport,
) -> dict[str, Any]:
    recorder = Recorder(out / "transcript.jsonl", transport.redact)
    provider = spec["provider"]
    messages: list[dict[str, Any]] = [dict(message) for message in spec["messages"]]
    pending_user_turns = list(spec["user_turns"])
    usage_total = {
        "input_tokens": 0, "output_tokens": 0,
        "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
    }
    tool_counts: dict[str, int] = {}
    tool_sequence: list[str] = []
    missing_stubs: set[str] = set()
    budget = spec["budget"]
    status = "completed"
    detail = ""
    final_text = ""
    turn = 0
    latency_total = 0.0
    recorder.write({
        "event": "run_start", "name": spec["name"], "provider": provider, "model": spec["model"],
        "mock": transport.mock is not None, "spec_sha256": spec_digest, "started_at": now_iso(),
        "budget": budget, "max_turns": spec["max_turns"],
    })
    try:
        while True:
            if turn >= spec["max_turns"]:
                status, detail = "turn_limit", f"stopped after {turn} turns (max_turns)"
                break
            if transport.requests_made >= budget["max_requests"]:
                status, detail = "budget_exceeded", f"max_requests={budget['max_requests']} reached"
                break
            turn += 1
            body = anthropic_request(spec, messages) if provider == "anthropic" else openai_request(spec, messages)
            recorder.write({"event": "request", "turn": turn, "body": body})
            try:
                response, latency_ms = transport.send(body)
            except BenchError as exc:
                recorder.write({"event": "error", "turn": turn, "status": exc.status, "message": str(exc)})
                status, detail = exc.status, str(exc)
                break
            latency_total += latency_ms
            parsed = parse_anthropic(response) if provider == "anthropic" else parse_openai(response)
            for key in usage_total:
                usage_total[key] += parsed["usage"][key]
            recorder.write({
                "event": "response", "turn": turn, "stop_reason": parsed["stop_reason"],
                "stop_details": parsed["stop_details"], "content": parsed["raw_content"],
                "usage": parsed["usage"], "latency_ms": round(latency_ms, 1),
            })
            if parsed["text"]:
                final_text = parsed["text"]
            messages.append(parsed["assistant_message"])

            total_tokens = usage_total["input_tokens"] + usage_total["output_tokens"]
            max_total = budget.get("max_total_tokens")
            spend = estimate_usd(spec, usage_total)
            if max_total is not None and total_tokens > max_total:
                status, detail = "budget_exceeded", f"total tokens {total_tokens} exceed max_total_tokens={max_total}"
                break
            if budget.get("max_usd") is not None and spend is not None and spend > budget["max_usd"]:
                status, detail = "budget_exceeded", f"estimated spend {spend} USD exceeds max_usd={budget['max_usd']}"
                break

            stop = parsed["stop_reason"]
            if stop == "tool_use" or (parsed["tool_calls"] and stop not in {"max_tokens", "refusal"}):
                if not parsed["tool_calls"]:
                    status, detail = "protocol_error", "stop_reason tool_use without tool_use blocks"
                    break
                results = []
                for call in parsed["tool_calls"]:
                    name = str(call.get("name"))
                    kind, content, is_error = stub_result(spec, name, call.get("input"))
                    if kind == "missing":
                        missing_stubs.add(name)
                    tool_counts[name] = tool_counts.get(name, 0) + 1
                    tool_sequence.append(name)
                    recorder.write({
                        "event": "tool_call", "turn": turn, "id": call.get("id"), "name": name,
                        "input": call.get("input"), "stub": kind, "result": content, "is_error": is_error,
                    })
                    results.append({"id": call.get("id"), "content": content, "is_error": is_error})
                messages.extend(anthropic_tool_results(results) if provider == "anthropic" else openai_tool_results(results))
                continue
            if stop == "pause_turn":
                recorder.write({"event": "pause_turn", "turn": turn})
                continue
            if stop == "max_tokens":
                status, detail = "truncated", f"response hit max_tokens={spec['max_tokens']}"
                break
            if stop == "refusal":
                status, detail = "refusal", json.dumps(parsed["stop_details"]) if parsed["stop_details"] else "provider declined the request"
                break
            if stop in {"end_turn", "stop_sequence", None}:
                if pending_user_turns:
                    next_turn = pending_user_turns.pop(0)
                    messages.append({"role": "user", "content": next_turn})
                    recorder.write({"event": "user_turn", "turn": turn, "content": next_turn})
                    continue
                status, detail = "completed", "conversation ended"
                break
            status, detail = "protocol_error", f"unrecognized stop_reason {stop!r}"
            break
    finally:
        summary = {
            "name": spec["name"],
            "provider": provider,
            "model": spec["model"],
            "mock": transport.mock is not None,
            "spec_sha256": spec_digest,
            "status": status,
            "detail": detail,
            "turns": turn,
            "requests": transport.requests_made,
            "usage": usage_total,
            "estimated_usd": estimate_usd(spec, usage_total),
            "latency_ms_total": round(latency_total, 1),
            "tool_calls": tool_counts,
            "tool_sequence": tool_sequence,
            "missing_stubs": sorted(missing_stubs),
            "unused_user_turns": pending_user_turns,
            "final_text": final_text,
            "finished_at": now_iso(),
            "transcript": str(out / "transcript.jsonl"),
        }
        summary = json.loads(transport.redact(json.dumps(summary, ensure_ascii=False)))
        recorder.write({"event": "run_end", **{k: v for k, v in summary.items() if k != "transcript"}})
        recorder.close()
        (out / "summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return summary


def load_mock(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchError("invalid_mock", f"cannot load mock file: {exc}") from exc
    if isinstance(data, dict) and isinstance(data.get("responses"), list):
        data = data["responses"]
    if not isinstance(data, list) or not data or not all(isinstance(item, dict) for item in data):
        raise BenchError("invalid_mock", "mock file must be a non-empty list of response objects")
    return data


# --------------------------------------------------------------------------- compare


def load_summary(path: Path) -> dict[str, Any]:
    candidate = path / "summary.json" if path.is_dir() else path
    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchError("invalid_summary", f"cannot load summary {candidate}: {exc}") from exc
    if not isinstance(data, dict) or "status" not in data or "usage" not in data:
        raise BenchError("invalid_summary", f"{candidate} is not an api-bench summary")
    return data


def compare_summaries(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    def total(summary: dict[str, Any]) -> int:
        return int(summary["usage"].get("input_tokens", 0)) + int(summary["usage"].get("output_tokens", 0))

    rows = []
    for label, getter in (
        ("status", lambda s: s.get("status")),
        ("model", lambda s: s.get("model")),
        ("mock", lambda s: s.get("mock")),
        ("turns", lambda s: s.get("turns")),
        ("requests", lambda s: s.get("requests")),
        ("input_tokens", lambda s: s["usage"].get("input_tokens")),
        ("output_tokens", lambda s: s["usage"].get("output_tokens")),
        ("total_tokens", total),
        ("cache_read_input_tokens", lambda s: s["usage"].get("cache_read_input_tokens")),
        ("estimated_usd", lambda s: s.get("estimated_usd")),
        ("tool_sequence", lambda s: s.get("tool_sequence")),
        ("missing_stubs", lambda s: s.get("missing_stubs")),
    ):
        a, b = getter(left), getter(right)
        rows.append({"metric": label, "a": a, "b": b, "same": a == b})
    return {
        "a": left.get("name"), "b": right.get("name"), "rows": rows,
        "final_text_a": left.get("final_text", ""), "final_text_b": right.get("final_text", ""),
        "final_text_same": left.get("final_text", "") == right.get("final_text", ""),
    }


def render_compare(report: dict[str, Any]) -> str:
    lines = [f"api-bench compare: a={report['a']!r} b={report['b']!r}", ""]
    lines.append(f"{'metric':<26}{'a':<34}{'b':<34}same")
    for row in report["rows"]:
        a = json.dumps(row["a"], ensure_ascii=False)
        b = json.dumps(row["b"], ensure_ascii=False)
        lines.append(f"{row['metric']:<26}{a[:32]:<34}{b[:32]:<34}{'yes' if row['same'] else 'NO'}")
    lines.append("")
    lines.append(f"final text identical: {'yes' if report['final_text_same'] else 'no'}")
    return "\n".join(lines)


# ------------------------------------------------------------------------------ CLI


def cmd_validate(args: argparse.Namespace) -> int:
    spec, digest = load_spec(args.spec)
    report = {
        "status": "ok",
        "name": spec["name"],
        "provider": spec["provider"],
        "model": spec["model"],
        "endpoint": Transport(spec, credential=None, timeout=1).endpoint(),
        "spec_sha256": digest,
        "tools": [tool["name"] for tool in spec["tools"]],
        "stubbed_tools": sorted(name for name in spec["tool_results"] if name != "*"),
        "unstubbed_tools": sorted(
            tool["name"] for tool in spec["tools"]
            if tool["name"] not in spec["tool_results"] and "*" not in spec["tool_results"]
        ),
        "seed_messages": len(spec["messages"]),
        "scripted_user_turns": len(spec["user_turns"]),
        "max_turns": spec["max_turns"],
        "budget": spec["budget"],
        "pricing": spec.get("pricing"),
        "credential_source": _credential_source(spec, dict(os.environ)),
    }
    print(json.dumps(report, indent=2))
    return 0


def _credential_source(spec: dict[str, Any], environ: dict[str, str]) -> str:
    try:
        scheme, _ = resolve_credential(spec, environ)
    except BenchError:
        return "none (live runs need a credential; --mock does not)"
    if spec.get("api_key_env"):
        return f"{spec['api_key_env']} ({scheme})"
    if spec["provider"] == "anthropic":
        return "ANTHROPIC_API_KEY" if scheme == "api-key" else "ANTHROPIC_AUTH_TOKEN"
    return "OPENAI_API_KEY"


def cmd_run(args: argparse.Namespace) -> int:
    spec, digest = load_spec(args.spec)
    if args.max_turns is not None:
        _require(1 <= args.max_turns <= HARD_MAX_TURNS, f"--max-turns must be from 1 to {HARD_MAX_TURNS}")
        spec["max_turns"] = min(spec["max_turns"], args.max_turns)
    if args.max_requests is not None:
        _require(1 <= args.max_requests <= 500, "--max-requests must be from 1 to 500")
        spec["budget"] = dict(spec["budget"], max_requests=min(spec["budget"]["max_requests"], args.max_requests))
    timeout = args.timeout_seconds
    _require(1 <= timeout <= MAX_TIMEOUT_SECONDS, f"--timeout-seconds must be from 1 to {MAX_TIMEOUT_SECONDS}")
    mock = load_mock(args.mock) if args.mock else None
    credential = None
    if mock is None:
        confirm_credential_env(spec, args.credential_env)
        credential = resolve_credential(spec, dict(os.environ))
    out = prepare_out_dir(args.out, args.force)
    transport = Transport(spec, credential=credential, timeout=timeout, mock=mock)
    summary = run_bench(spec, digest, out, transport=transport)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["status"] == "completed" else 2


def cmd_compare(args: argparse.Namespace) -> int:
    report = compare_summaries(load_summary(args.a), load_summary(args.b))
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render_compare(report))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="check a spec without any network access")
    validate.add_argument("--spec", type=Path, required=True)
    validate.set_defaults(func=cmd_validate)

    run = sub.add_parser("run", help="run the bounded loop and record a transcript")
    run.add_argument("--spec", type=Path, required=True)
    run.add_argument("--out", type=Path, required=True, help="fresh output directory for transcript.jsonl and summary.json")
    run.add_argument("--mock", type=Path, help="canned provider responses; no network, no credential")
    run.add_argument("--max-turns", type=int)
    run.add_argument("--max-requests", type=int)
    run.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    run.add_argument(
        "--credential-env",
        help="repeat the spec's non-default api_key_env to confirm that variable may be sent to base_url",
    )
    run.add_argument("--force", action="store_true", help="allow writing into a non-empty output directory")
    run.set_defaults(func=cmd_run)

    compare = sub.add_parser("compare", help="compare two run summaries")
    compare.add_argument("--a", type=Path, required=True)
    compare.add_argument("--b", type=Path, required=True)
    compare.add_argument("--json", action="store_true")
    compare.set_defaults(func=cmd_compare)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except BenchError as exc:
        print(json.dumps({"status": exc.status, "message": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
