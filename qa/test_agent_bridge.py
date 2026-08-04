from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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
if "--version" in sys.argv:
    print(f"{provider} fake-1.0")
    raise SystemExit(0)

behavior = os.environ.get("FAKE_BRIDGE_BEHAVIOR", "consult")
prompt = sys.stdin.read() if provider == "codex" else " ".join(sys.argv[1:])
log_path = os.environ.get("FAKE_BRIDGE_LOG")
if log_path:
    Path(log_path).write_text(json.dumps({"argv": sys.argv[1:]}), encoding="utf-8")
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

    def make_env(self, root: Path, behavior: str = "consult") -> dict[str, str]:
        bin_dir = root / "bin"
        bin_dir.mkdir(exist_ok=True)
        for provider in ("claude", "codex", "gemini"):
            executable = bin_dir / provider
            executable.write_text(FAKE_PROVIDER, encoding="utf-8")
            executable.chmod(0o755)
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
        env["FAKE_BRIDGE_BEHAVIOR"] = behavior
        return env

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
            self.assertEqual(payload["changed_files"], ["src/value.txt"])
            self.assertNotEqual(Path(payload["workspace"]), repo)
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
                "codex": ["--ephemeral", "--sandbox", "read-only"],
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
                provider_env = dict(env)
                provider_env["FAKE_BRIDGE_LOG"] = str(log_path)
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
                    env=provider_env,
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
            delegated = self.run_bridge(
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
                request=self.delegate_request(),
            )
            payload = json.loads(delegated.stdout)
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

    def test_runtime_never_uses_shell_execution(self) -> None:
        source = BRIDGE.read_text(encoding="utf-8")
        self.assertIn("shell=False", source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.system", source)


if __name__ == "__main__":
    unittest.main()
