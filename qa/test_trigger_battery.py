from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from read_eval_api_key import read_key  # noqa: E402
from trigger_battery import (  # noqa: E402
    LiveEvalRuntime,
    build_claude_command,
    contract_file_exists,
    current_description,
    isolated_claude_environment,
    live_eval_runtime,
    materialize_fixture,
    prompt_contract,
    quality_metrics,
    result_artifact_name,
    result_metadata,
    routing_evidence,
    run_prompt,
    score,
    run_streaming_command,
    row_passes,
    selected_skill,
    selected_skills,
    swap_description,
    threshold_failures,
    validate_battery_install_modes,
    validate_battery_prompt_contracts,
    write_private_api_key,
)

REPO = Path(__file__).resolve().parents[1]


class TriggerBatteryTest(unittest.TestCase):
    def test_result_artifacts_are_namespaced_by_distribution(self) -> None:
        self.assertEqual(
            result_artifact_name(
                Path("/repo/plugins/session-memory/skills/lessons-learned"),
                "lessons-learned",
                "skill",
            ),
            "session-memory-lessons-learned-skill.results.json",
        )
        self.assertEqual(
            result_artifact_name(
                Path("/repo/plugins/learning-loop/skills/lessons-learned"),
                "lessons-learned",
                "plugin",
            ),
            "learning-loop-lessons-learned-plugin.results.json",
        )

    def test_every_battery_declares_required_install_matrix(self) -> None:
        errors: list[str] = []
        for battery_path in sorted((REPO / "qa/trigger-battery").glob("*.json")):
            battery = json.loads(battery_path.read_text(encoding="utf-8"))
            skill = battery["skill"]
            plugin = battery.get("plugin")
            if plugin:
                skill_dir = REPO / "plugins" / plugin / "skills" / skill
            else:
                matches = list((REPO / "plugins").glob(f"*/skills/{skill}"))
                if len(matches) != 1:
                    errors.append(f"{battery_path}: ambiguous skill distribution")
                    continue
                skill_dir = matches[0]
            errors.extend(
                f"{battery_path}: {error}"
                for error in validate_battery_install_modes(battery, skill_dir)
            )
            errors.extend(
                f"{battery_path}: {error}"
                for error in validate_battery_prompt_contracts(battery)
            )
        self.assertEqual(errors, [])

    def test_prompt_contract_supports_strings_and_owned_prompt_objects(self) -> None:
        self.assertEqual(
            prompt_contract("plain prompt"),
            ("plain prompt", None, []),
        )
        self.assertEqual(
            prompt_contract(
                {
                    "prompt": "hybrid negative",
                    "allowed_skills": ["groundwork"],
                    "forbidden_skills": ["debugging-discipline"],
                },
                inherited_forbidden=["solutions"],
            ),
            (
                "hybrid negative",
                ["groundwork"],
                ["solutions", "debugging-discipline"],
            ),
        )
        with self.assertRaisesRegex(ValueError, "allows and forbids"):
            prompt_contract(
                {
                    "prompt": "conflict",
                    "allowed_skills": ["groundwork"],
                    "forbidden_skills": ["groundwork"],
                }
            )

    def test_description_is_yaml_safe(self) -> None:
        source = "---\nname: demo\ndescription: old\n---\nbody\n"
        updated = swap_description(source, "Use when prose contains: a risky colon")
        self.assertIn('description: "Use when prose contains: a risky colon"', updated)

    def test_detects_namespaced_skill_tool_call(self) -> None:
        event = {
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use",
                "name": "Skill",
                "input": {"skill": "natural-writing:natural-writing"},
            }]},
        }
        self.assertTrue(selected_skill(json.dumps(event), "natural-writing"))
        self.assertFalse(selected_skill(json.dumps(event), "test-discipline"))
        self.assertEqual(selected_skills(json.dumps(event)), {"natural-writing"})

    def test_detects_command_shaped_skill_tool_call(self) -> None:
        event = {
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use",
                "name": "Skill",
                "input": {
                    "command": "/critical-thinking:critical-thinking inspect this"
                },
            }]},
        }
        self.assertTrue(selected_skill(json.dumps(event), "critical-thinking"))
        self.assertEqual(selected_skills(json.dumps(event)), {"critical-thinking"})

    def test_extracts_result_cost_and_latency(self) -> None:
        events = "\n".join([
            json.dumps({"type": "assistant", "message": {"content": []}}),
            json.dumps({
                "type": "result",
                "duration_ms": 1234,
                "total_cost_usd": 0.0125,
                "num_turns": 3,
            }),
        ])
        self.assertEqual(result_metadata(events), {
            "duration_ms": 1234,
            "total_cost_usd": 0.0125,
            "num_turns": 3,
        })

    def test_filters_routing_init_and_skill_tool_evidence(self) -> None:
        events = "\n".join([
            json.dumps({
                "type": "system",
                "subtype": "init",
                "tools": ["Read", "Skill"],
                "skills": ["demo:critical-thinking"],
                "slash_commands": ["demo:critical-thinking"],
                "apiKeySource": "apiKeyHelper",
            }),
            json.dumps({
                "type": "assistant",
                "message": {"content": [{
                    "type": "tool_use",
                    "name": "Skill",
                    "input": {"command": "demo:critical-thinking", "args": "private"},
                }]},
            }),
        ])
        self.assertEqual(routing_evidence(events), {
            "api_key_sources": ["apiKeyHelper"],
            "available_tools": ["Read", "Skill"],
            "listed_skills": ["demo:critical-thinking"],
            "slash_commands": ["demo:critical-thinking"],
            "skill_tool_events": [{
                "tool_name": "Skill",
                "input_keys": ["args", "command"],
                "selected": "demo:critical-thinking",
            }],
        })

    def test_materializes_safe_fixture_and_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            materialize_fixture(root, {"fixture_files": {"src/demo.js": "ok\n"}})
            self.assertEqual((root / "src/demo.js").read_text(), "ok\n")
            with self.assertRaisesRegex(ValueError, "unsafe fixture path"):
                materialize_fixture(root, {"fixture_files": {"../escape": "bad"}})

    def test_contract_detector_is_root_confined_and_no_follow(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work = root / "work"
            outside = root / "outside"
            work.mkdir()
            outside.mkdir()
            (work / "contract.md").write_text("ok\n", encoding="utf-8")
            (outside / "secret.md").write_text("secret\n", encoding="utf-8")
            (work / "escape").symlink_to(outside, target_is_directory=True)

            self.assertTrue(contract_file_exists(work, "contract.md"))
            self.assertFalse(contract_file_exists(work, "missing.md"))
            self.assertFalse(contract_file_exists(work, "escape/secret.md"))
            with self.assertRaisesRegex(ValueError, "unsafe contract detector"):
                contract_file_exists(work, "../outside/secret.md")

    def test_private_key_file_is_owner_only_and_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            key_file = Path(temp) / "api-key"
            write_private_api_key(key_file, "sk-test")
            self.assertEqual(read_key(key_file), "sk-test")
            self.assertEqual(stat.S_IMODE(key_file.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                write_private_api_key(key_file, "replacement")
            self.assertEqual(read_key(key_file), "sk-test")

    def test_command_and_environment_are_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = LiveEvalRuntime(
                claude_bin=Path("/opt/claude"),
                auth_root=root / "auth",
                key_file=root / "auth/api-key",
                tool_root=root / "tools",
            )
            case_runtime = root / "runtime"
            environment = isolated_claude_environment(runtime, case_runtime)
            command = build_claude_command(
                runtime,
                prompt="route this",
                model="test-model",
                plugin_dirs=[root / "plugins/demo"],
                settings=case_runtime / "settings.json",
            )

            self.assertEqual(environment["HOME"], str(case_runtime / "home"))
            self.assertEqual(
                environment["CLAUDE_CONFIG_DIR"], str(case_runtime / "config")
            )
            self.assertTrue(environment["PATH"].startswith(f"{runtime.tool_root}:"))
            self.assertEqual(environment["CLAUDE_CODE_DISABLE_CLAUDE_MDS"], "1")
            self.assertEqual(environment["CLAUDE_CODE_DISABLE_AUTO_MEMORY"], "1")
            self.assertNotIn("ANTHROPIC_API_KEY", environment)
            self.assertNotIn("ANTHROPIC_AUTH_TOKEN", environment)
            self.assertNotIn("SSH_AUTH_SOCK", environment)
            self.assertEqual(command[0], "/opt/claude")
            self.assertNotIn("--bare", command)
            self.assertEqual(
                command[command.index("--tools") + 1],
                "Bash,Edit,Read,Glob,Grep,Skill,Write",
            )
            self.assertIn("--strict-mcp-config", command)
            self.assertIn("--no-chrome", command)
            self.assertEqual(
                command[command.index("--setting-sources") + 1],
                "",
            )
            self.assertEqual(
                command[command.index("--permission-mode") + 1],
                "dontAsk",
            )
            self.assertEqual(
                command[command.index("--plugin-dir") + 1],
                str(root / "plugins/demo"),
            )

    def test_runtime_requires_explicit_auth_and_creates_private_tools(self) -> None:
        version = SimpleNamespace(returncode=0, stdout="2.1.145 (Claude Code)")
        with (
            patch("trigger_battery.shutil.which", return_value="/opt/claude"),
            patch(
                "trigger_battery.subprocess.run",
                return_value=version,
            ) as run_version,
            patch.dict(
                os.environ,
                {
                    "ANTHROPIC_API_KEY": "sk-test",
                    "ANTHROPIC_AUTH_TOKEN": "token-not-selected",
                },
                clear=True,
            ),
        ):
            with live_eval_runtime() as runtime:
                version_environment = run_version.call_args.kwargs["env"]
                self.assertNotIn("ANTHROPIC_API_KEY", version_environment)
                self.assertNotIn("ANTHROPIC_AUTH_TOKEN", version_environment)
                auth_root = runtime.auth_root
                tool_root = runtime.tool_root
                self.assertEqual(read_key(runtime.key_file), "sk-test")
                self.assertEqual(stat.S_IMODE(auth_root.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE(tool_root.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE((tool_root / "gh").stat().st_mode), 0o700)
                self.assertEqual(
                    stat.S_IMODE(
                        (tool_root / "read_eval_api_key.py").stat().st_mode
                    ),
                    0o700,
                )
                self.assertNotIn("ANTHROPIC_API_KEY", os.environ)
                self.assertNotIn("ANTHROPIC_AUTH_TOKEN", os.environ)
            self.assertFalse(auth_root.exists())
            self.assertFalse(tool_root.exists())

        import trigger_battery

        # A prior successful entry caches the credential for multi-mode
        # batteries; a fresh process (cache empty) must still demand env auth.
        with patch.object(trigger_battery, "_CACHED_CREDENTIAL", None):
            with (
                patch("trigger_battery.shutil.which", return_value="/opt/claude"),
                patch("trigger_battery.subprocess.run", return_value=version),
                patch.dict(os.environ, {}, clear=True),
                self.assertRaisesRegex(RuntimeError, "ANTHROPIC_API_KEY"),
            ):
                with live_eval_runtime():
                    self.fail("missing explicit auth should fail before yielding")

        # Within one process, a second runtime entry (the next install mode)
        # reuses the ingested credential after the environment was scrubbed.
        with patch.object(trigger_battery, "_CACHED_CREDENTIAL", "sk-cached"):
            with (
                patch("trigger_battery.shutil.which", return_value="/opt/claude"),
                patch("trigger_battery.subprocess.run", return_value=version),
                patch.dict(os.environ, {}, clear=True),
            ):
                with live_eval_runtime() as runtime:
                    self.assertEqual(read_key(runtime.key_file), "sk-cached")

    def test_run_prompt_uses_private_settings_and_disposable_plugins(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            auth_root = root / "auth"
            tool_root = root / "tools"
            auth_root.mkdir(mode=0o700)
            tool_root.mkdir(mode=0o700)
            key_file = auth_root / "api-key"
            write_private_api_key(key_file, "sk-test")
            fake_gh = tool_root / "gh"
            fake_gh.write_text("#!/bin/sh\nexit 69\n", encoding="utf-8")
            fake_gh.chmod(0o700)
            key_reader = tool_root / "read_eval_api_key.py"
            key_reader.write_text("# test helper\n", encoding="utf-8")
            key_reader.chmod(0o700)
            runtime = LiveEvalRuntime(
                claude_bin=Path("/opt/claude"),
                auth_root=auth_root,
                key_file=key_file,
                tool_root=tool_root,
            )
            skill_dir = (
                REPO / "plugins/natural-writing/skills/natural-writing"
            )

            def inspect_launch(
                command: list[str],
                cwd: Path,
                skill: str,
                stop_on_skill: bool,
                timeout_seconds: float,
                env: dict[str, str] | None = None,
            ) -> dict:
                self.assertEqual(skill, "natural-writing")
                self.assertTrue(stop_on_skill)
                self.assertGreater(timeout_seconds, 0)
                self.assertIsNotNone(env)
                assert env is not None
                self.assertEqual(
                    env,
                    isolated_claude_environment(runtime, cwd.parent / "runtime"),
                )
                self.assertNotIn("ANTHROPIC_API_KEY", env)
                self.assertFalse(any(str(REPO) in value for value in env.values()))

                settings_path = Path(command[command.index("--settings") + 1])
                settings = json.loads(settings_path.read_text(encoding="utf-8"))
                sandbox = settings["sandbox"]
                self.assertTrue(sandbox["enabled"])
                self.assertTrue(sandbox["failIfUnavailable"])
                self.assertFalse(sandbox["allowUnsandboxedCommands"])
                self.assertEqual(sandbox["network"]["deniedDomains"], ["*"])
                repository = os.path.abspath(REPO)
                self.assertTrue(
                    any(
                        os.path.commonpath([root, repository]) == root
                        for root in sandbox["filesystem"]["denyRead"]
                    ),
                    "repository must be covered by a denied read root",
                )
                self.assertIn(
                    os.path.abspath(auth_root),
                    sandbox["filesystem"]["denyRead"],
                )
                self.assertIn("read_eval_api_key.py", settings["apiKeyHelper"])
                self.assertIn(str(key_file), settings["apiKeyHelper"])
                self.assertNotIn(str(REPO), settings["apiKeyHelper"])
                self.assertNotIn("sk-test", settings_path.read_text(encoding="utf-8"))

                plugin_dirs = [
                    Path(command[index + 1])
                    for index, item in enumerate(command)
                    if item == "--plugin-dir"
                ]
                self.assertEqual(len(plugin_dirs), 1)
                self.assertNotIn(REPO, plugin_dirs[0].parents)
                self.assertTrue(
                    (plugin_dirs[0] / ".claude-plugin/plugin.json").is_file()
                )
                return {
                    "stdout": "",
                    "fired": False,
                    "selected_skills": [],
                    "stopped_early": False,
                    "duration_ms": 1,
                    "total_cost_usd": 0.0,
                    "num_turns": 1,
                }

            with patch(
                "trigger_battery.run_streaming_command",
                side_effect=inspect_launch,
            ):
                result = run_prompt(
                    skill_dir,
                    "natural-writing",
                    current_description(skill_dir),
                    "Polish this release note.",
                    "test-model",
                    {"type": "skill_tool"},
                    {},
                    runtime,
                    timeout_seconds=1,
                )
            self.assertFalse(result["fired"])
            self.assertEqual(result["install_mode"], "plugin")

    def test_route_only_stream_stops_at_skill_selection(self) -> None:
        init = json.dumps({
            "type": "system",
            "subtype": "init",
            "apiKeySource": "apiKeyHelper",
        })
        event = json.dumps({
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use",
                "name": "Skill",
                "input": {"skill": "demo:test-discipline"},
            }]},
        })
        command = [
            sys.executable,
            "-u",
            "-c",
            (
                f"import time; print({init!r}, flush=True); time.sleep(0.1); "
                f"print({event!r}, flush=True); time.sleep(5)"
            ),
        ]
        with tempfile.TemporaryDirectory() as temp:
            result = run_streaming_command(
                command, Path(temp), "test-discipline", True, 2
            )
        self.assertTrue(result["fired"])
        self.assertTrue(result["stopped_early"])
        self.assertLess(result["duration_ms"], 2000)

    def test_stream_timeout_is_infrastructure_error(self) -> None:
        command = [sys.executable, "-u", "-c", "import time; time.sleep(5)"]
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                run_streaming_command(command, Path(temp), "demo", False, 0.05)

    def test_quality_metrics_and_thresholds(self) -> None:
        rows = [
            {"kind": "should", "fired": True, "forbidden_selected": []},
            {"kind": "should", "fired": False},
            {"kind": "should_not", "fired": False},
            {"kind": "should_not", "fired": True},
        ]
        metrics = quality_metrics(rows)
        self.assertEqual(metrics["true_positive"], 1)
        self.assertEqual(metrics["false_negative"], 1)
        self.assertEqual(metrics["true_negative"], 1)
        self.assertEqual(metrics["false_positive"], 1)
        self.assertEqual(metrics["precision"], 0.5)
        self.assertEqual(metrics["recall"], 0.5)
        self.assertEqual(
            threshold_failures(metrics, {"precision": 0.6, "recall": 0.5}),
            ["precision 50.0% < 60.0%"],
        )
        with self.assertRaisesRegex(ValueError, "unknown routing threshold"):
            threshold_failures(metrics, {"f1": 0.9})

    def test_forbidden_positive_route_counts_as_false_negative(self) -> None:
        metrics = quality_metrics(
            [
                {
                    "kind": "should",
                    "fired": True,
                    "ownership_violations": ["lessons-learned"],
                }
            ]
        )
        self.assertEqual(metrics["true_positive"], 0)
        self.assertEqual(metrics["false_negative"], 1)

    def test_unexpected_sibling_fails_negative_but_allowed_sibling_passes(self) -> None:
        unexpected = {
            "kind": "should_not",
            "fired": False,
            "selected_skills": ["solutions"],
            "ownership_violations": ["solutions"],
        }
        allowed = {
            "kind": "should_not",
            "fired": False,
            "selected_skills": ["solutions"],
            "ownership_violations": [],
        }
        self.assertFalse(row_passes(unexpected))
        self.assertTrue(row_passes(allowed))
        metrics = quality_metrics([unexpected, allowed])
        self.assertEqual(metrics["true_negative"], 1)
        self.assertEqual(metrics["false_positive"], 1)

    def test_score_applies_prompt_ownership_contracts_to_negative_rows(self) -> None:
        calls: list[tuple[list[str] | None, list[str] | None]] = []

        def fake_run_prompt(*args, **kwargs):
            calls.append(
                (
                    kwargs.get("allowed_skills"),
                    kwargs.get("forbidden_skills"),
                )
            )
            prompt = args[3]
            is_positive = prompt == "use target"
            return {
                "fired": is_positive,
                "selected_skills": (
                    ["target"] if is_positive else ["allowed-sibling"]
                ),
                "allowed_skills": kwargs.get("allowed_skills"),
                "forbidden_skills": kwargs.get("forbidden_skills") or [],
                "forbidden_selected": [],
                "outside_allowed": [],
                "ownership_violations": [],
                "stopped_early": False,
                "duration_ms": 1,
                "total_cost_usd": 0.0,
                "num_turns": 1,
                "install_mode": "plugin",
            }

        battery = {
            "should_trigger": ["use target"],
            "should_not": [
                {
                    "prompt": "use sibling",
                    "allowed_skills": ["allowed-sibling"],
                    "forbidden_skills": ["wrong-sibling"],
                }
            ],
        }
        with patch("trigger_battery.run_prompt", side_effect=fake_run_prompt):
            result = score(
                Path("/repo/plugins/demo/skills/target"),
                "target",
                "description",
                battery,
                "model",
                object(),  # type: ignore[arg-type]
            )
        self.assertEqual(result["correct"], 2)
        self.assertEqual(
            calls,
            [
                (None, []),
                (["allowed-sibling"], ["wrong-sibling"]),
            ],
        )

    def test_probe_retries_once_then_aborts_naming_the_entry(self) -> None:
        battery = {
            "should_trigger": ["use target", "second probe"],
            "should_not": [],
        }
        good_row = {
            "fired": True,
            "selected_skills": ["target"],
            "allowed_skills": None,
            "forbidden_skills": [],
            "forbidden_selected": [],
            "outside_allowed": [],
            "ownership_violations": [],
            "stopped_early": False,
            "duration_ms": 1,
            "total_cost_usd": 0.0,
            "num_turns": 1,
            "install_mode": "skill",
        }

        def run_score() -> dict:
            return score(
                Path("/repo/plugins/demo/skills/target"),
                "target",
                "description",
                battery,
                "model",
                object(),  # type: ignore[arg-type]
                install_mode="skill",
            )

        with patch(
            "trigger_battery.run_prompt",
            side_effect=[
                RuntimeError("claude exited 1: boom"),
                dict(good_row),
                dict(good_row),
            ],
        ) as flaky:
            result = run_score()
        self.assertEqual(flaky.call_count, 3)
        self.assertEqual(result["correct"], 2)
        self.assertEqual(result["total"], 2)

        with patch(
            "trigger_battery.run_prompt",
            side_effect=RuntimeError("claude exited 1: boom"),
        ) as failing:
            with self.assertRaisesRegex(
                RuntimeError,
                r"probe failed twice \(sample 1/1, install mode skill, "
                r"should\): 'use target': claude exited 1: boom",
            ):
                run_score()
        self.assertEqual(failing.call_count, 2)

    def test_agent_bridge_probe_prompts_are_verbatim_and_bounded(self) -> None:
        """Every constructed routing probe is the battery text itself, never inflated.

        Regression guard for a live agent-bridge run that died with the API's
        "Prompt is too long" mid-battery: drive the harness's own score() ->
        run_prompt() -> build_claude_command() path for every entry in both
        declared install modes and pin the exact `-p` argument each child
        would receive.
        """
        battery_path = REPO / "qa/trigger-battery/agent-bridge.json"
        battery = json.loads(battery_path.read_text(encoding="utf-8"))
        skill = battery["skill"]
        skill_dir = REPO / "plugins" / battery["plugin"] / "skills" / skill
        description = current_description(skill_dir)
        inherited = battery.get("forbidden_skills", [])
        expected = [
            prompt_contract(spec, inherited_forbidden=inherited)[0]
            for spec in battery["should_trigger"]
        ] + [prompt_contract(spec)[0] for spec in battery["should_not"]]

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "auth").mkdir(mode=0o700)
            (root / "tools").mkdir(mode=0o700)
            write_private_api_key(root / "auth/api-key", "sk-test")
            (root / "tools/read_eval_api_key.py").write_text(
                "# test helper\n", encoding="utf-8"
            )
            runtime = LiveEvalRuntime(
                claude_bin=Path("/opt/claude"),
                auth_root=root / "auth",
                key_file=root / "auth/api-key",
                tool_root=root / "tools",
            )
            for install_mode in battery["install_modes"]:
                sent: list[str] = []

                def capture_launch(
                    command: list[str],
                    cwd: Path,
                    skill: str,
                    stop_on_skill: bool,
                    timeout_seconds: float,
                    env: dict[str, str] | None = None,
                ) -> dict:
                    sent.append(command[command.index("-p") + 1])
                    return {
                        "stdout": "",
                        "fired": False,
                        "selected_skills": [],
                        "stopped_early": False,
                        "duration_ms": 1,
                        "total_cost_usd": 0.0,
                        "num_turns": 1,
                    }

                with patch(
                    "trigger_battery.run_streaming_command",
                    side_effect=capture_launch,
                ):
                    score(
                        skill_dir,
                        skill,
                        description,
                        battery,
                        "test-model",
                        runtime,
                        samples=1,
                        timeout_seconds=1,
                        route_only=True,
                        install_mode=install_mode,
                    )
                self.assertEqual(sent, expected, install_mode)
                for index, prompt in enumerate(sent):
                    self.assertLess(
                        len(prompt),
                        50_000,
                        f"{install_mode} entry {index}: over-long probe prompt",
                    )


if __name__ == "__main__":
    unittest.main()
