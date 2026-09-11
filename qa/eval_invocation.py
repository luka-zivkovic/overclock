#!/usr/bin/env python3
"""Build and verify target activation and continuation evidence for behavioral evals."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path


EXPLICIT_INVOCATION = "explicit"
SAFE_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")


def _safe_name(value: str, label: str) -> str:
    if not isinstance(value, str) or SAFE_NAME.fullmatch(value) is None:
        raise ValueError(f"unsafe {label}: {value!r}")
    return value


def command_name(plugin: str, skill: str) -> str:
    """Return Claude Code's namespaced command for one plugin skill."""
    return f"{_safe_name(plugin, 'plugin')}:{_safe_name(skill, 'skill')}"


def explicit_prompt(plugin: str, skill: str, prompt: str) -> str:
    """Invoke the target directly, preserving an already explicit prompt."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("behavioral eval prompt must be non-empty")
    prefix = f"/{command_name(plugin, skill)}"
    if prompt == prefix or prompt.startswith(prefix + " ") or prompt.startswith(
        prefix + "\n"
    ):
        return prompt
    return f"{prefix} {prompt}"


def _skill_selection(block: dict) -> str | None:
    if block.get("name") != "Skill":
        return None
    value = block.get("input", {})
    if not isinstance(value, dict):
        return None
    for key in ("skill", "command", "name"):
        selected = value.get(key)
        if isinstance(selected, str) and selected:
            return selected.removeprefix("/")
    return None


def setup_turn_record(stdout_jsonl: Path, prompt: str) -> tuple[dict, str]:
    """Retain setup actions and results so the judge can assess the whole conversation."""
    result = None
    tool_events: list[dict] = []
    for line in stdout_jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("type") == "result":
            result = event
        elif event.get("type") in {"assistant", "user"}:
            tool_events.extend(
                block for block in event.get("message", {}).get("content", [])
                if isinstance(block, dict) and block.get("type") in {"tool_use", "tool_result"}
            )
    if result is None or result.get("is_error") or result.get("subtype") != "success":
        raise ValueError("setup turn did not complete successfully")
    context = (
        f"USER:\n{prompt}\n\nSETUP TOOL EVENTS:\n{json.dumps(tool_events)}\n\n"
        f"ASSISTANT:\n{result.get('result', '')}\n"
    )
    return result, context


def record_setup_failure(out: Path, variant: str, turn: int, exit_status: int) -> None:
    """Keep a failed cell visible without fabricating a model grade or losing later cells."""
    failure = {"mode": "setup", "verified": False, "setup_turn": turn,
               "exit_status": exit_status, "error": "setup_failed"}
    (out / "invocation.json").write_text(json.dumps(failure, indent=1) + "\n")
    results = []
    for stream in sorted(out.glob("setup-*.jsonl")):
        result = None
        for line in stream.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue  # Accounting only; malformed evidence still fails setup validation.
            if isinstance(event, dict) and event.get("type") == "result":
                result = event
        if result is not None:
            results.append(result)
    metrics = {"variant": variant, "infrastructure_error": "setup_failed"}
    def number(value: object) -> int | float:
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else 0
    for field in ("total_cost_usd", "duration_ms", "num_turns"):
        metrics[field] = sum(number(result.get(field)) for result in results)
    for field in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
        metrics[field] = sum(number(result["usage"].get(field)) for result in results
                             if isinstance(result.get("usage"), dict))
    (out / "metrics.json").write_text(json.dumps(metrics, indent=1) + "\n")


def invocation_evidence(
    stdout_jsonl: Path,
    *,
    plugin: str,
    skill: str,
    effective_prompt: str,
    setup_prompt: str | None = None,
    setup_result: dict | None = None,
) -> dict:
    """Verify direct activation, or continuity from its successful isolated setup turn."""
    command = command_name(plugin, skill)
    prefix = f"/{command}"
    requested_directly = (
        effective_prompt == prefix
        or effective_prompt.startswith(prefix + " ")
        or effective_prompt.startswith(prefix + "\n")
    )
    slash_commands: set[str] = set()
    listed_skills: set[str] = set()
    loaded_plugins: set[str] = set()
    skill_tool_calls: list[str] = []
    api_key_sources: set[str] = set()
    session_ids: set[str] = set()
    init_events = 0

    for raw_line in stdout_jsonl.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            init_events += 1
            if isinstance(event.get("session_id"), str):
                session_ids.add(event["session_id"])
            if isinstance(event.get("apiKeySource"), str):
                api_key_sources.add(event["apiKeySource"])
            slash_commands.update(
                item
                for item in event.get("slash_commands", [])
                if isinstance(item, str)
            )
            listed_skills.update(
                item for item in event.get("skills", []) if isinstance(item, str)
            )
            for item in event.get("plugins", []):
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    loaded_plugins.add(item["name"])
        if event.get("type") != "assistant":
            continue
        for block in event.get("message", {}).get("content", []):
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            selected = _skill_selection(block)
            if selected is not None:
                skill_tool_calls.append(selected)

    command_available = command in slash_commands
    target_plugin_loaded = plugin in loaded_plugins
    isolated_auth = api_key_sources == {"apiKeyHelper"}
    continued_activation = bool(
        isinstance(setup_prompt, str)
        and (setup_prompt == prefix or setup_prompt.startswith(prefix + " ") or setup_prompt.startswith(prefix + "\n"))
        and isinstance(setup_result, dict)
        and setup_result.get("type") == "result"
        and setup_result.get("subtype") == "success"
        and setup_result.get("is_error") is not True
        and isinstance(setup_result.get("session_id"), str)
        and session_ids == {setup_result["session_id"]}
    )
    verified = (
        (continued_activation if setup_prompt is not None else requested_directly)
        and command_available
        and target_plugin_loaded
        and isolated_auth
    )
    return {
        "mode": "continuation" if setup_prompt is not None else EXPLICIT_INVOCATION,
        "mechanism": "resumed-explicit-activation" if setup_prompt is not None else "direct-namespaced-command",
        "continued_activation": continued_activation,
        "requested_command": command,
        "requested_directly": requested_directly,
        "command_available": command_available,
        "target_listed_as_skill": command in listed_skills,
        "target_plugin_loaded": target_plugin_loaded,
        "api_key_sources": sorted(api_key_sources),
        "isolated_auth": isolated_auth,
        "init_events": init_events,
        "skill_tool_calls": skill_tool_calls,
        "verified": verified,
    }
