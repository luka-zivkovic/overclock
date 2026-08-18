#!/usr/bin/env python3
"""Build and verify explicit target-skill prompts for behavioral evals."""

from __future__ import annotations

import json
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


def invocation_evidence(
    stdout_jsonl: Path,
    *,
    plugin: str,
    skill: str,
    effective_prompt: str,
) -> dict:
    """Verify that a direct target command was available in the isolated run."""
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
    init_events = 0

    for raw_line in stdout_jsonl.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            init_events += 1
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
    verified = (
        requested_directly
        and command_available
        and target_plugin_loaded
        and isolated_auth
    )
    return {
        "mode": EXPLICIT_INVOCATION,
        "mechanism": "direct-namespaced-command",
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
