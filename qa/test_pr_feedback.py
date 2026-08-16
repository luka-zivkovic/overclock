from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

SCRIPT_DIR = (
    Path(__file__).resolve().parent.parent
    / "plugins/pr-feedback/skills/publish-pr-feedback/scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))
import publish_plan  # noqa: E402

RESOLVER_SCRIPT_DIR = (
    Path(__file__).resolve().parent.parent
    / "plugins/pr-feedback/skills/resolve-pr-feedback/scripts"
)
RESOLVER_SKILL_DIR = RESOLVER_SCRIPT_DIR.parent
sys.path.insert(0, str(RESOLVER_SCRIPT_DIR))
import prepare_publish_plan  # noqa: E402


def draft_plan() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "host": "github.example.com",
        "owner": "acme",
        "repo": "widgets",
        "pr_number": 42,
        "pr_node_id": "PR_kwDOabc123",
        "head_oid": "a" * 40,
        "actions": [
            {
                "action_id": "null-guard",
                "surface": "review-thread",
                "source_id": "PRRC_kwDOcomment1",
                "thread_id": "PRRT_kwDOthread1",
                "verdict": "fixed",
                "reply_body": "> Add a null guard.\n\nFixed in `src/orders.js`.",
                "resolve": True,
            },
            {
                "action_id": "design-note",
                "surface": "review-body",
                "source_id": "PRR_kwDOreview1",
                "verdict": "needs-human",
                "reply_body": "We are keeping this open while we choose the design.",
                "resolve": False,
            },
        ],
    }


def preparation_request() -> dict[str, Any]:
    plan = draft_plan()
    return {
        key: value
        for key, value in plan.items()
        if key not in {"pr_node_id", "head_oid"}
    }


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.thread_states: dict[str, dict[str, bool]] = {}
        self.fail_thread: str | None = None
        self.fail_mutation: tuple[str, str] | None = None
        self.verify_calls = 0
        self.head_changes_on_second_verify = False

    def verify_target(self, plan: dict[str, Any]) -> None:
        self.verify_calls += 1
        self.calls.append(("verify", str(plan["pr_number"])))
        if self.head_changes_on_second_verify and self.verify_calls == 2:
            raise ValueError("pull request head changed after plan approval")

    def pin_target(self, owner: str, repo: str, number: int) -> dict[str, str]:
        self.calls.append(("pin", f"{owner}/{repo}#{number}"))
        return {
            "pr_node_id": "PR_fresh",
            "head_oid": "b" * 40,
        }

    def thread_state(
        self,
        thread_id: str,
        source_id: str,
        pr_node_id: str,
        marker: str,
    ) -> dict[str, bool]:
        self.calls.append(("thread-state", thread_id))
        if thread_id == self.fail_thread:
            raise ValueError("wrong PR")
        return self.thread_states.get(
            thread_id, {"resolved": False, "reply_exists": False}
        )

    def non_thread_state(
        self,
        surface: str,
        source_id: str,
        pr_node_id: str,
        marker: str,
    ) -> bool:
        self.calls.append(("source-state", source_id))
        return False

    def reply_thread(self, thread_id: str, body: str) -> None:
        self.calls.append(("reply", thread_id))
        if self.fail_mutation == ("reply", thread_id):
            raise RuntimeError("reply failed")
        self.assert_marker = "overclock-pr-feedback:" in body

    def resolve_thread(self, thread_id: str) -> None:
        self.calls.append(("resolve", thread_id))
        if self.fail_mutation == ("resolve", thread_id):
            raise RuntimeError("resolve failed")

    def post_pr_comment(self, pr_node_id: str, body: str) -> None:
        self.calls.append(("comment", pr_node_id))
        if self.fail_mutation == ("comment", pr_node_id):
            raise RuntimeError("comment failed")
        self.assert_marker = "overclock-pr-feedback:" in body


class PagingGhClient(publish_plan.GhClient):
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        super().__init__("github.example.com")
        self.responses = responses
        self.fields_seen: list[dict[str, object]] = []

    def graphql(self, query: str, fields: dict[str, object]) -> dict[str, Any]:
        self.fields_seen.append(fields)
        return self.responses.pop(0)


