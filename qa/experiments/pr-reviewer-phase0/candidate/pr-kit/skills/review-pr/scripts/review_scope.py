#!/usr/bin/env python3
"""Derive fail-closed, deterministic risk signals for a pinned PR diff."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path, PurePosixPath


CODE_EXTENSIONS = {
    ".c", ".cc", ".cpp", ".cs", ".ex", ".exs", ".go", ".java", ".js",
    ".jsx", ".kt", ".php", ".py", ".rb", ".rs", ".scala", ".swift",
    ".ts", ".tsx", ".vue", ".svelte",
}
MANIFESTS = {
    "package.json", "package-lock.json", "npm-shrinkwrap.json", "yarn.lock",
    "pnpm-lock.yaml", "bun.lock", "bun.lockb", "pyproject.toml", "poetry.lock",
    "requirements.txt", "uv.lock", "cargo.toml", "cargo.lock", "go.mod", "go.sum",
    "gemfile", "gemfile.lock", "composer.json", "composer.lock", "pom.xml",
    "build.gradle", "build.gradle.kts", "mix.exs", "mix.lock",
}
BASE_LENSES = {"correctness", "failure-handling", "regression-coverage"}
ALL_LENSES = {
    *BASE_LENSES,
    "api-contract", "compatibility", "concurrency", "data-integrity",
    "maintainability", "migration", "observability", "security",
    "silent-pass-verification",
}
SILENT_PASS_CONTENT = re.compile(
    r"continue-on-error\s*:\s*true|allow_failure\s*:\s*true|\|\|\s*true\b|"
    r"\bset\s+\+e\b|\bexit\s+0\b|--passWithNoTests\b|--allow-empty\b",
    re.I,
)


def git(root: Path, *args: str, binary: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=not binary,
        check=False,
    )


def resolve_commit(root: Path, ref: str) -> str | None:
    result = git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    value = result.stdout.strip() if result.returncode == 0 else ""
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else None


def unique_merge_base(root: Path, base: str, head: str) -> str | None:
    result = git(root, "merge-base", "--all", base, head)
    values = [line for line in result.stdout.splitlines() if line]
    if result.returncode != 0 or len(values) != 1:
        return None
    return values[0]


def unknown(reason: str) -> dict[str, object]:
    return {
        "status": "unknown",
        "reason": reason,
        "merge_base": None,
        "changed_file_count": None,
        "changed_files": [],
        "executable_lines": None,
        "uncounted_files": None,
        "risk_signals": ["scope-unknown"],
        "activated_lenses": sorted(ALL_LENSES),
        "silent_pass_verification": True,
    }


def silent_pass_path(path: str) -> bool:
    lower = path.lower()
    base = PurePosixPath(lower).name
    parts = PurePosixPath(lower).parts
    if lower.startswith((".github/workflows/", ".circleci/")):
        return True
    if base in {
        ".gitlab-ci.yml", "jenkinsfile", "azure-pipelines.yml", "buildkite.yml",
        "pytest.ini", "tox.ini", "jest.config.js", "jest.config.ts",
        "vitest.config.js", "vitest.config.ts", "playwright.config.ts",
        "cypress.config.js", "cypress.config.ts", "codecov.yml", ".coveragerc",
    }:
        return True
    if any(part in {"__mocks__", "fixtures", "harness", "mocks", "support"} for part in parts):
        return any(part in {"test", "tests", "spec", "specs", "__tests__"} for part in parts)
    if base in {"conftest.py", "test-setup.ts", "test-setup.js", "setup-tests.ts", "setup-tests.js"}:
        return True
    return any(part in {"ci", "build", "scripts"} for part in parts) and any(
        token in base for token in ("check", "test", "verify", "lint", "coverage", "deploy")
    )


def signals_for(files: list[str], diff_text: str) -> set[str]:
    signals: set[str] = set()
    for path in files:
        lower = path.lower()
        base = PurePosixPath(lower).name
        parts = set(PurePosixPath(lower).parts)
        if silent_pass_path(path):
            signals.add("silent-pass-verification")
        if base in MANIFESTS:
            signals.update({"dependencies", "compatibility"})
        if parts & {"migration", "migrations", "schema", "schemas"} or base in {"schema.sql", "schema.rb"} or lower.endswith(".prisma"):
            signals.update({"migration", "data-integrity", "compatibility"})
        if parts & {"api", "apis", "route", "routes", "controller", "controllers", "graphql"} or lower.endswith((".proto", ".avsc")) or "openapi" in lower or "swagger" in lower:
            signals.update({"api-contract", "compatibility"})
        if parts & {"auth", "security", "credential", "credentials", "crypto", "permission", "permissions", "session", "sessions"} or any(token in base for token in ("auth", "token", "secret", "credential", "permission")):
            signals.add("security")
        if parts & {"db", "database", "entity", "entities", "model", "models", "repository", "repositories", "storage"}:
            signals.add("data-integrity")
        if parts & {"job", "jobs", "queue", "queues", "scheduler", "worker", "workers"} or any(token in base for token in ("lock", "mutex", "transaction", "concurrent", "retry")):
            signals.update({"concurrency", "observability"})
        if lower.startswith((".github/", "deploy/", "deployment/", "infra/", "infrastructure/", "k8s/", "kubernetes/", "terraform/")) or base in {"dockerfile", "containerfile", "docker-compose.yml", "docker-compose.yaml"}:
            signals.update({"compatibility", "observability"})
        if parts & {"skills", "agents", "prompts", "commands", "mcp"} or base in {"skill.md", "agents.md", "claude.md", "gemini.md"}:
            signals.add("agent-surface")
    if SILENT_PASS_CONTENT.search(diff_text):
        signals.add("silent-pass-verification")
    return signals


def activated_lenses(signals: set[str]) -> list[str]:
    lenses = set(BASE_LENSES)
    mapping = {
        "api-contract": {"api-contract", "compatibility"},
        "compatibility": {"compatibility"},
        "concurrency": {"concurrency", "failure-handling"},
        "data-integrity": {"data-integrity"},
        "dependencies": {"compatibility", "security"},
        "migration": {"migration", "data-integrity", "compatibility"},
        "observability": {"observability"},
        "security": {"security"},
        "silent-pass-verification": {"silent-pass-verification"},
        "agent-surface": {"maintainability", "security"},
    }
    for signal in signals:
        lenses.update(mapping.get(signal, set()))
    return sorted(lenses)


def derive_scope(root: Path, base_ref: str, head_ref: str) -> dict[str, object]:
    root = root.resolve(strict=True)
    base = resolve_commit(root, base_ref)
    head = resolve_commit(root, head_ref)
    if not base:
        return unknown("invalid base endpoint")
    if not head:
        return unknown("invalid head endpoint")
    merge_base = unique_merge_base(root, base, head)
    if not merge_base:
        return unknown("merge base unavailable or ambiguous")

    names = git(root, "diff", "--name-only", "-z", "--no-renames", merge_base, head, binary=True)
    numstat = git(root, "diff", "--numstat", "-z", "--no-renames", merge_base, head, binary=True)
    diff = git(root, "diff", "--no-color", "--no-ext-diff", "--no-renames", merge_base, head)
    if names.returncode != 0 or numstat.returncode != 0 or diff.returncode != 0:
        return unknown("git diff failed")

    files = sorted(
        item.decode("utf-8", errors="surrogateescape")
        for item in names.stdout.split(b"\0")
        if item
    )
    executable_lines = 0
    uncounted_files = 0
    for raw in numstat.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            added, deleted, path_bytes = raw.split(b"\t", 2)
        except ValueError:
            return unknown("malformed git numstat output")
        path = path_bytes.decode("utf-8", errors="surrogateescape")
        if Path(path).suffix.lower() not in CODE_EXTENSIONS:
            uncounted_files += 1
            continue
        if added == b"-" or deleted == b"-":
            uncounted_files += 1
            continue
        try:
            executable_lines += int(added) + int(deleted)
        except ValueError:
            return unknown("malformed executable line count")

    signals = signals_for(files, diff.stdout)
    return {
        "status": "complete",
        "reason": None,
        "base": base,
        "head": head,
        "merge_base": merge_base,
        "changed_file_count": len(files),
        "changed_files": files,
        "executable_lines": executable_lines,
        "uncounted_files": uncounted_files,
        "risk_signals": sorted(signals),
        "activated_lenses": activated_lenses(signals),
        "silent_pass_verification": "silent-pass-verification" in signals,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    try:
        result = derive_scope(args.repo, args.base, args.head)
    except (OSError, ValueError) as exc:
        result = unknown(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
