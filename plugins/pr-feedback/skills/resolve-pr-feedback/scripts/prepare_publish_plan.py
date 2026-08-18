#!/usr/bin/env python3
"""Prepare an unsealed PR-feedback plan from an explicitly approved action subset."""
from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import uuid
from pathlib import Path
from typing import Any, Protocol

import plan_contract

MAX_PLAN_BYTES = 256 * 1024
REQUEST_FIELDS = {
    "schema_version",
    "host",
    "owner",
    "repo",
    "pr_number",
    "actions",
}
NEVER_POSTED_MARKER = "<!-- overclock-pr-feedback:preparation-membership-check -->"


class PreparationClient(Protocol):
    def pin_target(self, owner: str, repo: str, number: int) -> dict[str, str]: ...

    def thread_state(
        self,
        thread_id: str,
        source_id: str,
        pr_node_id: str,
        marker: str,
    ) -> dict[str, bool]: ...

    def non_thread_state(
        self,
        surface: str,
        source_id: str,
        pr_node_id: str,
        marker: str,
    ) -> bool: ...


def _root(path: Path) -> Path:
    root = Path(os.path.abspath(os.fspath(path.expanduser())))
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(root, flags)
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise ValueError(f"root is not a directory: {root}")
    finally:
        os.close(fd)
    return root


def _relative(path: Path, root: Path) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = Path(os.path.abspath(os.fspath(candidate)))
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes authorized root: {path}") from exc
    if not relative.parts:
        raise ValueError("path must name a file below root")
    return relative


def _open_parent(root: Path, relative: Path) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    current = os.open(root, flags)
    try:
        for part in relative.parts[:-1]:
            following = os.open(part, flags, dir_fd=current)
            os.close(current)
            current = following
        return current
    except Exception:
        os.close(current)
        raise


