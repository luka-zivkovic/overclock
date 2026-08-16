#!/usr/bin/env python3
"""Validate the Overclock setup catalog against marketplace publication state."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CATALOG = REPO / "plugins/overclock-setup/skills/setup/references/capabilities.json"
MARKETPLACE = REPO / ".claude-plugin/marketplace.json"
ALLOWED_STATUS = {"published", "preview"}


def validate(
    catalog: dict,
    marketplace: dict,
    manifests: dict[str, dict] | None = None,
    shipped_skills: dict[str, set[str]] | None = None,
) -> list[str]:
    errors: list[str] = []
    if catalog.get("schema_version") != 1:
        errors.append("catalog schema_version must be 1")
    packages = catalog.get("packages")
    if not isinstance(packages, list):
        return errors + ["catalog packages must be an array"]

    by_id: dict[str, dict] = {}
    for index, package in enumerate(packages):
        if not isinstance(package, dict) or not isinstance(package.get("id"), str):
            errors.append(f"packages[{index}] must be an object with a string id")
            continue
        package_id = package["id"]
        if package_id in by_id:
            errors.append(f"duplicate catalog package: {package_id}")
        by_id[package_id] = package
        if package.get("publication_status") not in ALLOWED_STATUS:
            errors.append(f"{package_id}: invalid publication_status")
        for field in (
            "provides",
            "skill_names",
            "depends_on",
            "conflicts_with",
            "hooks",
            "persistent_files",
        ):
            if not isinstance(package.get(field), list):
                errors.append(f"{package_id}: {field} must be an array")

    marketplace_entries = {
        entry.get("name"): entry
        for entry in marketplace.get("plugins", [])
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }
    published = {
        package_id
        for package_id, package in by_id.items()
        if package.get("publication_status") == "published"
    }
    marketplace_ids = set(marketplace_entries)
    for missing in sorted(marketplace_ids - published):
        errors.append(f"{missing}: marketplace entry is not cataloged as published")
    for missing in sorted(published - marketplace_ids):
        errors.append(f"{missing}: catalog says published but marketplace entry is missing")

    for package_id, package in by_id.items():
        entry = marketplace_entries.get(package_id)
        if entry and entry.get("version") != package.get("version"):
            errors.append(
                f"{package_id}: catalog version {package.get('version')!r} != "
                f"marketplace version {entry.get('version')!r}"
            )
        if manifests is not None:
            manifest = manifests.get(package_id)
            if manifest is None:
                errors.append(f"{package_id}: plugin manifest is missing")
            else:
                if manifest.get("name") != package_id:
                    errors.append(
                        f"{package_id}: manifest name {manifest.get('name')!r} does not match"
                    )
                if manifest.get("version") != package.get("version"):
                    errors.append(
                        f"{package_id}: catalog version {package.get('version')!r} != "
                        f"manifest version {manifest.get('version')!r}"
                    )
        if shipped_skills is not None:
            declared = package.get("skill_names")
            if isinstance(declared, list):
                declared_set = {
                    name for name in declared if isinstance(name, str)
                }
                actual = shipped_skills.get(package_id, set())
                if declared_set != actual:
                    errors.append(
                        f"{package_id}: catalog skill_names {sorted(declared_set)!r} != "
                        f"shipped skills {sorted(actual)!r}"
                    )
        for dependency in package.get("depends_on", []):
            if dependency not in by_id:
                errors.append(f"{package_id}: unknown dependency {dependency!r}")
        for conflict in package.get("conflicts_with", []):
            if conflict == package_id:
                errors.append(f"{package_id}: package cannot conflict with itself")
            elif conflict not in by_id:
                errors.append(f"{package_id}: unknown conflict {conflict!r}")
            elif package_id not in by_id[conflict].get("conflicts_with", []):
                errors.append(f"{package_id}: conflict with {conflict!r} is not symmetric")
    return errors


def main() -> int:
    try:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
        manifests: dict[str, dict] = {}
        shipped_skills: dict[str, set[str]] = {}
        for plugin_dir in (REPO / "plugins").iterdir():
            manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
            if not manifest_path.is_file():
                continue
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            plugin_id = manifest.get("name")
            if not isinstance(plugin_id, str):
                continue
            manifests[plugin_id] = manifest
            skills_dir = plugin_dir / "skills"
            shipped_skills[plugin_id] = (
                {
                    path.name
                    for path in skills_dir.iterdir()
                    if path.is_dir() and (path / "SKILL.md").is_file()
                }
                if skills_dir.is_dir()
                else set()
            )
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    errors = validate(catalog, marketplace, manifests, shipped_skills)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"OK: setup catalog covers {len(catalog['packages'])} packages and matches marketplace state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
