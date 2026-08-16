#!/usr/bin/env python3
"""Bind live-eval artifacts to one paired run and exact suite/plugin sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any

from eval_packaging import materialize_installation, source_plugins_for_mode

PAIR_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
PLUGIN_RE = re.compile(r"[a-z0-9][a-z0-9-]*")


def _hash_parts(parts: list[bytes]) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)
    return digest.hexdigest()


def case_hash(case: object) -> str:
    encoded = json.dumps(
        case,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def tree_hash(root: Path) -> str:
    """Hash a no-follow regular-file tree including relative modes."""
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"source tree is missing or linked: {root}")
    parts: list[bytes] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        details = path.lstat()
        if stat.S_ISLNK(details.st_mode):
            raise ValueError(f"source tree contains a symlink: {relative}")
        if stat.S_ISDIR(details.st_mode):
            continue
        if not stat.S_ISREG(details.st_mode):
            raise ValueError(f"source tree contains a special file: {relative}")
        parts.extend(
            [
                relative.as_posix().encode(),
                f"{stat.S_IMODE(details.st_mode):o}".encode(),
                path.read_bytes(),
            ]
        )
    return _hash_parts(parts)


def plugin_tree_hash(plugin_root: Path, plugins: list[str]) -> str:
    parts: list[bytes] = []
    seen: set[str] = set()
    for plugin in plugins:
        if PLUGIN_RE.fullmatch(plugin) is None:
            raise ValueError(f"unsafe plugin name: {plugin!r}")
        if plugin in seen:
            continue
        seen.add(plugin)
        root = plugin_root / plugin
        manifest = root / ".claude-plugin/plugin.json"
        if not manifest.is_file() or manifest.is_symlink():
            raise ValueError(f"plugin manifest is missing or linked: {plugin}")
        parts.append(f"plugin:{plugin}".encode())
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            details = path.lstat()
            if stat.S_ISLNK(details.st_mode):
                raise ValueError(f"plugin source contains a symlink: {plugin}/{relative}")
            if stat.S_ISDIR(details.st_mode):
                continue
            if not stat.S_ISREG(details.st_mode):
                raise ValueError(
                    f"plugin source contains a special file: {plugin}/{relative}"
                )
            parts.extend(
                [
                    relative.as_posix().encode(),
                    f"{stat.S_IMODE(details.st_mode):o}".encode(),
                    path.read_bytes(),
                ]
            )
    return _hash_parts(parts)


def installation_source_hash(
    plugin_root: Path,
    *,
    plugin: str,
    skill: str,
    install_mode: str,
    case: dict[str, Any],
) -> str:
    """Hash exactly the disposable package tree the evaluated mode will load."""
    with tempfile.TemporaryDirectory(prefix="overclock-provenance.") as temp:
        destination = Path(temp) / "plugins"
        materialize_installation(
            source_plugin_root=plugin_root,
            destination_root=destination,
            target_plugin=plugin,
            target_skill=skill,
            mode=install_mode,
            config=case,
        )
        return tree_hash(destination)


def case_plugins(case: dict[str, Any], target_plugin: str) -> list[str]:
    requested = case.get("plugins") or [target_plugin]
    if not isinstance(requested, list):
        raise ValueError("case plugins must be a list")
    plugins = list(requested)
    if target_plugin not in plugins:
        plugins.insert(0, target_plugin)
    if not plugins or not all(
        isinstance(plugin, str) and PLUGIN_RE.fullmatch(plugin) for plugin in plugins
    ):
        raise ValueError("case plugins contain an unsafe name")
    return list(dict.fromkeys(plugins))


def record(
    *,
    pair_id: str,
    variant: str,
    plugin: str,
    skill: str,
    suite: Path,
    case: dict[str, Any],
    index: int,
    plugin_root: Path,
    install_mode: str,
) -> dict[str, Any]:
    if PAIR_RE.fullmatch(pair_id) is None:
        raise ValueError("unsafe eval pair id")
    if variant not in {"skill", "baseline"}:
        raise ValueError("variant must be skill or baseline")
    plugins = source_plugins_for_mode(case, plugin, install_mode)
    return {
        "schema_version": 2,
        "pair_id": pair_id,
        "variant": variant,
        "plugin": plugin,
        "skill": skill,
        "install_mode": install_mode,
        "case_index": index,
        "case_id": case.get("id", index),
        "suite_sha256": hashlib.sha256(suite.read_bytes()).hexdigest(),
        "case_sha256": case_hash(case),
        "plugins": plugins,
        "plugin_tree_sha256": installation_source_hash(
            plugin_root,
            plugin=plugin,
            skill=skill,
            install_mode=install_mode,
            case=case,
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pair-id", required=True)
    parser.add_argument("--variant", choices=("skill", "baseline"), required=True)
    parser.add_argument("--plugin", required=True)
    parser.add_argument("--skill", required=True)
    parser.add_argument("--suite", required=True, type=Path)
    parser.add_argument("--case-index", required=True, type=int)
    parser.add_argument("--plugin-root", required=True, type=Path)
    parser.add_argument(
        "--install-mode",
        choices=("skill", "plugin", "stack"),
        required=True,
    )
    args = parser.parse_args()
    data = json.loads(args.suite.read_text(encoding="utf-8"))
    cases = data.get("evals")
    if not isinstance(cases, list) or not 0 <= args.case_index < len(cases):
        raise SystemExit("invalid eval case index")
    case = cases[args.case_index]
    if not isinstance(case, dict):
        raise SystemExit("eval case must be an object")
    try:
        result = record(
            pair_id=args.pair_id,
            variant=args.variant,
            plugin=args.plugin,
            skill=args.skill,
            suite=args.suite,
            case=case,
            index=args.case_index,
            plugin_root=args.plugin_root,
            install_mode=args.install_mode,
        )
    except (OSError, ValueError) as exc:
        raise SystemExit(f"could not bind eval provenance: {exc}") from exc
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(args.output, flags, 0o600)
    try:
        encoded = (json.dumps(result, sort_keys=True, indent=1) + "\n").encode()
        view = memoryview(encoded)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
