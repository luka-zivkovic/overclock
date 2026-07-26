#!/usr/bin/env python3
"""Build fail-closed Claude Code sandbox settings for live eval sessions."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from pathlib import Path

MINIMUM_CLAUDE_VERSION = (2, 1, 145)


def parse_version(value: str) -> tuple[int, int, int]:
    match = re.match(r"\s*(\d+)\.(\d+)\.(\d+)(?:\D|$)", value)
    if match is None:
        raise ValueError("could not parse Claude Code version")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def require_supported_version(value: str) -> None:
    observed = parse_version(value)
    if observed < MINIMUM_CLAUDE_VERSION:
        required = ".".join(str(part) for part in MINIMUM_CLAUDE_VERSION)
        raise ValueError(
            f"live evals require Claude Code {required}+ for fail-closed sandboxing"
        )


def _absolute(path: Path) -> str:
    return os.path.abspath(os.fspath(path.expanduser()))


def _minimal_roots(paths: list[str]) -> list[str]:
    """Drop roots already covered by a broader denied ancestor."""
    roots: list[str] = []
    for path in sorted(dict.fromkeys(paths), key=lambda item: (len(Path(item).parts), item)):
        covered = False
        for root in roots:
            try:
                covered = os.path.commonpath([root, path]) == root
            except ValueError:
                covered = False
            if covered:
                break
        if covered:
            continue
        roots.append(path)
    return roots


def build_settings(
    *,
    work: Path,
    plugin_root: Path,
    runtime_root: Path,
    tool_root: Path,
    repository: Path,
    auth_root: Path,
    api_key_helper: str,
) -> dict:
    allowed = [
        _absolute(work),
        _absolute(plugin_root),
        _absolute(runtime_root),
        _absolute(tool_root),
    ]
    if sys.platform == "darwin":
        # /home is an autofs mount point on macOS; denying it deadlocks Claude
        # Code 2.1.220's Bash dispatcher. Linux-only roots also inflate the
        # generated Seatbelt profile enough to exceed macOS ARG_MAX.
        system_roots = ["/private/etc", "/private/var/db", "/private/var/root", "/dev"]
    else:
        system_roots = [
            "/etc",
            "/private/etc",
            "/private/var/db",
            "/private/var/root",
            "/root",
            "/home",
            "/proc",
            "/sys",
            "/dev",
            "/run",
        ]
    sensitive = _minimal_roots(
        [
            _absolute(repository),
            _absolute(auth_root),
            _absolute(Path.home()),
            *system_roots,
        ]
    )
    deny_rules = ["WebFetch", "WebSearch"]
    # Claude Code applies Read(path) denies to all file-reading tools. Emitting
    # duplicate Glob/Grep rules is both ineffective and, on macOS 2.1.220,
    # inflates the Bash sandbox profile beyond ARG_MAX.
    deny_rules.extend(f"Read({root}/**)" for root in sensitive)
    deny_rules.extend(
        [
            "Bash(gh *)",
            "Bash(curl *)",
            "Bash(wget *)",
            "Bash(ssh *)",
            "Bash(scp *)",
        ]
    )
    return {
        "apiKeyHelper": api_key_helper,
        "permissions": {"deny": deny_rules},
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "autoAllowBashIfSandboxed": False,
            "allowUnsandboxedCommands": False,
            "excludedCommands": [],
            "filesystem": {
                "allowRead": allowed,
                "allowWrite": [_absolute(work), _absolute(runtime_root)],
                "denyRead": sensitive,
                "denyWrite": sensitive,
            },
            "network": {
                "allowedDomains": [],
                "deniedDomains": ["*"],
                "allowAllUnixSockets": False,
                "allowLocalBinding": False,
            },
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    version = subparsers.add_parser("check-version")
    version.add_argument("value")
    settings = subparsers.add_parser("settings")
    for name in (
        "work",
        "plugin-root",
        "runtime-root",
        "tool-root",
        "repository",
        "auth-root",
    ):
        settings.add_argument(f"--{name}", required=True, type=Path)
    settings.add_argument("--key-file", required=True, type=Path)
    settings.add_argument("--key-reader", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "check-version":
            require_supported_version(args.value)
            return 0
        helper = shlex.join(
            [
                sys.executable,
                _absolute(args.key_reader),
                _absolute(args.key_file),
            ]
        )
        result = build_settings(
            work=args.work,
            plugin_root=args.plugin_root,
            runtime_root=args.runtime_root,
            tool_root=args.tool_root,
            repository=args.repository,
            auth_root=args.auth_root,
            api_key_helper=helper,
        )
        print(json.dumps(result, sort_keys=True))
    except ValueError as exc:
        print(f"unsafe eval sandbox configuration: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
