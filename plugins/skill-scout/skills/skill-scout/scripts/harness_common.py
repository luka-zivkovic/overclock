#!/usr/bin/env python3
"""Read-only harness discovery shared by the harness-audit and skill-scout helpers.

Resolves where each supported agent harness keeps its configuration, finds installed skills and
prompt commands, parses SKILL.md frontmatter without third-party packages, and redacts
secret-shaped text. Nothing here writes, executes a configured command, or opens the network.
This file is duplicated byte-for-byte into both skills; edit one copy and sync the other.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Iterable, Mapping

HARNESSES = ("claude-code", "codex", "pi", "cursor", "opencode")
MAX_TEXT_BYTES = 1_000_000
MAX_SKILL_FILES = 200
MAX_SKILL_BYTES = 5_000_000
MAX_WALK_ENTRIES = 20_000
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}

# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------


def resolve_roots(home: Path | None = None, env: Mapping[str, str] | None = None) -> dict:
    """Return each harness's user-level root. An explicit home ignores environment overrides."""
    env = os.environ if env is None else env
    overridden = home is not None
    base = Path(home).expanduser().resolve() if overridden else Path.home()

    def pick(variable: str, default: Path) -> Path:
        if overridden or not env.get(variable):
            return default
        return Path(env[variable]).expanduser()

    xdg = base / ".config"
    if not overridden and env.get("XDG_CONFIG_HOME"):
        xdg = Path(env["XDG_CONFIG_HOME"]).expanduser()
    return {
        "home": base,
        "overridden": overridden,
        "claude-code": pick("CLAUDE_CONFIG_DIR", base / ".claude"),
        "codex": pick("CODEX_HOME", base / ".codex"),
        "pi": pick("PI_CODING_AGENT_DIR", base / ".pi" / "agent"),
        "cursor": pick("CURSOR_CONFIG_DIR", base / ".cursor"),
        "opencode": pick("OPENCODE_CONFIG_DIR", xdg / "opencode"),
        "agents-skills": base / ".agents" / "skills",
        "claude-json": base / ".claude.json",
    }


def git_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def project_chain(project: Path | None) -> list[Path]:
    """Directories from the project up to its repository root, nearest first."""
    if project is None:
        return []
    project = project.resolve()
    root = git_root(project)
    if root is None:
        return [project]
    chain = []
    for candidate in (project, *project.parents):
        chain.append(candidate)
        if candidate == root:
            break
    return chain


def display(path: Path, roots: Mapping[str, object] | None = None) -> str:
    """Render a path relative to the project or home directory, for stable compact output."""
    text = str(path)
    if roots:
        project = roots.get("project")
        if project and (text == str(project) or text.startswith(str(project) + os.sep)):
            return "." + text[len(str(project)):] if text != str(project) else "."
        home = str(roots["home"])
        if text == home:
            return "~"
        if text.startswith(home + os.sep):
            return "~" + text[len(home):]
    return text


# ---------------------------------------------------------------------------
# Safe reads
# ---------------------------------------------------------------------------


def is_regular(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.stat().st_mode)
    except OSError:
        return False


