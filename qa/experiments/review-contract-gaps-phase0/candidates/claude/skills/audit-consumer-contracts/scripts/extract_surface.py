#!/usr/bin/env python3
"""Extract changed contract tokens with external base-tree matches."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path, PurePosixPath


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
STRING_RE = re.compile(r"(?P<quote>['\"])(?P<value>[A-Za-z][A-Za-z0-9_.:/-]{2,63})(?P=quote)")
MEMBER_RE = re.compile(r"(?:\.|\?\.)\s*([A-Za-z_][A-Za-z0-9_]{2,63})\b")
KEY_RE = re.compile(r"(?:^|[{,;(]\s*)([A-Za-z_][A-Za-z0-9_]{2,63})\s*[?:]")
STOPWORDS = {
    "const", "continue", "default", "else", "export", "false", "from",
    "function", "import", "interface", "null", "number", "object", "option", "options",
    "return", "string", "true", "undefined", "value", "values",
}
RESTRICTED_PARTS = {
    ".git", ".env", "dist", "build", "coverage", "node_modules", "vendor", "__pycache__",
}
RESTRICTED_SUFFIXES = {".lock", ".map", ".min.js"}
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cs", ".go", ".java", ".js", ".jsx", ".kt", ".php", ".py", ".rb", ".rs", ".swift", ".ts", ".tsx", ".vue"}


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def resolve(root: Path, value: str, label: str) -> str:
    if not SHA_RE.fullmatch(value):
        raise ValueError(f"{label} must be an exact 40-character lowercase SHA")
    result = git(root, "rev-parse", "--verify", "--quiet", f"{value}^{{commit}}")
    if result.returncode != 0 or result.stdout.strip() != value:
        raise ValueError(f"{label} commit is unavailable")
    return value


def merge_base(root: Path, base: str, head: str) -> str:
    result = git(root, "merge-base", "--all", base, head)
    values = [line for line in result.stdout.splitlines() if line]
    if result.returncode != 0 or len(values) != 1:
        raise ValueError("merge base is unavailable or ambiguous")
    return values[0]


def safe_source_path(value: str) -> bool:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return False
    if any(part in RESTRICTED_PARTS or part.startswith(".env") for part in path.parts):
        return False
    return not any(value.endswith(suffix) for suffix in RESTRICTED_SUFFIXES)


def production_source_path(value: str) -> bool:
    if not safe_source_path(value):
        return False
    path = PurePosixPath(value)
    lowered = value.lower()
    if path.suffix.lower() not in SOURCE_SUFFIXES:
        return False
    if any(
        marker in lowered
        for marker in (
            "/test/", "/tests/", "/__tests__/", "/fixtures/", "/snapshots/",
            ".test.", ".spec.", ".stories.", "/docs/",
        )
    ):
        return False
    return not any(part.startswith(".") for part in path.parts)


def changed_files(root: Path, base: str, head: str) -> list[str]:
    result = git(root, "diff", "--name-only", "--no-renames", base, head)
    if result.returncode != 0:
        raise ValueError("cannot enumerate changed files")
    return sorted(path for path in result.stdout.splitlines() if safe_source_path(path))


def diff_records(root: Path, base: str, head: str, files: list[str]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in files:
        result = git(
            root,
            "diff",
            "--unified=0",
            "--no-color",
            "--no-ext-diff",
            "--no-renames",
            base,
            head,
            "--",
            path,
        )
        if result.returncode != 0:
            raise ValueError(f"cannot inspect diff for {path}")
        old_line = new_line = 0
        for raw in result.stdout.splitlines():
            match = HUNK_RE.match(raw)
            if match:
                old_line = int(match.group(1))
                new_line = int(match.group(3))
                continue
            if raw.startswith("---") or raw.startswith("+++") or not raw:
                continue
            if raw.startswith("-"):
                records.append({"path": path, "side": "LEFT", "line": old_line, "text": raw[1:]})
                old_line += 1
            elif raw.startswith("+"):
                records.append({"path": path, "side": "RIGHT", "line": new_line, "text": raw[1:]})
                new_line += 1
            elif raw.startswith(" "):
                old_line += 1
                new_line += 1
    return records


def tokens(text: str) -> list[tuple[str, str]]:
    stripped = text.strip()
    if not stripped or stripped.startswith(("//", "#", "*")):
        return []
    found: dict[str, str] = {}
    for match in STRING_RE.finditer(text):
        value = match.group("value")
        if value.lower() not in STOPWORDS:
            found.setdefault(value, "string")
    for value in [*MEMBER_RE.findall(text), *KEY_RE.findall(text)]:
        if value.lower() not in STOPWORDS and not value.isdigit():
            found.setdefault(value, "property")
    return sorted(found.items())


def base_matches(
    root: Path,
    base: str,
    token: str,
    excluded: set[str],
    limit: int,
) -> list[dict[str, object]]:
    result = git(root, "grep", "-n", "-F", "-e", token, base, "--")
    if result.returncode not in {0, 1}:
        raise ValueError(f"cannot search base consumers for {token}")
    hits_by_path: dict[str, list[dict[str, object]]] = defaultdict(list)
    prefix = f"{base}:"
    for raw in result.stdout.splitlines():
        if not raw.startswith(prefix):
            continue
        remainder = raw[len(prefix):]
        parts = remainder.split(":", 2)
        if len(parts) != 3:
            continue
        path, line_text, text = parts
        if path in excluded or not production_source_path(path):
            continue
        try:
            line = int(line_text)
        except ValueError:
            continue
        hits_by_path[path].append({"path": path, "line": line, "ref": base, "line_text": text})
        if sum(len(items) for items in hits_by_path.values()) >= 5000:
            break
    ranked_paths = sorted(hits_by_path, key=lambda path: (-len(hits_by_path[path]), path))
    return [hits_by_path[path][0] for path in ranked_paths[:limit]]


def extract(
    root: Path,
    base_ref: str,
    head_ref: str,
    limit: int,
    consumer_limit: int,
    anchor_limit: int = 8,
) -> dict[str, object]:
    root = root.expanduser().resolve(strict=True)
    base_endpoint = resolve(root, base_ref, "base")
    head = resolve(root, head_ref, "head")
    base = merge_base(root, base_endpoint, head)
    files = changed_files(root, base, head)
    records = diff_records(root, base, head, files)
    by_token: dict[str, dict[str, object]] = {}
    for record in records:
        if not production_source_path(str(record["path"])):
            continue
        for token, kind in tokens(str(record["text"])):
            entry = by_token.setdefault(token, {"token": token, "kind": kind, "anchors": []})
            if len(entry["anchors"]) < anchor_limit:
                entry["anchors"].append(record)
            if kind == "string":
                entry["kind"] = "string"
    ranked = sorted(
        by_token.values(),
        key=lambda item: (item["kind"] != "string", -len(item["anchors"]), str(item["token"]).lower()),
    )
    surfaces: list[dict[str, object]] = []
    for entry in ranked:
        matches = base_matches(root, base, str(entry["token"]), set(files), consumer_limit)
        if not matches:
            continue
        surfaces.append(
            {
                "surface_id": f"S{len(surfaces) + 1}",
                "token": entry["token"],
                "kind": entry["kind"],
                "changed_anchors": entry["anchors"],
                "base_matches": matches,
            }
        )
        if len(surfaces) >= limit:
            break
    return {
        "schema_version": 1,
        "base": base,
        "head": head,
        "changed_files": files,
        "changed_line_count": len(records),
        "surface_count": len(surfaces),
        "surfaces": surfaces,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--consumer-limit", type=int, default=20)
    parser.add_argument("--anchor-limit", type=int, default=8)
    args = parser.parse_args()
    try:
        if (
            not 1 <= args.limit <= 100
            or not 1 <= args.consumer_limit <= 100
            or not 1 <= args.anchor_limit <= 100
        ):
            raise ValueError("limits must be between 1 and 100")
        print(
            json.dumps(
                extract(
                    args.repo,
                    args.base,
                    args.head,
                    args.limit,
                    args.consumer_limit,
                    args.anchor_limit,
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
