#!/usr/bin/env python3
"""Read-only Git and GitHub inspection for PR Kit."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
PR_TARGET_RE = re.compile(
    r"(?:[1-9][0-9]*|https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/[1-9][0-9]*)"
)
ISSUE_TARGET_RE = re.compile(
    r"(?:[1-9][0-9]*|https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/[1-9][0-9]*)"
)
GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_SEARCH_RESULTS = 100
PR_FIELDS = (
    "number,title,body,url,state,isDraft,author,baseRefName,baseRefOid,"
    "headRefName,headRefOid,changedFiles,additions,deletions"
)


def run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment.update({"GH_PAGER": "cat", "GIT_PAGER": "cat", "PAGER": "cat"})
    return subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def repository(value: Path) -> Path:
    root = value.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("repository must be a directory")
    probe = run(["git", "rev-parse", "--show-toplevel"], cwd=root)
    if probe.returncode != 0:
        raise ValueError("target is not a git repository")
    return Path(probe.stdout.strip()).resolve(strict=True)


def resolve_commit(root: Path, ref: str) -> str:
    result = run(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd=root)
    value = result.stdout.strip() if result.returncode == 0 else ""
    if not SHA_RE.fullmatch(value):
        raise ValueError(f"invalid commit endpoint: {ref}")
    return value


def merge_base(root: Path, base: str, head: str) -> str:
    result = run(["git", "merge-base", "--all", base, head], cwd=root)
    values = [line for line in result.stdout.splitlines() if line]
    if result.returncode != 0 or len(values) != 1:
        raise ValueError("merge base unavailable or ambiguous")
    return values[0]


def safe_path(value: str) -> str:
    if not value or any(ord(character) < 32 for character in value):
        raise ValueError("path must be a non-empty printable value")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("path must be repository-relative")
    return path.as_posix()


def emit(text: str) -> None:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= MAX_OUTPUT_BYTES:
        print(text, end="" if text.endswith("\n") else "\n")
        return
    clipped = encoded[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
    print(clipped, end="" if clipped.endswith("\n") else "\n")
    print(
        f"[PR Kit inspection truncated: {len(encoded)} bytes total; "
        "inspect narrower paths and record the blind spot.]"
    )


def checked_output(result: subprocess.CompletedProcess[str], operation: str) -> str:
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise ValueError(f"{operation} failed: {detail}")
    return result.stdout


def local_status(root: Path) -> str:
    head = resolve_commit(root, "HEAD")
    status = checked_output(
        run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=root),
        "git status",
    )
    return json.dumps({"head": head, "porcelain": status.splitlines()}, indent=2, sort_keys=True)


def local_diff(root: Path, base_ref: str, head_ref: str, path: str | None) -> str:
    base = resolve_commit(root, base_ref)
    head = resolve_commit(root, head_ref)
    common = merge_base(root, base, head)
    command = [
        "git", "diff", "--no-color", "--no-ext-diff", "--no-textconv", "--no-renames",
        common, head,
    ]
    if path:
        command.extend(["--", safe_path(path)])
    return checked_output(run(command, cwd=root), "git diff")


def local_show(
    root: Path,
    ref: str,
    path: str,
    start: int | None,
    end: int | None,
) -> str:
    commit = resolve_commit(root, ref)
    relative = safe_path(path)
    content = checked_output(run(["git", "show", f"{commit}:{relative}"], cwd=root), "git show")
    if start is None and end is None:
        return content
    first = start or 1
    last = end or first
    if first < 1 or last < first or last - first > 2000:
        raise ValueError("line range must be positive, ordered, and no larger than 2001 lines")
    lines = content.splitlines()
    selected = [
        f"{number:>6}\t{lines[number - 1]}"
        for number in range(first, min(last, len(lines)) + 1)
    ]
    return "\n".join(selected) + ("\n" if selected else "")


def local_log(root: Path, ref: str, path: str | None, max_count: int) -> str:
    if max_count < 1 or max_count > 100:
        raise ValueError("max-count must be between 1 and 100")
    commit = resolve_commit(root, ref)
    command = [
        "git", "log", f"--max-count={max_count}", "--date=iso-strict",
        "--format=%H%x09%ad%x09%an%x09%s", commit,
    ]
    if path:
        command.extend(["--", safe_path(path)])
    return checked_output(run(command, cwd=root), "git log")


def local_blame(root: Path, ref: str, path: str, start: int, end: int) -> str:
    if start < 1 or end < start or end - start > 200:
        raise ValueError("blame range must be positive, ordered, and no larger than 201 lines")
    commit = resolve_commit(root, ref)
    relative = safe_path(path)
    return checked_output(
        run(
            [
                "git", "blame", "--line-porcelain", "--no-progress",
                "-L", f"{start},{end}", commit, "--", relative,
            ],
            cwd=root,
        ),
        "git blame",
    )


def local_search(
    root: Path,
    ref: str,
    query: str,
    prefix: str | None,
    limit: int,
) -> str:
    if not 2 <= len(query) <= 256 or any(ord(character) < 32 for character in query):
        raise ValueError("query must contain 2-256 printable characters")
    if not 1 <= limit <= MAX_SEARCH_RESULTS:
        raise ValueError(f"limit must be between 1 and {MAX_SEARCH_RESULTS}")
    commit = resolve_commit(root, ref)
    command = ["git", "grep", "--no-color", "-n", "-F", "-e", query, commit, "--"]
    normalized_prefix = safe_path(prefix) if prefix else None
    if normalized_prefix:
        command.append(normalized_prefix)
    result = run(command, cwd=root)
    if result.returncode not in {0, 1}:
        raise ValueError(result.stderr.strip() or "git grep failed")
    lines = result.stdout.splitlines()
    return json.dumps(
        {
            "ref": commit,
            "query": query,
            "prefix": normalized_prefix,
            "matches": lines[:limit],
            "returned": min(len(lines), limit),
            "truncated": len(lines) > limit,
        },
        indent=2,
        sort_keys=True,
    )


def validate_github_target(value: str, pattern: re.Pattern[str], kind: str) -> str:
    if not pattern.fullmatch(value):
        raise ValueError(f"{kind} target must be a number or canonical GitHub URL")
    return value


def github_repo_args(value: str | None) -> list[str]:
    if value is None:
        return []
    if not GITHUB_REPO_RE.fullmatch(value):
        raise ValueError("github-repo must be owner/name")
    return ["--repo", value]


def github_pr_metadata(target: str, github_repo: str | None) -> str:
    target = validate_github_target(target, PR_TARGET_RE, "PR")
    command = ["gh", "pr", "view", target, "--json", PR_FIELDS, *github_repo_args(github_repo)]
    return checked_output(run(command), "gh pr view")


def github_pr_diff(target: str, github_repo: str | None) -> str:
    target = validate_github_target(target, PR_TARGET_RE, "PR")
    command = ["gh", "pr", "diff", target, "--patch", *github_repo_args(github_repo)]
    return checked_output(run(command), "gh pr diff")


def github_pr_comments(target: str, github_repo: str | None) -> str:
    target = validate_github_target(target, PR_TARGET_RE, "PR")
    command = ["gh", "pr", "view", target, "--comments", *github_repo_args(github_repo)]
    return checked_output(run(command), "gh pr view --comments")


def github_issue(target: str, github_repo: str | None) -> str:
    target = validate_github_target(target, ISSUE_TARGET_RE, "issue")
    command = ["gh", "issue", "view", target, "--json", "number,title,body,url,state,author"]
    command.extend(github_repo_args(github_repo))
    return checked_output(run(command), "gh issue view")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status")
    status.add_argument("--repo", required=True, type=Path)

    diff = subparsers.add_parser("diff")
    diff.add_argument("--repo", required=True, type=Path)
    diff.add_argument("--base", required=True)
    diff.add_argument("--head", required=True)
    diff.add_argument("--path")

    show = subparsers.add_parser("show")
    show.add_argument("--repo", required=True, type=Path)
    show.add_argument("--ref", required=True)
    show.add_argument("--path", required=True)
    show.add_argument("--start", type=int)
    show.add_argument("--end", type=int)

    log = subparsers.add_parser("log")
    log.add_argument("--repo", required=True, type=Path)
    log.add_argument("--ref", required=True)
    log.add_argument("--path")
    log.add_argument("--max-count", type=int, default=20)

    blame = subparsers.add_parser("blame")
    blame.add_argument("--repo", required=True, type=Path)
    blame.add_argument("--ref", required=True)
    blame.add_argument("--path", required=True)
    blame.add_argument("--start", required=True, type=int)
    blame.add_argument("--end", required=True, type=int)

    search = subparsers.add_parser("search")
    search.add_argument("--repo", required=True, type=Path)
    search.add_argument("--ref", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--prefix")
    search.add_argument("--limit", type=int, default=50)

    for name in ("pr-metadata", "pr-diff", "pr-comments"):
        command = subparsers.add_parser(name)
        command.add_argument("--target", required=True)
        command.add_argument("--github-repo")

    issue = subparsers.add_parser("issue")
    issue.add_argument("--target", required=True)
    issue.add_argument("--github-repo")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "status":
            result = local_status(repository(args.repo))
        elif args.command == "diff":
            result = local_diff(repository(args.repo), args.base, args.head, args.path)
        elif args.command == "show":
            result = local_show(repository(args.repo), args.ref, args.path, args.start, args.end)
        elif args.command == "log":
            result = local_log(repository(args.repo), args.ref, args.path, args.max_count)
        elif args.command == "blame":
            result = local_blame(
                repository(args.repo), args.ref, args.path, args.start, args.end
            )
        elif args.command == "search":
            result = local_search(
                repository(args.repo), args.ref, args.query, args.prefix, args.limit
            )
        elif args.command == "pr-metadata":
            result = github_pr_metadata(args.target, args.github_repo)
        elif args.command == "pr-diff":
            result = github_pr_diff(args.target, args.github_repo)
        elif args.command == "pr-comments":
            result = github_pr_comments(args.target, args.github_repo)
        else:
            result = github_issue(args.target, args.github_repo)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
