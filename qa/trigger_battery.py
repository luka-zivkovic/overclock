#!/usr/bin/env python3
"""Measure skill routing precision against should/should-not-trigger prompts.

Each prompt runs in a fresh temporary project with a disposable installation in
one of three explicit modes: target skill only, full owning plugin, or declared
multi-plugin stack. This separates standalone behavior from sibling routing effects
without exposing repository source. Skills that write a
deterministic contract file can use a contract-file detector; other skills are detected
from the Claude Code `Skill` tool call in stream-json output. CLI errors abort the run
instead of being misclassified as "did not trigger".

Usage:
  qa/trigger_battery.py qa/trigger-battery/lessons-learned.json
  qa/trigger_battery.py qa/trigger-battery/natural-writing.json --model MODEL
  qa/trigger_battery.py qa/trigger-battery/test-discipline.json --samples 3

Results are written under qa/_work/trigger-battery/ and are gitignored.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import errno
import json
import os
import re
import selectors
import shlex
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

REPO = Path(__file__).resolve().parent.parent
QA = REPO / "qa"
ALLOWED = "Skill,Task,Read,Glob,Grep,Bash(ls*),Bash(cat*),Bash(mkdir*),Write,Edit"
AVAILABLE_TOOLS = "Bash,Edit,Read,Glob,Grep,Skill,Write"
DEFAULT_TIMEOUT_SECONDS = 180.0
DEFAULT_SAMPLES = 3
SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin"

sys.path.insert(0, str(REPO / "tools"))
from validate_skill import parse_frontmatter  # noqa: E402
from eval_sandbox import build_settings, require_supported_version  # noqa: E402
from eval_packaging import (  # noqa: E402
    INSTALL_MODES,
    materialize_installation,
    resolve_install_modes,
)


@dataclass(frozen=True)
class LiveEvalRuntime:
    """Host-owned resources shared by network-isolated routing sessions."""

    claude_bin: Path
    auth_root: Path
    key_file: Path
    tool_root: Path


def write_private_api_key(path: Path, value: str) -> None:
    """Create a single-link, owner-only credential file without following links."""
    value = value.strip()
    if not value or "\n" in value or "\r" in value:
        raise ValueError("live-eval credential must be one non-empty line")
    if len(value.encode("utf-8")) > 16_384:
        raise ValueError("live-eval credential is unexpectedly large")
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", closefd=False) as handle:
            handle.write(value)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)
    path.chmod(0o600)


def isolated_claude_environment(runtime: LiveEvalRuntime, case_runtime: Path) -> dict[str, str]:
    """Return the complete environment for an `env -i` equivalent launch."""
    return {
        "HOME": str(case_runtime / "home"),
        "CLAUDE_CONFIG_DIR": str(case_runtime / "config"),
        "TMPDIR": str(case_runtime / "tmp"),
        "PATH": f"{runtime.tool_root}:{SYSTEM_PATH}",
        "USER": "overclock-eval",
        "LOGNAME": "overclock-eval",
        "SHELL": "/bin/sh",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_ERROR_REPORTING": "1",
        "DISABLE_TELEMETRY": "1",
        "DISABLE_BUG_COMMAND": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1",
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
    }


def build_claude_command(
    runtime: LiveEvalRuntime,
    *,
    prompt: str,
    model: str,
    plugin_dirs: list[Path],
    settings: Path,
) -> list[str]:
    """Build one fail-closed, settings-isolated routing command."""
    plugin_args = [
        item
        for destination_copy in plugin_dirs
        for item in ("--plugin-dir", str(destination_copy))
    ]
    return [
        str(runtime.claude_bin),
        "-p",
        prompt,
        "--model",
        model,
        "--output-format",
        "stream-json",
        "--verbose",
        "--no-session-persistence",
        *plugin_args,
        "--settings",
        str(settings),
        "--setting-sources",
        "",
        "--strict-mcp-config",
        "--no-chrome",
        "--permission-mode",
        "dontAsk",
        "--tools",
        AVAILABLE_TOOLS,
        "--allowedTools",
        ALLOWED,
    ]


def _version_environment(home: Path) -> dict[str, str]:
    """Keep credential-bearing host state out of even the version preflight."""
    return {
        "PATH": SYSTEM_PATH,
        "HOME": str(home),
        "USER": "overclock-eval",
        "LOGNAME": "overclock-eval",
        "SHELL": "/bin/sh",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_TELEMETRY": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }


_CACHED_CREDENTIAL: str | None = None


@contextmanager
def live_eval_runtime() -> Iterator[LiveEvalRuntime]:
    """Preflight Claude/auth and yield private resources for all battery cases."""
    discovered = shutil.which("claude")
    if discovered is None:
        raise RuntimeError("claude CLI not found")
    claude_bin = Path(discovered).resolve()
    with tempfile.TemporaryDirectory(prefix="overclock-trigger-version.") as version_home:
        version = subprocess.run(
            [str(claude_bin), "--version"],
            env=_version_environment(Path(version_home)),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15,
            check=False,
        )
    if version.returncode != 0:
        raise RuntimeError("could not verify the Claude Code version")
    require_supported_version(version.stdout)

    global _CACHED_CREDENTIAL
    credential = os.environ.pop("ANTHROPIC_API_KEY", "")
    auth_token = os.environ.pop("ANTHROPIC_AUTH_TOKEN", "")
    if not credential:
        credential = auth_token
    auth_token = ""
    if not credential:
        # A multi-mode battery enters this context once per install mode; the
        # first entry scrubs the environment, so later entries reuse the
        # already-ingested credential instead of failing mid-battery.
        credential = _CACHED_CREDENTIAL or ""
    if not credential:
        raise RuntimeError(
            "live routing batteries require ANTHROPIC_API_KEY or "
            "ANTHROPIC_AUTH_TOKEN; host OAuth/keychain credentials are isolated"
        )
    _CACHED_CREDENTIAL = credential

    with (
        tempfile.TemporaryDirectory(prefix="overclock-trigger-auth.") as auth_temp,
        tempfile.TemporaryDirectory(prefix="overclock-trigger-tools.") as tool_temp,
    ):
        auth_root = Path(auth_temp)
        tool_root = Path(tool_temp)
        auth_root.chmod(0o700)
        tool_root.chmod(0o700)
        key_file = auth_root / "api-key"
        write_private_api_key(key_file, credential)
        credential = ""
        fake_gh = tool_root / "gh"
        shutil.copyfile(QA / "fake_gh.py", fake_gh)
        fake_gh.chmod(0o700)
        key_reader = tool_root / "read_eval_api_key.py"
        shutil.copyfile(QA / "read_eval_api_key.py", key_reader)
        key_reader.chmod(0o700)
        yield LiveEvalRuntime(
            claude_bin=claude_bin,
            auth_root=auth_root,
            key_file=key_file,
            tool_root=tool_root,
        )


def locate_skill(battery: dict) -> Path:
    skill = battery["skill"]
    plugin = battery.get("plugin")
    if plugin:
        path = REPO / "plugins" / plugin / "skills" / skill
        if not (path / "SKILL.md").is_file():
            raise ValueError(f"skill not found: {path}")
        return path

    matches = sorted((REPO / "plugins").glob(f"*/skills/{skill}"))
    matches = [path for path in matches if (path / "SKILL.md").is_file()]
    if not matches:
        raise ValueError(f"no plugin contains skill {skill!r}")
    if len(matches) > 1:
        choices = ", ".join(str(path.relative_to(REPO)) for path in matches)
        raise ValueError(f"skill {skill!r} is distributed by multiple plugins; set 'plugin': {choices}")
    return matches[0]


def validate_battery_install_modes(battery: dict, skill_dir: Path) -> list[str]:
    """Require committed standalone and relevant composition routing evidence."""
    errors: list[str] = []
    declared = battery.get("install_modes")
    try:
        modes = resolve_install_modes(
            {"install_modes": declared},
            skill_dir.parent.parent.name,
        )
    except ValueError as exc:
        return [str(exc)]
    if "skill" not in modes:
        errors.append("install_modes must contain skill")

    owning_plugin = skill_dir.parent.parent
    shipped_skills = [
        child
        for child in (owning_plugin / "skills").iterdir()
        if child.is_dir() and (child / "SKILL.md").is_file()
    ]
    if (len(shipped_skills) > 1 or (owning_plugin / "hooks").exists()) and (
        "plugin" not in modes
    ):
        errors.append(
            "multi-skill or hook-bearing plugin batteries must contain plugin"
        )
    requested = battery.get("plugins")
    if isinstance(requested, list) and any(
        name != owning_plugin.name for name in requested
    ) and "stack" not in modes:
        errors.append("batteries with external plugins must contain stack")
    return errors


def prompt_contract(
    value: object,
    *,
    inherited_forbidden: list[str] | None = None,
) -> tuple[str, list[str] | None, list[str]]:
    """Normalize a string or ownership-aware routing prompt object."""
    inherited_forbidden = inherited_forbidden or []
    if isinstance(value, str):
        prompt = value
        allowed: object = None
        forbidden: object = []
    elif isinstance(value, dict):
        unknown = set(value) - {"prompt", "allowed_skills", "forbidden_skills"}
        if unknown:
            raise ValueError(f"unknown routing prompt fields: {sorted(unknown)}")
        prompt = value.get("prompt")
        allowed = value.get("allowed_skills")
        forbidden = value.get("forbidden_skills", [])
    else:
        raise ValueError("routing prompt must be a string or object")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("routing prompt text must be a non-empty string")

    def skill_list(raw: object, field: str, *, optional: bool) -> list[str] | None:
        if optional and raw is None:
            return None
        if (
            not isinstance(raw, list)
            or not all(
                isinstance(item, str)
                and re.fullmatch(r"[a-z0-9][a-z0-9-]*", item)
                for item in raw
            )
            or len(set(raw)) != len(raw)
        ):
            suffix = " or omitted" if optional else ""
            raise ValueError(
                f"{field} must be a unique list of safe skill names{suffix}"
            )
        return list(raw)

    normalized_allowed = skill_list(
        allowed,
        "allowed_skills",
        optional=True,
    )
    normalized_forbidden = skill_list(
        forbidden,
        "forbidden_skills",
        optional=False,
    )
    normalized_inherited = skill_list(
        inherited_forbidden,
        "inherited forbidden_skills",
        optional=False,
    )
    assert normalized_forbidden is not None
    assert normalized_inherited is not None
    combined_forbidden = list(
        dict.fromkeys([*normalized_inherited, *normalized_forbidden])
    )
    if normalized_allowed is not None:
        overlap = set(normalized_allowed).intersection(combined_forbidden)
        if overlap:
            raise ValueError(
                "routing prompt allows and forbids the same skills: "
                + ", ".join(sorted(overlap))
            )
    return prompt, normalized_allowed, combined_forbidden


def validate_battery_prompt_contracts(battery: dict) -> list[str]:
    """Validate prompt objects and require ownership metadata on composed negatives."""
    errors: list[str] = []
    inherited = battery.get("forbidden_skills", [])
    if not isinstance(inherited, list):
        inherited = []
    composed = len(battery.get("install_modes", [])) > 1 or bool(
        battery.get("plugins")
    )
    for kind, values in (
        ("should_trigger", battery.get("should_trigger")),
        ("should_not", battery.get("should_not")),
    ):
        if not isinstance(values, list) or not values:
            errors.append(f"{kind} must be a non-empty list")
            continue
        for index, value in enumerate(values):
            try:
                prompt_contract(
                    value,
                    inherited_forbidden=(
                        inherited if kind == "should_trigger" else []
                    ),
                )
            except ValueError as exc:
                errors.append(f"{kind}[{index}]: {exc}")
            if (
                composed
                and kind == "should_not"
                and (
                    not isinstance(value, dict)
                    or "allowed_skills" not in value
                )
            ):
                errors.append(
                    f"{kind}[{index}] in a composed battery must declare "
                    "allowed_skills"
                )
    return errors


def result_artifact_name(skill_dir: Path, skill: str, install_mode: str) -> str:
    """Namespace evidence by plugin so duplicate skill distributions cannot collide."""
    plugin = skill_dir.parent.parent.name
    if install_mode not in INSTALL_MODES:
        raise ValueError("unknown install mode")
    return f"{plugin}-{skill}-{install_mode}.results.json"


def current_description(skill_dir: Path) -> str:
    frontmatter, _ = parse_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    description = frontmatter.get("description", "")
    if not description:
        raise ValueError(f"{skill_dir}/SKILL.md has no description")
    return description


def swap_description(text: str, description: str) -> str:
    """Replace a one-line description with a JSON-quoted YAML scalar."""
    quoted = json.dumps(description, ensure_ascii=False)
    updated, count = re.subn(r"(?m)^description:.*$", f"description: {quoted}", text, count=1)
    if count != 1:
        raise ValueError("SKILL.md needs one top-level, one-line description field")
    return updated


def selected_skills(stdout: str) -> set[str]:
    """Return all final namespace components selected through the Skill tool."""
    selected_names: set[str] = set()
    for raw in stdout.splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "assistant":
            continue
        for block in event.get("message", {}).get("content", []):
            if block.get("type") != "tool_use" or block.get("name") != "Skill":
                continue
            tool_input = block.get("input", {})
            selected = (
                tool_input.get("skill")
                or tool_input.get("command")
                or tool_input.get("name")
                or ""
            )
            if selected:
                invocation = str(selected).lstrip("/").split(maxsplit=1)[0]
                selected_names.add(invocation.split(":")[-1])
    return selected_names


def selected_skill(stdout: str, skill: str) -> bool:
    """Return whether stream-json contains a Skill tool call selecting `skill`."""
    return skill in selected_skills(stdout)


def result_metadata(stdout: str) -> dict:
    """Extract cost/latency metadata from the final stream-json result event."""
    metadata = {"duration_ms": 0, "total_cost_usd": 0.0, "num_turns": 0}
    for raw in stdout.splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "result":
            continue
        for key in metadata:
            if event.get(key) is not None:
                metadata[key] = event[key]
    return metadata


def routing_evidence(stdout: str) -> dict:
    """Return filtered init/tool evidence without retaining model or file output."""
    api_key_sources: set[str] = set()
    available_tools: set[str] = set()
    listed_skills: set[str] = set()
    slash_commands: set[str] = set()
    skill_tool_events: list[dict[str, object]] = []
    for raw in stdout.splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            if isinstance(event.get("apiKeySource"), str):
                api_key_sources.add(event["apiKeySource"])
            available_tools.update(
                item for item in event.get("tools", []) if isinstance(item, str)
            )
            listed_skills.update(
                item for item in event.get("skills", []) if isinstance(item, str)
            )
            slash_commands.update(
                item
                for item in event.get("slash_commands", [])
                if isinstance(item, str)
            )
        if event.get("type") != "assistant":
            continue
        for block in event.get("message", {}).get("content", []):
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if block.get("name") != "Skill":
                continue
            tool_input = block.get("input", {})
            if not isinstance(tool_input, dict):
                tool_input = {}
            selected = (
                tool_input.get("skill")
                or tool_input.get("command")
                or tool_input.get("name")
            )
            skill_tool_events.append(
                {
                    "tool_name": block.get("name"),
                    "input_keys": sorted(
                        key for key in tool_input if isinstance(key, str)
                    ),
                    "selected": selected,
                }
            )
    return {
        "api_key_sources": sorted(api_key_sources),
        "available_tools": sorted(available_tools),
        "listed_skills": sorted(listed_skills),
        "slash_commands": sorted(slash_commands),
        "skill_tool_events": skill_tool_events,
    }


def materialize_fixture(cwd: Path, battery: dict) -> None:
    """Create optional repo-owned text fixtures for routing prompts that name files."""
    files = battery.get("fixture_files", {})
    if not isinstance(files, dict) or not all(
        isinstance(name, str) and isinstance(content, str)
        for name, content in files.items()
    ):
        raise ValueError("fixture_files must map relative paths to text")
    for name, content in files.items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError(f"unsafe fixture path: {name!r}")
        destination = cwd / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    if battery.get("fixture_git"):
        env = dict(os.environ)
        env.update(
            {
                "GIT_AUTHOR_NAME": "fixture",
                "GIT_AUTHOR_EMAIL": "fixture@example.com",
                "GIT_COMMITTER_NAME": "fixture",
                "GIT_COMMITTER_EMAIL": "fixture@example.com",
            }
        )
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=cwd, env=env, check=True)
        subprocess.run(["git", "add", "-A"], cwd=cwd, env=env, check=True)
        subprocess.run(["git", "commit", "-qm", "routing fixture"], cwd=cwd, env=env, check=True)


def first_symlink(root: Path) -> Path | None:
    """Return the first link in a plugin tree without traversing directory links."""
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in [*directories, *files]:
            candidate = current_path / name
            if candidate.is_symlink():
                return candidate
    return None


def write_case_settings(
    runtime: LiveEvalRuntime,
    *,
    work: Path,
    plugin_root: Path,
    case_runtime: Path,
) -> Path:
    """Write fail-closed settings whose only credential path is apiKeyHelper."""
    helper = shlex.join(
        [
            sys.executable,
            str(runtime.tool_root / "read_eval_api_key.py"),
            str(runtime.key_file),
        ]
    )
    settings = build_settings(
        work=work,
        plugin_root=plugin_root,
        runtime_root=case_runtime,
        tool_root=runtime.tool_root,
        repository=REPO,
        auth_root=runtime.auth_root,
        api_key_helper=helper,
    )
    destination = case_runtime / "eval-settings.json"
    destination.write_text(
        json.dumps(settings, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    destination.chmod(0o600)
    return destination


def contract_file_exists(work: Path, value: object) -> bool:
    """Check a detector path beneath work without following any links."""
    if not isinstance(value, str):
        raise ValueError("contract detector path must be a relative string")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError(f"unsafe contract detector path: {value!r}")

    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    root_fd = os.open(work, directory_flags)
    current_fd = root_fd
    try:
        for part in relative.parts[:-1]:
            try:
                next_fd = os.open(part, directory_flags, dir_fd=current_fd)
            except OSError as exc:
                if exc.errno in {
                    errno.EACCES,
                    errno.ELOOP,
                    errno.ENOENT,
                    errno.ENOTDIR,
                }:
                    return False
                raise
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = next_fd
        try:
            details = os.stat(
                relative.parts[-1],
                dir_fd=current_fd,
                follow_symlinks=False,
            )
        except (FileNotFoundError, NotADirectoryError, PermissionError):
            return False
        return stat.S_ISREG(details.st_mode) and details.st_nlink == 1
    finally:
        if current_fd != root_fd:
            os.close(current_fd)
        os.close(root_fd)


def stop_process(process: subprocess.Popen) -> None:
    """Stop a Claude process and any children it launched."""
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=2)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if process.poll() is None:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.wait()


def run_streaming_command(
    command: list[str],
    cwd: Path,
    skill: str,
    stop_on_skill: bool,
    timeout_seconds: float,
    env: dict[str, str] | None = None,
) -> dict:
    """Run one session, optionally stopping as soon as its Skill route is observable."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
        env=env,
    )
    assert process.stdout is not None
    output: list[str] = []
    fired = False
    stopped_early = False
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        deadline = started + timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                stop_process(process)
                tail = "".join(output)[-500:].strip()
                suffix = f"; last output: {tail}" if tail else ""
                raise RuntimeError(
                    f"claude timed out after {timeout_seconds:g}s{suffix}"
                )
            events = selector.select(timeout=min(0.25, remaining))
            if events:
                line = process.stdout.readline()
                if line:
                    output.append(line)
                    if stop_on_skill and selected_skill(line, skill):
                        fired = True
                        stopped_early = True
                        stop_process(process)
                        break
                elif process.poll() is not None:
                    break
            elif process.poll() is not None:
                remainder = process.stdout.read()
                if remainder:
                    output.append(remainder)
                break
    finally:
        selector.close()
        if process.poll() is None:
            stop_process(process)
        process.stdout.close()

    stdout = "".join(output)
    if not stopped_early and process.returncode != 0:
        error = stdout[-500:].strip()
        # Persist the full child stream: the 500-char tail rarely shows which
        # tool call blew up a failing probe session.
        debug_dir = QA / "_work" / "trigger-battery"
        debug_dir.mkdir(parents=True, exist_ok=True)
        debug_path = debug_dir / f"failed-probe-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{os.getpid()}.jsonl"
        debug_path.write_text(stdout, encoding="utf-8")
        raise RuntimeError(
            f"claude exited {process.returncode} (full stream: {debug_path}): {error}"
        )
    elapsed_ms = round((time.monotonic() - started) * 1000)
    metadata = result_metadata(stdout)
    evidence = routing_evidence(stdout)
    if evidence["api_key_sources"] != ["apiKeyHelper"]:
        raise RuntimeError(
            "claude routing run did not use the isolated apiKeyHelper"
        )
    if not metadata["duration_ms"]:
        metadata["duration_ms"] = elapsed_ms
    return {
        "stdout": stdout,
        "fired": fired or selected_skill(stdout, skill),
        "selected_skills": sorted(selected_skills(stdout)),
        "stopped_early": stopped_early,
        "routing_evidence": evidence,
        **metadata,
    }


