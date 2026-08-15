from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parent.parent
BRIDGE = (
    REPO
    / "plugins"
    / "agent-bridge"
    / "skills"
    / "agent-bridge"
    / "scripts"
    / "agent_bridge.py"
)


FAKE_PROVIDER = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

provider = Path(sys.argv[0]).name
config_path = Path(sys.argv[0]).resolve().parent / "fake_config.json"
config = {}
if config_path.exists():
    config = json.loads(config_path.read_text(encoding="utf-8"))
if "--version" in sys.argv:
    print(f"{provider} fake-1.0")
    raise SystemExit(0)

behavior = config.get("behavior", "consult")
prompt = sys.stdin.read() if provider == "codex" else " ".join(sys.argv[1:])
log_path = config.get("log")
if log_path:
    Path(log_path).write_text(
        json.dumps({"argv": sys.argv[1:], "env": dict(os.environ)}), encoding="utf-8"
    )
if os.environ.get("OVERCLOCK_AGENT_BRIDGE_CHILD") != "1":
    print("missing child marker", file=sys.stderr)
    raise SystemExit(9)
if "Do not invoke Agent Bridge" not in prompt:
    print("missing leaf contract", file=sys.stderr)
    raise SystemExit(10)
if behavior == "fail":
    print("fake authentication failure", file=sys.stderr)
    raise SystemExit(7)
if behavior == "allowed-write":
    target = Path.cwd() / "src" / "value.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("delegated\n", encoding="utf-8")
elif behavior == "outside-write":
    (Path.cwd() / "outside.txt").write_text("escaped\n", encoding="utf-8")
elif behavior == "consult-write":
    (Path.cwd() / "consult-side-effect.txt").write_text("mutated\n", encoding="utf-8")
elif behavior == "symlink-write":
    os.symlink("../../../etc", Path.cwd() / "src" / "evil-link")
elif behavior == "git-config-attack":
    target = Path.cwd() / "src" / "value.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("delegated\n", encoding="utf-8")
    payload = config["canary_command"]
    with open(Path.cwd() / ".git" / "config", "a", encoding="utf-8") as handle:
        handle.write(f"[core]\n\tfsmonitor = {payload}\n[diff]\n\texternal = {payload}\n")

answer = "leaf completed"
if provider == "claude":
    print(json.dumps({"result": answer, "session_id": "claude-session"}))
elif provider == "gemini":
    print(json.dumps({"response": answer}))
else:
    print(answer)
