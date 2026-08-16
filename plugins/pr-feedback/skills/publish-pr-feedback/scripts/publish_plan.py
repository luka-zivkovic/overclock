#!/usr/bin/env python3
"""Seal, verify, and publish immutable GitHub PR feedback plans."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import stat
import subprocess
import uuid
from pathlib import Path
from typing import Any, Protocol

import plan_contract

SCHEMA_VERSION = plan_contract.SCHEMA_VERSION
MAX_PLAN_BYTES = 256 * 1024
DIGEST_RE = re.compile(r"[0-9a-f]{64}")
OID_RE = plan_contract.OID_RE
NODE_RE = plan_contract.NODE_RE
TOP_LEVEL_FIELDS = plan_contract.TOP_LEVEL_FIELDS


class Client(Protocol):
    def verify_target(self, plan: dict[str, Any]) -> None: ...

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

    def reply_thread(self, thread_id: str, body: str) -> None: ...

    def resolve_thread(self, thread_id: str) -> None: ...

    def post_pr_comment(self, pr_node_id: str, body: str) -> None: ...


def canonical_payload(plan: dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in plan.items() if key != "plan_digest"}
    return json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def plan_digest(plan: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_payload(plan)).hexdigest()


_need_string = plan_contract.need_string


def validate_plan(data: object, *, sealed: bool) -> dict[str, Any]:
    if not sealed:
        return plan_contract.validate_draft_plan(data)
    if not isinstance(data, dict):
        raise ValueError("plan must be a JSON object")
    allowed_top = TOP_LEVEL_FIELDS | {"plan_digest"}
    unknown = set(data) - allowed_top
    missing = TOP_LEVEL_FIELDS - set(data)
    if unknown:
        raise ValueError(f"unknown top-level fields: {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"missing top-level fields: {', '.join(sorted(missing))}")
    if set(data) != allowed_top:
        raise ValueError("sealed plan must contain exactly the documented fields")
    plan_contract.validate_draft_plan(
        {key: data[key] for key in TOP_LEVEL_FIELDS}
    )
    _need_string(data["plan_digest"], "plan_digest", DIGEST_RE)
    return data


def seal_plan(draft: object) -> dict[str, Any]:
    validated = validate_plan(draft, sealed=False)
    sealed = copy.deepcopy(validated)
    sealed["plan_digest"] = plan_digest(sealed)
    return validate_plan(sealed, sealed=True)


def verify_digest(plan: dict[str, Any], expected_digest: str) -> str:
    if DIGEST_RE.fullmatch(expected_digest) is None:
        raise ValueError("expected digest must be 64 lowercase hexadecimal characters")
    stored = _need_string(plan.get("plan_digest"), "plan_digest", DIGEST_RE)
    actual = plan_digest(plan)
    if stored != actual:
        raise ValueError("stored plan_digest does not match canonical plan content")
    if expected_digest != actual:
        raise ValueError("expected digest does not match the sealed plan")
    return actual


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
        decoded = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("plan must be valid UTF-8 JSON") from exc
    return decoded


def read_plan(path: Path, *, root: Path, sealed: bool) -> dict[str, Any]:
    return validate_plan(read_json_file(path, root=root), sealed=sealed)


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


def marker(digest: str, action_id: str) -> str:
    return f"<!-- overclock-pr-feedback:{digest}:{action_id} -->"


def published_body(body: str, digest: str, action_id: str) -> str:
    return f"{body.rstrip()}\n\n{marker(digest, action_id)}"


def summarize(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "host": plan["host"],
        "repository": f"{plan['owner']}/{plan['repo']}",
        "pr_number": plan["pr_number"],
        "pr_node_id": plan["pr_node_id"],
        "head_oid": plan["head_oid"],
        "plan_digest": plan["plan_digest"],
        "actions": [
            {
                "action_id": action["action_id"],
                "surface": action["surface"],
                "source_id": action["source_id"],
                "thread_id": action.get("thread_id"),
                "verdict": action["verdict"],
                "resolve": action["resolve"],
                "reply_body": action["reply_body"],
            }
            for action in plan["actions"]
        ],
    }


def publish(
    plan: dict[str, Any],
    *,
    expected_digest: str,
    client: Client,
    confirm_no_concurrent_publisher: bool,
) -> dict[str, Any]:
    if not confirm_no_concurrent_publisher:
        raise ValueError(
            "publish requires confirmation that no concurrent publisher is active"
        )
    digest, preflight = preflight_plan(
        plan,
        expected_digest=expected_digest,
        client=client,
    )
    needs_mutation = any(
        not item["resolved"]
        and (
            not item["reply_exists"]
            or item["action"]["resolve"]
        )
        for item in preflight
    )
    if needs_mutation:
        # Marker discovery is fully paginated but check-then-create is not an atomic
        # GitHub operation. The caller confirms single-publisher execution above;
        # re-pin the target after every preflight read and immediately before the
        # first mutation to catch a head change during pagination.
        client.verify_target(plan)

    results: list[dict[str, str]] = []
    for item in preflight:
        action = item["action"]
        action_id = action["action_id"]
        if item["resolved"]:
            results.append({"action_id": action_id, "status": "already-resolved"})
            continue
        body = published_body(action["reply_body"], digest, action_id)
        try:
            if item["reply_exists"]:
                results.append({"action_id": action_id, "status": "already-posted"})
            elif action["surface"] == "review-thread":
                client.reply_thread(action["thread_id"], body)
                results.append({"action_id": action_id, "status": "posted"})
            else:
                client.post_pr_comment(plan["pr_node_id"], body)
                results.append({"action_id": action_id, "status": "posted"})
            if action["resolve"]:
                client.resolve_thread(action["thread_id"])
                results.append({"action_id": action_id, "status": "resolved"})
        except Exception as exc:
            results.append(
                {
                    "action_id": action_id,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            return {
                "plan_digest": digest,
                "complete": False,
                "error": str(exc),
                "results": results,
            }
    return {"plan_digest": digest, "complete": True, "results": results}


def preflight_plan(
    plan: dict[str, Any],
    *,
    expected_digest: str,
    client: Client,
) -> tuple[str, list[dict[str, Any]]]:
    digest = verify_digest(validate_plan(plan, sealed=True), expected_digest)
    client.verify_target(plan)
    preflight: list[dict[str, Any]] = []
    for action in plan["actions"]:
        item_marker = marker(digest, action["action_id"])
        if action["surface"] == "review-thread":
            state = client.thread_state(
                action["thread_id"],
                action["source_id"],
                plan["pr_node_id"],
                item_marker,
            )
            preflight.append({"action": action, **state})
        else:
            preflight.append(
                {
                    "action": action,
                    "resolved": False,
                    "reply_exists": client.non_thread_state(
                        action["surface"],
                        action["source_id"],
                        plan["pr_node_id"],
                        item_marker,
                    ),
                }
            )
    return digest, preflight


class GhClient:
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
            {
                "owner": owner,
                "repo": repo,
                "number": number,
            },
        )
        repository = data.get("data", {}).get("repository")
        pull = None if repository is None else repository.get("pullRequest")
        if pull is None:
            raise ValueError("target pull request was not found on the selected host/repository")
        if pull.get("state") != "OPEN":
            raise ValueError("pull request is no longer open")
        return {
            "pr_node_id": _need_string(pull.get("id"), "remote PR node ID", NODE_RE),
            "head_oid": _need_string(pull.get("headRefOid"), "remote head OID", OID_RE),
        }

    def verify_target(self, plan: dict[str, Any]) -> None:
        pinned = self.pin_target(plan["owner"], plan["repo"], plan["pr_number"])
        if pinned["pr_node_id"] != plan["pr_node_id"]:
            raise ValueError("pull request node ID no longer matches the plan")
        if pinned["head_oid"] != plan["head_oid"]:
            raise ValueError("pull request head changed after plan approval")

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
            cursor = _need_string(page_info.get("endCursor"), "thread comments cursor")
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
            cursor = _need_string(page_info.get("endCursor"), "PR comments cursor")
        return reply_exists

    def reply_thread(self, thread_id: str, body: str) -> None:
        self.graphql(
            """
