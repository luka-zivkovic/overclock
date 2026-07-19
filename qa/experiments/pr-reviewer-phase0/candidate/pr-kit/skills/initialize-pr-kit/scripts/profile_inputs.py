#!/usr/bin/env python3
"""Compute and verify the committed inputs that ground a PR Kit profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath


INPUT_SCHEMA_VERSION = 1
PROFILE_SCHEMA_VERSION = "2"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_TAG_RE = re.compile(r"\[source: ([^\]\r\n]+)\]")

MANIFESTS = {
    "package.json", "package-lock.json", "npm-shrinkwrap.json", "yarn.lock",
    "pnpm-lock.yaml", "pnpm-workspace.yaml", "bun.lock", "bun.lockb",
    "deno.json", "deno.jsonc", "deno.lock", "pyproject.toml", "poetry.lock",
    "requirements.txt", "pipfile", "pipfile.lock", "uv.lock", "setup.py",
    "setup.cfg", "cargo.toml", "cargo.lock", "go.mod", "go.sum", "go.work",
    "gemfile", "gemfile.lock", "composer.json", "composer.lock", "pom.xml",
    "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
    "mix.exs", "mix.lock", "pubspec.yaml", "pubspec.lock", "package.swift",
    "package.resolved", "podfile", "podfile.lock", "cmakelists.txt", "vcpkg.json",
    "terraform.lock.hcl", "nx.json", "turbo.json", "lerna.json", "rush.json",
}
ROOT_DOCS = {
    "readme.md", "architecture.md", "security.md", "contributing.md",
    "strategy.md", "concepts.md", "license", "license.md", "license.txt",
}
INSTRUCTION_DOCS = {"agents.md", "claude.md", "gemini.md", "codeowners"}
VERSION_SELECTORS = {
    ".nvmrc", ".node-version", ".python-version", ".ruby-version",
    ".java-version", ".go-version", ".terraform-version", ".tool-versions",
    "mise.toml", ".mise.toml", ".sdkmanrc",
}
TOPOLOGY_FILES = {
    "dockerfile", "containerfile", "docker-compose.yml", "docker-compose.yaml",
    "vercel.json", "netlify.toml", "fly.toml", "render.yaml", "procfile",
    "serverless.yml", "serverless.yaml", "app.yaml", "chart.yaml",
    ".gitmodules", ".gitlab-ci.yml", "jenkinsfile", "azure-pipelines.yml",
}
INPUT_PREFIXES = (
    ".github/workflows/", ".circleci/", ".cursor/rules/", ".claude/rules/",
    "infra/", "infrastructure/", "deploy/", "deployment/", "terraform/",
    "k8s/", "kubernetes/", "helm/",
)
SCHEMA_SUFFIXES = (".prisma", ".proto", ".avsc")
PROJECT_SUFFIXES = (
    ".csproj", ".fsproj", ".vbproj", ".sln", ".tf", ".tfvars",
)


def git(root: Path, *args: str, binary: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=not binary,
        check=False,
    )


def resolve_commit(root: Path, ref: str) -> str:
    result = git(root, "rev-parse", "--verify", f"{ref}^{{commit}}")
    value = result.stdout.strip() if result.returncode == 0 else ""
    if not SHA_RE.fullmatch(value):
        raise ValueError(f"invalid commit endpoint: {ref}")
    return value


def tree_entries(root: Path, ref: str) -> dict[str, tuple[str, str, str]]:
    commit = resolve_commit(root, ref)
    result = git(root, "ls-tree", "-r", "-z", commit, binary=True)
    if result.returncode != 0:
        raise ValueError("git ls-tree failed")
    entries: dict[str, tuple[str, str, str]] = {}
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            metadata, path_bytes = raw.split(b"\t", 1)
            mode, object_type, object_id = metadata.decode("ascii").split()
        except (UnicodeError, ValueError) as exc:
            raise ValueError("malformed git tree entry") from exc
        path = path_bytes.decode("utf-8", errors="surrogateescape")
        entries[path] = (mode, object_type, object_id)
    return entries


def is_profile_input(path: str, object_type: str = "blob") -> bool:
    normalized = path.replace(os.sep, "/")
    lower = normalized.lower()
    base = PurePosixPath(lower).name
    parts = PurePosixPath(lower).parts
    if object_type == "commit":
        return True
    if base in MANIFESTS or base in VERSION_SELECTORS or base in TOPOLOGY_FILES:
        return True
    if base in INSTRUCTION_DOCS or (len(parts) == 1 and base in ROOT_DOCS):
        return True
    if lower.startswith(INPUT_PREFIXES):
        return True
    wrapped = f"/{lower}"
    if "/.claude-plugin/" in wrapped or "/.codex-plugin/" in wrapped:
        return True
    if lower.startswith(".openai/"):
        return True
    if base.endswith(PROJECT_SUFFIXES) or base.endswith(SCHEMA_SUFFIXES):
        return True
    if base in {"schema.sql", "schema.rb"}:
        return True
    return any(part in {"migration", "migrations", "db", "schema", "schemas"} for part in parts)


def digest_for_ref(root: Path, ref: str) -> dict[str, object]:
    root = root.resolve(strict=True)
    commit = resolve_commit(root, ref)
    entries = tree_entries(root, commit)
    inputs = [
        (path, *metadata)
        for path, metadata in entries.items()
        if is_profile_input(path, metadata[1])
    ]
    inputs.sort(key=lambda item: item[0])
    digest = hashlib.sha256()
    digest.update(f"pr-kit-profile-inputs-v{INPUT_SCHEMA_VERSION}\0".encode())
    for path, mode, object_type, object_id in inputs:
        digest.update(path.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        digest.update(f"{mode}\0{object_type}\0{object_id}\0".encode())
    return {
        "status": "complete",
        "input_schema_version": INPUT_SCHEMA_VERSION,
        "resolved_ref": commit,
        "profile_inputs_digest": digest.hexdigest(),
        "input_count": len(inputs),
        "input_paths": [item[0] for item in inputs],
    }


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("profile frontmatter is missing")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("profile frontmatter is not closed") from exc
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        match = re.fullmatch(r"([a-z_]+):\s*(.+)", line)
        if not match:
            raise ValueError(f"invalid frontmatter line: {line!r}")
        key, value = match.groups()
        fields[key] = value.strip().strip("\"'")
    return fields


def source_paths(text: str) -> list[str]:
    paths: set[str] = set()
    for value in SOURCE_TAG_RE.findall(text):
        if re.fullmatch(r"commit [0-9a-f]{40}", value):
            continue
        if re.fullmatch(r"PR #[1-9][0-9]* @ [0-9a-f]{40}", value):
            continue
        path_value = value
        if ":" in value:
            candidate, line = value.rsplit(":", 1)
            if line.isdigit():
                path_value = candidate
        path = PurePosixPath(path_value)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise ValueError(f"invalid source path: {path_value}")
        paths.add(path.as_posix())
    return sorted(paths)


def is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    return git(root, "merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def validate_profile_content(root: Path, text: str) -> dict[str, object]:
    root = root.resolve(strict=True)
    fields = parse_frontmatter(text)
    if fields.get("schema_version") != PROFILE_SCHEMA_VERSION:
        raise ValueError(f"profile schema_version must be {PROFILE_SCHEMA_VERSION}")
    profile_base = fields.get("base_commit", "")
    stored_digest = fields.get("profile_inputs_digest", "")
    if not SHA_RE.fullmatch(profile_base):
        raise ValueError("profile base_commit is invalid")
    if not DIGEST_RE.fullmatch(stored_digest):
        raise ValueError("profile_inputs_digest is invalid")
    resolved_base = resolve_commit(root, profile_base)
    original = digest_for_ref(root, resolved_base)
    if original["profile_inputs_digest"] != stored_digest:
        raise ValueError("stored profile-input digest does not match the profile base")
    tree = tree_entries(root, resolved_base)
    missing_sources = [path for path in source_paths(text) if path not in tree]
    if missing_sources:
        raise ValueError(
            "profile cites paths absent from its base commit: " + ", ".join(missing_sources)
        )
    return {
        "fields": fields,
        "profile_base": resolved_base,
        "profile_inputs_digest": stored_digest,
        "source_paths": source_paths(text),
        "tree": tree,
    }


def check_profile(root: Path, profile: Path, review_base: str) -> dict[str, object]:
    root = root.resolve(strict=True)
    text = profile.read_text(encoding="utf-8")
    validated = validate_profile_content(root, text)
    resolved_base = str(validated["profile_base"])
    stored_digest = str(validated["profile_inputs_digest"])
    resolved_review = resolve_commit(root, review_base)
    if not is_ancestor(root, resolved_base, resolved_review):
        return {
            "status": "invalid",
            "profile_base": resolved_base,
            "review_base": resolved_review,
            "reasons": ["profile base is not an ancestor of the review base"],
            "changed_source_paths": [],
        }

    current = digest_for_ref(root, resolved_review)
    old_tree = validated["tree"]
    new_tree = tree_entries(root, resolved_review)
    changed_sources = [
        path for path in validated["source_paths"] if old_tree.get(path) != new_tree.get(path)
    ]
    reasons: list[str] = []
    if current["profile_inputs_digest"] != stored_digest:
        reasons.append("repository profile inputs changed after initialization")
    if changed_sources:
        reasons.append("one or more cited source paths changed after initialization")
    return {
        "status": "stale" if reasons else "fresh",
        "profile_base": resolved_base,
        "review_base": resolved_review,
        "stored_profile_inputs_digest": stored_digest,
        "current_profile_inputs_digest": current["profile_inputs_digest"],
        "changed_source_paths": changed_sources,
        "reasons": reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    digest_parser = subparsers.add_parser("digest")
    digest_parser.add_argument("--repo", required=True, type=Path)
    digest_parser.add_argument("--ref", default="HEAD")
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--repo", required=True, type=Path)
    check_parser.add_argument("--profile", required=True, type=Path)
    check_parser.add_argument("--review-base", required=True)
    args = parser.parse_args()
    try:
        if args.command == "digest":
            result = digest_for_ref(args.repo, args.ref)
        else:
            result = check_profile(args.repo, args.profile, args.review_base)
    except (OSError, UnicodeError, ValueError) as exc:
        result = {"status": "invalid", "reasons": [str(exc)], "changed_source_paths": []}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