def read_json_file(path: Path, *, root: Path) -> object:
    relative = _relative(path, root)
    parent = _open_parent(root, relative)
    try:
        fd = os.open(
            relative.name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent,
        )
        details = os.fstat(fd)
        if not stat.S_ISREG(details.st_mode):
            os.close(fd)
            raise ValueError("plan is not a regular file")
        if details.st_nlink != 1:
            os.close(fd)
            raise ValueError("plan must have exactly one hard link")
        if details.st_size > MAX_PLAN_BYTES:
            os.close(fd)
            raise ValueError(f"plan exceeds {MAX_PLAN_BYTES} bytes")
        try:
            chunks: list[bytes] = []
            remaining = MAX_PLAN_BYTES + 1
            while remaining:
                chunk = os.read(fd, min(65536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            data = b"".join(chunks)
        finally:
            os.close(fd)
    finally:
        os.close(parent)
    if len(data) > MAX_PLAN_BYTES:
        raise ValueError(f"plan exceeds {MAX_PLAN_BYTES} bytes")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("plan must be valid UTF-8 JSON") from exc


def write_new_plan(path: Path, plan: dict[str, Any], *, root: Path) -> None:
    relative = _relative(path, root)
    parent = _open_parent(root, relative)
    temporary = f".{relative.name}.tmp-{uuid.uuid4().hex}"
    encoded = (
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            existing = os.stat(relative.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            raise FileExistsError(f"refusing to replace existing output: {path}")
        temporary_fd = os.open(temporary, flags, 0o600, dir_fd=parent)
        try:
            view = memoryview(encoded)
            while view:
                view = view[os.write(temporary_fd, view):]
            os.fsync(temporary_fd)
        finally:
            os.close(temporary_fd)
        try:
            os.link(
                temporary,
                relative.name,
                src_dir_fd=parent,
                dst_dir_fd=parent,
                follow_symlinks=False,
            )
        except FileExistsError:
            raise FileExistsError(f"refusing to replace existing output: {path}") from None
        os.unlink(temporary, dir_fd=parent)
        temporary = ""
        os.fsync(parent)
    finally:
        if temporary:
            try:
                os.unlink(temporary, dir_fd=parent)
            except OSError:
                pass
        os.close(parent)


class GhClient:
    """Read-only GitHub client for pinning and source-membership checks."""

    def __init__(self, host: str):
        self.host = host

    def graphql(self, query: str, fields: dict[str, object]) -> dict[str, Any]:
        command = ["gh", "api", "--hostname", self.host, "graphql"]
        for key, value in fields.items():
            flag = "-F" if isinstance(value, int) and not isinstance(value, bool) else "-f"
            command.extend([flag, f"{key}={value}"])
        command.extend(["-f", f"query={query}"])
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"GitHub API call failed: {message}")
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("GitHub API returned invalid JSON") from exc

    def pin_target(self, owner: str, repo: str, number: int) -> dict[str, str]:
        data = self.graphql(
            """
query Target($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) { id state headRefOid }
  }
}
""",
            {"owner": owner, "repo": repo, "number": number},
        )
        repository = data.get("data", {}).get("repository")
        pull = None if repository is None else repository.get("pullRequest")
        if pull is None:
            raise ValueError("target pull request was not found on the selected host/repository")
        if pull.get("state") != "OPEN":
            raise ValueError("pull request is no longer open")
        return {
            "pr_node_id": plan_contract.need_string(
                pull.get("id"),
                "remote PR node ID",
                plan_contract.NODE_RE,
            ),
            "head_oid": plan_contract.need_string(
                pull.get("headRefOid"),
                "remote head OID",
                plan_contract.OID_RE,
            ),
        }

    def thread_state(
        self,
        thread_id: str,
        source_id: str,
        pr_node_id: str,
        expected_marker: str,
    ) -> dict[str, bool]:
        cursor: str | None = None
        reply_exists = False
        source_exists = False
        resolved = False
        while True:
            fields: dict[str, object] = {"id": thread_id}
            if cursor is not None:
                fields["cursor"] = cursor
            data = self.graphql(
                """
query Thread($id: ID!, $cursor: String) {
  node(id: $id) {
    ... on PullRequestReviewThread {
      id
      isResolved
      pullRequest { id }
      comments(first: 100, after: $cursor) {
        nodes { id body }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
""",
                fields,
            )
            node = data.get("data", {}).get("node")
            if not isinstance(node, dict) or node.get("id") != thread_id:
                raise ValueError(f"review thread not found: {thread_id}")
            if node.get("pullRequest", {}).get("id") != pr_node_id:
                raise ValueError(f"review thread belongs to a different PR: {thread_id}")
            resolved = bool(node.get("isResolved"))
            comments = node.get("comments", {})
            for comment in comments.get("nodes", []):
                source_exists = source_exists or comment.get("id") == source_id
                reply_exists = reply_exists or expected_marker in (
                    comment.get("body") or ""
                )
            page_info = comments.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = plan_contract.need_string(
                page_info.get("endCursor"),
                "thread comments cursor",
            )
        if not source_exists:
            raise ValueError(
                f"approved source comment does not belong to thread {thread_id}: {source_id}"
            )
        return {"resolved": resolved, "reply_exists": reply_exists}

    def non_thread_state(
        self,
        surface: str,
        source_id: str,
        pr_node_id: str,
        expected_marker: str,
    ) -> bool:
        source = self.graphql(
            """
query Source($id: ID!) {
  node(id: $id) {
    __typename
    ... on IssueComment { id pullRequest { id } }
    ... on PullRequestReview { id pullRequest { id } }
  }
}
""",
            {"id": source_id},
        ).get("data", {}).get("node")
        expected_type = "IssueComment" if surface == "pr-comment" else "PullRequestReview"
        if (
            not isinstance(source, dict)
            or source.get("__typename") != expected_type
            or source.get("id") != source_id
            or source.get("pullRequest", {}).get("id") != pr_node_id
        ):
            raise ValueError(
                f"{surface} source does not belong to the planned PR: {source_id}"
            )

        cursor: str | None = None
        reply_exists = False
        while True:
            fields: dict[str, object] = {"id": pr_node_id}
            if cursor is not None:
                fields["cursor"] = cursor
            data = self.graphql(
                """
query Comments($id: ID!, $cursor: String) {
  node(id: $id) {
    ... on PullRequest {
      comments(first: 100, after: $cursor) {
        nodes { body }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
""",
                fields,
            )
            node = data.get("data", {}).get("node")
            if not isinstance(node, dict):
                raise ValueError("pull request disappeared during preflight")
            comments = node.get("comments", {})
            reply_exists = reply_exists or any(
                expected_marker in (comment.get("body") or "")
                for comment in comments.get("nodes", [])
            )
            page_info = comments.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = plan_contract.need_string(
                page_info.get("endCursor"),
                "PR comments cursor",
            )
        return reply_exists


def validate_request(data: object) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("preparation request must be a JSON object")
    unknown = set(data) - REQUEST_FIELDS
    missing = REQUEST_FIELDS - set(data)
    if unknown:
        raise ValueError(f"unknown preparation fields: {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"missing preparation fields: {', '.join(sorted(missing))}")
    candidate = {
        **data,
        "pr_node_id": "PR_preparation_placeholder",
        "head_oid": "0" * 40,
    }
    plan_contract.validate_draft_plan(candidate)
    return data


def prepare_plan(
    request: object,
    *,
    client: PreparationClient,
) -> dict[str, Any]:
    approved = validate_request(request)
    pinned = client.pin_target(
        approved["owner"],
        approved["repo"],
        approved["pr_number"],
    )
    plan = {
        **approved,
        "pr_node_id": pinned["pr_node_id"],
        "head_oid": pinned["head_oid"],
    }
    plan_contract.validate_draft_plan(plan)
    for action in plan["actions"]:
        if action["surface"] == "review-thread":
            client.thread_state(
                action["thread_id"],
                action["source_id"],
                plan["pr_node_id"],
                NEVER_POSTED_MARKER,
            )
        else:
            client.non_thread_state(
                action["surface"],
                action["source_id"],
                plan["pr_node_id"],
                NEVER_POSTED_MARKER,
            )
    return plan


def summary(plan: dict[str, Any], output: Path) -> dict[str, Any]:
    return {
        "output": str(output),
        "sealed": False,
        "host": plan["host"],
        "repository": f"{plan['owner']}/{plan['repo']}",
        "pr_number": plan["pr_number"],
        "pr_node_id": plan["pr_node_id"],
        "head_oid": plan["head_oid"],
        "actions": [
            {
                "action_id": action["action_id"],
                "surface": action["surface"],
                "source_id": action["source_id"],
                "thread_id": action.get("thread_id"),
                "verdict": action["verdict"],
                "reply_body": action["reply_body"],
                "resolve": action["resolve"],
            }
            for action in plan["actions"]
        ],
        "next_step": "explicitly invoke $publish-pr-feedback seal with this draft and a new output path",
    }


def prepare_from_file(
    *,
    root_path: Path,
    request_path: Path,
    output_path: Path,
    client: PreparationClient,
) -> tuple[dict[str, Any], Path]:
    root = _root(root_path)
    request = read_json_file(request_path, root=root)
    plan = prepare_plan(request, client=client)
    write_new_plan(output_path, plan, root=root)
    output = root / _relative(output_path, root)
    return plan, output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    root = _root(args.root)
    request = read_json_file(args.request, root=root)
    approved = validate_request(request)
    client = GhClient(approved["host"])
    plan = prepare_plan(approved, client=client)
    write_new_plan(args.output, plan, root=root)
    output = root / _relative(args.output, root)
    print(json.dumps(summary(plan, output), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