def read_text(path: Path, limit: int = MAX_TEXT_BYTES) -> str | None:
    """Read a regular UTF-8 file up to a byte cap; None when absent, special, or unreadable."""
    if not is_regular(path):
        return None
    try:
        with path.open("rb") as handle:
            data = handle.read(limit + 1)
    except OSError:
        return None
    if len(data) > limit:
        data = data[:limit]
    return data.decode("utf-8", errors="replace")


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments and trailing commas outside strings."""
    out = []
    index = 0
    in_string = False
    length = len(text)
    while index < length:
        char = text[index]
        if in_string:
            out.append(char)
            if char == "\\" and index + 1 < length:
                out.append(text[index + 1])
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            index += 1
            continue
        if text.startswith("//", index):
            newline = text.find("\n", index)
            index = length if newline < 0 else newline
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            index = length if end < 0 else end + 2
            continue
        out.append(char)
        index += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def read_json(path: Path, jsonc: bool = False) -> tuple[object | None, str | None]:
    """Return (value, error). A missing file is (None, None)."""
    text = read_text(path)
    if text is None:
        return None, None
    try:
        return json.loads(strip_jsonc(text) if jsonc else text), None
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON at line {exc.lineno}"


def walk_files(root: Path, *, max_entries: int = MAX_WALK_ENTRIES) -> Iterable[Path]:
    """Yield regular files under root, skipping vendored dirs and symlink cycles."""
    seen: set[str] = set()
    stack = [root]
    count = 0
    while stack:
        current = stack.pop()
        try:
            real = os.path.realpath(current)
        except OSError:
            continue
        if real in seen:
            continue
        seen.add(real)
        try:
            entries = sorted(os.scandir(current), key=lambda entry: entry.name)
        except OSError:
            continue
        for entry in entries:
            count += 1
            if count > max_entries:
                return
            if entry.name in SKIP_DIRS:
                continue
            path = Path(entry.path)
            try:
                if entry.is_dir():
                    stack.append(path)
                elif entry.is_file():
                    yield path
            except OSError:
                continue


def tree_hash(directory: Path) -> str:
    """Content fingerprint of a skill directory: sorted relative paths and file digests."""
    digest = hashlib.sha256()
    total = 0
    files = sorted(walk_files(directory), key=lambda item: str(item))[:MAX_SKILL_FILES]
    for path in files:
        try:
            data = path.read_bytes()
        except OSError:
            continue
        total += len(data)
        if total > MAX_SKILL_BYTES:
            digest.update(b"<truncated>")
            break
        digest.update(str(path.relative_to(directory)).encode("utf-8", "replace") + b"\0")
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()[:16]


def est_tokens(text: str) -> int:
    return (len(text) + 3) // 4


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------


def _scalar(value: str) -> object:
    value = value.strip()
    if not value:
        return ""
    if value[0] == '"' and value.endswith('"') and len(value) >= 2:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
    if value[0] == "'" and value.endswith("'") and len(value) >= 2:
        return value[1:-1].replace("''", "'")
    lowered = value.lower()
    if lowered in {"true", "yes"}:
        return True
    if lowered in {"false", "no"}:
        return False
    return re.sub(r"\s+#.*$", "", value)


def parse_frontmatter(text: str) -> tuple[dict | None, str | None, str]:
    """Return (fields, error, body). Top-level keys only; nested maps are skipped."""
    if not text.startswith("---"):
        return None, "no frontmatter", text
    lines = text.splitlines()
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        return None, "unterminated frontmatter", text
    fields: dict = {}
    index = 1
    while index < end:
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#") or line[:1].isspace():
            index += 1
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+):(.*)$", line)
        if not match:
            return None, f"unparsable frontmatter line {index + 1}", text
        key, rest = match.group(1), match.group(2).strip()
        if rest in {"|", ">", "|-", ">-", "|+", ">+"}:
            block = []
            index += 1
            while index < end and (not lines[index].strip() or lines[index][:1].isspace()):
                block.append(lines[index].strip())
                index += 1
            joiner = "\n" if rest.startswith("|") else " "
            fields[key] = joiner.join(block).strip()
            continue
        if rest == "":
            nested_index = index + 1
            while nested_index < end and (lines[nested_index][:1].isspace() or not lines[nested_index].strip()):
                nested_index += 1
            fields[key] = {} if nested_index > index + 1 else ""
            index = nested_index
            continue
        fields[key] = _scalar(rest)
        index += 1
    return fields, None, "\n".join(lines[end + 1:])


def implicit_invocation_disabled(skill_dir: Path) -> bool:
    """True when agents/openai.yaml sets policy.allow_implicit_invocation: false."""
    text = read_text(skill_dir / "agents" / "openai.yaml", 64_000) or ""
    return re.search(r"(?m)^\s+allow_implicit_invocation:\s*false\s*$", text) is not None


# ---------------------------------------------------------------------------
# Skill and command discovery
# ---------------------------------------------------------------------------


def skill_record(
    skill_md: Path, *, harness: str, scope: str, origin: str | None = None, roots: Mapping | None = None
) -> dict:
    text = read_text(skill_md) or ""
    fields, error, _ = parse_frontmatter(text)
    fields = fields or {}
    name = fields.get("name") if isinstance(fields.get("name"), str) else None
    description = fields.get("description") if isinstance(fields.get("description"), str) else ""
    if error is None and not description:
        error = "missing description"
    explicit_only = fields.get("disable-model-invocation") is True or implicit_invocation_disabled(skill_md.parent)
    return {
        "harness": harness,
        "kind": "skill",
        "name": name or skill_md.parent.name,
        "dir_name": skill_md.parent.name,
        "declared_name": name,
        "description": description,
        "model_invoked": not explicit_only,
        "scope": scope,
        "origin": origin,
        "path": display(skill_md, roots),
        "real_path": os.path.realpath(skill_md),
        "content_hash": tree_hash(skill_md.parent),
        "frontmatter_error": error,
    }


def command_record(path: Path, *, harness: str, scope: str, origin: str | None = None, roots: Mapping | None = None) -> dict:
    text = read_text(path, 64_000) or ""
    fields, _, body = parse_frontmatter(text)
    description = ""
    if fields and isinstance(fields.get("description"), str):
        description = fields["description"]
    else:
        for line in (body if fields else text).splitlines():
            if line.strip():
                description = line.strip().lstrip("# ")[:200]
                break
    return {
        "harness": harness,
        "kind": "command",
        "name": path.stem,
        "description": description,
        "model_invoked": False,
        "scope": scope,
        "origin": origin,
        "path": display(path, roots),
    }


def skills_in(directory: Path, *, harness: str, scope: str, origin: str | None = None,
              roots: Mapping | None = None, recursive: bool = False) -> list[dict]:
    """Find skill directories one level below directory, or at any depth when recursive."""
    if not directory.is_dir():
        return []
    found = []
    if recursive:
        candidates = [path for path in walk_files(directory) if path.name == "SKILL.md"]
    else:
        candidates = []
        try:
            for entry in sorted(directory.iterdir()):
                if entry.is_dir() and (entry / "SKILL.md").is_file():
                    candidates.append(entry / "SKILL.md")
        except OSError:
            return []
    for skill_md in sorted(candidates):
        found.append(skill_record(skill_md, harness=harness, scope=scope, origin=origin, roots=roots))
    return found


def commands_in(directory: Path, *, harness: str, scope: str, origin: str | None = None,
                roots: Mapping | None = None) -> list[dict]:
    if not directory.is_dir():
        return []
    return [
        command_record(path, harness=harness, scope=scope, origin=origin, roots=roots)
        for path in sorted(walk_files(directory, max_entries=2_000))
        if path.suffix == ".md"
    ]


def claude_plugins(roots: Mapping, project: Path | None) -> list[dict]:
    """Installed Claude Code plugins with their install path and effective enabled state."""
    config = Path(roots["claude-code"])
    data, _ = read_json(config / "plugins" / "installed_plugins.json")
    enabled: dict[str, bool] = {}
    layers = [config / "settings.json"]
    if project is not None:
        layers += [project / ".claude" / "settings.json", project / ".claude" / "settings.local.json"]
    for layer in layers:
        settings, _ = read_json(layer)
        if isinstance(settings, dict) and isinstance(settings.get("enabledPlugins"), dict):
            for plugin_id, value in settings["enabledPlugins"].items():
                if isinstance(plugin_id, str):
                    enabled[plugin_id] = bool(value)
    plugins = []
    raw = data.get("plugins", {}) if isinstance(data, dict) else {}
    if isinstance(raw, dict):
        for plugin_id, installs in raw.items():
            if not isinstance(plugin_id, str):
                continue
            for install in installs if isinstance(installs, list) else [installs]:
                if not isinstance(install, dict):
                    continue
                scope = install.get("scope") if isinstance(install.get("scope"), str) else "user"
                project_path = install.get("projectPath")
                if scope in {"project", "local"} and project is not None and isinstance(project_path, str):
                    if os.path.realpath(project_path) != os.path.realpath(project):
                        continue
                install_path = Path(str(install.get("installPath", "")))
                if not install_path.is_dir():
                    name, _, marketplace = plugin_id.partition("@")
                    version = str(install.get("version", ""))
                    fallback = config / "plugins" / "cache" / marketplace / name / version
                    install_path = fallback if fallback.is_dir() else install_path
                plugins.append({
                    "id": plugin_id,
                    "scope": scope,
                    "version": str(install.get("version", "unknown")),
                    "install_path": install_path,
                    "installed": install_path.is_dir(),
                    "enabled": enabled.get(plugin_id, False),
                })
    known = {plugin["id"] for plugin in plugins}
    for plugin_id, value in enabled.items():
        if plugin_id not in known:
            plugins.append({"id": plugin_id, "scope": "unknown", "version": "unknown",
                            "install_path": None, "installed": False, "enabled": value})
    return plugins


def _plugin_dirs(install_path: Path, key: str, default: str) -> list[Path]:
    manifest, _ = read_json(install_path / ".claude-plugin" / "plugin.json")
    dirs = [install_path / default]
    if isinstance(manifest, dict):
        value = manifest.get(key)
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, str) and item:
                dirs.append((install_path / item).resolve())
    return list(dict.fromkeys(dirs))


def _pi_setting_paths(settings_path: Path, base: Path, key: str) -> list[Path]:
    settings, _ = read_json(settings_path)
    paths = []
    if isinstance(settings, dict) and isinstance(settings.get(key), list):
        for item in settings[key]:
            if not isinstance(item, str) or not item or item[0] in "!-":
                continue
            item = item.lstrip("+")
            target = Path(item).expanduser() if item.startswith(("~", "/")) else base / item
            paths.append(target)
    return paths


def discover(harness: str, roots: Mapping, project: Path | None, *, include_plugins: bool = True) -> dict:
    """Skills and prompt commands one harness would discover for this user and project."""
    chain = project_chain(project)
    skills: list[dict] = []
    commands: list[dict] = []
    kw = {"harness": harness, "roots": roots}
    if harness == "claude-code":
        config = Path(roots["claude-code"])
        skills += skills_in(config / "skills", scope="user", **kw)
        commands += commands_in(config / "commands", scope="user", **kw)
        if project is not None:
            skills += skills_in(project / ".claude" / "skills", scope="project", **kw)
            commands += commands_in(project / ".claude" / "commands", scope="project", **kw)
        if include_plugins:
            for plugin in claude_plugins(roots, project):
                if not (plugin["enabled"] and plugin["installed"]):
                    continue
                origin = f"plugin:{plugin['id']}"
                for directory in _plugin_dirs(plugin["install_path"], "skills", "skills"):
                    skills += skills_in(directory, scope="plugin", origin=origin, **kw)
                for directory in _plugin_dirs(plugin["install_path"], "commands", "commands"):
                    commands += commands_in(directory, scope="plugin", origin=origin, **kw)
    elif harness == "codex":
        home = Path(roots["codex"])
        skills += skills_in(home / "skills", scope="user", recursive=True, **kw)
        skills += skills_in(Path(roots["agents-skills"]), scope="shared", **kw)
        for directory in chain:
            skills += skills_in(directory / ".agents" / "skills", scope="project", **kw)
        if not roots.get("overridden"):
            skills += skills_in(Path("/etc/codex/skills"), scope="admin", **kw)
        commands += commands_in(home / "prompts", scope="user", **kw)
    elif harness == "pi":
        agent = Path(roots["pi"])
        skills += skills_in(agent / "skills", scope="user", recursive=True, **kw)
        skills += skills_in(Path(roots["agents-skills"]), scope="shared", **kw)
        for extra in _pi_setting_paths(agent / "settings.json", agent, "skills"):
            skills += skills_in(extra, scope="user", recursive=True, **kw)
        commands += commands_in(agent / "prompts", scope="user", **kw)
        if project is not None:
            skills += skills_in(project / ".pi" / "skills", scope="project", recursive=True, **kw)
            for extra in _pi_setting_paths(project / ".pi" / "settings.json", project / ".pi", "skills"):
                skills += skills_in(extra, scope="project", recursive=True, **kw)
            commands += commands_in(project / ".pi" / "prompts", scope="project", **kw)
        for directory in chain:
            skills += skills_in(directory / ".agents" / "skills", scope="project", **kw)
    elif harness == "cursor":
        user = Path(roots["cursor"])
        skills += skills_in(user / "skills", scope="user", **kw)
        skills += skills_in(Path(roots["agents-skills"]), scope="shared", **kw)
        commands += commands_in(user / "commands", scope="user", **kw)
        if project is not None:
            skills += skills_in(project / ".cursor" / "skills", scope="project", **kw)
            commands += commands_in(project / ".cursor" / "commands", scope="project", **kw)
        for directory in chain:
            skills += skills_in(directory / ".agents" / "skills", scope="project", **kw)
    elif harness == "opencode":
        config = Path(roots["opencode"])
        for name in ("skill", "skills"):
            skills += skills_in(config / name, scope="user", **kw)
        skills += skills_in(Path(roots["claude-code"]) / "skills", scope="user", **kw)
        skills += skills_in(Path(roots["agents-skills"]), scope="shared", **kw)
        for name in ("command", "commands"):
            commands += commands_in(config / name, scope="user", **kw)
        if project is not None:
            for name in ("skill", "skills"):
                skills += skills_in(project / ".opencode" / name, scope="project", **kw)
            skills += skills_in(project / ".claude" / "skills", scope="project", **kw)
            for name in ("command", "commands"):
                commands += commands_in(project / ".opencode" / name, scope="project", **kw)
        for directory in chain:
            skills += skills_in(directory / ".agents" / "skills", scope="project", **kw)
    unique: dict[str, dict] = {}
    for record in skills:
        unique.setdefault(record["real_path"], record)
    return {"skills": list(unique.values()), "commands": commands}


def harness_present(harness: str, roots: Mapping, project: Path | None) -> bool:
    """True when the harness has user or project configuration on disk."""
    root = Path(roots[harness])
    if root.exists():
        return True
    if project is None:
        return False
    markers = {
        "claude-code": [".claude", ".mcp.json", "CLAUDE.md"],
        "codex": [".codex"],
        "pi": [".pi"],
        "cursor": [".cursor"],
        "opencode": [".opencode", "opencode.json", "opencode.jsonc"],
    }[harness]
    return any((project / marker).exists() for marker in markers)


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------

SECRET_KEY_RE = re.compile(
    r"(?:^|_)(?:api_?keys?|apikeys?|tokens?|secrets?|pass_?words?|passwd|credentials?|"
    r"authorization|auth|private_?key|access_?key|client_?secret|bearer|cookie)(?:_|$)"
)
KNOWN_TOKEN_RES = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\b[A-Za-z0-9]+_(?:sk|sc)_[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bnpm_[A-Za-z0-9]{30,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)"),
]
ASSIGNMENT_RE = re.compile(
    r"""(?P<key>["']?[A-Za-z_][A-Za-z0-9_.-]*["']?)(?P<sep>\s*[=:]\s*)(?P<value>"[^"\n]*"|'[^'\n]*'|[^\s"',;}\]]+)"""
)
ENV_REFERENCE_RE = re.compile(r"^(?:\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|\{env:[A-Za-z_][A-Za-z0-9_]*\}|!.+|<[^>]+>|\*+|x+|\.\.\.|your[-_ ].*|changeme)$", re.IGNORECASE)


def normalize_key(key: str) -> str:
    separated = re.sub(r"[^A-Za-z0-9]+", "_", key.strip("\"'"))
    separated = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", separated)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", separated).lower().strip("_")


def is_secret_key(key: str) -> bool:
    normalized = normalize_key(key)
    if re.search(r"(?:^|_)(?:tokens?_(?:count|limit|budget)|max_tokens?|keys?_?path|path|file|env|helper|url|uri|endpoint)$", normalized):
        return False
    return SECRET_KEY_RE.search(normalized) is not None


def is_literal_secret(key: str, value: object) -> bool:
    """A configured value that looks like a real secret rather than a reference to one."""
    if not isinstance(value, str):
        return False
    text = value.strip()
    if any(pattern.search(text) for pattern in KNOWN_TOKEN_RES):
        return True
    if not is_secret_key(key) or len(text) < 8 or ENV_REFERENCE_RE.match(text):
        return False
    if re.search(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?", text) and not re.search(r"(?i)bearer\s+[A-Za-z0-9]", text):
        return False
    return True


def redact(text: str) -> str:
    """Best-effort redaction of known token shapes and secret-named assignments."""
    for pattern in KNOWN_TOKEN_RES:
        text = pattern.sub("[REDACTED]", text)

    def replace(match: re.Match) -> str:
        if not is_secret_key(match.group("key")):
            return match.group(0)
        value = match.group("value")
        if value.lstrip("\"'").startswith("[REDACTED") or ENV_REFERENCE_RE.match(value.strip("\"'")):
            return match.group(0)
        quote = value[0] if value[:1] in {'"', "'"} else ""
        return f"{match.group('key')}{match.group('sep')}{quote}[REDACTED]{quote}"

    return ASSIGNMENT_RE.sub(replace, text)