def run_prompt(
    skill_dir: Path,
    skill: str,
    description: str,
    prompt: str,
    model: str,
    detector: dict,
    battery: dict,
    runtime: LiveEvalRuntime,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    route_only: bool = True,
    install_mode: str | None = None,
    allowed_skills: list[str] | None = None,
    forbidden_skills: list[str] | None = None,
) -> dict:
    with tempfile.TemporaryDirectory(prefix="overclock-trigger-case.") as temp:
        case_root = Path(temp)
        work = case_root / "work"
        plugin_root = case_root / "plugins"
        case_runtime = case_root / "runtime"
        work.mkdir()
        plugin_root.mkdir()
        (case_runtime / "home").mkdir(parents=True)
        (case_runtime / "config").mkdir()
        (case_runtime / "tmp").mkdir()
        materialize_fixture(work, battery)
        source_plugin = skill_dir.parent.parent
        target_plugin = source_plugin.name
        if install_mode is None:
            install_mode = resolve_install_modes(
                battery,
                target_plugin,
                suite=battery,
            )[0]
        installation = materialize_installation(
            source_plugin_root=REPO / "plugins",
            destination_root=plugin_root,
            target_plugin=target_plugin,
            target_skill=skill,
            mode=install_mode,
            config=battery,
        )
        destination_plugins = list(installation.plugin_dirs)
        destination_plugin = plugin_root / target_plugin
        destination = destination_plugin / "skills" / skill
        skill_md = destination / "SKILL.md"
        skill_md.write_text(
            swap_description(skill_md.read_text(encoding="utf-8"), description),
            encoding="utf-8",
        )

        kind = detector.get("type", "skill_tool")
        forbidden_skills = forbidden_skills or []
        if not isinstance(forbidden_skills, list) or not all(
            isinstance(item, str) and item for item in forbidden_skills
        ):
            raise ValueError("forbidden_skills must be a list of skill names")
        installed_skill_names = {
            candidate.name
            for plugin_dir in destination_plugins
            for candidate in (plugin_dir / "skills").iterdir()
            if candidate.is_dir() and (candidate / "SKILL.md").is_file()
        }
        active_forbidden_skills = [
            item for item in forbidden_skills if item in installed_skill_names
        ]
        settings = write_case_settings(
            runtime,
            work=work,
            plugin_root=plugin_root,
            case_runtime=case_runtime,
        )
        streamed = run_streaming_command(
            build_claude_command(
                runtime,
                prompt=prompt,
                model=model,
                plugin_dirs=destination_plugins,
                settings=settings,
            ),
            work,
            skill,
            stop_on_skill=(
                route_only
                and not active_forbidden_skills
                and allowed_skills is None
                and kind in {"skill_tool", "skill_or_contract"}
            ),
            timeout_seconds=timeout_seconds,
            env=isolated_claude_environment(runtime, case_runtime),
        )

        if kind == "skill_tool":
            fired = streamed["fired"]
        elif kind == "contract_file":
            relative = detector.get("path")
            if not relative:
                raise ValueError("contract_file detector requires a path")
            fired = contract_file_exists(work, relative)
        elif kind == "skill_or_contract":
            relative = detector.get("path")
            if not relative:
                raise ValueError("skill_or_contract detector requires a path")
            fired = streamed["fired"] or contract_file_exists(work, relative)
        else:
            raise ValueError(f"unknown detector type: {kind}")
        selected = set(streamed["selected_skills"])
        forbidden_selected = sorted(
            selected.intersection(active_forbidden_skills)
        )
        outside_allowed = (
            sorted(selected - set(allowed_skills))
            if allowed_skills is not None
            else []
        )
        return {
            "fired": fired,
            "selected_skills": streamed["selected_skills"],
            "allowed_skills": allowed_skills,
            "forbidden_skills": active_forbidden_skills,
            "forbidden_selected": forbidden_selected,
            "outside_allowed": outside_allowed,
            "ownership_violations": sorted(
                set(forbidden_selected).union(outside_allowed)
            ),
            "routing_evidence": streamed.get(
                "routing_evidence",
                {
                    "api_key_sources": [],
                    "available_tools": [],
                    "listed_skills": [],
                    "slash_commands": [],
                    "skill_tool_events": [],
                },
            ),
            "stopped_early": streamed["stopped_early"],
            "duration_ms": streamed["duration_ms"],
            "total_cost_usd": streamed["total_cost_usd"],
            "num_turns": streamed["num_turns"],
            "install_mode": install_mode,
        }