mutation Reply($thread: ID!, $body: String!) {
  addPullRequestReviewThreadReply(
    input: {pullRequestReviewThreadId: $thread, body: $body}
  ) { comment { id } }
}
""",
            {"thread": thread_id, "body": body},
        )

    def resolve_thread(self, thread_id: str) -> None:
        self.graphql(
            """
mutation Resolve($thread: ID!) {
  resolveReviewThread(input: {threadId: $thread}) {
    thread { id isResolved }
  }
}
""",
            {"thread": thread_id},
        )

    def post_pr_comment(self, pr_node_id: str, body: str) -> None:
        self.graphql(
            """
mutation Comment($subject: ID!, $body: String!) {
  addComment(input: {subjectId: $subject, body: $body}) {
    commentEdge { node { id } }
  }
}
""",
            {"subject": pr_node_id, "body": body},
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    seal_parser = subparsers.add_parser("seal")
    seal_parser.add_argument("--root", required=True, type=Path)
    seal_parser.add_argument("--draft", required=True, type=Path)
    seal_parser.add_argument("--output", required=True, type=Path)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--root", required=True, type=Path)
    verify_parser.add_argument("--plan", required=True, type=Path)
    verify_parser.add_argument("--expected-digest", required=True)

    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument("--root", required=True, type=Path)
    publish_parser.add_argument("--plan", required=True, type=Path)
    publish_parser.add_argument("--expected-digest", required=True)
    publish_parser.add_argument("--confirm-remote-mutations", action="store_true")
    publish_parser.add_argument(
        "--confirm-no-concurrent-publisher",
        action="store_true",
    )

    args = parser.parse_args()
    root = _root(args.root)
    if args.command == "seal":
        draft = read_plan(args.draft, root=root, sealed=False)
        sealed = seal_plan(draft)
        write_new_plan(args.output, sealed, root=root)
        result = summarize(sealed)
    else:
        plan = read_plan(args.plan, root=root, sealed=True)
        verify_digest(plan, args.expected_digest)
        client = GhClient(plan["host"])
        if args.command == "verify":
            digest, preflight = preflight_plan(
                plan,
                expected_digest=args.expected_digest,
                client=client,
            )
            result = {
                **summarize(plan),
                "plan_digest": digest,
                "remote_preflight": [
                    {
                        "action_id": item["action"]["action_id"],
                        "resolved": item["resolved"],
                        "reply_exists": item["reply_exists"],
                    }
                    for item in preflight
                ],
            }
        else:
            if not args.confirm_remote_mutations:
                raise ValueError("publish requires --confirm-remote-mutations")
            result = publish(
                plan,
                expected_digest=args.expected_digest,
                client=client,
                confirm_no_concurrent_publisher=args.confirm_no_concurrent_publisher,
            )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("complete", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
