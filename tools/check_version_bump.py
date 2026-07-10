#!/usr/bin/env python3
"""Fail if a plugin's content changed without a version bump.

Marketplace semantics make the version field the ship switch: users only
receive updates when the version string changes. A PR that edits
plugins/<name>/** but leaves the version untouched merges cleanly and ships
nothing — the worst kind of green build. This check compares the working tree
against a base ref (default origin/master) and requires, for every plugin with
content changes:

  1. plugin.json "version" differs from the base ref's version, and
  2. the marketplace.json entry for that plugin carries the same new version.

Manifest-only edits (e.g. fixing a description) also count as content changes
on purpose: they ship to users too. A plugin that was already absent from the
base marketplace may continue iterating unpublished; adding it to marketplace.json
remains the explicit publication switch.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, check=True, capture_output=True, text=True
    ).stdout


def file_at_ref(ref: str, path: str) -> str | None:
    try:
        return git("show", f"{ref}:{path}")
    except subprocess.CalledProcessError:
        return None  # file did not exist at base


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="origin/master")
    args = parser.parse_args()

    try:
        merge_base = git("merge-base", args.base, "HEAD").strip()
    except subprocess.CalledProcessError:
        print(f"WARN: cannot resolve merge-base with {args.base}; skipping check")
        return 0

    changed = git("diff", "--name-only", merge_base, "HEAD").splitlines()
    # Also include uncommitted changes so the check works locally pre-commit.
    changed += git("diff", "--name-only").splitlines()
    changed += git("ls-files", "--others", "--exclude-standard").splitlines()

    touched_plugins = sorted(
        {p.split("/")[1] for p in changed if p.startswith("plugins/") and len(p.split("/")) > 2}
    )
    if not touched_plugins:
        print("OK: no plugin content changed")
        return 0

    marketplace = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())
    entries = {e["name"]: e for e in marketplace.get("plugins", [])}
    base_marketplace_raw = file_at_ref(merge_base, ".claude-plugin/marketplace.json")
    base_marketplace = json.loads(base_marketplace_raw) if base_marketplace_raw else {"plugins": []}
    base_entries = {e["name"]: e for e in base_marketplace.get("plugins", [])}

    failures = 0
    for name in touched_plugins:
        manifest_path = f"plugins/{name}/.claude-plugin/plugin.json"
        manifest_file = REPO / manifest_path
        if not manifest_file.exists():
            print(f"ERROR: {manifest_path} missing for changed plugin {name!r}", file=sys.stderr)
            failures += 1
            continue
        new_version = json.loads(manifest_file.read_text()).get("version")
        base_raw = file_at_ref(merge_base, manifest_path)
        base_version = json.loads(base_raw).get("version") if base_raw else None

        if new_version is None:
            print(f"ERROR: {name}: plugin.json has no version field — set one; "
                  "without it every commit auto-ships", file=sys.stderr)
            failures += 1
            continue
        if base_version is not None and new_version == base_version:
            print(f"ERROR: {name}: content changed but version is still {new_version!r} "
                  f"— bump plugin.json (users receive nothing until you do)", file=sys.stderr)
            failures += 1
        entry = entries.get(name)
        if entry is None:
            if name not in base_entries:
                # The plugin was already unpublished at the base. An absent
                # marketplace entry still ships nothing, so iteration is safe.
                print(f"WARN: {name}: plugin remains unpublished (not in marketplace.json)")
            else:
                print(f"ERROR: {name}: marketplace.json entry was removed", file=sys.stderr)
                failures += 1
        elif entry.get("version") != new_version:
            print(f"ERROR: {name}: marketplace.json entry version {entry.get('version')!r} "
                  f"!= plugin.json version {new_version!r}", file=sys.stderr)
            failures += 1

    if failures:
        return 1
    for name in touched_plugins:
        print(f"OK: {name} changed and version bumped consistently")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