def row_passes(row: dict) -> bool:
    """Return whether target routing and the row's ownership contract both pass."""
    target_correct = (
        row["fired"] if row["kind"] == "should" else not row["fired"]
    )
    return bool(target_correct and not row.get("ownership_violations"))


def quality_metrics(rows: list[dict]) -> dict:
    """Return routing confusion counts and stable rate metrics."""
    true_positive = sum(
        1
        for row in rows
        if row["kind"] == "should" and row_passes(row)
    )
    false_negative = sum(
        1
        for row in rows
        if row["kind"] == "should" and not row_passes(row)
    )
    true_negative = sum(
        1
        for row in rows
        if row["kind"] == "should_not" and row_passes(row)
    )
    false_positive = sum(
        1
        for row in rows
        if row["kind"] == "should_not" and not row_passes(row)
    )

    def rate(numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator else 1.0

    total = len(rows)
    return {
        "true_positive": true_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
        "false_positive": false_positive,
        "accuracy": rate(true_positive + true_negative, total),
        "precision": rate(true_positive, true_positive + false_positive),
        "recall": rate(true_positive, true_positive + false_negative),
        "specificity": rate(true_negative, true_negative + false_positive),
    }


def threshold_failures(metrics: dict, thresholds: dict) -> list[str]:
    """Describe any configured minimum quality rates the result misses."""
    allowed = {"accuracy", "precision", "recall", "specificity"}
    failures = []
    for name, minimum in thresholds.items():
        if name not in allowed:
            raise ValueError(f"unknown routing threshold: {name}")
        if not isinstance(minimum, (int, float)) or not 0 <= minimum <= 1:
            raise ValueError(f"threshold {name} must be a number from 0 to 1")
        actual = metrics[name]
        if actual < minimum:
            failures.append(f"{name} {actual:.1%} < {minimum:.1%}")
    return failures


def score(
    skill_dir: Path,
    skill: str,
    description: str,
    battery: dict,
    model: str,
    runtime: LiveEvalRuntime,
    samples: int = 1,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    route_only: bool = True,
    progress: Callable[[dict], None] | None = None,
    install_mode: str | None = None,
) -> dict:
    if samples <= 0:
        raise ValueError("samples must be greater than zero")
    detector = battery.get("detector", {"type": "skill_tool"})
    inherited_forbidden = battery.get("forbidden_skills", [])
    rows = []
    for sample in range(1, samples + 1):
        for kind, prompts in (("should", battery["should_trigger"]),
                              ("should_not", battery["should_not"])):
            for prompt_spec in prompts:
                prompt, allowed_skills, forbidden_skills = prompt_contract(
                    prompt_spec,
                    inherited_forbidden=(
                        inherited_forbidden if kind == "should" else []
                    ),
                )
                # One bounded retry per probe: a single child runtime failure
                # must not discard every completed probe in the battery. A
                # second failure still aborts fail-closed, naming the entry.
                for attempt in (1, 2):
                    try:
                        result = run_prompt(
                            skill_dir, skill, description, prompt, model,
                            detector, battery,
                            runtime,
                            timeout_seconds=timeout_seconds,
                            route_only=route_only,
                            install_mode=install_mode,
                            allowed_skills=allowed_skills,
                            forbidden_skills=forbidden_skills,
                        )
                        break
                    except RuntimeError as exc:
                        if attempt == 2:
                            raise RuntimeError(
                                "probe failed twice "
                                f"(sample {sample}/{samples}, install mode "
                                f"{install_mode or 'default'}, {kind}): "
                                f"{prompt[:80]!r}: {exc}"
                            ) from exc
                row = {"sample": sample, "kind": kind, "prompt": prompt, **result}
                rows.append(row)
                if progress:
                    progress(row)
    correct = sum(row_passes(row) for row in rows)
    return {
        "correct": correct,
        "total": len(rows),
        "duration_ms": sum(row["duration_ms"] for row in rows),
        "total_cost_usd": sum(row["total_cost_usd"] for row in rows),
        "num_turns": sum(row["num_turns"] for row in rows),
        "metrics": quality_metrics(rows),
        "rows": rows,
    }


def score_variants(
    skill_dir: Path,
    skill: str,
    variants: dict,
    battery: dict,
    model: str,
    *,
    samples: int,
    timeout_seconds: float,
    route_only: bool,
    install_mode: str,
) -> dict:
    """Score every description while one private live-eval runtime is active."""
    scores = {}
    with live_eval_runtime() as runtime:
        for label, description in variants.items():
            print(f"-- scoring variant: {label}")

            def print_progress(row: dict) -> None:
                kind, prompt, fired = row["kind"], row["prompt"], row["fired"]
                passed = row_passes(row)
                early = " route-only" if row["stopped_early"] else ""
                collision = (
                    " ownership=" + ",".join(row["ownership_violations"])
                    if row.get("ownership_violations")
                    else ""
                )
                print(
                    f"     [{'OK ' if passed else 'MISS'}] "
                    f"sample {row['sample']}/{samples} "
                    f"want {'fire' if kind == 'should' else 'silent':6} "
                    f"got {'fired' if fired else 'silent':6} | {prompt[:58]} "
                    f"| {row['duration_ms']/1000:.1f}s "
                    f"${row['total_cost_usd']:.4f}{early}{collision}",
                    flush=True,
                )

            result = score(
                skill_dir,
                skill,
                description,
                battery,
                model,
                runtime,
                samples=samples,
                timeout_seconds=timeout_seconds,
                route_only=route_only,
                progress=print_progress,
                install_mode=install_mode,
            )
            scores[label] = result
            metrics = result["metrics"]
            print(
                f"   => {label}: {result['correct']}/{result['total']} | "
                f"precision={metrics['precision']:.1%} "
                f"recall={metrics['recall']:.1%} "
                f"specificity={metrics['specificity']:.1%} | "
                f"{result['duration_ms']/1000:.1f}s "
                f"${result['total_cost_usd']:.4f}\n"
            )
    return scores


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("battery", type=Path)
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--samples", type=int)
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument(
        "--install-mode",
        choices=INSTALL_MODES,
        help="run one mode instead of the battery's declared install_modes matrix",
    )
    parser.add_argument(
        "--full-session", action="store_true",
        help="let positive cases finish instead of stopping at the observed Skill route",
    )
    for metric in ("accuracy", "precision", "recall", "specificity"):
        parser.add_argument(f"--min-{metric}", type=float)
    args = parser.parse_args()

    battery = json.loads(args.battery.read_text(encoding="utf-8"))
    samples = (
        args.samples
        if args.samples is not None
        else battery.get("samples", DEFAULT_SAMPLES)
    )
    timeout_seconds = (
        args.timeout_seconds
        if args.timeout_seconds is not None
        else battery.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    )
    if samples <= 0:
        parser.error("--samples must be greater than zero")
    if timeout_seconds <= 0:
        parser.error("--timeout-seconds must be greater than zero")
    route_only = not args.full_session and battery.get("route_only", True)
    thresholds = dict(battery.get("thresholds", {}))
    for metric in ("accuracy", "precision", "recall", "specificity"):
        override = getattr(args, f"min_{metric}")
        if override is not None:
            thresholds[metric] = override
    threshold_failures(
        {name: 1.0 for name in ("accuracy", "precision", "recall", "specificity")},
        thresholds,
    )
    skill = battery["skill"]
    skill_dir = locate_skill(battery)
    matrix_errors = validate_battery_install_modes(battery, skill_dir)
    contract_errors = validate_battery_prompt_contracts(battery)
    if matrix_errors or contract_errors:
        parser.error("; ".join([*matrix_errors, *contract_errors]))
    target_plugin = skill_dir.parent.parent.name
    try:
        install_modes = resolve_install_modes(
            battery,
            target_plugin,
            suite=battery,
            override=args.install_mode,
        )
    except ValueError as exc:
        parser.error(str(exc))
    variants = battery.get("variants") or {"current": current_description(skill_dir)}
    output_dir = REPO / "qa" / "_work" / "trigger-battery"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Trigger battery for {skill} (model={args.model})")
    print(f"Source: {skill_dir.relative_to(REPO)}")
    print(
        f"{len(battery['should_trigger'])} should-trigger + "
        f"{len(battery['should_not'])} should-not x {samples} sample(s) "
        f"x {len(variants)} variant(s)"
    )
    print(
        f"Mode: {'route-only' if route_only else 'full-session'} | "
        f"timeout={timeout_seconds:g}s"
    )
    print("Install matrix: " + ", ".join(install_modes))
    if thresholds:
        print(
            "Thresholds: "
            + ", ".join(f"{name}>={value:.0%}" for name, value in thresholds.items())
        )
    print()

    gate_failed = False
    for install_mode in install_modes:
        print(f"== install mode: {install_mode}")
        try:
            scores = score_variants(
                skill_dir,
                skill,
                variants,
                battery,
                args.model,
                samples=samples,
                timeout_seconds=timeout_seconds,
                route_only=route_only,
                install_mode=install_mode,
            )
        except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as exc:
            print(f"live routing infrastructure failed: {exc}", file=sys.stderr)
            return 2

        artifact = {
            "skill": skill,
            "source": str(skill_dir.relative_to(REPO)),
            "install_mode": install_mode,
            "model": args.model,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "samples": samples,
            "timeout_seconds": timeout_seconds,
            "route_only": route_only,
            "thresholds": thresholds,
            "scores": scores,
        }
        (output_dir / result_artifact_name(skill_dir, skill, install_mode)).write_text(
            json.dumps(artifact, indent=1) + "\n", encoding="utf-8"
        )

        ranked = sorted(
            scores.items(),
            key=lambda item: item[1]["correct"],
            reverse=True,
        )
        baseline_label = "baseline" if "baseline" in scores else next(iter(variants))
        baseline = scores[baseline_label]["correct"]
        print(f"scoreboard ({install_mode}):")
        for label, result in ranked:
            delta = result["correct"] - baseline
            suffix = (
                " <- baseline"
                if label == baseline_label
                else f" ({delta:+d} vs baseline)"
            )
            print(
                f"  {result['correct']}/{result['total']}  {label}{suffix} | "
                f"{result['duration_ms']/1000:.1f}s "
                f"${result['total_cost_usd']:.4f}"
            )

        winner, result = ranked[0]
        if winner == baseline_label or result["correct"] <= baseline:
            print(
                f"\nDECISION ({install_mode}): keep {baseline_label} "
                f"({baseline}/{result['total']})."
            )
        else:
            print(
                f"\nDECISION ({install_mode}): candidate {winner!r} leads "
                f"({result['correct']}/{result['total']} vs "
                f"{baseline}/{result['total']}). Re-run before changing the "
                "shipped description."
            )

        gate_label = "current" if "current" in scores else baseline_label
        failures = threshold_failures(scores[gate_label]["metrics"], thresholds)
        if failures:
            print(
                f"\nGATE FAILED ({install_mode}/{gate_label}): "
                + "; ".join(failures)
            )
            gate_failed = True
        elif thresholds:
            print(f"\nGATE PASSED ({install_mode}/{gate_label}).")
        print()
    return 1 if gate_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
