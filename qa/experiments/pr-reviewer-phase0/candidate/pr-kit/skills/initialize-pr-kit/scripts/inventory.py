#!/usr/bin/env python3
"""Emit a bounded, content-free repository inventory for PR Kit initialization."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

MAX_FILES = 20_000
MAX_PATH_LENGTH = 300
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".ai",
    ".idea",
    ".vscode",
    "_work",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
    "vendor",
}
SECRET_NAMES = {
    ".env",
    ".env.local",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
}
DOC_NAMES = {
    "AGENTS.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "README.md",
    "SECURITY.md",
}
MANIFEST_NAMES = {
    "Cargo.toml",
    "Gemfile",
    "go.mod",
    "package.json",
    "pnpm-workspace.yaml",
    "pyproject.toml",
    "requirements.txt",
}
TEST_MARKERS = {"test", "tests", "__tests__", "spec", "specs"}
SENSITIVE_MARKERS = {
    "auth",
    "credential",
    "crypto",
    "migration",
    "permission",
    "security",
    "session",
    "tenant",
}


def fail(message: str) -> "NoReturn":
    raise SystemExit(message)


def git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value or None


def sanitize_remote(value: str | None) -> str | None:
    if not value:
        return None
    if "://" in value:
        parsed = urlsplit(value)
        hostname = parsed.hostname or ""
        if parsed.port:
            hostname = f"{hostname}:{parsed.port}"
        return urlunsplit((parsed.scheme, hostname, parsed.path, "", ""))
    scp_like = re.fullmatch(r"[^@/\s]+@([^:\s]+):(.+)", value)
    if scp_like:
        return f"{scp_like.group(1)}:{scp_like.group(2)}"
    return value


def classify(rel: Path) -> set[str]:
    tags: set[str] = set()
    name = rel.name
    lower_parts = {part.lower() for part in rel.parts}
    suffix = rel.suffix.lower()
    if name in DOC_NAMES or suffix in {".md", ".mdx"}:
        tags.add("documentation")
    if name in MANIFEST_NAMES or name.endswith((".lock", ".toml", ".yaml", ".yml")):
        tags.add("manifest-or-config")
    if TEST_MARKERS & lower_parts or name.lower().startswith(("test_", "spec_")):
        tags.add("test")
    if ".github" in rel.parts and "workflows" in rel.parts:
        tags.add("ci")
    if SENSITIVE_MARKERS & lower_parts:
        tags.add("risk-surface")
    if suffix in {".sql", ".prisma"} or "migrations" in lower_parts:
        tags.add("schema-or-migration")
    return tags


def is_secret_path(rel: Path) -> bool:
    lower_name = rel.name.lower()
    if lower_name in SECRET_NAMES or lower_name.startswith(".env."):
        return True
    if lower_name.startswith(("credential.", "credentials.", "secret.", "secrets.")):
        return True
    if lower_name.endswith((".key", ".pem", ".p12", ".pfx")):
        return True
    return any(part.lower() in {"secrets", ".secrets"} for part in rel.parts)


def walk(root: Path) -> tuple[list[dict[str, object]], bool]:
    found: list[dict[str, object]] = []
    truncated = False

    def visit(directory: Path) -> None:
        nonlocal truncated
        if truncated:
            return
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except (OSError, PermissionError):
            return
        for entry in entries:
            if len(found) >= MAX_FILES:
                truncated = True
                return
            path = Path(entry.path)
            try:
                rel = path.relative_to(root)
            except ValueError:
                continue
            if len(rel.as_posix()) > MAX_PATH_LENGTH or entry.is_symlink():
                continue
            if entry.is_dir(follow_symlinks=False):
                if entry.name not in SKIP_DIRS:
                    visit(path)
                continue
            if not entry.is_file(follow_symlinks=False) or is_secret_path(rel):
                continue
            tags = classify(rel)
            if tags:
                found.append({"path": rel.as_posix(), "tags": sorted(tags)})
    visit(root)
    return found, truncated


def main() -> int:
    if len(sys.argv) != 2:
        fail("usage: inventory.py PROJECT_ROOT")
    supplied = Path(sys.argv[1])
    if supplied.is_symlink():
        fail("project root must not be a symlink")
    root = supplied.resolve(strict=True)
    if not root.is_dir():
        fail("project root is not a directory")

    files, truncated = walk(root)
    extensions = Counter(Path(item["path"]).suffix.lower() or "(none)" for item in files)
    payload = {
        "schema_version": 1,
        "root": ".",
        "head": git(root, "rev-parse", "HEAD"),
        "remote": sanitize_remote(git(root, "remote", "get-url", "origin")),
        "default_branch": git(root, "symbolic-ref", "refs/remotes/origin/HEAD"),
        "inventory_truncated": truncated,
        "classified_file_count": len(files),
        "extensions": dict(extensions.most_common(20)),
        "files": files,
        "limitations": [
            "Paths only; file contents were not read.",
            "Symlinks, secret-like paths, dependencies, generated output, and VCS metadata were skipped.",
        ],
    }
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
