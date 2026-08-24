#!/usr/bin/env python3
"""Resolve and inspect only an immutable pre-change Git snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse


EXACT_SHA_RE = re.compile(r"[0-9a-fA-F]{40}")
SAFE_REF_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/@{}^~:+-]{0,199}")
MAX_GITHUB_BODY_BYTES = 32 * 1024
MAX_LIST_LIMIT = 1000
MAX_SEARCH_LIMIT = 100
MAX_SEARCH_LINE_BYTES = 16 * 1024
MAX_BLOB_BYTES = 256 * 1024
MAX_DISPLAY_BYTES = 32 * 1024
MAX_LOG_LIMIT = 50

BLOCKED_PARTS = {
    ".ai",
    ".claude",
    ".git",
    ".next",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
    "vendor",
    "venv",
}
BLOCKED_NAMES = {
    ".env",
    ".env.local",
    "agents.md",
    "claude.local.md",
    "claude.md",
    "credentials",
    "credentials.json",
    "id_dsa",
    "id_ed25519",
    "id_rsa",
}
BLOCKED_SUFFIXES = (".key", ".p12", ".pem", ".pfx")


def command_environment() -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "cat",
            "LC_ALL": "C",
        }
    )
    return env


def git_command(root: Path, *args: str) -> list[str]:
    return [
        "git",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "color.ui=false",
        "-C",
        str(root),
        *args,
    ]


def run_command(
    command: list[str],
    *,
    binary: bool = False,
    accepted: set[int] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=not binary,
        check=False,
        env=command_environment(),
        cwd=cwd,
    )
    allowed = accepted or {0}
    if completed.returncode not in allowed:
        stderr = completed.stderr
        stdout = completed.stdout
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        raise ValueError((stderr or stdout or "command failed").strip())
    return completed


def repository_root(path: Path) -> Path:
    candidate = path.expanduser().resolve(strict=True)
    if not candidate.is_dir():
        raise ValueError("repository path must be a directory")
    completed = run_command(
        git_command(candidate, "rev-parse", "--show-toplevel")
    )
    root = Path(str(completed.stdout).strip()).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("resolved repository root is not a directory")
    return root


def validate_ref(ref: str) -> str:
    if not SAFE_REF_RE.fullmatch(ref) or ref.startswith("-"):
        raise ValueError(f"unsafe Git ref: {ref!r}")
    return ref


def resolve_commit(root: Path, ref: str) -> str:
    ref = validate_ref(ref)
    completed = run_command(
        git_command(
            root,
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{ref}^{{commit}}",
        )
    )
    sha = str(completed.stdout).strip().lower()
    if EXACT_SHA_RE.fullmatch(sha) is None:
        raise ValueError(f"Git did not resolve {ref!r} to one commit")
    return sha


def exact_base(root: Path, base: str) -> str:
    if EXACT_SHA_RE.fullmatch(base) is None:
        raise ValueError("inspection requires the exact 40-character analysis-base SHA")
    resolved = resolve_commit(root, base.lower())
    if resolved != base.lower():
        raise ValueError("analysis-base SHA did not resolve exactly")
    return resolved


def merge_base(root: Path, base: str, head: str) -> str:
    completed = run_command(
        git_command(root, "merge-base", "--all", base, head)
    )
    candidates = [line.strip().lower() for line in str(completed.stdout).splitlines() if line]
    if len(candidates) != 1 or EXACT_SHA_RE.fullmatch(candidates[0]) is None:
        raise ValueError("pre-change merge base is unavailable or ambiguous")
    return candidates[0]


def optional_git_output(root: Path, *args: str) -> str | None:
    completed = run_command(git_command(root, *args), accepted={0, 1})
    if completed.returncode != 0:
        return None
    value = str(completed.stdout).strip()
    return value or None


def detect_default_ref(root: Path) -> str | None:
    current = optional_git_output(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    if current in {"main", "master", "trunk"}:
        return current

    remote_head = optional_git_output(
        root,
        "symbolic-ref",
        "--quiet",
        "--short",
        "refs/remotes/origin/HEAD",
    )
    candidates = [remote_head, "main", "master", "trunk", "origin/main", "origin/master"]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            resolve_commit(root, candidate)
        except ValueError:
            continue
        return candidate
    return None


def resolve_local(
    root: Path,
    *,
    base_ref: str | None,
    head_ref: str | None,
) -> dict[str, object]:
    if base_ref and not head_ref:
        return {
            "analysis_base": resolve_commit(root, base_ref),
            "resolution": "explicit-base",
            "target_ref": base_ref,
        }

    if base_ref and head_ref:
        base = resolve_commit(root, base_ref)
        head = resolve_commit(root, head_ref)
        return {
            "analysis_base": merge_base(root, base, head),
            "resolution": "explicit-base-head-merge-base",
            "target_ref": base_ref,
        }

    head = resolve_commit(root, head_ref or "HEAD")
    target = detect_default_ref(root)
    if target:
        target_sha = resolve_commit(root, target)
        if target_sha != head:
            return {
                "analysis_base": merge_base(root, target_sha, head),
                "resolution": "detected-default-merge-base",
                "target_ref": target,
            }
    return {
        "analysis_base": head,
        "resolution": "committed-head-no-distinct-implementation-branch",
        "target_ref": head_ref or "HEAD",
    }


def validate_github_target(target: str) -> str:
    if target.isdigit():
        return target
    if SAFE_REF_RE.fullmatch(target) and not target.startswith("-"):
        return target
    parsed = urlparse(target)
    if (
        parsed.scheme == "https"
        and parsed.netloc
        and parsed.path
        and not parsed.params
        and not parsed.query
        and not parsed.fragment
    ):
        return target
    raise ValueError("GitHub target must be a number, safe branch name, or HTTPS URL")


def bounded_body(value: object) -> tuple[str, bool]:
    text = value if isinstance(value, str) else ""
    payload = text.encode("utf-8", errors="replace")
    if len(payload) <= MAX_GITHUB_BODY_BYTES:
        return text, False
    return payload[:MAX_GITHUB_BODY_BYTES].decode("utf-8", errors="ignore"), True


def gh_json(args: list[str], *, root: Path) -> dict[str, object]:
    completed = run_command(["gh", *args], cwd=root)
    raw = str(completed.stdout)
    if len(raw.encode("utf-8", errors="replace")) > 1024 * 1024:
        raise ValueError("GitHub metadata response exceeded 1 MiB")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("GitHub returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("GitHub metadata response must be an object")
    return data


def resolve_pr(root: Path, target: str) -> dict[str, object]:
    target = validate_github_target(target)
    fields = ",".join(
        (
            "number",
            "title",
            "body",
            "url",
            "baseRefName",
            "headRefName",
            "baseRefOid",
            "headRefOid",
            "closingIssuesReferences",
        )
    )
    metadata = gh_json(["pr", "view", target, "--json", fields], root=root)
    base_oid = metadata.get("baseRefOid")
    head_oid = metadata.get("headRefOid")
    if not isinstance(base_oid, str) or not isinstance(head_oid, str):
        raise ValueError("PR metadata omitted base or head object identity")
    try:
        base = resolve_commit(root, base_oid)
        head = resolve_commit(root, head_oid)
    except ValueError as exc:
        raise ValueError(
            "PR endpoints are not available locally; refusing to fetch or substitute another base"
        ) from exc
    body, truncated = bounded_body(metadata.get("body"))
    issues = metadata.get("closingIssuesReferences")
    if not isinstance(issues, list):
        issues = []
    return {
        "analysis_base": merge_base(root, base, head),
        "resolution": "github-pr-local-merge-base",
        "target_ref": metadata.get("baseRefName"),
        "intent": {
            "kind": "pull-request",
            "number": metadata.get("number"),
            "title": metadata.get("title"),
            "body": body,
            "body_truncated": truncated,
            "url": metadata.get("url"),
            "linked_issues": [
                {
                    "number": item.get("number"),
                    "title": item.get("title"),
                    "url": item.get("url"),
                }
                for item in issues
                if isinstance(item, dict)
            ],
        },
    }


def issue_intent(root: Path, target: str) -> dict[str, object]:
    target = validate_github_target(target)
    metadata = gh_json(
        ["issue", "view", target, "--json", "number,title,body,url"],
        root=root,
    )
    body, truncated = bounded_body(metadata.get("body"))
    return {
        "kind": "issue",
        "number": metadata.get("number"),
        "title": metadata.get("title"),
        "body": body,
        "body_truncated": truncated,
        "url": metadata.get("url"),
    }


def normalized_path(value: str, *, allow_empty: bool = False) -> str:
    if value == "" and allow_empty:
        return value
    if any(ord(char) < 32 for char in value):
        raise ValueError("path contains control characters")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"path must be normalized and repository-relative: {value!r}")
    return path.as_posix()


def path_allowed(value: str) -> bool:
    try:
        normalized = normalized_path(value)
    except ValueError:
        return False
    path = PurePosixPath(normalized)
    lowered_parts = tuple(part.casefold() for part in path.parts)
    name = path.name.casefold()
    if any(part in BLOCKED_PARTS for part in lowered_parts):
        return False
    if name in BLOCKED_NAMES or name.startswith(".env") or name.endswith(BLOCKED_SUFFIXES):
        return False
    return True


def tree_entries(root: Path, base: str) -> list[dict[str, str]]:
    completed = run_command(
        git_command(root, "ls-tree", "-r", "-z", "--full-tree", base),
        binary=True,
    )
    entries: list[dict[str, str]] = []
    assert isinstance(completed.stdout, bytes)
    for record in completed.stdout.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, kind, object_id = metadata.decode("ascii").split(" ", 2)
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError("malformed Git tree entry") from exc
        path = raw_path.decode("utf-8", errors="surrogateescape")
        if kind != "blob" or mode == "120000" or not path_allowed(path):
            continue
        entries.append({"mode": mode, "object": object_id, "path": path})
    return entries


def list_paths(root: Path, base: str, *, prefix: str | None, limit: int) -> dict[str, object]:
    base = exact_base(root, base)
    if not 1 <= limit <= MAX_LIST_LIMIT:
        raise ValueError(f"list limit must be between 1 and {MAX_LIST_LIMIT}")
    normalized_prefix = ""
    if prefix:
        normalized_prefix = normalized_path(prefix).rstrip("/") + "/"
    matches = [
        entry["path"]
        for entry in tree_entries(root, base)
        if not normalized_prefix or entry["path"].startswith(normalized_prefix)
    ]
    return {
        "analysis_base": base,
        "prefix": prefix,
        "paths": matches[:limit],
        "truncated": len(matches) > limit,
        "returned": min(len(matches), limit),
    }


def entry_for_path(root: Path, base: str, path: str) -> dict[str, str]:
    normalized = normalized_path(path)
    if not path_allowed(normalized):
        raise ValueError(f"restricted or generated path refused: {normalized}")
    matches = [entry for entry in tree_entries(root, base) if entry["path"] == normalized]
    if len(matches) != 1:
        raise ValueError(f"path is absent or ambiguous at analysis base: {normalized}")
    return matches[0]


def show_file(
    root: Path,
    base: str,
    path: str,
    *,
    start: int,
    end: int | None,
) -> dict[str, object]:
    base = exact_base(root, base)
    entry = entry_for_path(root, base, path)
    size_result = run_command(git_command(root, "cat-file", "-s", entry["object"]))
    try:
        size = int(str(size_result.stdout).strip())
    except ValueError as exc:
        raise ValueError("Git returned an invalid blob size") from exc
    if size > MAX_BLOB_BYTES:
        raise ValueError(f"blob exceeds {MAX_BLOB_BYTES} byte source limit")
    blob_result = run_command(
        git_command(root, "cat-file", "blob", entry["object"]),
        binary=True,
    )
    assert isinstance(blob_result.stdout, bytes)
    payload = blob_result.stdout
    if b"\0" in payload:
        raise ValueError("binary blob refused")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("non-UTF-8 blob refused") from exc
    lines = text.splitlines()
    if start < 1 or (end is not None and end < start):
        raise ValueError("line range must be positive and ordered")
    stop = min(end or len(lines), len(lines))
    selected = lines[start - 1 : stop]
    rendered = "\n".join(f"{number}: {line}" for number, line in enumerate(selected, start=start))
    if len(rendered.encode("utf-8")) > MAX_DISPLAY_BYTES:
        raise ValueError(f"selected lines exceed {MAX_DISPLAY_BYTES} display bytes")
    return {
        "analysis_base": base,
        "path": entry["path"],
        "blob_bytes": len(payload),
        "blob_sha256": hashlib.sha256(payload).hexdigest(),
        "line_start": start,
        "line_end": stop,
        "text": rendered,
    }


def search_base(
    root: Path,
    base: str,
    query: str,
    *,
    prefix: str | None,
    limit: int,
) -> dict[str, object]:
    base = exact_base(root, base)
    if not 2 <= len(query) <= 256 or any(ord(char) < 32 for char in query):
        raise ValueError("search query must contain 2-256 printable characters")
    if not 1 <= limit <= MAX_SEARCH_LIMIT:
        raise ValueError(f"search limit must be between 1 and {MAX_SEARCH_LIMIT}")
    normalized_prefix = None
    if prefix:
        normalized_prefix = normalized_path(prefix).rstrip("/")
        if not path_allowed(normalized_prefix):
            raise ValueError(f"restricted or generated search prefix refused: {normalized_prefix}")
    command = git_command(
        root,
        "grep",
        "--no-color",
        "-n",
        "--full-name",
        "-F",
        "-e",
        query,
        base,
        "--",
    )
    if normalized_prefix:
        command.append(normalized_prefix)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=command_environment(),
    )
    assert process.stdout is not None
    matches: list[dict[str, object]] = []
    truncated = False
    prefix = f"{base}:"
    try:
        while True:
            raw = process.stdout.readline(MAX_SEARCH_LINE_BYTES + 1)
            if not raw:
                break
            if len(raw) > MAX_SEARCH_LINE_BYTES and not raw.endswith(b"\n"):
                truncated = True
                break
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line.startswith(prefix):
                continue
            match = re.fullmatch(r"(.*):([0-9]+):(.*)", line[len(prefix) :])
            if not match or not path_allowed(match.group(1)):
                continue
            matches.append(
                {
                    "path": match.group(1),
                    "line": int(match.group(2)),
                    "text": match.group(3)[:1000],
                }
            )
            if len(matches) >= limit:
                truncated = True
                break
    finally:
        if process.poll() is None and truncated:
            process.terminate()
        _, stderr = process.communicate()
    if not truncated and process.returncode not in {0, 1}:
        raise ValueError(stderr.decode("utf-8", errors="replace").strip() or "git grep failed")
    return {
        "analysis_base": base,
        "query": query,
        "prefix": normalized_prefix,
        "matches": matches,
        "truncated": truncated,
        "returned": len(matches),
    }


def history(
    root: Path,
    base: str,
    *,
    path: str | None,
    limit: int,
) -> dict[str, object]:
    base = exact_base(root, base)
    if not 1 <= limit <= MAX_LOG_LIMIT:
        raise ValueError(f"log limit must be between 1 and {MAX_LOG_LIMIT}")
    normalized = None
    if path:
        normalized = normalized_path(path)
        if not path_allowed(normalized):
            raise ValueError(f"restricted or generated path refused: {normalized}")
    args = [
        "log",
        "--no-show-signature",
        f"--max-count={limit}",
        "--format=%H%x09%cs%x09%an%x09%s",
        base,
    ]
    if normalized:
        args.extend(["--", normalized])
    completed = run_command(git_command(root, *args))
    commits: list[dict[str, str]] = []
    for line in str(completed.stdout).splitlines():
        fields = line.split("\t", 3)
        if len(fields) != 4 or EXACT_SHA_RE.fullmatch(fields[0]) is None:
            continue
        commits.append(
            {
                "sha": fields[0].lower(),
                "date": fields[1],
                "author": fields[2][:200],
                "subject": fields[3][:500],
            }
        )
    return {
        "analysis_base": base,
        "path": normalized,
        "commits": commits,
        "returned": len(commits),
    }


def lenses() -> dict[str, object]:
    path = Path(__file__).resolve().parent.parent / "references" / "risk-lenses.md"
    text = path.read_text(encoding="utf-8")
    return {
        "source": "references/risk-lenses.md",
        "bytes": len(text.encode("utf-8")),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text": text,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Resolve and inspect only a pinned pre-change Git snapshot."
    )
    commands = result.add_subparsers(dest="command", required=True)

    resolve = commands.add_parser("resolve")
    resolve.add_argument("--repo", required=True, type=Path)
    resolve.add_argument("--base")
    resolve.add_argument("--head")
    resolve.add_argument("--pr")

    issue = commands.add_parser("issue")
    issue.add_argument("--repo", required=True, type=Path)
    issue.add_argument("--target", required=True)

    listing = commands.add_parser("list")
    listing.add_argument("--repo", required=True, type=Path)
    listing.add_argument("--base", required=True)
    listing.add_argument("--prefix")
    listing.add_argument("--limit", type=int, default=200)

    search = commands.add_parser("search")
    search.add_argument("--repo", required=True, type=Path)
    search.add_argument("--base", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--prefix")
    search.add_argument("--limit", type=int, default=50)

    show = commands.add_parser("show")
    show.add_argument("--repo", required=True, type=Path)
    show.add_argument("--base", required=True)
    show.add_argument("--path", required=True)
    show.add_argument("--start", type=int, default=1)
    show.add_argument("--end", type=int)

    log = commands.add_parser("log")
    log.add_argument("--repo", required=True, type=Path)
    log.add_argument("--base", required=True)
    log.add_argument("--path")
    log.add_argument("--limit", type=int, default=20)

    commands.add_parser("lenses")
    return result


def execute(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "lenses":
        return lenses()
    if args.command == "issue":
        root = repository_root(args.repo)
        return {"repository": str(root), "intent": issue_intent(root, args.target)}

    root = repository_root(args.repo)
    if args.command == "resolve":
        if args.pr and (args.base or args.head):
            raise ValueError("--pr cannot be combined with --base or --head")
        resolved = resolve_pr(root, args.pr) if args.pr else resolve_local(
            root,
            base_ref=args.base,
            head_ref=args.head,
        )
        return {"repository": str(root), **resolved}
    if args.command == "list":
        return {
            "repository": str(root),
            **list_paths(root, args.base, prefix=args.prefix, limit=args.limit),
        }
    if args.command == "search":
        return {
            "repository": str(root),
            **search_base(
                root,
                args.base,
                args.query,
                prefix=args.prefix,
                limit=args.limit,
            ),
        }
    if args.command == "show":
        return {
            "repository": str(root),
            **show_file(root, args.base, args.path, start=args.start, end=args.end),
        }
    if args.command == "log":
        return {
            "repository": str(root),
            **history(root, args.base, path=args.path, limit=args.limit),
        }
    raise ValueError(f"unsupported command: {args.command}")


def main(argv: list[str]) -> int:
    args = parser().parse_args(argv[1:])
    try:
        result = execute(args)
    except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
        print(f"base-only inspection refused: {exc}", file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
