#!/usr/bin/env python3
"""Read-only audit of a local agent setup across Claude Code, Codex, Pi, Cursor, and OpenCode.

`scan` inventories every configuration layer the harnesses would load for this user and project,
applies deterministic rules, prepares candidate pairs for model judgment, optionally runs an
already-installed `casefile`, and prints one JSON report. It never writes a file, never runs a
configured hook or MCP server, never opens the network, and never prints a secret value.
"""
from __future__ import annotations

import argparse
import ast
import datetime as _dt
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness_common import (  # noqa: E402
    HARNESSES,
    claude_plugins,
    discover,
    display,
    est_tokens,
    harness_present,
    is_literal_secret,
    is_secret_key,
    parse_frontmatter,
    project_chain,
    read_json,
    read_text,
    redact,
    resolve_roots,
    walk_files,
)

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

SCHEMA = "harness-audit/v1"
SEVERITIES = ("critical", "high", "medium", "low", "info")
AREAS = ("safety", "coherence", "hygiene", "context")
MAX_FINDINGS = 80
MAX_EVIDENCE = 5
MAX_ROUTING_PAIRS = 15
MAX_DIRECTIVES_PER_FILE = 30
MAX_DIRECTIVES = 120
CASEFILE_MAX_TARGETS = 40
CLAUDE_JSON_LIMIT = 32_000_000

ARBITRARY_EXEC = {
    "bash", "sh", "zsh", "fish", "dash", "ksh", "python", "python2", "python3", "py", "node",
    "nodejs", "deno", "bun", "npx", "bunx", "pnpx", "uvx", "uv", "pipx", "ruby", "perl", "php",
    "lua", "eval", "exec", "sudo", "su", "doas", "env", "xargs", "nohup", "osascript", "pwsh",
    "powershell", "cmd", "rscript",
}
NETWORK_TOOLS = {"curl", "wget", "nc", "ncat", "netcat", "ssh", "scp", "sftp", "rsync", "ftp", "telnet"}
DESTRUCTIVE_TOOLS = {"rm", "dd", "mkfs", "shred", "chmod", "chown", "truncate"}
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0"}
SECURITY_SETTING_KEYS = {
    "permissions.defaultMode", "enableAllProjectMcpServers", "disableAllHooks", "sandbox.enabled",
    "apiKeyHelper", "approval_policy", "sandbox_mode",
}
BLOCKING_EVENTS = {"PreToolUse", "UserPromptSubmit", "Stop", "SubagentStop", "PermissionRequest",
                   "beforeShellExecution", "beforeMCPExecution", "beforeReadFile", "beforeSubmitPrompt"}
CONTEXT_EVENTS = {"SessionStart", "UserPromptSubmit"}
CLAUDE_BUILTINS = {
    "add-dir", "agents", "bug", "clear", "compact", "config", "context", "cost", "doctor", "exit",
    "export", "help", "hooks", "init", "insights", "login", "logout", "mcp", "memory", "model",
    "permissions", "plugin", "pr-comments", "review", "resume", "rewind", "security-review",
    "status", "statusline", "terminal-setup", "usage", "vim", "skills", "plan", "fast", "ide",
    "upgrade", "release-notes", "privacy-settings", "output-style", "todos", "feedback",
}
CODEX_BUILTINS = {"init", "review", "model", "approvals", "status", "diff", "mention", "new",
                  "compact", "mcp", "logout", "quit", "exit", "undo", "prompts", "skills", "resume"}
STOPWORDS = set("""
a about above after again against all also an and any are as at be because been before being below
between both but by can could did do does doing done down during each either etc even every few for
from further had has have having here how i if in into is it its itself just like make makes many may
might more most must my no nor not now of off on once one only or other our out over own per same
should so some such than that the their them then there these they this those through to too under
until up upon us use used uses using very via was we were what when where whether which while who whom
why will with within without would yes you your e.g eg i.e ie skill skills invoke invoked invokes
invocation explicitly explicit automatically automatic user users user's ask asks asked asking want
wants wanted request requests requested say says said mention mentions trigger triggers triggered
task tasks help helps run runs running work works working get gets need needs needed instead always
never don't doesn't isn't won't them it's
""".split())
ANTI_TRIGGER_SPLIT = re.compile(r"(?i:\bdo not\b|\bdon't\b|\bnot for\b|\bnever (?:use|invoke)\b|\banti-trigger)|\bNOT\b")
DIRECTIVE_RE = re.compile(
    r"(?i)\b(always|never|must(?:\s+not)?|do not|don't|avoid|prefer|only use|instead of|required|"
    r"forbidden|mandatory|should not|shouldn't|no longer)\b"
)
IMPORT_RE = re.compile(r"(?:^|\s)@((?:~/|\.{1,2}/|/)?[A-Za-z0-9_.][A-Za-z0-9_./-]*)")
REMOTE_EXEC_RE = re.compile(
    r"(?i)\b(?:curl|wget)\b[^|;&\n]*\|\s*(?:sudo\s+)?(?:ba|z|da|k)?sh\b|"
    r"\b(?:ba|z)?sh\s+<\(\s*(?:curl|wget)\b|\biex\b.*\b(?:iwr|invoke-webrequest)\b"
)
NETWORK_RE = re.compile(r"(?i)\b(?:curl|wget|nc|ncat|netcat|invoke-webrequest|iwr)\b|https?://")
HIDDEN_UNICODE_RE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff\U000e0000-\U000e007f]")
INJECTION_RE = re.compile(
    r"(?i)\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+)?(?:the\s+)?(?:previous|prior|above|earlier)\s+"
    r"(?:instructions|prompts|rules|messages)|\bdo not (?:tell|inform|show) the user\b"
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def short(text: object, limit: int = 220) -> str:
    value = re.sub(r"\s+", " ", str(text)).strip()
    return value if len(value) <= limit else value[: limit - 1] + "…"


def new_harness(kind: str) -> dict:
    return {
        "harness": kind, "detected": False, "version": None, "layers": [], "permissions": [],
        "scalars": [], "hooks": [], "mcp": [], "secrets": [], "instructions": [], "agents": [],
        "plugins": [], "packages": [], "extensions": [], "exec_rules": [], "posture": [],
        "skills": [], "commands": [], "parse_errors": [], "notes": [],
    }


def add_layer(h: dict, scope: str, path: Path, roots: dict, error: str | None = None) -> None:
    h["layers"].append({"scope": scope, "path": display(path, roots), "exists": path.exists(), "error": error})
    if error:
        h["parse_errors"].append({"path": display(path, roots), "scope": scope, "error": error})


def read_toml(path: Path) -> tuple[dict | None, str | None]:
    text = read_text(path)
    if text is None:
        return None, None
    if tomllib is None:
        return None, "TOML not parsed: Python 3.11 or newer is required"
    try:
        return tomllib.loads(text), None
    except Exception as exc:  # tomllib.TOMLDecodeError and friends
        return None, f"invalid TOML: {short(exc, 120)}"


def detect_version(binary: str) -> str | None:
    executable = shutil.which(binary)
    if not executable:
        return None
    try:
        result = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=5,
                                stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"\d+\.\d+\.\d+(?:[-+][\w.-]+)?", result.stdout or "")
    return match.group(0) if match else None


