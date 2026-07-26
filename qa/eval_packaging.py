#!/usr/bin/env python3
"""Build disposable skill evaluation installations with explicit isolation modes."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Mapping


INSTALL_MODES = ("skill", "plugin", "stack")
SAFE_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")


@dataclass(frozen=True)
class MaterializedInstallation:
    """The effective mode and disposable plugin directories passed to Claude."""

    mode: str
    plugin_dirs: tuple[Path, ...]
    source_plugins: tuple[str, ...]


def _safe_name(value: object, label: str) -> str:
    if not isinstance(value, str) or SAFE_NAME.fullmatch(value) is None:
        raise ValueError(f"unsafe {label}: {value!r}")
    return value


def _declared_plugins(config: Mapping[str, Any], target_plugin: str) -> list[str]:
    requested = config.get("plugins") or [target_plugin]
    if not isinstance(requested, list) or not requested:
        raise ValueError("plugins must be a non-empty list")
    plugins = [_safe_name(item, "plugin name") for item in requested]
    if target_plugin not in plugins:
        plugins.insert(0, target_plugin)
    return list(dict.fromkeys(plugins))


def _mode_list(value: object) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item in INSTALL_MODES for item in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError(
            "install_modes must be a non-empty unique list drawn from: "
            + ", ".join(INSTALL_MODES)
        )
    return list(value)


def resolve_install_modes(
    config: Mapping[str, Any],
    target_plugin: str,
    *,
    suite: Mapping[str, Any] | None = None,
    override: str | None = None,
) -> list[str]:
    """Resolve override > case matrix > suite matrix, preserving old defaults."""
    if override is not None:
        if override not in INSTALL_MODES:
            raise ValueError(
                "install mode override must be one of: " + ", ".join(INSTALL_MODES)
            )
        return [override]
    if "install_modes" in config:
        return _mode_list(config["install_modes"])
    if suite is not None and "install_modes" in suite:
        return _mode_list(suite["install_modes"])
    historical = (
        "stack"
        if len(_declared_plugins(config, target_plugin)) > 1
        else "plugin"
    )
    return [historical]


def source_plugins_for_mode(
    config: Mapping[str, Any],
    target_plugin: str,
    mode: str,
) -> list[str]:
    """Return source distributions whose content is installed for ``mode``."""
    _safe_name(target_plugin, "target plugin")
    if mode not in INSTALL_MODES:
        raise ValueError("unknown install mode")
    if mode in {"skill", "plugin"}:
        return [target_plugin]
    return _declared_plugins(config, target_plugin)


def first_symlink(root: Path) -> Path | None:
    """Return the first symlink beneath ``root`` without following directory links."""
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in [*directories, *files]:
            candidate = current_path / name
            if candidate.is_symlink():
                return candidate
    return None


def _skill_description(skill_md: Path) -> str:
    text = skill_md.read_text(encoding="utf-8")
    match = re.search(r"(?m)^description:\s*(.+?)\s*$", text)
    if match is None:
        raise ValueError(f"{skill_md} needs a one-line description")
    raw = match.group(1)
    if raw.startswith('"'):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{skill_md} has an invalid quoted description") from exc
    else:
        value = raw.strip("'")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{skill_md} needs a non-empty description")
    return value


def _materialize_skill_only(
    source_plugin: Path,
    destination_plugin: Path,
    target_plugin: str,
    target_skill: str,
) -> None:
    source_manifest = source_plugin / ".claude-plugin" / "plugin.json"
    source_skill = source_plugin / "skills" / target_skill
    skill_md = source_skill / "SKILL.md"
    if (
        source_plugin.is_symlink()
        or source_skill.is_symlink()
        or not source_manifest.is_file()
        or source_manifest.is_symlink()
        or not skill_md.is_file()
        or skill_md.is_symlink()
    ):
        raise ValueError(
            f"target skill or plugin manifest is missing or linked: "
            f"{target_plugin}/{target_skill}"
        )
    linked_entry = first_symlink(source_skill)
    if linked_entry is not None:
        raise ValueError(f"refusing symlinked skill source: {linked_entry}")
    try:
        manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid plugin manifest: {source_manifest}") from exc
    version = manifest.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError(f"plugin manifest has no version: {source_manifest}")

    (destination_plugin / ".claude-plugin").mkdir(parents=True)
    shutil.copytree(source_skill, destination_plugin / "skills" / target_skill)
    isolated_manifest = {
        "name": target_plugin,
        "displayName": target_skill,
        "description": _skill_description(skill_md),
        "version": version,
    }
    (destination_plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(isolated_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (destination_plugin / ".claude-plugin" / "plugin.json").chmod(0o644)


def materialize_installation(
    *,
    source_plugin_root: Path,
    destination_root: Path,
    target_plugin: str,
    target_skill: str,
    mode: str,
    config: Mapping[str, Any],
) -> MaterializedInstallation:
    """Copy exactly the sources allowed by one evaluation install mode."""
    target_plugin = _safe_name(target_plugin, "target plugin")
    target_skill = _safe_name(target_skill, "target skill")
    if mode not in INSTALL_MODES:
        raise ValueError("unknown install mode")
    if destination_root.exists() and any(destination_root.iterdir()):
        raise ValueError("destination plugin root must be empty")
    destination_root.mkdir(parents=True, exist_ok=True)

    source_plugins = source_plugins_for_mode(config, target_plugin, mode)
    destinations: list[Path] = []
    for plugin_name in source_plugins:
        source = source_plugin_root / plugin_name
        manifest = source / ".claude-plugin" / "plugin.json"
        if source.is_symlink() or not manifest.is_file() or manifest.is_symlink():
            raise ValueError(f"plugin not found or manifest is linked: {source}")
        destination = destination_root / plugin_name
        if mode == "skill":
            _materialize_skill_only(
                source,
                destination,
                target_plugin,
                target_skill,
            )
        else:
            linked_entry = first_symlink(source)
            if linked_entry is not None:
                raise ValueError(f"refusing symlinked plugin source: {linked_entry}")
            shutil.copytree(source, destination)
        destinations.append(destination)

    return MaterializedInstallation(
        mode=mode,
        plugin_dirs=tuple(destinations),
        source_plugins=tuple(source_plugins),
    )