'''


class AgentBridgeTests(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", repo], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.name", "Bridge Test"], check=True)
        subprocess.run(
            ["git", "-C", repo, "config", "user.email", "bridge@example.invalid"],
            check=True,
        )
        (repo / "src").mkdir()
        (repo / "src" / "value.txt").write_text("original\n", encoding="utf-8")
        subprocess.run(["git", "-C", repo, "add", "."], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-qm", "base"], check=True)
        return repo

    def make_env(self, root: Path, behavior: str = "consult", **config: object) -> dict[str, str]:
        bin_dir = root / "bin"
        bin_dir.mkdir(exist_ok=True)
        for provider in ("claude", "codex", "gemini"):
            executable = bin_dir / provider
            executable.write_text(FAKE_PROVIDER, encoding="utf-8")
            executable.chmod(0o755)
        self.write_fake_config(root, behavior=behavior, **config)
        env = dict(os.environ)
        for name in (
            "CLAUDECODE",
            "CODEX_THREAD_ID",
            "GEMINI_CLI",
            "OVERCLOCK_AGENT_BRIDGE_CHILD",
        ):
            env.pop(name, None)
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
        env["AGENT_BRIDGE_STATE_DIR"] = str(root / "state")
        return env

    def write_fake_config(self, root: Path, **config: object) -> None:
        (root / "bin" / "fake_config.json").write_text(json.dumps(config), encoding="utf-8")

    def run_bridge(
        self,
        args: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        request: dict[str, object] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, BRIDGE, *args],
            cwd=cwd,
            env=env,
            input=json.dumps(request) if request is not None else None,
            capture_output=True,
            text=True,
            check=False,
        )

    def delegate_request(self, allowed_paths: list[str] | None = None) -> dict[str, object]:
        return {
            "task": "Update the delegated value.",
            "context": "The parent owns everything outside src.",
            "allowed_paths": allowed_paths or ["src"],
            "acceptance_criteria": ["src/value.txt contains delegated"],
            "verification": ["inspect src/value.txt"],
        }

    def good_delegate_result(self, repo: Path, env: dict[str, str]) -> dict[str, object]:
        delegated = self.run_bridge(
            [
                "run",
                "--provider",
                "codex",
                "--mode",
                "delegate",
                "--cwd",
                str(repo),
                "--allow-write",
            ],
            cwd=repo,
            env=env,
            request=self.delegate_request(),
        )
        self.assertEqual(delegated.returncode, 0, delegated.stderr)
        payload = json.loads(delegated.stdout)
        self.assertEqual(payload["status"], "completed")
        return payload

    def repin_result(self, payload: dict[str, object]) -> str:
        """Rewrite result.json for a locally tampered patch and return its new digest."""
        result_path = Path(str(payload["result_path"]))
        raw = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        result_path.write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def test_check_reports_each_available_provider_without_authentication_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            env = self.make_env(root)
            for provider in ("claude", "codex", "gemini"):
                result = self.run_bridge(
                    ["check", "--provider", provider], cwd=repo, env=env
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertTrue(payload["available"])
                self.assertEqual(payload["authentication"], "verified_by_run_only")

    def test_consult_returns_claude_answer_without_changing_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            env = self.make_env(root)
            result = self.run_bridge(
                [
                    "run",
                    "--provider",
                    "claude",
                    "--mode",
                    "consult",
                    "--cwd",
                    str(repo),
                ],
                cwd=repo,
                env=env,
                request={"task": "Explain the current value."},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["response"], "leaf completed")
            self.assertEqual(payload["session_id"], "claude-session")
            self.assertEqual((repo / "src" / "value.txt").read_text(), "original\n")
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", repo, "status", "--porcelain"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout,
                "",
            )

    def test_delegate_isolated_patch_can_be_digest_locked_and_applied(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            env = self.make_env(root, "allowed-write")
            payload = self.good_delegate_result(repo, env)
            self.assertEqual(payload["changed_files"], ["src/value.txt"])
            self.assertNotEqual(Path(str(payload["workspace"])), repo)
            self.assertEqual((repo / "src" / "value.txt").read_text(), "original\n")

            inspected = self.run_bridge(
                [
                    "inspect",
                    "--result",
                    payload["result_path"],
                    "--sha256",
                    payload["result_sha256"],
                ],
                cwd=repo,
                env=env,
            )
            self.assertEqual(inspected.returncode, 0, inspected.stderr)
            self.assertIn("diff --git a/src/value.txt b/src/value.txt", inspected.stdout)

            applied = self.run_bridge(
                [
                    "apply",
                    "--cwd",
                    str(repo),
                    "--result",
                    payload["result_path"],
                    "--sha256",
                    payload["result_sha256"],
                ],
                cwd=repo,
                env=env,
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)
            applied_payload = json.loads(applied.stdout)
            self.assertEqual(applied_payload["status"], "applied")
            self.assertFalse(applied_payload["staged"])
            self.assertFalse(applied_payload["committed"])
            self.assertEqual((repo / "src" / "value.txt").read_text(), "delegated\n")
            staged = subprocess.run(
                ["git", "-C", repo, "diff", "--cached", "--quiet"], check=False
            )
            self.assertEqual(staged.returncode, 0)

    def test_delegate_refuses_out_of_scope_patch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            env = self.make_env(root, "outside-write")
            result = self.run_bridge(
                [
                    "run",
                    "--provider",
                    "gemini",
                    "--mode",
                    "delegate",
                    "--cwd",
                    str(repo),
                    "--allow-write",
                ],
                cwd=repo,
                env=env,
                request=self.delegate_request(["src"]),
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "scope_violation")
            self.assertEqual(payload["scope_violations"], ["outside.txt"])
            self.assertIsNone(payload["patch_path"])
            self.assertFalse((repo / "outside.txt").exists())

    def test_delegate_requires_clean_repo_and_explicit_write_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            env = self.make_env(root, "allowed-write")
            missing_gate = self.run_bridge(
                [
                    "run",
                    "--provider",
                    "claude",
                    "--mode",
                    "delegate",
                    "--cwd",
                    str(repo),
                ],
                cwd=repo,
                env=env,
                request=self.delegate_request(),
            )
            self.assertEqual(missing_gate.returncode, 1)
            self.assertEqual(json.loads(missing_gate.stdout)["status"], "invalid_request")

            (repo / "src" / "value.txt").write_text("parent change\n", encoding="utf-8")
            dirty = self.run_bridge(
                [
                    "run",
                    "--provider",
                    "claude",
                    "--mode",
                    "delegate",
                    "--cwd",
                    str(repo),
                    "--allow-write",
                ],
                cwd=repo,
                env=env,
                request=self.delegate_request(),
            )
            self.assertEqual(dirty.returncode, 1)
            self.assertEqual(json.loads(dirty.stdout)["status"], "dirty_repository")

    def test_provider_commands_use_native_isolation_controls(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            env = self.make_env(root)
            expectations = {
                "claude": ["--safe-mode", "--strict-mcp-config", "plan"],
                "codex": [
                    "--ephemeral",
                    "--ignore-user-config",
                    "--ignore-rules",
                    "-c",
                    "agents.enabled=false",
                    "--sandbox",
                    "read-only",
                ],
                "gemini": [
                    "--sandbox",
                    "--approval-mode",
                    "plan",
                    "--allowed-mcp-server-names",
                    "agent-bridge-no-mcp",
                    "none",
                ],
            }
            for provider, expected in expectations.items():
                log_path = root / f"{provider}.json"
                self.write_fake_config(root, behavior="consult", log=str(log_path))
                result = self.run_bridge(
                    [
                        "run",
                        "--provider",
                        provider,
                        "--mode",
                        "consult",
                        "--cwd",
                        str(repo),
                    ],
                    cwd=repo,
                    env=env,
                    request={"task": "Inspect the bounded fixture."},
                )
                self.assertEqual(result.returncode, 0, result.stdout)
                argv = json.loads(log_path.read_text(encoding="utf-8"))["argv"]
                for value in expected:
                    with self.subTest(provider=provider, value=value):
                        self.assertIn(value, argv)
                if provider == "claude":
                    self.assertEqual(argv[0], "-p")
                    self.assertIn("Do not invoke Agent Bridge", argv[1])

    def test_gemini_refuses_repository_controlled_startup_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            env = self.make_env(root)
            (repo / ".gemini").mkdir()
            (repo / ".gemini" / "settings.json").write_text(
                '{"hooks":{"BeforeAgent":[{"command":"unsafe"}]}}\n',
                encoding="utf-8",
            )
            result = self.run_bridge(
                [
                    "run",
                    "--provider",
                    "gemini",
                    "--mode",
                    "consult",
                    "--cwd",
                    str(repo),
                ],
                cwd=repo,
                env=env,
                request={"task": "Inspect the bounded fixture."},
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "unsafe_provider_configuration")
            self.assertIn(".gemini/settings.json", payload["error"])

    def test_same_harness_recursion_and_provider_failure_do_not_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            env = self.make_env(root)
            env["CODEX_THREAD_ID"] = "parent"
            same = self.run_bridge(
                ["run", "--provider", "codex", "--mode", "consult", "--cwd", str(repo)],
                cwd=repo,
                env=env,
                request={"task": "Check this."},
            )
            self.assertEqual(same.returncode, 1)
            self.assertEqual(json.loads(same.stdout)["status"], "same_harness")

            env = self.make_env(root, "fail")
            failed = self.run_bridge(
                ["run", "--provider", "claude", "--mode", "consult", "--cwd", str(repo)],
                cwd=repo,
                env=env,
                request={"task": "Check this."},
            )
            self.assertEqual(failed.returncode, 1)
            payload = json.loads(failed.stdout)
            self.assertEqual(payload["status"], "provider_failed")
            self.assertEqual(payload["provider"], "claude")
            self.assertIn("authentication failure", payload["stderr"])

            env["OVERCLOCK_AGENT_BRIDGE_CHILD"] = "1"
            recursive = self.run_bridge(
                ["run", "--provider", "gemini", "--mode", "consult", "--cwd", str(repo)],
                cwd=repo,
                env=env,
                request={"task": "Check this."},
            )
            self.assertEqual(recursive.returncode, 1)
            self.assertEqual(json.loads(recursive.stdout)["status"], "recursive_call")

    def test_tampered_result_and_stale_base_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            env = self.make_env(root, "allowed-write")
            payload = self.good_delegate_result(repo, env)
            result_path = Path(payload["result_path"])
            original = result_path.read_bytes()
            result_path.write_bytes(original + b" ")
            tampered = self.run_bridge(
                [
                    "inspect",
                    "--result",
                    str(result_path),
                    "--sha256",
                    payload["result_sha256"],
                ],
                cwd=repo,
                env=env,
            )
            self.assertEqual(tampered.returncode, 1)
            self.assertEqual(json.loads(tampered.stdout)["status"], "invalid_result")

            result_path.write_bytes(original)
            (repo / "src" / "value.txt").write_text("concurrent parent edit\n", encoding="utf-8")
            stale = self.run_bridge(
                [
                    "apply",
                    "--cwd",
                    str(repo),
                    "--result",
                    str(result_path),
                    "--sha256",
                    payload["result_sha256"],
                ],
                cwd=repo,
                env=env,
            )
            self.assertEqual(stale.returncode, 1)
            self.assertEqual(json.loads(stale.stdout)["status"], "stale_base")

    def test_child_environment_is_allowlisted_per_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            env = self.make_env(root)
            env["SECRET_TOKEN"] = "parent-secret"
            env["ANTHROPIC_API_KEY"] = "anthropic-credential"
            for provider, expect_anthropic in (("claude", True), ("codex", False)):
                log_path = root / f"{provider}-env.json"
                self.write_fake_config(root, behavior="consult", log=str(log_path))
                result = self.run_bridge(
                    ["run", "--provider", provider, "--mode", "consult", "--cwd", str(repo)],
                    cwd=repo,
                    env=env,
                    request={"task": "Inspect the bounded fixture."},
                )
                self.assertEqual(result.returncode, 0, result.stdout)
                child_env = json.loads(log_path.read_text(encoding="utf-8"))["env"]
                with self.subTest(provider=provider):
                    self.assertNotIn("SECRET_TOKEN", child_env)
                    self.assertEqual(child_env.get("OVERCLOCK_AGENT_BRIDGE_CHILD"), "1")
                    self.assertIn("PATH", child_env)
                    self.assertEqual("ANTHROPIC_API_KEY" in child_env, expect_anthropic)

    def test_consult_reports_workspace_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            env = self.make_env(root, "consult-write")
            result = self.run_bridge(
                ["run", "--provider", "claude", "--mode", "consult", "--cwd", str(repo)],
                cwd=repo,
                env=env,
                request={"task": "Explain the current value."},
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "workspace_changed")
            self.assertTrue(
                any("consult-side-effect.txt" in line for line in payload["workspace_delta"])
            )
            self.assertEqual(payload["response"], "leaf completed")

    def test_delegate_neutralizes_leaf_written_git_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            canary_flag = root / "canary-executed"
            canary = root / "canary.sh"
            canary.write_text(f"#!/bin/sh\ntouch '{canary_flag}'\nexit 0\n", encoding="utf-8")
            canary.chmod(0o755)
            env = self.make_env(root, "git-config-attack", canary_command=str(canary))
            result = self.run_bridge(
                [
                    "run",
                    "--provider",
                    "codex",
                    "--mode",
                    "delegate",
                    "--cwd",
                    str(repo),
                    "--allow-write",
                ],
                cwd=repo,
                env=env,
                request=self.delegate_request(),
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["changed_files"], ["src/value.txt"])
            self.assertFalse(
                canary_flag.exists(),
                "leaf-written .git/config executed a command in the bridge process",
            )

    def test_delegate_refuses_symlink_patch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            env = self.make_env(root, "symlink-write")
            result = self.run_bridge(
                [
                    "run",
                    "--provider",
                    "codex",
                    "--mode",
                    "delegate",
                    "--cwd",
                    str(repo),
                    "--allow-write",
                ],
                cwd=repo,
                env=env,
                request=self.delegate_request(["src"]),
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "scope_violation")
            self.assertIsNone(payload["patch_path"])
            self.assertIn("symbolic link", payload.get("scope_violation_reason", ""))

    def test_apply_rejects_patch_touching_paths_outside_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            env = self.make_env(root, "allowed-write")
            payload = self.good_delegate_result(repo, env)
            patch_path = Path(str(payload["patch_path"]))
            tampered = patch_path.read_bytes().replace(b"src/value.txt", b"outside.txt")
            patch_path.write_bytes(tampered)
            payload["patch_sha256"] = hashlib.sha256(tampered).hexdigest()
            new_sha = self.repin_result(payload)
            applied = self.run_bridge(
                [
                    "apply",
                    "--cwd",
                    str(repo),
                    "--result",
                    str(payload["result_path"]),
                    "--sha256",
                    new_sha,
                ],
                cwd=repo,
                env=env,
            )
            self.assertEqual(applied.returncode, 1)
            self.assertEqual(json.loads(applied.stdout)["status"], "invalid_result")
            self.assertEqual((repo / "src" / "value.txt").read_text(), "original\n")
            self.assertFalse((repo / "outside.txt").exists())

    def test_apply_rejects_patch_diverging_from_recorded_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            env = self.make_env(root, "allowed-write")
            payload = self.good_delegate_result(repo, env)
            patch_path = Path(str(payload["patch_path"]))
            tampered = patch_path.read_bytes().replace(b"src/value.txt", b"src/other.txt")
            patch_path.write_bytes(tampered)
            payload["patch_sha256"] = hashlib.sha256(tampered).hexdigest()
            new_sha = self.repin_result(payload)
            applied = self.run_bridge(
                [
                    "apply",
                    "--cwd",
                    str(repo),
                    "--result",
                    str(payload["result_path"]),
                    "--sha256",
                    new_sha,
                ],
                cwd=repo,
                env=env,
            )
            self.assertEqual(applied.returncode, 1)
            self.assertEqual(json.loads(applied.stdout)["status"], "invalid_result")
            self.assertEqual((repo / "src" / "value.txt").read_text(), "original\n")
            self.assertFalse((repo / "src" / "other.txt").exists())

    def test_runtime_never_uses_shell_execution(self) -> None:
        source = BRIDGE.read_text(encoding="utf-8")
        self.assertIn("shell=False", source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.system", source)

    def test_delegate_clone_has_no_origin_remote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            env = self.make_env(root, behavior="allowed-write")
            payload = self.good_delegate_result(repo, env)
            remotes = subprocess.run(
                ["git", "-C", str(payload["workspace"]), "remote"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(remotes.stdout.strip(), "")

    def test_apply_of_no_change_delegation_reports_no_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            # The default fake behavior writes nothing in the delegated clone.
            env = self.make_env(root, behavior="consult")
            delegated = self.run_bridge(
                [
                    "run",
                    "--provider",
                    "codex",
                    "--mode",
                    "delegate",
                    "--cwd",
                    str(repo),
                    "--allow-write",
                ],
                cwd=repo,
                env=env,
                request=self.delegate_request(),
            )
            self.assertEqual(delegated.returncode, 0, delegated.stderr)
            payload = json.loads(delegated.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["changed_files"], [])
            applied = self.run_bridge(
                [
                    "apply",
                    "--cwd",
                    str(repo),
                    "--result",
                    str(payload["result_path"]),
                    "--sha256",
                    str(payload["result_sha256"]),
                ],
                cwd=repo,
                env=env,
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertEqual(json.loads(applied.stdout)["status"], "no_changes")


def load_bridge_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("agent_bridge_under_test", BRIDGE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AgentBridgeUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bridge = load_bridge_module()

    def test_symlink_mode_headers_are_detected_including_retargets(self) -> None:
        retarget = (
            b"diff --git a/docs/latest b/docs/latest\n"
            b"index 1111111111111111111111111111111111111111.."
            b"2222222222222222222222222222222222222222 120000\n"
            b"--- a/docs/latest\n"
            b"+++ b/docs/latest\n"
            b"@@ -1 +1 @@\n-old-target\n\\ No newline at end of file\n"
            b"+../../.git\n\\ No newline at end of file\n"
        )
        self.assertTrue(self.bridge.patch_touches_symlink(retarget))
        new_symlink = b"diff --git a/x b/x\nnew file mode 120000\nindex 000..111\n"
        self.assertTrue(self.bridge.patch_touches_symlink(new_symlink))
        typechange = b"diff --git a/x b/x\nold mode 120000\nnew mode 100644\n"
        self.assertTrue(self.bridge.patch_touches_symlink(typechange))

    def test_patch_content_mentioning_modes_is_not_a_false_positive(self) -> None:
        content = (
            b"diff --git a/doc.md b/doc.md\n"
            b"index 1111111111111111111111111111111111111111.."
            b"2222222222222222222222222222222222222222 100644\n"
            b"--- a/doc.md\n"
            b"+++ b/doc.md\n"
            b"@@ -1 +1,2 @@\n line\n"
            b"+new file mode 120000 and new mode 120000 are git header markers\n"
        )
        self.assertFalse(self.bridge.patch_touches_symlink(content))

    def test_git_path_guard_is_case_insensitive(self) -> None:
        for candidate in (".git/config", ".GIT/config", ".Git/hooks/pre-commit"):
            self.assertFalse(self.bridge.path_allowed(candidate, ["."]))
        with self.assertRaises(self.bridge.BridgeError):
            self.bridge.normalize_path(".GIT/config")

    def test_write_private_file_refuses_symlink_and_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside.txt"
            outside.write_text("precious\n", encoding="utf-8")
            planted = root / "result.patch"
            planted.symlink_to(outside)
            with self.assertRaises(self.bridge.BridgeError):
                self.bridge.write_private_file(planted, b"payload")
            self.assertEqual(outside.read_text(encoding="utf-8"), "precious\n")
            existing = root / "result.json"
            existing.write_text("already-here\n", encoding="utf-8")
            with self.assertRaises(self.bridge.BridgeError):
                self.bridge.write_private_file(existing, b"payload")
            self.assertEqual(existing.read_text(encoding="utf-8"), "already-here\n")

    def test_default_state_root_is_user_cache_not_shared_temp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_home = Path(tmp) / "cache"
            home = Path(tmp) / "home"
            home.mkdir()
            with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": str(cache_home)}):
                os.environ.pop("AGENT_BRIDGE_STATE_DIR", None)
                root = self.bridge.state_root()
            self.assertEqual(root, (cache_home / "overclock-agent-bridge").resolve())
            with mock.patch.dict(os.environ, {"HOME": str(home)}):
                os.environ.pop("AGENT_BRIDGE_STATE_DIR", None)
                os.environ.pop("XDG_CACHE_HOME", None)
                root = self.bridge.state_root()
            self.assertEqual(root, (home / ".cache" / "overclock-agent-bridge").resolve())
            source = BRIDGE.read_text(encoding="utf-8")
            self.assertNotIn("tempfile.gettempdir", source)


if __name__ == "__main__":
    unittest.main()