class PublishPlanTest(unittest.TestCase):
    def test_prepare_plan_repins_and_preserves_exact_approved_subset(self) -> None:
        request = preparation_request()
        request["actions"] = [request["actions"][0]]
        client = FakeClient()

        plan = prepare_publish_plan.prepare_plan(request, client=client)

        self.assertEqual(plan["pr_node_id"], "PR_fresh")
        self.assertEqual(plan["head_oid"], "b" * 40)
        self.assertNotIn("plan_digest", plan)
        self.assertEqual(plan["actions"], request["actions"])
        self.assertIn(("pin", "acme/widgets#42"), client.calls)
        self.assertIn(("thread-state", "PRRT_kwDOthread1"), client.calls)
        self.assertNotIn(("source-state", "PRR_kwDOreview1"), client.calls)

    def test_prepare_request_rejects_prepinned_or_unknown_fields(self) -> None:
        request = preparation_request()
        request["head_oid"] = "a" * 40
        with self.assertRaisesRegex(ValueError, "unknown preparation fields"):
            prepare_publish_plan.validate_request(request)

    def test_prepare_file_never_replaces_user_named_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request = root / "approved.json"
            request.write_text(
                json.dumps(preparation_request()),
                encoding="utf-8",
            )
            output = root / "user-named-draft.json"
            output.write_text("preserve me", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "refusing to replace"):
                prepare_publish_plan.prepare_from_file(
                    root_path=root,
                    request_path=request,
                    output_path=output,
                    client=FakeClient(),
                )

            self.assertEqual(output.read_text(encoding="utf-8"), "preserve me")

    def test_standalone_resolver_copy_prepares_without_publisher_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            installed = base / "installed"
            installed.mkdir()
            resolver = installed / "resolve-pr-feedback"
            shutil.copytree(RESOLVER_SKILL_DIR, resolver)
            self.assertFalse((installed / "publish-pr-feedback").exists())

            root = base / "repo"
            root.mkdir()
            request_data = preparation_request()
            request_data["actions"] = [request_data["actions"][0]]
            request = root / "approved.json"
            request.write_text(json.dumps(request_data), encoding="utf-8")
            output = root / "draft.json"

            fake_bin = base / "bin"
            fake_bin.mkdir()
            fake_gh = fake_bin / "gh"
            fake_gh.write_text(
                """#!/usr/bin/env python3
import json
import sys

command = " ".join(sys.argv[1:])
if "query Target(" in command:
    result = {
        "data": {
            "repository": {
                "pullRequest": {
                    "id": "PR_fresh",
                    "state": "OPEN",
                    "headRefOid": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                }
            }
        }
    }
elif "query Thread(" in command:
    result = {
        "data": {
            "node": {
                "id": "PRRT_kwDOthread1",
                "isResolved": False,
                "pullRequest": {"id": "PR_fresh"},
                "comments": {
                    "nodes": [
                        {
                            "id": "PRRC_kwDOcomment1",
                            "body": "Original review comment",
                        }
                    ],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                },
            }
        }
    }
else:
    print("unexpected gh operation", file=sys.stderr)
    raise SystemExit(73)
print(json.dumps(result))
""",
                encoding="utf-8",
            )
            fake_gh.chmod(0o700)
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(resolver / "scripts" / "prepare_publish_plan.py"),
                    "--root",
                    str(root),
                    "--request",
                    str(request),
                    "--output",
                    str(output),
                ],
                cwd=root,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertNotIn("publish-pr-feedback", completed.stderr)
            plan = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(plan["actions"], request_data["actions"])
            self.assertEqual(plan["pr_node_id"], "PR_fresh")
            self.assertEqual(plan["head_oid"], "b" * 40)
            self.assertNotIn("plan_digest", plan)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_seal_is_canonical_and_detects_tampering(self) -> None:
        sealed = publish_plan.seal_plan(draft_plan())
        digest = sealed["plan_digest"]
        self.assertEqual(digest, publish_plan.plan_digest(sealed))
        self.assertEqual(publish_plan.verify_digest(sealed, digest), digest)

        tampered = copy.deepcopy(sealed)
        tampered["actions"][0]["reply_body"] = "Different reply"
        with self.assertRaisesRegex(ValueError, "stored plan_digest"):
            publish_plan.verify_digest(tampered, digest)

    def test_needs_human_cannot_resolve(self) -> None:
        plan = draft_plan()
        plan["actions"][0]["verdict"] = "needs-human"
        with self.assertRaisesRegex(ValueError, "needs-human"):
            publish_plan.seal_plan(plan)

    def test_non_thread_surface_cannot_resolve(self) -> None:
        plan = draft_plan()
        plan["actions"][1]["resolve"] = True
        with self.assertRaisesRegex(ValueError, "non-thread"):
            publish_plan.seal_plan(plan)

    def test_all_actions_are_preflighted_before_first_mutation(self) -> None:
        plan = draft_plan()
        plan["actions"].insert(
            1,
            {
                "action_id": "second-thread",
                "surface": "review-thread",
                "source_id": "PRRC_kwDOcomment2",
                "thread_id": "PRRT_kwDOthread2",
                "verdict": "replied",
                "reply_body": "Thanks, answered above.",
                "resolve": False,
            },
        )
        sealed = publish_plan.seal_plan(plan)
        client = FakeClient()
        client.fail_thread = "PRRT_kwDOthread2"

        with self.assertRaisesRegex(ValueError, "wrong PR"):
            publish_plan.publish(
                sealed,
                expected_digest=sealed["plan_digest"],
                client=client,
                confirm_no_concurrent_publisher=True,
            )

        self.assertNotIn("reply", [name for name, _value in client.calls])
        self.assertNotIn("resolve", [name for name, _value in client.calls])
        self.assertNotIn("comment", [name for name, _value in client.calls])

    def test_publish_requires_single_publisher_confirmation(self) -> None:
        sealed = publish_plan.seal_plan(draft_plan())
        client = FakeClient()

        with self.assertRaisesRegex(ValueError, "no concurrent publisher"):
            publish_plan.publish(
                sealed,
                expected_digest=sealed["plan_digest"],
                client=client,
                confirm_no_concurrent_publisher=False,
            )

        self.assertEqual(client.calls, [])

    def test_head_change_after_full_preflight_is_refused_before_mutation(self) -> None:
        sealed = publish_plan.seal_plan(draft_plan())
        client = FakeClient()
        client.head_changes_on_second_verify = True

        with self.assertRaisesRegex(ValueError, "head changed"):
            publish_plan.publish(
                sealed,
                expected_digest=sealed["plan_digest"],
                client=client,
                confirm_no_concurrent_publisher=True,
            )

        self.assertEqual(
            [name for name, _value in client.calls],
            ["verify", "thread-state", "source-state", "verify"],
        )
        self.assertNotIn("reply", [name for name, _value in client.calls])
        self.assertNotIn("resolve", [name for name, _value in client.calls])
        self.assertNotIn("comment", [name for name, _value in client.calls])

    def test_publish_posts_exact_plan_and_resolves_only_approved_thread(self) -> None:
        sealed = publish_plan.seal_plan(draft_plan())
        client = FakeClient()
        result = publish_plan.publish(
            sealed,
            expected_digest=sealed["plan_digest"],
            client=client,
            confirm_no_concurrent_publisher=True,
        )

        self.assertIn(("reply", "PRRT_kwDOthread1"), client.calls)
        self.assertIn(("resolve", "PRRT_kwDOthread1"), client.calls)
        self.assertIn(("comment", "PR_kwDOabc123"), client.calls)
        self.assertTrue(client.assert_marker)
        self.assertEqual(result["plan_digest"], sealed["plan_digest"])

    def test_retry_skips_existing_reply_but_finishes_resolution(self) -> None:
        plan = draft_plan()
        plan["actions"] = [plan["actions"][0]]
        sealed = publish_plan.seal_plan(plan)
        client = FakeClient()
        client.thread_states["PRRT_kwDOthread1"] = {
            "resolved": False,
            "reply_exists": True,
        }
        result = publish_plan.publish(
            sealed,
            expected_digest=sealed["plan_digest"],
            client=client,
            confirm_no_concurrent_publisher=True,
        )

        self.assertNotIn(("reply", "PRRT_kwDOthread1"), client.calls)
        self.assertIn(("resolve", "PRRT_kwDOthread1"), client.calls)
        self.assertEqual(
            [item["status"] for item in result["results"]],
            ["already-posted", "resolved"],
        )

    def test_serial_retry_from_another_account_skips_existing_reply(self) -> None:
        plan = draft_plan()
        plan["actions"] = [plan["actions"][0]]
        plan["actions"][0]["resolve"] = False
        sealed = publish_plan.seal_plan(plan)
        item_marker = publish_plan.marker(
            sealed["plan_digest"],
            plan["actions"][0]["action_id"],
        )
        target = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "id": plan["pr_node_id"],
                        "state": "OPEN",
                        "headRefOid": plan["head_oid"],
                    }
                }
            }
        }
        thread = {
            "data": {
                "node": {
                    "id": plan["actions"][0]["thread_id"],
                    "isResolved": False,
                    "pullRequest": {"id": plan["pr_node_id"]},
                    "comments": {
                        "nodes": [
                            {
                                "id": plan["actions"][0]["source_id"],
                                "body": "Original review comment",
                            },
                            {
                                "id": "PRRC_old_account_reply",
                                "body": item_marker,
                                "author": {"login": "former-maintainer"},
                            },
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                }
            }
        }
        client = PagingGhClient([target, thread])

        result = publish_plan.publish(
            sealed,
            expected_digest=sealed["plan_digest"],
            client=client,
            confirm_no_concurrent_publisher=True,
        )

        self.assertTrue(result["complete"])
        self.assertEqual(
            result["results"],
            [{"action_id": "null-guard", "status": "already-posted"}],
        )
        self.assertEqual(client.responses, [])

    def test_failure_after_mutation_returns_structured_partial_result(self) -> None:
        plan = draft_plan()
        plan["actions"] = [plan["actions"][0]]
        sealed = publish_plan.seal_plan(plan)
        client = FakeClient()
        client.fail_mutation = ("resolve", "PRRT_kwDOthread1")

        result = publish_plan.publish(
            sealed,
            expected_digest=sealed["plan_digest"],
            client=client,
            confirm_no_concurrent_publisher=True,
        )

        self.assertFalse(result["complete"])
        self.assertEqual(
            [item["status"] for item in result["results"]],
            ["posted", "failed"],
        )
        self.assertEqual(result["results"][-1]["action_id"], "null-guard")
        self.assertIn("resolve failed", result["error"])

    def test_thread_retry_marker_from_another_account_is_found_across_pages(self) -> None:
        marker = "<!-- overclock-pr-feedback:digest:action -->"
        first = {
            "data": {
                "node": {
                    "id": "PRRT_thread",
                    "isResolved": False,
                    "pullRequest": {"id": "PR_pull"},
                    "comments": {
                        "nodes": [
                            {
                                "id": "PRRC_source",
                                "body": "review",
                                "author": {"login": "reviewer"},
                            }
                        ],
                        "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
                    },
                }
            }
        }
        second = {
            "data": {
                "node": {
                    "id": "PRRT_thread",
                    "isResolved": False,
                    "pullRequest": {"id": "PR_pull"},
                    "comments": {
                        "nodes": [
                            {
                                "id": "PRRC_reply",
                                "body": marker,
                                "author": {"login": "former-maintainer"},
                            }
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                }
            }
        }
        client = PagingGhClient([first, second])

        state = client.thread_state(
            "PRRT_thread",
            "PRRC_source",
            "PR_pull",
            marker,
        )

        self.assertTrue(state["reply_exists"])
        self.assertEqual(client.fields_seen, [{"id": "PRRT_thread"}, {
            "id": "PRRT_thread",
            "cursor": "cursor-1",
        }])

    def test_non_thread_retry_marker_from_another_account_is_found_across_pages(
        self,
    ) -> None:
        marker = "<!-- overclock-pr-feedback:digest:action -->"
        source = {
            "data": {
                "node": {
                    "__typename": "IssueComment",
                    "id": "IC_source",
                    "pullRequest": {"id": "PR_pull"},
                }
            }
        }
        first = {
            "data": {
                "node": {
                    "comments": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
                    }
                }
            }
        }
        second = {
            "data": {
                "node": {
                    "comments": {
                        "nodes": [
                            {
                                "body": marker,
                                "author": {"login": "former-maintainer"},
                            }
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
        client = PagingGhClient([source, first, second])

        exists = client.non_thread_state(
            "pr-comment",
            "IC_source",
            "PR_pull",
            marker,
        )

        self.assertTrue(exists)
        self.assertEqual(len(client.fields_seen), 3)

    def test_non_thread_source_from_another_pr_is_refused_before_comment_scan(self) -> None:
        client = PagingGhClient([
            {
                "data": {
                    "node": {
                        "__typename": "PullRequestReview",
                        "id": "PRR_source",
                        "pullRequest": {"id": "PR_other"},
                    }
                }
            }
        ])
        with self.assertRaisesRegex(ValueError, "does not belong"):
            client.non_thread_state(
                "review-body",
                "PRR_source",
                "PR_pull",
                "<!-- marker -->",
            )
        self.assertEqual(len(client.fields_seen), 1)

    def test_plan_reader_refuses_symlink_and_hardlink(self) -> None:
        sealed = publish_plan.seal_plan(draft_plan())
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "repo"
            root.mkdir()
            outside = base / "outside.json"
            outside.write_text(json.dumps(sealed), encoding="utf-8")
            linked = root / "plan.json"
            linked.symlink_to(outside)
            with self.assertRaises(OSError):
                publish_plan.read_plan(linked, root=root, sealed=True)

            linked.unlink()
            linked.write_text(json.dumps(sealed), encoding="utf-8")
            os.link(linked, root / "second.json")
            with self.assertRaisesRegex(ValueError, "hard link"):
                publish_plan.read_plan(linked, root=root, sealed=True)

    def test_seal_writer_never_replaces_existing_output(self) -> None:
        sealed = publish_plan.seal_plan(draft_plan())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "sealed.json"
            output.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "refusing to replace"):
                publish_plan.write_new_plan(output, sealed, root=root)
            self.assertEqual(output.read_text(encoding="utf-8"), "keep")

    def test_seal_writer_creates_single_link_private_file(self) -> None:
        sealed = publish_plan.seal_plan(draft_plan())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "sealed.json"
            publish_plan.write_new_plan(output, sealed, root=root)
            details = output.stat()
            self.assertEqual(details.st_nlink, 1)
            self.assertEqual(details.st_mode & 0o777, 0o600)
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")),
                sealed,
            )


if __name__ == "__main__":
    unittest.main()