def git_tracked(path: Path) -> bool:
    directory = path.parent
    try:
        result = subprocess.run(
            ["git", "-C", str(directory), "ls-files", "--error-unmatch", "--", path.name],
            capture_output=True, text=True, timeout=5, stdin=subprocess.DEVNULL,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def import_targets(text: str, base: Path, roots: dict) -> list[tuple[int, str, Path]]:
    """Claude-style @path imports outside code, as (line, spelling, resolved path)."""
    found = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in IMPORT_RE.finditer(re.sub(r"`[^`]*`", "", line)):
            target = match.group(1).rstrip(".,;:)")
            if "/" not in target and not re.search(r"\.(?:md|txt|json|ya?ml|toml)$", target):
                continue
            path = Path(roots["home"]) / target[2:] if target.startswith("~/") else base / target
            found.append((number, target, path))
    return found


def instruction(h: dict, path: Path, scope: str, roots: dict, depth: int = 0) -> None:
    text = read_text(path)
    if text is None:
        return
    real = os.path.realpath(path)
    if any(item["real"] == real for item in h["instructions"]):
        return
    h["instructions"].append({
        "path": display(path, roots), "real": real, "scope": scope, "file": path,
        "tokens": est_tokens(text), "text": text, "symlink": path.is_symlink(),
    })
    if h["harness"] == "claude-code" and depth < 5:
        for _, _, target in import_targets(text, path.parent, roots):
            if target.is_file():
                instruction(h, target, f"{scope} import", roots, depth + 1)


def agents_in(h: dict, directory: Path, scope: str, roots: dict, origin: str | None = None) -> None:
    if not directory.is_dir():
        return
    for path in sorted(directory.glob("*.md")):
        fields, _, _ = parse_frontmatter(read_text(path, 64_000) or "")
        name = fields.get("name") if fields and isinstance(fields.get("name"), str) else path.stem
        h["agents"].append({"name": name, "scope": scope, "origin": origin, "path": display(path, roots)})


def flatten_scalars(data: dict, scope: str, source: str, prefix: str = "") -> list[dict]:
    rows = []
    for key, value in data.items():
        if not isinstance(key, str):
            continue
        name = f"{prefix}{key}"
        if isinstance(value, (str, int, float, bool)):
            if not is_secret_key(key):
                rows.append({"key": name, "value": value, "scope": scope, "source": source})
        elif isinstance(value, dict) and not prefix and key in {"permissions", "sandbox"}:
            rows += flatten_scalars(value, scope, source, prefix=f"{key}.")
    return rows


# ---------------------------------------------------------------------------
# MCP, hooks, permissions
# ---------------------------------------------------------------------------


def is_pinned_package(spec: str, python: bool) -> bool:
    if python:
        match = re.search(r"(?:==|@)\s*([^\s=@]+)$", spec)
        return bool(match) and match.group(1).lower() != "latest"
    body = spec[1:] if spec.startswith("@") else spec
    if "@" not in body:
        return False
    version = body.rsplit("@", 1)[1]
    return version.lower() not in {"", "latest", "next", "*", "x"}


def docker_image(args: list[str]) -> tuple[str, str | None, bool | None]:
    value_flags = {"-e", "--env", "-v", "--volume", "--name", "--network", "-p", "--publish", "--mount",
                   "-w", "--workdir", "--entrypoint", "-u", "--user", "--env-file", "--platform", "-l",
                   "--label", "--add-host", "--cpus", "--memory", "-m", "--pull", "--cap-add", "--cap-drop"}
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in value_flags:
            index += 2
            continue
        if arg.startswith("-"):
            index += 1
            continue
        image = arg
        if "@sha256:" in image:
            return "docker run", image, True
        last = image.rsplit("/", 1)[-1]
        tag = last.split(":", 1)[1] if ":" in last else ""
        return "docker run", image, bool(tag) and tag != "latest"
    return "docker run", None, None


def launcher_package(command: object, args: list) -> tuple[str | None, str | None, bool | None]:
    if not isinstance(command, str) or not command:
        return None, None, None
    base = os.path.basename(command)
    args = [str(item) for item in args]
    rest = args
    if base in {"npx", "bunx", "pnpx", "uvx"}:
        launcher = base
    elif base == "pipx" and args[:1] == ["run"]:
        launcher, rest = "pipx run", args[1:]
    elif base in {"pnpm", "yarn", "bun", "npm"} and args[:1] and args[0] in {"dlx", "x", "exec"}:
        launcher, rest = f"{base} {args[0]}", args[1:]
    elif base in {"docker", "podman"} and args[:1] == ["run"]:
        return docker_image(args[1:])
    else:
        return None, None, None
    package = None
    index = 0
    while index < len(rest):
        arg = rest[index]
        if arg in {"-p", "--package", "--from"} and index + 1 < len(rest):
            package = rest[index + 1]
            break
        if arg.startswith(("--package=", "--from=")):
            package = arg.split("=", 1)[1]
            break
        if arg.startswith("-"):
            index += 1
            continue
        package = arg
        break
    if package is None:
        return launcher, None, None
    if package.startswith((".", "/", "~", "file:")):
        return launcher, package, True
    if package.startswith(("git+", "http://", "https://", "github:")):
        return launcher, package, "#" in package
    return launcher, package, is_pinned_package(package, python=launcher in {"uvx", "pipx run"})


def mcp_entry(name: str, raw: object, *, scope: str, source: str) -> dict | None:
    if not isinstance(raw, dict):
        return None
    command = raw.get("command")
    args = raw.get("args") if isinstance(raw.get("args"), list) else []
    if isinstance(command, list):
        args = [*command[1:], *args]
        command = command[0] if command else None
    env = raw.get("env") if isinstance(raw.get("env"), dict) else raw.get("environment")
    env = env if isinstance(env, dict) else {}
    headers = raw.get("headers") if isinstance(raw.get("headers"), dict) else raw.get("http_headers")
    headers = headers if isinstance(headers, dict) else {}
    url = next((raw[key] for key in ("url", "serverUrl", "httpUrl") if isinstance(raw.get(key), str)), None)
    secret_keys = [f"env.{key}" for key, value in env.items() if is_literal_secret(str(key), value)]
    secret_keys += [f"headers.{key}" for key, value in headers.items()
                    if is_literal_secret(str(key), value) or (str(key).lower() == "authorization"
                                                               and is_literal_secret("token", str(value)))]
    if is_literal_secret("bearer_token", raw.get("bearer_token")):
        secret_keys.append("bearer_token")
    for index, arg in enumerate(args):
        text = str(arg)
        previous = str(args[index - 1]) if index else ""
        flag = re.match(r"^--?([A-Za-z0-9_-]+)=(.+)$", text)
        if flag and is_literal_secret(flag.group(1), flag.group(2)):
            secret_keys.append(f"args[{index}]")
        elif previous.startswith("-") and is_literal_secret(previous.lstrip("-"), text):
            secret_keys.append(f"args[{index}]")
        elif text != redact(text):
            secret_keys.append(f"args[{index}]")
    insecure = False
    if url:
        match = re.match(r"^(https?)://(?:([^@/]*)@)?([^/:?#]+|\[[^\]]+\])", url)
        if match:
            insecure = match.group(1) == "http" and match.group(3).lower() not in LOOPBACK_HOSTS
            if match.group(2):
                secret_keys.append("url.userinfo")
        query = url.split("?", 1)[1] if "?" in url else ""
        for pair in query.split("&"):
            key, _, value = pair.partition("=")
            if key and is_literal_secret(key, value):
                secret_keys.append(f"url.query.{key}")
    launcher, package, pinned = launcher_package(command, args)
    fingerprint = hashlib.sha256(json.dumps(
        [command, [str(item) for item in args], url], sort_keys=True, default=str
    ).encode()).hexdigest()[:12]
    enabled = raw.get("enabled", True) is not False and raw.get("disabled") is not True
    return {
        "name": name, "scope": scope, "source": source, "transport": "http" if url else "stdio",
        "command": os.path.basename(command) if isinstance(command, str) else None,
        "launcher": launcher, "package": package, "pinned": pinned, "insecure_http": insecure,
        "secret_keys": sorted(set(secret_keys)), "fingerprint": fingerprint, "enabled": enabled,
    }


def add_mcp_servers(h: dict, servers: object, *, scope: str, source: str) -> None:
    if not isinstance(servers, dict):
        return
    for name, raw in servers.items():
        entry = mcp_entry(str(name), raw, scope=scope, source=source)
        if entry:
            h["mcp"].append(entry)


def hook_rows(raw: object, *, source: str, scope: str, origin: str, base: Path | None) -> list[dict]:
    """Normalize Claude-style {event: [{matcher, hooks: [...]}]} and flat {event: [{command}]}."""
    rows = []
    if not isinstance(raw, dict):
        return rows
    for event, groups in raw.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            matcher = group.get("matcher", "") if isinstance(group.get("matcher", ""), str) else ""
            entries = group.get("hooks") if isinstance(group.get("hooks"), list) else [group]
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                command = entry.get("command")
                kind = entry.get("type", "command")
                rows.append({
                    "event": str(event), "matcher": matcher, "type": kind,
                    "command": command if isinstance(command, str) else None,
                    "source": source, "scope": scope, "origin": origin, "base": base,
                })
    return rows


def rule_parts(rule: str) -> tuple[str, str | None]:
    match = re.match(r"^\s*([A-Za-z_][\w.:-]*)\s*(?:\((.*)\))?\s*$", rule, re.S)
    if not match:
        return rule.strip(), None
    return match.group(1), match.group(2)


def command_prefix(spec: str | None) -> str:
    if spec is None:
        return ""
    text = spec.strip()
    if text in {"", "*", ":*", "**"}:
        return ""
    return re.sub(r"(?::\*|\s+\*|\*)$", "", text).strip()


def classify_prefix(prefix: str) -> str | None:
    """'any' for a full shell, else the risk class of the prefix's first word."""
    if prefix == "":
        return "any"
    first = os.path.basename(prefix.split()[0]).lower()
    if first in ARBITRARY_EXEC:
        return "exec"
    if first in NETWORK_TOOLS:
        return "network"
    if first in DESTRUCTIVE_TOOLS:
        return "destructive"
    return None


def parse_codex_rules(text: str) -> list[dict]:
    rules = []
    for match in re.finditer(r"prefix_rule\s*\(", text):
        depth, index, quote = 1, match.end(), None
        while index < len(text) and depth:
            char = text[index]
            if quote:
                if char == "\\":
                    index += 1
                elif char == quote:
                    quote = None
            elif char in "\"'":
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            index += 1
        body = text[match.end(): index - 1]
        decision = re.search(r"decision\s*=\s*[\"'](\w+)[\"']", body)
        start = re.search(r"pattern\s*=\s*\[", body)
        if not start:
            continue
        depth, cursor = 1, start.end()
        while cursor < len(body) and depth:
            depth += {"[": 1, "]": -1}.get(body[cursor], 0)
            cursor += 1
        try:
            pattern = ast.literal_eval(body[start.end() - 1: cursor])
        except (ValueError, SyntaxError):
            continue
        tokens = []
        for item in pattern if isinstance(pattern, list) else []:
            tokens.append(item if isinstance(item, str) else "|".join(str(alt) for alt in item))
        line = text.count("\n", 0, match.start()) + 1
        rules.append({"pattern": tokens, "decision": decision.group(1) if decision else "allow", "line": line})
    return rules


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------


def collect_claude(roots: dict, project: Path | None) -> dict:
    h = new_harness("claude-code")
    config = Path(roots["claude-code"])
    layers = []
    if not roots["overridden"]:
        managed_dir = Path("/Library/Application Support/ClaudeCode") if sys.platform == "darwin" else Path("/etc/claude-code")
        layers.append(("managed", managed_dir / "managed-settings.json"))
        instruction(h, managed_dir / "CLAUDE.md", "managed", roots)
    layers.append(("user", config / "settings.json"))
    if project is not None:
        layers += [("project", project / ".claude" / "settings.json"),
                   ("local", project / ".claude" / "settings.local.json")]
    for scope, path in layers:
        data, error = read_json(path)
        add_layer(h, scope, path, roots, error)
        if not isinstance(data, dict):
            continue
        source = display(path, roots)
        permissions = data.get("permissions") if isinstance(data.get("permissions"), dict) else {}
        for kind in ("allow", "deny", "ask"):
            for rule in permissions.get(kind, []) if isinstance(permissions.get(kind), list) else []:
                if isinstance(rule, str):
                    h["permissions"].append({"list": kind, "rule": rule, "scope": scope, "source": source})
        h["scalars"] += flatten_scalars(data, scope, source)
        mode = permissions.get("defaultMode")
        if mode == "bypassPermissions":
            h["posture"].append({"rule": "perm/bypass-mode", "severity": "high", "scope": scope, "source": source,
                                 "detail": "permissions.defaultMode is bypassPermissions: every tool call runs without asking"})
        if data.get("enableAllProjectMcpServers") is True:
            h["posture"].append({"rule": "perm/project-mcp-autoapprove", "severity": "medium", "scope": scope,
                                 "source": source,
                                 "detail": "enableAllProjectMcpServers approves every MCP server a repository's .mcp.json declares"})
        env = data.get("env") if isinstance(data.get("env"), dict) else {}
        for key, value in env.items():
            if is_literal_secret(str(key), value):
                h["secrets"].append({"source": source, "file": path, "key": f"env.{key}", "scope": scope})
        h["hooks"] += hook_rows(data.get("hooks"), source=source, scope=scope, origin="settings",
                                base=project if scope in {"project", "local"} else None)
    for candidate in (config / ".claude.json", Path(roots["claude-json"])):
        text = read_text(candidate, CLAUDE_JSON_LIMIT)
        if text is None:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            h["parse_errors"].append({"path": display(candidate, roots), "scope": "user", "error": "invalid JSON"})
            break
        source = display(candidate, roots)
        if isinstance(data, dict):
            add_mcp_servers(h, data.get("mcpServers"), scope="user", source=source)
            projects = data.get("projects") if isinstance(data.get("projects"), dict) else {}
            if project is not None:
                entry = projects.get(str(project)) or projects.get(os.path.realpath(project))
                if isinstance(entry, dict):
                    add_mcp_servers(h, entry.get("mcpServers"), scope="local", source=f"{source} (project entry)")
        break
    if project is not None:
        data, error = read_json(project / ".mcp.json")
        if error:
            h["parse_errors"].append({"path": display(project / ".mcp.json", roots), "scope": "project", "error": error})
        if isinstance(data, dict):
            add_mcp_servers(h, data.get("mcpServers", data), scope="project", source=display(project / ".mcp.json", roots))
    for plugin in claude_plugins(roots, project):
        install = plugin["install_path"]
        h["plugins"].append({key: (display(value, roots) if isinstance(value, Path) else value)
                             for key, value in plugin.items()})
        if not (plugin["enabled"] and plugin["installed"]):
            continue
        origin = f"plugin:{plugin['id']}"
        hooks_file = install / "hooks" / "hooks.json"
        data, _ = read_json(hooks_file)
        if isinstance(data, dict):
            h["hooks"] += hook_rows(data.get("hooks", data), source=display(hooks_file, roots), scope="plugin",
                                    origin=origin, base=install)
        data, _ = read_json(install / ".mcp.json")
        if isinstance(data, dict):
            add_mcp_servers(h, data.get("mcpServers", data), scope="plugin", source=display(install / ".mcp.json", roots))
        manifest, _ = read_json(install / ".claude-plugin" / "plugin.json")
        if isinstance(manifest, dict) and isinstance(manifest.get("mcpServers"), dict):
            add_mcp_servers(h, manifest["mcpServers"], scope="plugin", source=display(install / ".claude-plugin" / "plugin.json", roots))
        agents_in(h, install / "agents", "plugin", roots, origin)
    instruction(h, config / "CLAUDE.md", "user", roots)
    for directory in reversed(project_chain(project)):
        scope = "project" if directory == project else "ancestor"
        for name in ("CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md"):
            instruction(h, directory / name, scope, roots)
    if project is not None:
        rules_dir = project / ".claude" / "rules"
        if rules_dir.is_dir():
            for path in sorted(walk_files(rules_dir, max_entries=2_000)):
                if path.suffix == ".md":
                    instruction(h, path, "project", roots)
    agents_in(h, config / "agents", "user", roots)
    if project is not None:
        agents_in(h, project / ".claude" / "agents", "project", roots)
    credential = config / ".credentials.json"
    if credential.is_file():
        h["credential_files"] = [credential]
    return h


def collect_codex(roots: dict, project: Path | None) -> dict:
    h = new_harness("codex")
    home = Path(roots["codex"])
    layers = [("user", home / "config.toml")]
    if project is not None:
        layers.append(("project", project / ".codex" / "config.toml"))
    disabled_skill_paths: set[str] = set()
    for scope, path in layers:
        data, error = read_toml(path)
        add_layer(h, scope, path, roots, error)
        if not isinstance(data, dict):
            continue
        source = display(path, roots)
        h["scalars"] += [row for row in flatten_scalars(data, scope, source)
                         if row["key"] in {"approval_policy", "sandbox_mode", "model", "profile", "model_reasoning_effort"}]
        profiles = data.get("profiles") if isinstance(data.get("profiles"), dict) else {}
        variants = [("", data)] + [(f"profiles.{name}.", value) for name, value in profiles.items() if isinstance(value, dict)]
        for prefix, block in variants:
            approval, sandbox = block.get("approval_policy"), block.get("sandbox_mode")
            if approval == "never" and sandbox == "danger-full-access":
                h["posture"].append({"rule": "perm/bypass-mode", "severity": "high", "scope": scope, "source": source,
                                     "detail": f"{prefix}approval_policy = never with {prefix}sandbox_mode = danger-full-access: commands run unsandboxed without asking"})
            elif sandbox == "danger-full-access":
                h["posture"].append({"rule": "perm/unsandboxed", "severity": "medium", "scope": scope, "source": source,
                                     "detail": f"{prefix}sandbox_mode = danger-full-access disables the sandbox"})
            elif approval == "never":
                h["posture"].append({"rule": "perm/never-ask", "severity": "low", "scope": scope, "source": source,
                                     "detail": f"{prefix}approval_policy = never: the sandbox is the only boundary"})
        workspace = data.get("sandbox_workspace_write")
        if isinstance(workspace, dict) and workspace.get("network_access") is True:
            h["posture"].append({"rule": "perm/sandbox-network", "severity": "low", "scope": scope, "source": source,
                                 "detail": "sandbox_workspace_write.network_access = true lets sandboxed commands reach the network"})
        projects = data.get("projects") if isinstance(data.get("projects"), dict) else {}
        home_dir = str(roots["home"])
        for trusted_path, entry in projects.items():
            if isinstance(entry, dict) and entry.get("trust_level") == "trusted":
                raw_path = str(trusted_path)
                if raw_path == "~" or raw_path.startswith("~/"):
                    raw_path = home_dir + raw_path[1:]
                normalized = os.path.realpath(raw_path)
                if normalized in {"/", os.path.realpath(home_dir)}:
                    h["posture"].append({"rule": "perm/trusted-broad-path", "severity": "medium", "scope": scope,
                                         "source": source,
                                         "detail": f"projects.\"{display(Path(trusted_path), roots)}\" is trusted, which covers every repository beneath it"})
        add_mcp_servers(h, data.get("mcp_servers"), scope=scope, source=source)
        notify = data.get("notify")
        if isinstance(notify, list) and notify:
            command = " ".join(shlex.quote(str(item)) for item in notify)
            h["hooks"].append({"event": "notify", "matcher": "", "type": "command", "command": command,
                               "source": source, "scope": scope, "origin": "settings", "base": None})
        if isinstance(data.get("hooks"), dict):
            h["hooks"] += hook_rows(data["hooks"], source=source, scope=scope, origin="settings",
                                    base=project if scope == "project" else None)
        skills_config = data.get("skills", {}).get("config") if isinstance(data.get("skills"), dict) else None
        for entry in skills_config if isinstance(skills_config, list) else []:
            if isinstance(entry, dict) and entry.get("enabled") is False and isinstance(entry.get("path"), str):
                disabled_skill_paths.add(os.path.realpath(os.path.expanduser(entry["path"])))
        for key, value in (data.get("shell_environment_policy") or {}).items() if isinstance(data.get("shell_environment_policy"), dict) else []:
            if key == "set" and isinstance(value, dict):
                for env_key, env_value in value.items():
                    if is_literal_secret(str(env_key), env_value):
                        h["secrets"].append({"source": source, "file": path, "key": f"shell_environment_policy.set.{env_key}", "scope": scope})
    for rules_dir, scope in ((home / "rules", "user"), (project / ".codex" / "rules" if project else None, "project")):
        if rules_dir is None or not rules_dir.is_dir():
            continue
        for path in sorted(rules_dir.glob("*.rules")):
            for rule in parse_codex_rules(read_text(path) or ""):
                h["exec_rules"].append({**rule, "scope": scope, "source": f"{display(path, roots)}:{rule['line']}"})
    override = home / "AGENTS.override.md"
    instruction(h, override if override.is_file() else home / "AGENTS.md", "user", roots)
    for directory in reversed(project_chain(project)):
        scope = "project" if directory == project else "ancestor"
        local_override = directory / "AGENTS.override.md"
        instruction(h, local_override if local_override.is_file() else directory / "AGENTS.md", scope, roots)
    credential = home / "auth.json"
    if credential.is_file():
        h["credential_files"] = [credential]
    h["disabled_skill_paths"] = disabled_skill_paths
    return h


def collect_pi(roots: dict, project: Path | None) -> dict:
    h = new_harness("pi")
    agent = Path(roots["pi"])
    h["posture"].append({"rule": "posture/no-approval-gate", "severity": "info", "scope": "user",
                         "source": display(agent, roots),
                         "detail": "Pi runs tool calls without asking; isolation (container or VM) is its documented safety boundary"})
    layers = [("user", agent, agent / "settings.json")]
    if project is not None:
        layers.append(("project", project / ".pi", project / ".pi" / "settings.json"))
    for scope, base, path in layers:
        data, error = read_json(path)
        add_layer(h, scope, path, roots, error)
        source = display(path, roots)
        if isinstance(data, dict):
            h["scalars"] += [row for row in flatten_scalars(data, scope, source)
                             if row["key"] in {"defaultProvider", "defaultModel", "enableSkillCommands", "defaultThinkingLevel"}]
            for item in data.get("packages", []) if isinstance(data.get("packages"), list) else []:
                spec = item.get("source") if isinstance(item, dict) else item
                if isinstance(spec, str):
                    h["packages"].append({"spec": spec, "scope": scope, "source": source})
            for item in data.get("extensions", []) if isinstance(data.get("extensions"), list) else []:
                if isinstance(item, str) and not item.startswith(("-", "!", "builtin:", "+builtin:")):
                    h["extensions"].append({"path": item, "scope": scope, "source": source})
        extensions_dir = base / "extensions"
        if extensions_dir.is_dir():
            for child in sorted(extensions_dir.iterdir()):
                h["extensions"].append({"path": display(child, roots), "scope": scope, "source": display(extensions_dir, roots)})
        mcp_path = base / "mcp.json"
        data, error = read_json(mcp_path)
        if error:
            h["parse_errors"].append({"path": display(mcp_path, roots), "scope": scope, "error": error})
        if isinstance(data, dict):
            add_mcp_servers(h, data.get("mcpServers", {}), scope=scope, source=display(mcp_path, roots))
        models_path = base / "models.json"
        data, _ = read_json(models_path)
        providers = data.get("providers") if isinstance(data, dict) and isinstance(data.get("providers"), dict) else {}
        for provider, entry in providers.items():
            if not isinstance(entry, dict):
                continue
            value = entry.get("apiKey")
            if isinstance(value, str) and not re.fullmatch(r"[A-Z][A-Z0-9_]+", value) and is_literal_secret("apiKey", value):
                h["secrets"].append({"source": display(models_path, roots), "file": models_path,
                                     "key": f"providers.{provider}.apiKey", "scope": scope})
            headers = entry.get("headers") if isinstance(entry.get("headers"), dict) else {}
            for key, header in headers.items():
                if is_literal_secret(str(key), header):
                    h["secrets"].append({"source": display(models_path, roots), "file": models_path,
                                         "key": f"providers.{provider}.headers.{key}", "scope": scope})
        for name in ("SYSTEM.md", "APPEND_SYSTEM.md") + (("AGENTS.md",) if scope == "user" else ()):
            instruction(h, base / name, scope, roots)
    for directory in reversed(project_chain(project)):
        scope = "project" if directory == project else "ancestor"
        for name in ("AGENTS.override.md", "AGENTS.md", "CLAUDE.md"):
            if (directory / name).is_file():
                instruction(h, directory / name, scope, roots)
                break
    credential = agent / "auth.json"
    if credential.is_file():
        h["credential_files"] = [credential]
    return h


def collect_cursor(roots: dict, project: Path | None) -> dict:
    h = new_harness("cursor")
    user = Path(roots["cursor"])
    configs = [("user", user / "cli-config.json")]
    if project is not None:
        configs.append(("project", project / ".cursor" / "cli.json"))
    for scope, path in configs:
        data, error = read_json(path, jsonc=True)
        add_layer(h, scope, path, roots, error)
        permissions = data.get("permissions") if isinstance(data, dict) and isinstance(data.get("permissions"), dict) else {}
        for kind in ("allow", "deny"):
            for rule in permissions.get(kind, []) if isinstance(permissions.get(kind), list) else []:
                if isinstance(rule, str):
                    h["permissions"].append({"list": kind, "rule": rule, "scope": scope, "source": display(path, roots)})
    bases = [("user", user)] + ([("project", project / ".cursor")] if project is not None else [])
    for scope, base in bases:
        data, error = read_json(base / "mcp.json", jsonc=True)
        if error:
            h["parse_errors"].append({"path": display(base / "mcp.json", roots), "scope": scope, "error": error})
        if isinstance(data, dict):
            add_mcp_servers(h, data.get("mcpServers", {}), scope=scope, source=display(base / "mcp.json", roots))
        data, error = read_json(base / "hooks.json", jsonc=True)
        if error:
            h["parse_errors"].append({"path": display(base / "hooks.json", roots), "scope": scope, "error": error})
        if isinstance(data, dict):
            h["hooks"] += hook_rows(data.get("hooks", {}), source=display(base / "hooks.json", roots), scope=scope,
                                    origin="settings", base=project if scope == "project" else base)
        agents_in(h, base / "agents", scope, roots)
    if project is not None:
        rules_dir = project / ".cursor" / "rules"
        if rules_dir.is_dir():
            for path in sorted(walk_files(rules_dir, max_entries=2_000)):
                if path.suffix in {".mdc", ".md"}:
                    instruction(h, path, "project", roots)
        instruction(h, project / ".cursorrules", "project", roots)
        instruction(h, project / "AGENTS.md", "project", roots)
    return h


def collect_opencode(roots: dict, project: Path | None) -> dict:
    h = new_harness("opencode")
    config = Path(roots["opencode"])
    candidates = [("user", config / "opencode.jsonc"), ("user", config / "opencode.json")]
    if project is not None:
        candidates += [("project", project / "opencode.jsonc"), ("project", project / "opencode.json"),
                       ("project", project / ".opencode" / "opencode.jsonc"), ("project", project / ".opencode" / "opencode.json")]
    for scope, path in candidates:
        if not path.exists():
            continue
        data, error = read_json(path, jsonc=True)
        add_layer(h, scope, path, roots, error)
        if not isinstance(data, dict):
            continue
        source = display(path, roots)
        permission = data.get("permission")
        if permission == "allow":
            h["posture"].append({"rule": "perm/bypass-mode", "severity": "high", "scope": scope, "source": source,
                                 "detail": "permission = \"allow\" lets every tool run without asking"})
        elif isinstance(permission, dict):
            for tool, value in permission.items():
                if isinstance(value, str):
                    h["permissions"].append({"list": value, "rule": f"{tool}", "scope": scope, "source": source})
                elif isinstance(value, dict):
                    for pattern, action in value.items():
                        if isinstance(action, str):
                            h["permissions"].append({"list": action, "rule": f"{tool}({pattern})", "scope": scope, "source": source})
        add_mcp_servers(h, data.get("mcp"), scope=scope, source=source)
        for item in data.get("plugin", []) if isinstance(data.get("plugin"), list) else []:
            if isinstance(item, str):
                h["packages"].append({"spec": f"npm:{item}" if not item.startswith((".", "/", "~")) else item,
                                      "scope": scope, "source": source})
        providers = data.get("provider") if isinstance(data.get("provider"), dict) else {}
        for provider, entry in providers.items():
            options = entry.get("options") if isinstance(entry, dict) and isinstance(entry.get("options"), dict) else {}
            for key, value in options.items():
                if is_literal_secret(str(key), value):
                    h["secrets"].append({"source": source, "file": path, "key": f"provider.{provider}.options.{key}", "scope": scope})
        for item in data.get("instructions", []) if isinstance(data.get("instructions"), list) else []:
            if isinstance(item, str) and "*" not in item:
                base = path.parent
                target = Path(item).expanduser() if item.startswith(("~", "/")) else base / item
                instruction(h, target, scope, roots)
    instruction(h, config / "AGENTS.md", "user", roots)
    for directory in reversed(project_chain(project)):
        scope = "project" if directory == project else "ancestor"
        if (directory / "AGENTS.md").is_file():
            instruction(h, directory / "AGENTS.md", scope, roots)
        elif (directory / "CLAUDE.md").is_file():
            instruction(h, directory / "CLAUDE.md", scope, roots)
    for scope, base in [("user", config)] + ([("project", project / ".opencode")] if project is not None else []):
        for name in ("agent", "agents"):
            agents_in(h, base / name, scope, roots)
        for name in ("plugin", "plugins"):
            directory = base / name
            if directory.is_dir():
                for child in sorted(directory.iterdir()):
                    h["extensions"].append({"path": display(child, roots), "scope": scope, "source": display(directory, roots)})
    return h


COLLECTORS = {
    "claude-code": collect_claude, "codex": collect_codex, "pi": collect_pi,
    "cursor": collect_cursor, "opencode": collect_opencode,
}
VERSION_BINARIES = {"claude-code": "claude", "codex": "codex", "pi": "pi", "cursor": "cursor-agent", "opencode": "opencode"}


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


class Findings:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, rule: str, severity: str, area: str, harness: str | list, title: str,
            evidence: list[str], fix: str) -> None:
        harnesses = harness if isinstance(harness, list) else [harness]
        self.items.append({
            "rule": rule, "severity": severity, "area": area, "harness": harnesses, "title": title,
            "evidence": [short(item, 240) for item in evidence[:MAX_EVIDENCE]],
            "evidence_total": len(evidence), "fix": fix,
        })


