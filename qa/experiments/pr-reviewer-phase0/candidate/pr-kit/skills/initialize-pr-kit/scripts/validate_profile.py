#!/usr/bin/env python3
"""Validate a PR Kit repository profile without following linked targets."""

from __future__ import annotations

import argparse
import re
import stat
from datetime import datetime
from pathlib import Path, PurePosixPath

import profile_inputs

MAX_BYTES = 30 * 1024
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_TAG_RE = re.compile(r"\[source: ([^\]\r\n]+)\]")
SOURCE_PATH_RE = re.compile(r"^[A-Za-z0-9_.@+/-]+$")
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{16,}\b", re.I),
    re.compile(r"\b(?:password|passwd|api[_-]?key|client[_-]?secret)\s*[:=]\s*\S+", re.I),
)
REQUIRED_HEADINGS = (
    "# PR Kit Repository Profile",
    "## Review scope",
    "## Architecture and ownership",
    "## Critical invariants",
    "## Trust boundaries and sensitive paths",
    "## Failure modes and edge cases",
    "## Verification map",
    "## Local conventions",
    "## Verified precedents",
    "## Source index",
)
REQUIRED_FIELDS = (
    "schema_version", "repository", "base_commit", "profile_inputs_digest", "generated_at",
)
PLACEHOLDER_PATTERNS = (
    re.compile(r"\breplace with\b", re.I),
    re.compile(r"\breplace-with-", re.I),
    re.compile(r"\bTODO\b"),
)


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if len(lines) < 3 or lines[0] != "---":
        raise ValueError("profile must begin with YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("profile frontmatter is not closed") from exc
    values: dict[str, str] = {}
    for line in lines[1:end]:
        match = re.fullmatch(r"([a-z_]+):\s*(.+)", line)
        if not match:
            raise ValueError(f"invalid frontmatter line: {line!r}")
        key, value = match.groups()
        if key in values:
            raise ValueError(f"duplicate frontmatter field: {key}")
        values[key] = value.strip().strip("\"'")
    return values


def valid_source(value: str) -> bool:
    if re.fullmatch(r"commit [0-9a-f]{40}", value):
        return True
    if re.fullmatch(r"PR #[1-9][0-9]* @ [0-9a-f]{40}", value):
        return True
    path_value = value
    if ":" in value:
        candidate, line = value.rsplit(":", 1)
        if line.isdigit() and not line.startswith("0"):
            path_value = candidate
    if not SOURCE_PATH_RE.fullmatch(path_value):
        return False
    path = PurePosixPath(path_value)
    return not path.is_absolute() and bool(path.parts) and ".." not in path.parts


def validate_path(profile: Path, project_root: Path) -> None:
    if project_root.is_symlink():
        raise ValueError("project root must not be a symlink")
    supplied_root = project_root.absolute()
    supplied_profile = profile.absolute()
    if supplied_profile != supplied_root / ".ai" / "pr-kit" / "REPOSITORY.md":
        raise ValueError("profile must be exactly .ai/pr-kit/REPOSITORY.md under project root")
    root = project_root.resolve(strict=True)
    expected = root / ".ai" / "pr-kit" / "REPOSITORY.md"

    current = root
    for part in (".ai", "pr-kit", "REPOSITORY.md"):
        current = current / part
        if not current.exists() and not current.is_symlink():
            continue
        mode = current.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f"linked profile path is forbidden: {current}")
    mode = expected.lstat().st_mode
    if not stat.S_ISREG(mode):
        raise ValueError("profile must be a regular file")


def validate_text(text: str) -> tuple[dict[str, str], int]:
    raw = text.encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise ValueError(f"profile exceeds {MAX_BYTES} bytes")
    if b"\x00" in raw:
        raise ValueError("profile contains NUL bytes")
    fields = parse_frontmatter(text)
    missing = [field for field in REQUIRED_FIELDS if field not in fields]
    if missing:
        raise ValueError(f"missing frontmatter fields: {', '.join(missing)}")
    if fields["schema_version"] != "2":
        raise ValueError("schema_version must be 2")
    if not fields["repository"].strip():
        raise ValueError("repository must not be empty")
    if not SHA_RE.fullmatch(fields["base_commit"]):
        raise ValueError("base_commit must be a 40-character lowercase git SHA")
    if not DIGEST_RE.fullmatch(fields["profile_inputs_digest"]):
        raise ValueError("profile_inputs_digest must be a 64-character lowercase SHA-256")
    try:
        timestamp = datetime.fromisoformat(fields["generated_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("generated_at must be an RFC-3339 timestamp") from exc
    if timestamp.tzinfo is None:
        raise ValueError("generated_at must include a timezone")

    for heading in REQUIRED_HEADINGS:
        if text.splitlines().count(heading) != 1:
            raise ValueError(f"required heading must appear exactly once: {heading}")
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise ValueError("profile appears to contain secret material")
    for pattern in PLACEHOLDER_PATTERNS:
        if pattern.search(text):
            raise ValueError("profile still contains template placeholders")

    bullets = [
        line
        for line in text.splitlines()
        if re.match(r"^\s*[-*]\s+\S", line)
        and not line.lstrip().startswith(("- None", "- (none)", "- Unknown"))
    ]
    missing_sources = []
    for line in bullets:
        sources = SOURCE_TAG_RE.findall(line)
        if not sources or not all(valid_source(source) for source in sources):
            missing_sources.append(line)
    if missing_sources:
        raise ValueError(
            "every substantive bullet needs an inspectable source tag; first violation: "
            + missing_sources[0][:160]
        )
    if len(bullets) < 5:
        raise ValueError("profile needs at least five source-grounded substantive bullets")
    return fields, len(bullets)


def validate(profile: Path, project_root: Path) -> list[str]:
    validate_path(profile, project_root)
    raw = profile.read_bytes()
    if b"\x00" in raw:
        raise ValueError("profile contains NUL bytes")
    text = raw.decode("utf-8")
    fields, bullet_count = validate_text(text)
    freshness = profile_inputs.check_profile(project_root, profile, fields["base_commit"])
    if freshness.get("status") != "fresh":
        reasons = freshness.get("reasons") or ["profile digest or source validation failed"]
        raise ValueError("; ".join(str(reason) for reason in reasons))
    return [
        f"valid profile: {profile}",
        f"source-grounded bullets: {bullet_count}",
        f"base_commit: {fields['base_commit']}",
        f"profile_inputs_digest: {fields['profile_inputs_digest']}",
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        messages = validate(args.profile, args.project_root)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
