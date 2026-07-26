#!/usr/bin/env python3
"""Common unsealed PR-feedback plan contract carried by each standalone skill."""
from __future__ import annotations

import re
from typing import Any

SCHEMA_VERSION = 1
MAX_ACTIONS = 100
MAX_REPLY_BYTES = 20 * 1024
OID_RE = re.compile(r"[0-9a-f]{40}")
HOST_RE = re.compile(r"[A-Za-z0-9.-]+")
NAME_RE = re.compile(r"[A-Za-z0-9_.-]+")
NODE_RE = re.compile(r"[A-Za-z0-9_=-]+")
ACTION_RE = re.compile(r"[A-Za-z0-9_.:-]+")
SURFACES = {"review-thread", "pr-comment", "review-body"}
VERDICTS = {
    "fixed",
    "fixed-differently",
    "replied",
    "not-addressing",
    "declined",
    "needs-human",
}
TOP_LEVEL_FIELDS = {
    "schema_version",
    "host",
    "owner",
    "repo",
    "pr_number",
    "pr_node_id",
    "head_oid",
    "actions",
}
ACTION_FIELDS = {
    "action_id",
    "surface",
    "source_id",
    "thread_id",
    "verdict",
    "reply_body",
    "resolve",
}


def need_string(
    value: object,
    field: str,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise ValueError(f"{field} has an invalid format")
    return value


def validate_draft_plan(data: object) -> dict[str, Any]:
    """Validate the exact unsealed schema shared by preparation and publication."""
    if not isinstance(data, dict):
        raise ValueError("plan must be a JSON object")
    unknown = set(data) - TOP_LEVEL_FIELDS
    missing = TOP_LEVEL_FIELDS - set(data)
    if unknown:
        raise ValueError(f"unknown top-level fields: {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"missing top-level fields: {', '.join(sorted(missing))}")
    if data["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    need_string(data["host"], "host", HOST_RE)
    need_string(data["owner"], "owner", NAME_RE)
    need_string(data["repo"], "repo", NAME_RE)
    if not isinstance(data["pr_number"], int) or isinstance(data["pr_number"], bool):
        raise ValueError("pr_number must be an integer")
    if data["pr_number"] < 1:
        raise ValueError("pr_number must be positive")
    need_string(data["pr_node_id"], "pr_node_id", NODE_RE)
    need_string(data["head_oid"], "head_oid", OID_RE)

    actions = data["actions"]
    if not isinstance(actions, list) or not actions:
        raise ValueError("actions must be a non-empty list")
    if len(actions) > MAX_ACTIONS:
        raise ValueError(f"actions may contain at most {MAX_ACTIONS} items")
    action_ids: set[str] = set()
    source_ids: set[str] = set()
    thread_ids: set[str] = set()
    for index, action in enumerate(actions):
        label = f"actions[{index}]"
        if not isinstance(action, dict):
            raise ValueError(f"{label} must be an object")
        unknown_action = set(action) - ACTION_FIELDS
        required = ACTION_FIELDS - {"thread_id"}
        missing_action = required - set(action)
        if unknown_action:
            raise ValueError(
                f"{label} has unknown fields: {', '.join(sorted(unknown_action))}"
            )
        if missing_action:
            raise ValueError(
                f"{label} is missing fields: {', '.join(sorted(missing_action))}"
            )
        action_id = need_string(action["action_id"], f"{label}.action_id", ACTION_RE)
        if action_id in action_ids:
            raise ValueError(f"duplicate action_id: {action_id}")
        action_ids.add(action_id)
        surface = need_string(action["surface"], f"{label}.surface")
        if surface not in SURFACES:
            raise ValueError(f"{label}.surface is invalid")
        source_id = need_string(action["source_id"], f"{label}.source_id", NODE_RE)
        if source_id in source_ids:
            raise ValueError(f"duplicate source_id: {source_id}")
        source_ids.add(source_id)
        verdict = need_string(action["verdict"], f"{label}.verdict")
        if verdict not in VERDICTS:
            raise ValueError(f"{label}.verdict is invalid")
        body = need_string(action["reply_body"], f"{label}.reply_body")
        if len(body.encode("utf-8")) > MAX_REPLY_BYTES:
            raise ValueError(f"{label}.reply_body exceeds {MAX_REPLY_BYTES} bytes")
        if "<!-- overclock-pr-feedback:" in body:
            raise ValueError(f"{label}.reply_body contains a reserved idempotency marker")
        if not isinstance(action["resolve"], bool):
            raise ValueError(f"{label}.resolve must be boolean")
        if surface == "review-thread":
            if "thread_id" not in action:
                raise ValueError(f"{label}.thread_id is required for review-thread")
            thread_id = need_string(action["thread_id"], f"{label}.thread_id", NODE_RE)
            if thread_id in thread_ids:
                raise ValueError(f"duplicate thread_id: {thread_id}")
            thread_ids.add(thread_id)
        elif "thread_id" in action:
            raise ValueError(f"{label}.thread_id is only valid for review-thread")
        if action["resolve"] and surface != "review-thread":
            raise ValueError(f"{label} cannot resolve a non-thread surface")
        if action["resolve"] and verdict == "needs-human":
            raise ValueError(f"{label} cannot resolve needs-human feedback")
    return data