def expand_path(token: str, *, roots: dict, project: Path | None, plugin_root: Path | None) -> Path | None:
    replacements = {
        "${CLAUDE_PROJECT_DIR}": str(project) if project else None,
        "$CLAUDE_PROJECT_DIR": str(project) if project else None,
        "${CLAUDE_PLUGIN_ROOT}": str(plugin_root) if plugin_root else None,
        "$CLAUDE_PLUGIN_ROOT": str(plugin_root) if plugin_root else None,
        "${HOME}": str(roots["home"]), "$HOME": str(roots["home"]),
    }
    for variable, value in replacements.items():
        if variable in token:
            if value is None:
                return None
            token = token.replace(variable, value)
    if "$" in token:
        return None
    if token.startswith("~/"):
        return Path(roots["home"]) / token[2:]
    return Path(token)


def hook_script(command: str, *, roots: dict, project: Path | None, base: Path | None) -> Path | None:
    """The script file a hook command depends on, when it can be resolved statically."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    if not tokens:
        return None
    candidate = tokens[0]
    interpreters = {"python", "python3", "node", "bash", "sh", "zsh", "bun", "deno", "ruby", "perl", "uv"}
    if os.path.basename(candidate) in interpreters:
        rest = [token for token in tokens[1:] if not token.startswith("-") and token != "run"]
        if not rest:
            return None
        candidate = rest[0]
    if "/" not in candidate and not candidate.startswith(("$", "~")):
        return None
    path = expand_path(candidate, roots=roots, project=project, plugin_root=base)
    if path is None:
        return None
    if not path.is_absolute():
        if base is None:
            return None
        path = base / path
    return path


def hook_owner(hook: dict) -> str:
    return hook["source"] if hook["origin"] == "settings" else hook["origin"]


def matchers_overlap(left: str, right: str) -> bool:
    if left in {"", "*", ".*"} or right in {"", "*", ".*"}:
        return True
    return bool(set(left.split("|")) & set(right.split("|")))


def permission_rules(f: Findings, h: dict) -> None:
    kind = h["harness"]
    allows = [row for row in h["permissions"] if row["list"] == "allow"]
    blocks = [row for row in h["permissions"] if row["list"] in {"deny", "ask"}]
    shell_tools = {"Bash", "Shell", "bash"}
    dead: set[int] = set()
    for index, row in enumerate(allows):
        tool, spec = rule_parts(row["rule"])
        for block in blocks:
            other_tool, other_spec = rule_parts(block["rule"])
            if other_tool != tool:
                continue
            evidence = [f"{row['source']}: allow {row['rule']}", f"{block['source']}: {block['list']} {block['rule']}"]
            if row["rule"].strip() == block["rule"].strip():
                dead.add(index)
                f.add("perm/allow-deny-conflict", "medium", "coherence", kind,
                      f"`{row['rule']}` is both allowed and in {block['list']}", evidence,
                      f"Keep `{row['rule']}` in one list; {block['list']} takes precedence, so the allow entry is misleading.")
                continue
            if tool in shell_tools:
                allow_prefix, block_prefix = command_prefix(spec), command_prefix(other_spec)
                covered = block_prefix == "" or allow_prefix == block_prefix or allow_prefix.startswith(block_prefix + " ")
            else:
                covered = other_spec is None
            if covered and block["list"] == "deny":
                dead.add(index)
                f.add("perm/dead-allow", "low", "coherence", kind,
                      f"`{row['rule']}` can never apply because `{block['rule']}` denies it", evidence,
                      f"Delete the allow entry, or narrow the deny rule if `{row['rule']}` should work.")
    for index, row in enumerate(allows):
        if index in dead:
            continue
        tool, spec = rule_parts(row["rule"])
        if tool in shell_tools:
            risk = classify_prefix(command_prefix(spec))
            where = f"{row['source']}: allow {row['rule']}"
            if risk == "any":
                f.add("perm/broad-allow", "high", "safety", kind, "Every shell command is pre-approved", [where],
                      f"Remove `{row['rule']}` and allow the specific read-only commands you use instead.")
            elif risk == "exec":
                f.add("perm/broad-allow", "high", "safety", kind,
                      f"`{row['rule']}` pre-approves an interpreter, which can run anything", [where],
                      f"Replace `{row['rule']}` with the exact scripts you run, or keep it on ask.")
            elif risk in {"network", "destructive"}:
                f.add("perm/broad-allow", "medium", "safety", kind,
                      f"`{row['rule']}` pre-approves a {risk} command family", [where],
                      f"Narrow `{row['rule']}` to the specific invocation, or move it to ask.")
        elif tool in {"Write", "Edit"} and (spec is None or spec.strip() in {"**", "/**", "//**", "*"}):
            f.add("perm/broad-allow", "low", "safety", kind, f"`{row['rule']}` pre-approves edits anywhere",
                  [f"{row['source']}: allow {row['rule']}"], "Scope the rule to the project path, for example `Edit(./**)`.")
    for rule in h["exec_rules"]:
        tokens = rule["pattern"]
        first = tokens[0] if tokens else ""
        if rule["decision"] != "allow" or not first:
            continue
        risk = classify_prefix(" ".join(tokens))
        if risk == "exec" and len(tokens) == 1:
            f.add("perm/broad-allow", "high", "safety", kind,
                  f"Exec rule allows `{first}` with any arguments, which can run anything",
                  [f"{rule['source']}: prefix_rule(pattern={tokens}, decision=allow)"],
                  "Add the script or subcommand to the pattern, or set the decision to prompt.")
        elif risk in {"network", "destructive"}:
            f.add("perm/broad-allow", "medium", "safety", kind, f"Exec rule allows the {risk} command `{first}`",
                  [f"{rule['source']}: prefix_rule(pattern={tokens}, decision=allow)"],
                  "Narrow the pattern or set the decision to prompt.")
        for other in h["exec_rules"]:
            if other["decision"] == "forbidden" and tokens[: len(other["pattern"])] == other["pattern"]:
                f.add("perm/dead-allow", "low", "coherence", kind,
                      f"Exec rule allowing {tokens} is overridden by a forbidden rule",
                      [rule["source"], other["source"]], "Delete the allow rule or narrow the forbidden one.")


def posture_rules(f: Findings, h: dict) -> None:
    for row in h["posture"]:
        area = "safety"
        title = row["detail"]
        f.add(row["rule"], row["severity"], area, h["harness"], title, [row["source"]],
              {
                  "perm/bypass-mode": "Use a prompting mode by default and opt into bypass only inside an isolated container or VM.",
                  "perm/unsandboxed": "Use workspace-write unless the work runs inside an isolated environment.",
                  "perm/never-ask": "Prefer on-request approvals unless the sandbox is the boundary you intend.",
                  "perm/sandbox-network": "Enable network access per session when a task needs it.",
                  "perm/project-mcp-autoapprove": "Turn it off and approve project MCP servers one at a time (enabledMcpjsonServers).",
                  "perm/trusted-broad-path": "Trust individual repositories instead of a parent directory.",
                  "posture/no-approval-gate": "Run Pi inside a container or VM for untrusted repositories.",
              }.get(row["rule"], "Review this setting."))
    kind = h["harness"]
    if kind == "opencode" and h["detected"]:
        bash_rules = [row for row in h["permissions"] if rule_parts(row["rule"])[0] == "bash"]
        if not bash_rules:
            f.add("posture/default-permissions", "info", "safety", kind,
                  "No permission.bash is configured, so OpenCode's defaults decide whether shell commands ask",
                  [layer["path"] for layer in h["layers"]] or ["no opencode.json found"],
                  "Set permission.bash to ask, with explicit allow patterns for the commands you trust.")


def secret_rules(f: Findings, h: dict, project: Path | None) -> None:
    for row in h["secrets"]:
        path = row["file"]
        tracked = project is not None and str(path).startswith(str(project)) and git_tracked(path)
        severity = "critical" if tracked else "high"
        where = f"{row['source']}: {row['key']}" + (" (tracked by git)" if tracked else "")
        f.add("secret/literal-in-config", severity, "safety", h["harness"],
              "A literal secret is stored in configuration" + (" that is committed to git" if tracked else ""),
              [where], "Move the value to an environment variable or the harness's credential store, reference it "
                       "by name, and rotate it" + (" because it is in git history." if tracked else "."))
    for server in h["mcp"]:
        if server["secret_keys"]:
            f.add("secret/mcp-literal", "high", "safety", h["harness"],
                  f"MCP server `{server['name']}` carries a literal secret in its definition",
                  [f"{server['source']}: {', '.join(server['secret_keys'])}"],
                  "Reference the secret through an environment variable instead of a literal value, and rotate it.")
    for path in h.get("credential_files", []):
        try:
            mode = path.stat().st_mode
        except OSError:
            continue
        if os.name == "posix" and mode & 0o077:
            f.add("secret/credential-file-permissions", "medium", "safety", h["harness"],
                  "The harness credential file is readable by other accounts",
                  [f"{path.name} mode {stat.filemode(mode)}"], f"chmod 600 {shlex.quote(str(path))}")


def mcp_rules(f: Findings, h: dict) -> None:
    kind = h["harness"]
    for server in h["mcp"]:
        if not server["enabled"]:
            continue
        if server["launcher"] and server["package"] and server["pinned"] is False:
            f.add("mcp/unpinned-package", "medium", "safety", kind,
                  f"MCP server `{server['name']}` launches an unpinned package on every start",
                  [f"{server['source']}: {server['launcher']} {server['package']}"],
                  f"Pin an exact version (for example `{server['package'].split('@latest')[0]}@<version>`) or a digest.")
        if server["insecure_http"]:
            f.add("mcp/insecure-http", "medium", "safety", kind,
                  f"MCP server `{server['name']}` uses plain HTTP to a non-loopback host",
                  [f"{server['source']}: {server['name']}"], "Use the server's https:// endpoint.")
    by_name: dict[str, list[dict]] = {}
    for server in h["mcp"]:
        by_name.setdefault(server["name"], []).append(server)
    precedence = {"claude-code": "local > project > user", "pi": "project replaces user",
                  "cursor": "project overrides user", "opencode": "project overrides user", "codex": "project overrides user"}
    for name, servers in by_name.items():
        if len({server["fingerprint"] for server in servers}) > 1:
            f.add("mcp/duplicate-name", "low", "coherence", kind,
                  f"MCP server `{name}` is defined differently in {len(servers)} places",
                  [f"{server['scope']}: {server['source']}" for server in servers],
                  f"Keep one definition; precedence is {precedence.get(kind, 'harness-specific')}.")
    enabled = [server for server in h["mcp"] if server["enabled"]]
    if len(enabled) > 8:
        f.add("context/many-mcp", "low", "context", kind,
              f"{len(enabled)} MCP servers are configured; each adds tool definitions to context",
              sorted({server["name"] for server in enabled}), "Disable servers you do not use in this project; check /context for their real cost.")
    for package in h["packages"]:
        spec = package["spec"]
        pinned = None
        if spec.startswith("npm:"):
            pinned = is_pinned_package(spec[4:], python=False)
        elif spec.startswith(("git:", "https://", "http://", "ssh://", "git@")):
            tail = spec.split("/")[-1]
            pinned = "@" in tail or "#" in spec
        if pinned is False:
            f.add("supply/unpinned-package", "medium", "safety", kind,
                  f"Package `{spec}` is not pinned, so updates install code you have not reviewed",
                  [f"{package['source']}: {spec}"], "Pin an exact version or git ref.")


def hook_rules(f: Findings, h: dict, roots: dict, project: Path | None) -> None:
    kind = h["harness"]
    commands = [hook for hook in h["hooks"] if hook["command"]]
    for hook in commands:
        where = f"{hook['source']}: {hook['event']}" + (f" [{hook['matcher']}]" if hook["matcher"] else "")
        command = redact(hook["command"])
        if REMOTE_EXEC_RE.search(hook["command"]):
            f.add("hooks/remote-exec", "critical", "safety", kind, "A hook downloads and executes code",
                  [f"{where}: {short(command, 160)}"], "Vendor the script locally, review it, and run the local copy.")
        elif NETWORK_RE.search(hook["command"]):
            f.add("hooks/network", "medium", "safety", kind, "A hook sends or fetches data over the network on every event",
                  [f"{where}: {short(command, 160)}"], "Confirm what the hook sends; keep transcripts and file contents local.")
        script = hook_script(hook["command"], roots=roots, project=project, base=hook["base"])
        if script is not None and not script.exists():
            f.add("hooks/missing-script", "high", "hygiene", kind, "A hook points at a script that does not exist",
                  [f"{where}: {display(script, roots)}"],
                  "Fix the path or remove the hook; it fails on every matching event.")
        if hook["event"] in {"PreToolUse", "PostToolUse"} and hook["matcher"] in {"", "*", ".*"}:
            f.add("hooks/every-tool-call", "low", "context", kind, "A hook runs on every tool call",
                  [where], "Narrow the matcher to the tools the hook cares about.")
    by_event: dict[str, list[dict]] = {}
    for hook in commands:
        by_event.setdefault(hook["event"], []).append(hook)
    for event, hooks in by_event.items():
        groups: list[list[dict]] = []
        for hook in hooks:
            for group in groups:
                if any(matchers_overlap(hook["matcher"], other["matcher"]) for other in group):
                    group.append(hook)
                    break
            else:
                groups.append([hook])
        for group in groups:
            sources = {hook_owner(hook) for hook in group}
            if len(sources) < 2:
                continue
            evidence = [f"{hook_owner(hook)}: {event}" + (f" [{hook['matcher']}]" if hook["matcher"] else "")
                        for hook in group]
            if event in BLOCKING_EVENTS:
                f.add("hooks/stacked", "medium", "coherence", kind,
                      f"{len(sources)} independent hooks can block or rewrite the same {event} events", evidence,
                      "Check that their decisions agree; one blocking hook can hide another's output.")
            elif event in CONTEXT_EVENTS:
                f.add("hooks/stacked", "low", "context", kind,
                      f"{len(sources)} independent hooks inject context on {event}", evidence,
                      "Merge or drop overlapping session-start reports.")


def skill_rules(f: Findings, harnesses: list[dict]) -> None:
    for h in harnesses:
        kind = h["harness"]
        disabled = h.get("disabled_skill_paths", set())
        skills = [skill for skill in h["skills"] if os.path.realpath(skill["real_path"]) not in disabled]
        h["skills"] = skills
        for skill in skills:
            if skill["frontmatter_error"]:
                f.add("skills/invalid-frontmatter", "medium", "hygiene", kind,
                      f"Skill `{skill['name']}` has unusable metadata ({skill['frontmatter_error']})",
                      [skill["path"]], "Add a frontmatter block with name and description; some harnesses skip it otherwise.")
            if len(skill["description"]) > 1024:
                f.add("skills/description-too-long", "medium", "hygiene", kind,
                      f"Skill `{skill['name']}` has a {len(skill['description'])}-character description",
                      [skill["path"]], "Keep descriptions under 1024 characters; longer ones are truncated or rejected.")
            if kind != "claude-code" and skill["declared_name"] and skill["declared_name"] != skill["dir_name"]:
                f.add("skills/name-mismatch", "low", "hygiene", kind,
                      f"Skill name `{skill['declared_name']}` differs from its directory `{skill['dir_name']}`",
                      [skill["path"]], "Rename the directory or the name field so they match.")
        owners: dict[str, set[str]] = {}
        for skill in skills:
            owners.setdefault(skill["name"], set()).add(skill["origin"] or f"{skill['scope']} skills")
        for name, origin_set in owners.items():
            plugin_origins = {origin for origin in origin_set if origin.startswith("plugin:")}
            if plugin_origins and len(origin_set) > 1:
                f.add("skills/plugin-overlap", "medium", "coherence", kind,
                      f"Skill name `{name}` is shipped by {len(origin_set)} sources",
                      sorted(origin_set), "Disable one source; overlapping skills compete for the same requests.")
        builtins = CLAUDE_BUILTINS if kind == "claude-code" else CODEX_BUILTINS if kind == "codex" else set()
        for item in [*skills, *h["commands"]]:
            if item["scope"] != "plugin" and item["name"] in builtins:
                f.add("skills/shadows-builtin", "low", "coherence", kind,
                      f"`{item['name']}` has the same name as a built-in command",
                      [item["path"]], "Rename it so `/` completion and routing are unambiguous.")
        agent_names: dict[str, list[dict]] = {}
        for agent in h["agents"]:
            agent_names.setdefault(agent["name"], []).append(agent)
        for name, copies in agent_names.items():
            if len({copy["scope"] for copy in copies}) > 1:
                f.add("agents/duplicate-name", "low", "coherence", kind, f"Subagent `{name}` is defined in several scopes",
                      [f"{copy['scope']}: {copy['path']}" for copy in copies], "Keep one definition.")
    # One finding per skill name: copies loaded twice by one harness, or diverged between harnesses.
    copies: dict[str, dict[str, dict]] = {}
    for h in harnesses:
        for skill in h["skills"]:
            if skill["scope"] == "plugin":
                continue
            entry = copies.setdefault(skill["name"], {}).setdefault(
                skill["real_path"], {"path": skill["path"], "hash": skill["content_hash"], "harnesses": [], "scope": skill["scope"]})
            entry["harnesses"].append(h["harness"])
    for name, by_path in copies.items():
        if len(by_path) < 2:
            continue
        loaded_twice = sorted(h["harness"] for h in harnesses
                              if sum(h["harness"] in entry["harnesses"] for entry in by_path.values()) > 1)
        differ = len({entry["hash"] for entry in by_path.values()}) > 1
        if not loaded_twice and not differ:
            continue
        evidence = [f"{entry['path']} ({', '.join(entry['harnesses'])})" for entry in by_path.values()]
        affected = sorted({kind for entry in by_path.values() for kind in entry["harnesses"]})
        if loaded_twice:
            f.add("skills/duplicate-name", "medium" if differ else "low", "coherence", loaded_twice,
                  f"Skill `{name}` is installed {len(by_path)} times" + (" with different content" if differ else ""),
                  evidence, "Keep one copy; the harness loads only one of them (Pi keeps the first and warns), so edits "
                            "to the others have no effect.")
        else:
            f.add("skills/cross-harness-drift", "medium", "coherence", affected,
                  f"Skill `{name}` differs between harness directories", evidence,
                  "Keep one canonical copy (for example ~/.agents/skills) and link or remove the others.")


def plugin_rules(f: Findings, h: dict) -> None:
    for plugin in h["plugins"]:
        if plugin["enabled"] and not plugin["installed"]:
            f.add("plugins/enabled-missing", "low", "hygiene", h["harness"],
                  f"Plugin `{plugin['id']}` is enabled but not installed", [plugin["id"]],
                  f"Run `claude plugin install {plugin['id']}` or remove it from enabledPlugins.")


def scope_override_rules(f: Findings, h: dict) -> None:
    order = {"user": 0, "project": 1, "local": 2, "managed": 3}
    by_key: dict[str, list[dict]] = {}
    for row in h["scalars"]:
        by_key.setdefault(row["key"], []).append(row)
    for key, rows in by_key.items():
        values = {json.dumps(row["value"], sort_keys=True) for row in rows}
        if len(rows) < 2 or len(values) < 2:
            continue
        winner = max(rows, key=lambda row: order.get(row["scope"], 0))
        severity = "medium" if key in SECURITY_SETTING_KEYS else "low"
        f.add("settings/scope-override", severity, "coherence", h["harness"],
              f"`{key}` is set differently in {len(rows)} scopes; {winner['scope']} wins",
              [f"{row['scope']}: {row['source']} = {short(row['value'], 60)}" for row in rows],
              f"Set `{key}` in one place so the effective value is obvious.")


def parse_error_rules(f: Findings, h: dict) -> None:
    for row in h["parse_errors"]:
        f.add("settings/parse-error", "medium", "hygiene", h["harness"], "A configuration file cannot be parsed and is ignored",
              [f"{row['path']}: {row['error']}"], "Fix the syntax; the harness falls back to defaults for this file.")


def instruction_rules(f: Findings, h: dict, roots: dict) -> None:
    if h["harness"] != "claude-code":
        return
    for item in h["instructions"]:
        for number, target, path in import_targets(item["text"], item["file"].parent, roots):
            if not path.exists():
                f.add("instructions/missing-import", "medium", "hygiene", "claude-code",
                      f"`@{target}` is imported but does not exist", [f"{item['path']}:{number}"],
                      "Fix the path or remove the import; the referenced instructions never load.")


def split_source_rules(f: Findings, harnesses: list[dict], project: Path | None) -> list[dict]:
    """Projects that carry both CLAUDE.md and AGENTS.md independently can drift apart."""
    if project is None:
        return []
    detected = {h["harness"] for h in harnesses if h["detected"]}
    if "claude-code" not in detected or not detected & {"codex", "pi", "cursor", "opencode"}:
        return []
    claude = next((project / name for name in ("CLAUDE.md", ".claude/CLAUDE.md") if (project / name).is_file()), None)
    agents = project / "AGENTS.md"
    if claude is None or not agents.is_file():
        return []
    claude_text, agents_text = read_text(claude) or "", read_text(agents) or ""
    if os.path.realpath(claude) == os.path.realpath(agents) or claude_text == agents_text:
        return []
    if re.search(r"(?m)^\s*@\.?/?AGENTS\.md\b", claude_text) or re.search(r"(?m)^\s*@\.?/?CLAUDE\.md\b", agents_text):
        return []
    f.add("instructions/split-sources", "low", "coherence", sorted(detected),
          "CLAUDE.md and AGENTS.md are maintained separately, so harnesses can receive different rules",
          [str(claude.relative_to(project)), "AGENTS.md"],
          "Make one the source (for example a CLAUDE.md that contains only `@AGENTS.md`) and compare their rules.")
    return [{"left": str(claude.relative_to(project)), "right": "AGENTS.md"}]


def unsafe_skill_rules(f: Findings, harnesses: list[dict], casefile_ran: set[str]) -> None:
    """Basic per-skill checks used when casefile did not scan a skill."""
    seen: set[str] = set()
    for h in harnesses:
        for skill in h["skills"]:
            directory = os.path.dirname(skill["real_path"])
            if directory in seen or any(directory == ran or directory.startswith(ran + os.sep) for ran in casefile_ran):
                continue
            seen.add(directory)
            hits = []
            for path in list(walk_files(Path(directory), max_entries=500))[:200]:
                text = read_text(path, 256_000)
                if text is None:
                    continue
                name = path.name
                if REMOTE_EXEC_RE.search(text):
                    hits.append(("high", f"{name}: downloads and executes code"))
                if HIDDEN_UNICODE_RE.search(text):
                    hits.append(("high", f"{name}: hidden or bidirectional Unicode characters"))
                if INJECTION_RE.search(text):
                    hits.append(("medium", f"{name}: instruction-override phrase"))
            for severity, detail in hits[:3]:
                f.add("skills/unsafe-basic", severity, "safety", h["harness"],
                      f"Skill `{skill['name']}`: {detail.split(': ', 1)[1]}", [f"{skill['path']} ({detail.split(':')[0]})"],
                      "Read the flagged file before trusting this skill; run casefile for a full scan.")


def run_casefile(f: Findings, harnesses: list[dict], mode: str, roots: dict) -> tuple[dict, set[str]]:
    executable = shutil.which("casefile") if mode != "off" else None
    info: dict = {"available": bool(executable), "mode": mode, "targets": 0, "scanned": 0, "failed": 0,
                  "summary": {"critical": 0, "warning": 0, "info": 0}}
    ran: set[str] = set()
    if mode == "off":
        info["skipped"] = "disabled with --casefile off"
        return info, ran
    if not executable:
        info["skipped"] = "casefile is not on PATH; per-skill safety used the basic checks only (npm i -g casefile)"
        return info, ran
    targets: list[tuple[str, str]] = []
    for h in harnesses:
        for plugin in h["plugins"]:
            if plugin["enabled"] and plugin["installed"] and plugin["install_path"]:
                path = str(Path(str(plugin["install_path"]).replace("~", str(roots["home"]), 1)))
                targets.append((h["harness"], os.path.realpath(path)))
        for skill in h["skills"]:
            if skill["scope"] != "plugin":
                targets.append((h["harness"], os.path.dirname(skill["real_path"])))
    unique = list(dict.fromkeys(targets))
    info["targets"] = len(unique)
    for kind, target in unique[:CASEFILE_MAX_TARGETS]:
        try:
            result = subprocess.run([executable, "scan", target, "--json", "--no-store", "--fail-on", "none"],
                                    capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
            report = json.loads(result.stdout)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            info["failed"] += 1
            continue
        info["scanned"] += 1
        ran.add(target)
        for finding in report.get("findings", []) if isinstance(report, dict) else []:
            if not isinstance(finding, dict):
                continue
            severity, rule = finding.get("severity"), str(finding.get("ruleId", "unknown"))
            if severity in info["summary"]:
                info["summary"][severity] += 1
            family = rule.split("/", 1)[0]
            if severity == "critical":
                mapped, area = "high", "safety" if family in {"capability", "injection", "supplychain"} else "hygiene"
            elif severity == "warning":
                mapped = "medium" if family in {"injection", "supplychain"} else "low"
                area = "safety" if family in {"capability", "injection", "supplychain"} else "hygiene"
            else:
                continue
            location = str(finding.get("file", ""))
            if finding.get("line"):
                location += f":{finding['line']}"
            f.add(f"casefile/{rule}", mapped, area, kind, short(finding.get("message", rule), 160),
                  [f"{display(Path(target), roots)}: {location}"], "Review the flagged file; casefile explains each rule.")
    if len(unique) > CASEFILE_MAX_TARGETS:
        info["truncated"] = len(unique) - CASEFILE_MAX_TARGETS
    return info, ran


# ---------------------------------------------------------------------------
# Judgment candidates and grades
# ---------------------------------------------------------------------------


def stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > 5 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def trigger_tokens(description: str) -> set[str]:
    positive = ANTI_TRIGGER_SPLIT.split(description, maxsplit=1)[0]
    return {stem(word) for word in re.findall(r"[a-z][a-z0-9-]{2,}", positive.lower()) if word not in STOPWORDS}


def routing_pairs(harnesses: list[dict]) -> list[dict]:
    pairs: dict[tuple[str, str], dict] = {}
    for h in harnesses:
        skills = [skill for skill in h["skills"] if skill["model_invoked"] and skill["description"]]
        tokens = {id(skill): trigger_tokens(skill["description"]) for skill in skills}
        for index, left in enumerate(skills):
            for right in skills[index + 1:]:
                if left["name"] == right["name"]:
                    continue  # same-name copies are reported as duplicates, not routing pairs
                owner_left = left["origin"] or os.path.dirname(os.path.dirname(left["real_path"]))
                owner_right = right["origin"] or os.path.dirname(os.path.dirname(right["real_path"]))
                if owner_left == owner_right and left["origin"]:
                    continue
                shared = tokens[id(left)] & tokens[id(right)]
                union = tokens[id(left)] | tokens[id(right)]
                if len(shared) < 4 or not union:
                    continue
                score = len(shared) / len(union)
                if score < 0.15:
                    continue
                key = tuple(sorted((left["name"], right["name"])))
                if key in pairs and pairs[key]["score"] >= score:
                    if h["harness"] not in pairs[key]["harness"]:
                        pairs[key]["harness"].append(h["harness"])
                    continue
                previous = pairs.pop(key, None)
                entry = pairs.setdefault(key, {
                    "score": round(score, 3), "harness": previous["harness"] if previous else [],
                    "shared_terms": sorted(shared)[:12],
                    "skills": [
                        {"name": skill["name"], "source": skill["origin"] or skill["scope"], "path": skill["path"],
                         "description": short(redact(skill["description"]), 500)}
                        for skill in (left, right)
                    ],
                })
                if h["harness"] not in entry["harness"]:
                    entry["harness"].append(h["harness"])
    return sorted(pairs.values(), key=lambda item: -item["score"])[:MAX_ROUTING_PAIRS]


def directive_lines(harnesses: list[dict]) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for h in harnesses:
        for item in h["instructions"]:
            if item["real"] in seen:
                continue
            seen.add(item["real"])
            count = 0
            in_fence = False
            for number, line in enumerate(item["text"].splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith(("```", "~~~")):
                    in_fence = not in_fence
                    continue
                if in_fence or len(stripped) < 12 or stripped.startswith(("#", "|", "<!--", "@")):
                    continue
                if DIRECTIVE_RE.search(stripped) or re.match(r"^(?:[-*+]|\d+[.)])\s+\S", stripped):
                    rows.append({"path": f"{item['path']}:{number}", "harness": h["harness"],
                                 "text": short(redact(re.sub(r"^[-*+>\d.)\s]+", "", stripped)), 220)})
                    count += 1
                    if count >= MAX_DIRECTIVES_PER_FILE or len(rows) >= MAX_DIRECTIVES:
                        break
            if len(rows) >= MAX_DIRECTIVES:
                return rows
    return rows


def letter(counts: dict) -> str:
    if counts.get("critical"):
        return "F"
    if counts.get("high", 0) >= 2:
        return "D"
    if counts.get("high", 0) == 1 or counts.get("medium", 0) >= 3:
        return "C"
    if counts.get("medium", 0) >= 1:
        return "B"
    return "A"


def context_letter(tokens: int) -> str:
    return "A" if tokens < 6_000 else "B" if tokens < 12_000 else "C" if tokens < 20_000 else "D"


def grades(findings: list[dict], context_tokens: int) -> dict:
    counts = {area: {severity: 0 for severity in SEVERITIES} for area in AREAS}
    for item in findings:
        counts[item["area"]][item["severity"]] += 1
    result = {area: letter(counts[area]) for area in ("safety", "coherence", "hygiene")}
    result["context"] = context_letter(context_tokens)
    result["overall"] = max((result[area] for area in ("safety", "coherence", "hygiene")), key="ABCDF".index)
    result["counts"] = counts
    result["context_tokens"] = context_tokens
    return result


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------


def scan(args: argparse.Namespace) -> dict:
    roots = resolve_roots(Path(args.home) if args.home else None)
    project = None if args.no_project else Path(args.project or os.getcwd()).resolve()
    if project is not None and project != Path(roots["home"]).resolve():
        roots["project"] = project
    selected = HARNESSES if args.harness in (None, "auto", "all") else tuple(
        item.strip() for item in args.harness.split(",") if item.strip())
    unknown = [item for item in selected if item not in HARNESSES]
    if unknown:
        raise SystemExit(f"unknown harness: {', '.join(unknown)} (choose from {', '.join(HARNESSES)})")
    harnesses = []
    for kind in selected:
        h = COLLECTORS[kind](roots, project)
        h["detected"] = harness_present(kind, roots, project)
        found = discover(kind, roots, project)
        h["skills"], h["commands"] = found["skills"], found["commands"]
        if h["detected"] and not args.no_versions and not roots["overridden"]:
            h["version"] = detect_version(VERSION_BINARIES[kind])
        harnesses.append(h)
    active = [h for h in harnesses if h["detected"]]
    f = Findings()
    for h in active:
        permission_rules(f, h)
        posture_rules(f, h)
        secret_rules(f, h, project)
        mcp_rules(f, h)
        hook_rules(f, h, roots, project)
        plugin_rules(f, h)
        scope_override_rules(f, h)
        parse_error_rules(f, h)
        instruction_rules(f, h, roots)
    skill_rules(f, active)
    split_pairs = split_source_rules(f, active, project)
    casefile_info, casefile_ran = run_casefile(f, active, args.casefile, roots)
    unsafe_skill_rules(f, active, casefile_ran)

    summaries = []
    worst_context = 0
    for h in harnesses:
        instruction_tokens = sum(item["tokens"] for item in h["instructions"])
        listing_tokens = sum(est_tokens(skill["name"] + skill["description"]) + 8
                             for skill in h["skills"] if skill["model_invoked"])
        if h["detected"]:
            worst_context = max(worst_context, instruction_tokens + listing_tokens)
        summaries.append({
            "harness": h["harness"], "detected": h["detected"], "version": h["version"],
            "layers": [layer for layer in h["layers"] if layer["exists"]],
            "counts": {
                "skills": len(h["skills"]), "model_invoked_skills": sum(skill["model_invoked"] for skill in h["skills"]),
                "commands": len(h["commands"]), "hooks": len(h["hooks"]), "mcp_servers": len(h["mcp"]),
                "permission_rules": len(h["permissions"]) + len(h["exec_rules"]), "instruction_files": len(h["instructions"]),
                "plugins_enabled": sum(1 for plugin in h["plugins"] if plugin["enabled"]),
                "agents": len(h["agents"]), "extensions": len(h["extensions"]), "packages": len(h["packages"]),
            },
            "context": {"instruction_tokens": instruction_tokens, "skill_listing_tokens": listing_tokens,
                        "mcp_servers": sum(1 for server in h["mcp"] if server["enabled"])},
            "instructions": [{"path": item["path"], "scope": item["scope"], "tokens": item["tokens"]} for item in h["instructions"]],
            "skills": {
                "local": [{"name": skill["name"], "scope": skill["scope"], "model_invoked": skill["model_invoked"]}
                          for skill in h["skills"] if skill["scope"] != "plugin"][:100],
                "by_plugin": {origin: sum(1 for skill in h["skills"] if skill["origin"] == origin)
                              for origin in sorted({skill["origin"] for skill in h["skills"] if skill["origin"]})},
            },
        })
        if h["detected"]:
            tokens = instruction_tokens + listing_tokens
            if tokens >= 12_000:
                f.add("context/always-loaded", "medium" if tokens >= 20_000 else "low", "context", h["harness"],
                      f"About {tokens:,} tokens of instructions and skill descriptions load in every session",
                      [f"instructions ~{instruction_tokens:,}", f"skill descriptions ~{listing_tokens:,}"],
                      "Move rarely needed instructions into skills and disable skills you do not use (see /skill-doctor).")
    ordered = sorted(f.items, key=lambda item: (SEVERITIES.index(item["severity"]), item["area"], item["rule"]))
    deduped: list[dict] = []
    seen_keys: set[str] = set()
    for item in ordered:
        key = json.dumps([item["rule"], item["title"], item["evidence"]], sort_keys=True)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(item)
    graded = grades(deduped, worst_context)
    omitted = max(0, len(deduped) - MAX_FINDINGS)
    for index, item in enumerate(deduped, 1):
        item["id"] = f"F{index}"
    not_checked = [
        "MCP tool-definition size (servers are never started); see /context",
        "skill and plugin usage frequency; see /skill-doctor and /usage",
        "installation health and measured hook latency; see /doctor",
    ]
    if any(not h["detected"] for h in harnesses):
        not_checked.append("harnesses with no configuration on disk: " + ", ".join(h["harness"] for h in harnesses if not h["detected"]))
    if tomllib is None:
        not_checked.append("Codex config.toml (needs Python 3.11+)")
    return {
        "schema": SCHEMA,
        "generated_at": now_iso(),
        "project": display(project, roots) if project else None,
        "home_override": roots["overridden"],
        "harnesses": summaries,
        "grades": graded,
        "findings": deduped[:MAX_FINDINGS],
        "findings_omitted": omitted,
        "judgment": {
            "routing_pairs": routing_pairs(active),
            "instruction_directives": directive_lines(active),
            "instruction_pairs": split_pairs,
        },
        "casefile": casefile_info,
        "coverage": {"not_checked": not_checked,
                     "parse_errors": [row for h in active for row in h["parse_errors"]]},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("scan", help="inventory and audit the local harness setup")
    run.add_argument("--project", help="project root to include (default: current directory)")
    run.add_argument("--no-project", action="store_true", help="audit user-level configuration only")
    run.add_argument("--home", help="audit a copied home directory instead of the current user's")
    run.add_argument("--harness", default="auto", help="comma-separated harnesses, or auto")
    run.add_argument("--casefile", choices=["auto", "off"], default="auto",
                     help="run an installed casefile on each skill and plugin (default: auto)")
    run.add_argument("--no-versions", action="store_true", help="do not run '<harness> --version'")
    args = parser.parse_args(argv)
    report = scan(args)
    json.dump(report, sys.stdout, indent=1, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
