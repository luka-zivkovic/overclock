#!/usr/bin/env python3
"""Deterministic helpers for the untangle skill.

Subcommands:

  scan   --root DIR [--out FILE] [--stale-days N]
         Produce a JSON inventory of coherence signals for a repository. Read-only.

  plan check --plan FILE
         Validate the structure of an untangle plan file. Exit 1 with one error per line
         when the plan is malformed.

  plan next --plan FILE --root DIR
         Apply-mode preflight. Requires a clean working tree (the plan file itself may be
         uncommitted) and returns the next unchecked checklist item as JSON.
         Exit 2 when the tree is dirty, exit 3 when nothing is left to do.

  plan tick --plan FILE --item ID --note TEXT --verified TEXT
         Mark one checklist item done and record what was done and how it was verified.
         Refuses unknown or already-ticked items. The write is atomic.

Every path the scan reports is relative to the root. Secret-looking values are never
printed; only the path that contains them.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NoReturn

PLAN_MARKER = "<!-- untangle-plan: v1 -->"
DEFAULT_PLAN_NAME = "UNTANGLE.md"
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "env", "__pycache__", "dist", "build",
    ".next", ".nuxt", "target", "vendor", ".cache", ".pytest_cache", ".mypy_cache",
    ".tox", "coverage", ".idea", ".vscode", ".terraform", "Pods", ".gradle",
}
MAX_FILES = 6000
MAX_CONTENT_BYTES = 512 * 1024
MAX_LIST = 200
TEXT_SUFFIXES = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py", ".rb", ".go", ".rs", ".java",
    ".kt", ".swift", ".php", ".cs", ".c", ".cc", ".cpp", ".h", ".hpp", ".sh", ".bash",
    ".zsh", ".md", ".mdx", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".env", ".html", ".css", ".scss", ".vue", ".svelte", ".sql", ".graphql",
    ".Makefile", ".dockerfile", ".xml", ".csv",
}
SOURCE_SUFFIXES = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py", ".rb", ".go", ".rs", ".java",
    ".kt", ".swift", ".php", ".cs", ".c", ".cc", ".cpp", ".vue", ".svelte",
}
SENTINEL_RE = re.compile(
    r"^(old|new|backup|bak|final|copy|tmp|temp|scratch|experiments?|playground|"
    r"sandbox|archive|legacy|deprecated|wip|draft|untitled|test\d+|v\d+|.*[-_](old|new|"
    r"backup|bak|final|copy|tmp|temp|v\d+))$",
    re.IGNORECASE,
)
# A file named backup.ts or sandbox.ts is a feature module; only an explicit copy or leftover
# suffix marks a file as set aside.
FILE_SENTINEL_RE = re.compile(
    r"^.+(\.bak|\.orig|[-_. ](old|backup|copy|final|tmp|temp|wip|draft)|\(\d+\)| copy( \d+)?)$",
    re.IGNORECASE,
)
ASSET_DIRS = {"icons", "assets", "images", "img", "fonts", "static", "public", "media"}
DIRECTION_DOC_RE = re.compile(
    r"(?<![A-Za-z])(roadmap|handoff|hand-off|strategy|charter|product|vision|plan|plans|batches|"
    r"ledger|decisions?|adr|backlog|todo|next-steps|milestones?)(?![A-Za-z])", re.IGNORECASE
)
PR_SUFFIX_RE = re.compile(r"\s*\(#(\d+)\)\s*$")
BRANCH_PR_RE = re.compile(r"(?:^|/)pr-(\d+)(?:-|$)")
SERVICE_HOMES = {
    "node", "app", "runner", "ubuntu", "deploy", "git", "www-data", "user", "admin", "docker",
    "ec2-user", "pi", "vagrant", "root", "ci", "circleci", "jenkins", "worker",
}
MIME_RE = re.compile(r"^(application|text|image|audio|video|multipart|font|model|message)/[A-Za-z0-9.+*-]+$")
ENTRY_RE = re.compile(r"^(main|index|app|server|cli|run|start)\.(js|ts|mjs|cjs|py|go|rb)$")
TODO_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
NODE_ENV_RE = re.compile(r"process\.env\.([A-Z][A-Z0-9_]+)")
PY_ENV_RE = re.compile(r"os\.(?:environ(?:\.get)?|getenv)\(\s*[\"']([A-Z][A-Z0-9_]+)[\"']")
SECRET_PATTERNS = [
    ("aws access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("github token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("slack token", re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}\b")),
    ("openai-style key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("stripe live key", re.compile(r"\b[sr]k_live_[A-Za-z0-9]{16,}\b")),
]
DOC_PATH_RE = re.compile(
    r"(?:`([A-Za-z0-9_./-]+/[A-Za-z0-9_.-]+)`)|(?:\]\(((?!https?://|#|mailto:)[A-Za-z0-9_./-]+)\))"
)
SCRIPT_TARGET_RE = re.compile(
    r"(?:^|\s)(?:node|python3?|bash|sh|ts-node|tsx)\s+((?:\./)?[A-Za-z0-9_./-]+\.(?:js|mjs|cjs|ts|py|sh))"
    r"|(?:^|\s)(\./[A-Za-z0-9_./-]+)"
)

# Families of dependencies that do the same job. Two members in one manifest is a
# duplicate-capability signal, not proof of a problem.
CAPABILITY_FAMILIES = {
    "http client (node)": {"axios", "node-fetch", "got", "superagent", "ky", "undici"},
    "web framework (node)": {"express", "fastify", "koa", "@hapi/hapi", "hapi", "restify", "nest", "@nestjs/core"},
    "state management (react)": {"redux", "@reduxjs/toolkit", "zustand", "mobx", "jotai", "recoil", "valtio"},
    "test runner (node)": {"jest", "vitest", "mocha", "ava", "tap", "jasmine"},
    "auth (node)": {"passport", "next-auth", "lucia", "@auth/core", "jsonwebtoken", "jose", "express-jwt"},
    "orm / query builder (node)": {"prisma", "@prisma/client", "typeorm", "sequelize", "knex", "drizzle-orm", "mongoose", "mikro-orm"},
    "http client (python)": {"requests", "httpx", "aiohttp", "urllib3"},
    "web framework (python)": {"flask", "fastapi", "django", "bottle", "sanic", "tornado", "starlette"},
    "orm (python)": {"sqlalchemy", "peewee", "tortoise-orm", "pony", "sqlmodel"},
    "cli framework (python)": {"click", "typer", "fire", "docopt"},
    "date library (node)": {"moment", "dayjs", "date-fns", "luxon"},
    "css framework": {"tailwindcss", "bootstrap", "bulma", "@mui/material", "antd", "@chakra-ui/react"},
}
TOOL_CONFIGS = {
    "eslint": [".eslintrc", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json", ".eslintrc.yml", ".eslintrc.yaml", "eslint.config.js", "eslint.config.mjs", "eslint.config.cjs"],
    "prettier": [".prettierrc", ".prettierrc.js", ".prettierrc.json", ".prettierrc.yml", ".prettierrc.yaml", "prettier.config.js", "prettier.config.cjs", "prettier.config.mjs"],
    "jest": ["jest.config.js", "jest.config.ts", "jest.config.cjs", "jest.config.mjs", "jest.config.json"],
    "vitest": ["vitest.config.js", "vitest.config.ts", "vitest.config.mjs"],
    "typescript": ["tsconfig.json"],
    "tailwindcss": ["tailwind.config.js", "tailwind.config.ts", "tailwind.config.cjs", "tailwind.config.mjs"],
    "@babel/core": [".babelrc", ".babelrc.json", "babel.config.js", "babel.config.json", "babel.config.cjs"],
    "webpack": ["webpack.config.js", "webpack.config.ts", "webpack.config.cjs", "webpack.config.mjs"],
    "vite": ["vite.config.js", "vite.config.ts", "vite.config.mjs"],
    "pytest": ["pytest.ini"],
    "mypy": ["mypy.ini"],
    "ruff": ["ruff.toml", ".ruff.toml"],
    "black": [],
}
PY_TOOLS = {"pytest", "mypy", "ruff", "black"}
MANIFESTS = [
    "package.json", "pyproject.toml", "requirements.txt", "Pipfile", "setup.py", "setup.cfg",
    "Cargo.toml", "go.mod", "Gemfile", "composer.json", "pom.xml", "build.gradle",
]
LOCKFILES = {
    "package.json": ["package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "bun.lock"],
    "requirements.txt": [],
    "pyproject.toml": ["poetry.lock", "uv.lock", "pdm.lock", "Pipfile.lock"],
    "Pipfile": ["Pipfile.lock"],
    "Cargo.toml": ["Cargo.lock"],
    "go.mod": ["go.sum"],
    "Gemfile": ["Gemfile.lock"],
    "composer.json": ["composer.lock"],
}
ENV_EXAMPLE_NAMES = [".env.example", ".env.sample", ".env.template", ".env.dist", "env.example"]
COMMITTED_ENV_NAMES = {".env", ".env.local", ".env.production", ".env.development"}
TEST_DIR_NAMES = {"test", "tests", "__tests__", "spec", "specs", "e2e"}
TEST_FILE_RE = re.compile(r"(\.test\.|\.spec\.|_test\.|^test_)")
RUN_HEADING_RE = re.compile(
    r"^#{1,6}\s.*(install|usage|getting started|quick ?start|run|setup|how to|develop|build|commands|contribut)",
    re.IGNORECASE | re.MULTILINE,
)
README_RE = re.compile(r"^readme(\.(md|markdown|rst|txt))?$", re.IGNORECASE)
HOME_PATH_RE = re.compile(r"(?<![\w])(/Users/[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+)(?=/|\b)")
HTML_TAG_RE = re.compile(r"<[^>]+>")
THREAD_ROLES = {"spine", "supporting", "side-quest", "abandoned", "contradicting"}
THREAD_DECISIONS = {"keep", "park", "delete", "merge", "pending"}


# --------------------------------------------------------------------------- utilities


def fail(message: str, code: int = 1) -> NoReturn:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def authorized_root(path: str) -> Path:
    root = Path(os.path.abspath(os.path.expanduser(path)))
    if not root.is_dir():
        fail(f"root is not a directory: {root}")
    return root


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def is_text_candidate(path: Path) -> bool:
    if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"Makefile", "Dockerfile", "Procfile", ".gitignore"}:
        return True
    return path.name.startswith(".env")


def read_text(path: Path) -> str | None:
    try:
        if path.is_symlink() or path.stat().st_size > MAX_CONTENT_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:4096]:
        return None
    return data.decode("utf-8", errors="replace")


def git(root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-c", "core.quotepath=off", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def cap(items: list, limit: int = MAX_LIST) -> dict:
    return {"items": items[:limit], "truncated": len(items) > limit, "total": len(items)}


# --------------------------------------------------------------------------- scan


def walk(root: Path) -> tuple[list[Path], bool]:
    files: list[Path] = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.is_symlink():
                continue
            files.append(path)
            if len(files) >= MAX_FILES:
                truncated = True
                return files, truncated
    return files, truncated


def parse_iso_date(value: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def git_activity(root: Path, files: list[Path], anchors: set[str] | None = None) -> dict:
    """Per-directory last-commit dates and commit counts, measured against HEAD's date."""
    result = {"available": False}
    head_date_raw = git(root, "log", "-1", "--format=%cs")
    if head_date_raw is None:
        return result
    head_date = parse_iso_date(head_date_raw)
    if head_date is None:
        return result
    log = git(root, "log", "--format=%H%x09%cs", "--name-only", "--no-renames")
    if log is None:
        return result
    last_seen: dict[str, dt.date] = {}
    commit_counts: dict[str, int] = {}
    current_date: dt.date | None = None
    for line in log.splitlines():
        if "\t" in line and len(line.split("\t")[0]) == 40:
            current_date = parse_iso_date(line.split("\t")[1])
            continue
        if not line.strip() or current_date is None:
            continue
        parts = line.strip().split("/")
        keys = {"/".join(parts[:depth]) for depth in range(1, min(len(parts), 5))}
        keys.add(line.strip())
        for key in keys:
            commit_counts[key] = commit_counts.get(key, 0) + 1
            if key not in last_seen or current_date > last_seen[key]:
                last_seen[key] = current_date
    directories = []
    seen_dirs: set[str] = set()
    anchor_depths = {0}
    for anchor in anchors or set():
        anchor_depths.add(len(anchor.split("/")))
    anchor_set = set(anchors or set())
    for path in files:
        relative = rel(path, root)
        parts = relative.split("/")
        if len(parts) < 2:
            continue
        wanted: set[int] = {1, 2}
        for depth in range(1, len(parts)):
            prefix = "/".join(parts[:depth])
            if prefix in anchor_set:
                wanted.update({depth + 1, depth + 2})
        for depth in sorted(wanted):
            if len(parts) <= depth or depth > 4:
                continue
            key = "/".join(parts[:depth])
            if key in seen_dirs:
                continue
            seen_dirs.add(key)
            last = last_seen.get(key)
            directories.append(
                {
                    "path": key,
                    "last_commit": last.isoformat() if last else None,
                    "age_days": (head_date - last).days if last else None,
                    "commit_count": commit_counts.get(key, 0),
                }
            )
    directories.sort(key=lambda item: item["path"])
    head = (git(root, "rev-parse", "HEAD") or "").strip()
    count = (git(root, "rev-list", "--count", "HEAD") or "0").strip()
    result.update(
        {
            "available": True,
            "head": head,
            "head_date": head_date.isoformat(),
            "commit_count": int(count) if count.isdigit() else 0,
            "directories": directories,
        }
    )
    return result


def git_branches(root: Path, head_date_raw: str | None) -> dict:
    """Every other branch: tip date, merge state by ancestry, and whether its tip subject
    already appears in HEAD's history (a squash merge leaves no ancestry)."""
    listing = git(
        root, "for-each-ref",
        "--format=%(refname)%09%(refname:short)%09%(committerdate:short)%09%(subject)",
        "refs/heads", "refs/remotes",
    )
    if listing is None:
        return {"available": False}
    current = (git(root, "rev-parse", "--abbrev-ref", "HEAD") or "").strip()
    head_log = (git(root, "log", "--format=%s", "-n", "5000") or "").splitlines()
    head_subjects = {PR_SUFFIX_RE.sub("", line).strip() for line in head_log}
    head_pr_numbers = {match.group(1) for line in head_log for match in [PR_SUFFIX_RE.search(line)] if match}
    head_date = parse_iso_date(head_date_raw) if head_date_raw else None
    seen_tips: set[str] = set()
    items = []
    for line in listing.splitlines():
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        full, name, date_raw, subject = parts
        short = name.split("/", 1)[1] if name.startswith(("origin/", "upstream/")) else name
        if full.endswith("/HEAD") or short in {current, "main", "master"} or name == current:
            continue
        tip = (git(root, "rev-parse", name) or "").strip()
        if not tip or tip in seen_tips:
            continue
        seen_tips.add(tip)
        ancestor = git(root, "merge-base", "--is-ancestor", name, "HEAD") is not None
        tip_date = parse_iso_date(date_raw)
        items.append(
            {
                "name": name,
                "tip_date": date_raw,
                "age_days": (head_date - tip_date).days if head_date and tip_date else None,
                "merged_by_ancestry": ancestor,
                "tip_subject_in_head_history": (
                    PR_SUFFIX_RE.sub("", subject).strip() in head_subjects
                    or bool(BRANCH_PR_RE.search(name) and BRANCH_PR_RE.search(name).group(1) in head_pr_numbers)
                ),
                "subject": subject[:120],
            }
        )
        if len(items) >= 100:
            break
    items.sort(key=lambda item: item["name"])
    unmerged = [i for i in items if not i["merged_by_ancestry"] and not i["tip_subject_in_head_history"]]
    return {
        "available": True,
        "note": "age is measured from HEAD's commit date; a negative age means the branch is newer than HEAD",
        "unmerged_total": len(unmerged),
        **cap(items, 100),
    }


def load_manifest_deps(root: Path) -> dict[str, dict]:
    """Return {manifest path: {"deps": set, "scripts": {...}}} for recognized manifests."""
    found: dict[str, dict] = {}
    package = root / "package.json"
    text = read_text(package) if package.is_file() else None
    if text is not None:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {}
        deps: set[str] = set()
        for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            value = data.get(key)
            if isinstance(value, dict):
                deps.update(str(name).lower() for name in value)
        scripts = data.get("scripts") if isinstance(data.get("scripts"), dict) else {}
        found["package.json"] = {"deps": deps, "scripts": scripts, "description": data.get("description")}
    for name in ("requirements.txt", "requirements-dev.txt", "requirements/dev.txt"):
        path = root / name
        text = read_text(path) if path.is_file() else None
        if text is None:
            continue
        deps = set()
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "-")):
                continue
            deps.add(re.split(r"[<>=!~\[; ]", line, 1)[0].lower())
        found[name] = {"deps": deps, "scripts": {}, "description": None}
    pyproject = root / "pyproject.toml"
    text = read_text(pyproject) if pyproject.is_file() else None
    if text is not None:
        deps = set()
        for match in re.finditer(r"^\s*[\"']([A-Za-z0-9_.-]+)[^\"']*[\"']\s*,?\s*$", text, re.MULTILINE):
            deps.add(match.group(1).lower())
        for match in re.finditer(r"^([A-Za-z0-9_.-]+)\s*=\s*[\"^~>=<0-9{]", text, re.MULTILINE):
            deps.add(match.group(1).lower())
        description = None
        desc_match = re.search(r"^description\s*=\s*[\"'](.*)[\"']", text, re.MULTILINE)
        if desc_match:
            description = desc_match.group(1)
        found["pyproject.toml"] = {"deps": deps, "scripts": {}, "description": description}
    return found


def scan(root: Path, stale_days: int) -> dict:
    files, truncated = walk(root)
    relatives = [rel(path, root) for path in files]
    top_level = sorted({r.split("/")[0] for r in relatives if "/" in r})
    contents: dict[str, str] = {}
    for path, relative in zip(files, relatives):
        if is_text_candidate(path):
            text = read_text(path)
            if text is not None:
                contents[relative] = text

    inventory: dict = {
        "schema": "untangle-scan/v1",
        "root": str(root),
        "file_count": len(files),
        "truncated": truncated,
        "top_level_directories": top_level,
        "top_level_files": sorted(r for r in relatives if "/" not in r),
    }

    # Purpose sources -----------------------------------------------------------------
    manifests = load_manifest_deps(root)
    all_readmes = sorted(r for r in relatives if README_RE.match(r.split("/")[-1]))
    # Purpose comes from the root README and any README one level down that is not a
    # workspace member's own README (a package README describes the package, not the project).
    manifest_dirs = {r.rsplit("/", 1)[0] for r in relatives if "/" in r and r.split("/")[-1] in MANIFESTS}
    readmes = [
        r for r in all_readmes
        if r.count("/") == 0 or (r.count("/") == 1 and r.rsplit("/", 1)[0] not in manifest_dirs)
    ]
    purpose_sources = []
    for name in readmes:
        text = contents.get(name)
        if text is None:
            continue
        first_heading = next((line.strip("# ").strip() for line in text.splitlines() if line.startswith("#")), None)
        first_paragraph = None
        for block in re.split(r"\n\s*\n", HTML_TAG_RE.sub(" ", text)):
            stripped = block.strip()
            if stripped and not stripped.startswith(("#", "!", "[!", "|", "```", "-", "*", "[")) and len(stripped.split()) >= 6:
                first_paragraph = " ".join(stripped.split())[:400]
                break
        purpose_sources.append({"path": name, "title": first_heading, "first_paragraph": first_paragraph})
    for name, data in manifests.items():
        if data.get("description"):
            purpose_sources.append({"path": name, "description": str(data["description"])[:400]})
    for name in ("CLAUDE.md", "AGENTS.md", "docs/README.md"):
        if name in contents and name not in readmes:
            purpose_sources.append({"path": name, "first_paragraph": " ".join(contents[name].split())[:400]})
    inventory["purpose_sources"] = purpose_sources
    inventory["manifests"] = sorted(r for r in relatives if r in MANIFESTS)
    inventory["multiple_readmes"] = readmes if len(readmes) > 1 else []
    inventory["nested_readmes"] = [r for r in all_readmes if r not in readmes]

    # Git activity ---------------------------------------------------------------------
    manifest_dirs = {r.rsplit("/", 1)[0] for r in relatives if "/" in r and r.split("/")[-1] in MANIFESTS}
    activity = git_activity(root, files, manifest_dirs)
    inventory["git"] = {k: v for k, v in activity.items() if k != "directories"}
    directories = activity.get("directories", [])
    stale = [
        d for d in directories
        if d["age_days"] is not None and d["age_days"] >= stale_days
    ]
    inventory["directory_activity"] = cap(directories)
    inventory["stale_directories"] = {"threshold_days": stale_days, **cap(stale)}

    # Sentinel names -------------------------------------------------------------------
    sentinel = sorted(
        {
            "/".join(r.split("/")[: i + 1])
            for r in relatives
            for i, part in enumerate(r.split("/")[:-1])
            if SENTINEL_RE.match(part) and not (set(r.split("/")[:i]) & ASSET_DIRS)
        }
        | {
            r for r in relatives
            if FILE_SENTINEL_RE.match(Path(r).stem) and not (set(r.split("/")[:-1]) & ASSET_DIRS)
        }
    )
    inventory["sentinel_names"] = cap(sentinel)

    # Entry points ---------------------------------------------------------------------
    entry_points = sorted(
        r for r in relatives
        if ENTRY_RE.match(r.split("/")[-1]) and r.count("/") <= 2
    )
    inventory["entry_points"] = cap(entry_points)

    # Language mix inside source directories ------------------------------------------
    js = [r for r in relatives if r.endswith((".js", ".jsx", ".mjs", ".cjs")) and not r.endswith(".config.js")]
    ts = [r for r in relatives if r.endswith((".ts", ".tsx"))]
    inventory["language_mix"] = {
        "javascript": len(js),
        "typescript": len(ts),
        "python": sum(r.endswith(".py") for r in relatives),
        "mixed_js_ts": bool(js) and bool(ts) and min(len(js), len(ts)) >= 3
        and min(len(js), len(ts)) / max(len(js), len(ts)) >= 0.15,
    }

    # Duplicate capabilities -----------------------------------------------------------
    duplicates = []
    for manifest, data in manifests.items():
        deps = data["deps"]
        for family, members in CAPABILITY_FAMILIES.items():
            hits = sorted(deps & {m.lower() for m in members})
            if len(hits) >= 2:
                duplicates.append({"family": family, "members": hits, "manifest": manifest})
    py_manifests = [m for m in ("requirements.txt", "pyproject.toml", "Pipfile", "setup.py") if m in relatives]
    if len(py_manifests) >= 2:
        duplicates.append({"family": "python dependency manifests", "members": py_manifests, "manifest": None})
    node_locks = [l for l in LOCKFILES["package.json"] if l in relatives]
    if len(node_locks) >= 2:
        duplicates.append({"family": "node lockfiles", "members": node_locks, "manifest": "package.json"})
    if len(entry_points) >= 2:
        duplicates.append({"family": "entry points", "members": entry_points, "manifest": None})
    inventory["duplicate_capabilities"] = duplicates

    # Tool config without the tool -----------------------------------------------------
    all_deps: set[str] = set()
    for data in manifests.values():
        all_deps |= data["deps"]
    orphan_configs = []
    for tool, names in TOOL_CONFIGS.items():
        present = [n for n in names if n in relatives]
        if tool in PY_TOOLS and "pyproject.toml" in contents and f"[tool.{tool}" in contents["pyproject.toml"]:
            present.append("pyproject.toml [tool." + tool + "]")
        if present and tool not in all_deps:
            orphan_configs.append({"tool": tool, "config": present})
    inventory["tool_config_without_dependency"] = orphan_configs

    # Script targets that do not exist ------------------------------------------------
    missing_targets = []
    scripts = manifests.get("package.json", {}).get("scripts", {})
    for script_name, command in scripts.items():
        if not isinstance(command, str):
            continue
        for match in SCRIPT_TARGET_RE.finditer(command):
            target = match.group(1) or match.group(2)
            if not target:
                continue
            candidate = (root / target).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                continue
            if not candidate.exists():
                missing_targets.append({"script": script_name, "target": target})
    inventory["script_targets_missing"] = missing_targets

    # Documentation paths that do not resolve -----------------------------------------
    missing_doc_paths = []
    resolves_elsewhere = []
    home_paths = []
    existing = set(relatives) | {d for r in relatives for d in _ancestors(r)}
    for name, text in contents.items():
        if not name.endswith((".md", ".mdx", ".rst", ".txt")):
            continue
        for match in HOME_PATH_RE.finditer(text):
            if match.group(1).split("/")[-1].lower() in SERVICE_HOMES:
                continue
            home_paths.append({"doc": name, "path": match.group(1)})
        base = Path(name).parent
        for match in DOC_PATH_RE.finditer(text):
            target = (match.group(1) or match.group(2) or "").strip()
            if not target or target.startswith(("http", "$", "<", "{", "/", "~")) or "*" in target:
                continue  # a leading slash is a URL route or an absolute path, not a repo file
            if target.endswith("/"):
                target = target[:-1]
            if MIME_RE.match(target) or all(seg.isdigit() for seg in target.split("/")):
                continue
            candidates = {target, (base / target).as_posix() if str(base) != "." else target}
            normalized = {os.path.normpath(c).replace("\\", "/") for c in candidates}
            if any(n in existing for n in normalized):
                continue
            if not re.search(r"[./]", target) or target.count("/") == 0 and "." not in target:
                continue
            elsewhere = sorted(r for r in existing if r.endswith("/" + target))
            if elsewhere:
                resolves_elsewhere.append({"doc": name, "path": target, "matches": elsewhere[:3]})
                continue
            has_extension = "." in target.split("/")[-1]
            missing_doc_paths.append(
                {"doc": name, "path": target, "confidence": "high" if has_extension else "low"}
            )
    inventory["doc_paths_missing"] = cap(_dedupe(missing_doc_paths))
    inventory["doc_paths_resolve_elsewhere"] = {
        "note": "cited relative to a package, not the root; a reader cannot resolve them without context",
        **cap(_dedupe(resolves_elsewhere)),
    }
    inventory["developer_home_paths"] = cap(_dedupe(home_paths), 50)

    # Environment variables --------------------------------------------------------------
    referenced: dict[str, set[str]] = {}
    for name, text in contents.items():
        if not name.endswith(tuple(SOURCE_SUFFIXES)):
            continue
        for regex in (NODE_ENV_RE, PY_ENV_RE):
            for match in regex.finditer(text):
                referenced.setdefault(match.group(1), set()).add(name)
    documented: set[str] = set()
    example_files = [n for n in ENV_EXAMPLE_NAMES if n in contents]
    for name in example_files + [r for r in readmes if r in contents]:
        for match in re.finditer(r"\b([A-Z][A-Z0-9_]{2,})\b\s*=", contents[name]):
            documented.add(match.group(1))
    ignored_env = {"NODE_ENV", "PATH", "HOME", "PORT", "CI"}
    undocumented = sorted(
        (
            {"name": var, "used_in": sorted(paths)[:5]}
            for var, paths in referenced.items()
            if var not in documented and var not in ignored_env
        ),
        key=lambda item: item["name"],
    )
    inventory["env_vars"] = {
        "example_files": example_files,
        "undocumented": cap(undocumented, 100),
    }

    # TODO density --------------------------------------------------------------------
    todos = []
    for name, text in contents.items():
        count = len(TODO_RE.findall(text))
        if count:
            todos.append({"path": name, "count": count})
    todos.sort(key=lambda item: (-item["count"], item["path"]))
    inventory["todos"] = {"total": sum(t["count"] for t in todos), **cap(todos, 50)}

    # Possibly unreferenced top-level directories --------------------------------------
    unreferenced = []
    for directory in top_level:
        if directory in SKIP_DIRS or directory.startswith("."):
            continue
        token = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(directory) + r"(?![A-Za-z0-9_])")
        mentioned = False
        for name, text in contents.items():
            if name.split("/")[0] == directory:
                continue
            if token.search(text):
                mentioned = True
                break
        if not mentioned:
            unreferenced.append(directory)
    inventory["unreferenced_top_level_directories"] = {
        "note": "heuristic: the directory name appears in no file outside itself",
        "items": unreferenced,
    }

    # Branches ------------------------------------------------------------------------
    inventory["branches"] = git_branches(root, activity.get("head_date"))

    # Direction documents -------------------------------------------------------------
    direction = []
    for name, text in contents.items():
        if not name.endswith((".md", ".mdx", ".rst", ".txt")) or name.count("/") > 3:
            continue
        stem = name.split("/")[-1].rsplit(".", 1)[0]
        parent_parts = name.split("/")[:-1]
        if DIRECTION_DOC_RE.search(stem) or any(DIRECTION_DOC_RE.fullmatch(p) for p in parent_parts):
            title = next((line.strip("# ").strip() for line in text.splitlines() if line.startswith("#")), None)
            direction.append({"path": name, "title": title})
    inventory["direction_documents"] = {
        "note": "roadmaps, handoffs, plans, decisions: more than one that do not link to each other is a finding",
        **cap(sorted(direction, key=lambda item: item["path"]), 100),
    }

    # Hygiene -------------------------------------------------------------------------
    manifest_names = [m for m in MANIFESTS if m in relatives]
    lock_expected = [m for m in manifest_names if LOCKFILES.get(m)]
    lock_present = any(l in relatives for m in lock_expected for l in LOCKFILES[m])
    has_tests = any(
        part in TEST_DIR_NAMES for r in relatives for part in r.split("/")[:-1]
    ) or any(TEST_FILE_RE.search(r.split("/")[-1]) for r in relatives)
    readme_text = contents.get(readmes[0]) if readmes else None
    committed_env = sorted(r for r in relatives if r.split("/")[-1] in COMMITTED_ENV_NAMES)
    secret_hits = []
    for name, text in contents.items():
        for label, regex in SECRET_PATTERNS:
            if regex.search(text):
                secret_hits.append({"path": name, "kind": label})
    inventory["hygiene"] = {
        "gitignore_present": ".gitignore" in relatives,
        "manifests": manifest_names,
        "lockfile_present": lock_present if lock_expected else None,
        "tests_present": has_tests,
        "readme_present": bool(readmes),
        "readme_has_run_section": bool(readme_text and RUN_HEADING_RE.search(readme_text)),
        "committed_env_files": committed_env,
        "secret_like_content": cap(secret_hits, 50),
    }
    return inventory


def _ancestors(relative: str) -> list[str]:
    parts = relative.split("/")
    return ["/".join(parts[:i]) for i in range(1, len(parts))]


def _dedupe(items: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out = []
    for item in items:
        key = json.dumps(item, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


# --------------------------------------------------------------------------- plan


SECTION_RE = re.compile(r"^## (\d)\. (.+)$", re.MULTILINE)
EXPECTED_SECTIONS = ["Spine", "Threads", "Checklist", "Foundations", "Suggested next moves"]
THREAD_ROW_RE = re.compile(r"^\|\s*(T\d+)\s*\|(.*)$")
CHECK_ITEM_RE = re.compile(
    r"^- \[( |x)\] (C\d+) \((T\d+|F\d+|H\d+)\) (.+?) \| paths: (.+?) \| verify: (.+?)\s*$"
)
DONE_LINE_RE = re.compile(r"^  - done: (\S+) \| (.+?) \| verified: (.+?)\s*$")
FOUNDATION_ROW_RE = re.compile(r"^\|\s*(F\d+)\s*\|(.*)$")
ROADMAP_ITEM_RE = re.compile(r"^- (N\d+) \(((?:T|F|C|H)\d+)\) (.+?)\s*$")
PARKED_ITEM_RE = re.compile(r"^- (T\d+): (.+?)\s*$")


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(SECTION_RE.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(2).strip()] = text[match.end():end]
    return sections


def parse_plan(text: str) -> tuple[dict, list[str]]:
    errors: list[str] = []
    if PLAN_MARKER not in text:
        errors.append(f"missing plan marker {PLAN_MARKER}")
    sections = split_sections(text)
    for name in EXPECTED_SECTIONS:
        if name not in sections:
            errors.append(f"missing section: {name}")
    if errors:
        return {}, errors

    spine = " ".join(
        line.strip() for line in sections["Spine"].splitlines()
        if line.strip() and not line.strip().startswith(("Source", "<!--", "|"))
    )
    if not spine:
        errors.append("Spine section must contain the one-sentence purpose")

    threads: dict[str, dict] = {}
    for line in sections["Threads"].splitlines():
        match = THREAD_ROW_RE.match(line.strip())
        if not match:
            continue
        cells = [c.strip() for c in match.group(2).strip().strip("|").split("|")]
        if len(cells) < 5:
            errors.append(f"thread {match.group(1)} needs columns: thread, role, evidence, decision, decided by")
            continue
        thread_id = match.group(1)
        if thread_id in threads:
            errors.append(f"duplicate thread id {thread_id}")
        role, decision = cells[1].lower(), cells[3].lower()
        if role not in THREAD_ROLES:
            errors.append(f"{thread_id}: role {cells[1]!r} must be one of {sorted(THREAD_ROLES)}")
        if decision not in THREAD_DECISIONS:
            errors.append(f"{thread_id}: decision {cells[3]!r} must be one of {sorted(THREAD_DECISIONS)}")
        if role == "spine" and decision not in {"keep", "pending"}:
            errors.append(f"{thread_id}: the spine can only be kept")
        if not cells[2]:
            errors.append(f"{thread_id}: evidence column is empty")
        threads[thread_id] = {
            "id": thread_id, "title": cells[0], "role": role, "evidence": cells[2],
            "decision": decision, "decided_by": cells[4],
        }
    if not any(t["role"] == "spine" for t in threads.values()):
        errors.append("Threads must include exactly one spine row")
    if sum(t["role"] == "spine" for t in threads.values()) > 1:
        errors.append("Threads must include exactly one spine row")

    foundations: dict[str, dict] = {}
    for line in sections["Foundations"].splitlines():
        match = FOUNDATION_ROW_RE.match(line.strip())
        if not match:
            continue
        cells = [c.strip() for c in match.group(2).strip().strip("|").split("|")]
        if len(cells) < 5:
            errors.append(f"foundation {match.group(1)} needs columns: finding, evidence, cost of keeping, cost of changing now, cost of changing later")
            continue
        foundations[match.group(1)] = {"id": match.group(1), "finding": cells[0], "evidence": cells[1]}
    if len(foundations) > 3:
        errors.append("Foundations is capped at three findings")

    checklist: list[dict] = []
    lines = sections["Checklist"].splitlines()
    for index, line in enumerate(lines):
        match = CHECK_ITEM_RE.match(line.rstrip())
        if match:
            done = match.group(1) == "x"
            item = {
                "id": match.group(2), "source": match.group(3), "title": match.group(4),
                "paths": [p.strip() for p in match.group(5).split(",") if p.strip()],
                "verify": match.group(6), "done": done, "line": index,
            }
            if done:
                next_line = lines[index + 1] if index + 1 < len(lines) else ""
                if not DONE_LINE_RE.match(next_line.rstrip()):
                    errors.append(f"{item['id']} is ticked but has no done line beneath it")
            source = match.group(3)
            if source.startswith("T") and source not in threads:
                errors.append(f"{item['id']} cites unknown thread {source}")
            if source.startswith("F") and source not in foundations:
                errors.append(f"{item['id']} cites unknown foundation {source}")
            checklist.append(item)
        elif line.startswith("- ["):
            errors.append(f"malformed checklist line: {line.strip()!r}")
    ids = [item["id"] for item in checklist]
    if len(ids) != len(set(ids)):
        errors.append("duplicate checklist ids")
    for thread in threads.values():
        if thread["decision"] in {"park", "delete", "merge"} and not any(
            item["source"] == thread["id"] for item in checklist
        ):
            errors.append(f"{thread['id']} is decided {thread['decision']} but has no checklist item")

    roadmap = sections["Suggested next moves"]
    next_items, then_items, parked = [], [], []
    bucket = None
    for line in roadmap.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            heading = stripped[4:].strip().lower()
            bucket = {"next": "next", "then": "then", "parked ideas": "parked"}.get(heading)
            if bucket is None:
                errors.append(f"unknown roadmap heading {stripped!r}")
            continue
        if bucket in {"next", "then"}:
            match = ROADMAP_ITEM_RE.match(stripped)
            if match:
                target = match.group(2)
                known = target in threads or target in foundations or target in ids or target.startswith("H")
                if not known:
                    errors.append(f"{match.group(1)} cites unknown id {target}")
                (next_items if bucket == "next" else then_items).append(match.group(1))
            elif stripped.startswith("- "):
                errors.append(f"malformed roadmap item: {stripped!r}")
        elif bucket == "parked":
            match = PARKED_ITEM_RE.match(stripped)
            if match:
                parked.append(match.group(1))
            elif stripped.startswith("- "):
                errors.append(f"malformed parked idea: {stripped!r}")
    decided = any(t["decision"] != "pending" for t in threads.values() if t["role"] != "spine")
    pending = [t["id"] for t in threads.values() if t["decision"] == "pending"]
    if len(next_items) > 1:
        errors.append("Next may hold exactly one move")
    if len(next_items) + len(then_items) > 5:
        errors.append("Next and Then together are capped at five moves")
    expected_parked = sorted(t["id"] for t in threads.values() if t["decision"] == "park")
    if not pending and sorted(parked) != expected_parked:
        errors.append(
            f"Parked ideas must list exactly the parked threads {expected_parked}, found {sorted(parked)}"
        )
    if not pending and threads and not next_items and decided and "nothing obvious" not in roadmap.lower():
        errors.append("Next must hold one move or say 'Nothing obvious' once decisions are recorded")

    return {
        "spine": spine, "threads": threads, "foundations": foundations, "checklist": checklist,
        "pending_decisions": pending, "roadmap": {"next": next_items, "then": then_items, "parked": parked},
    }, errors


def plan_check(path: Path) -> int:
    text = read_plan(path)
    parsed, errors = parse_plan(text)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    summary = {
        "ok": True,
        "threads": len(parsed["threads"]),
        "pending_decisions": parsed["pending_decisions"],
        "checklist_total": len(parsed["checklist"]),
        "checklist_done": sum(item["done"] for item in parsed["checklist"]),
        "foundations": len(parsed["foundations"]),
        "roadmap": parsed["roadmap"],
    }
    print(json.dumps(summary, indent=2))
    return 0


def read_plan(path: Path) -> str:
    if path.is_symlink():
        fail(f"plan must not be a symlink: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"cannot read plan: {exc}")


def working_tree_dirty(root: Path, plan: Path) -> list[str]:
    status = git(root, "status", "--porcelain", "--untracked-files=all")
    if status is None:
        fail("apply requires a git repository so every step can be reverted", 2)
    try:
        plan_rel = plan.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        plan_rel = None
    dirty = []
    for line in status.splitlines():
        if not line.strip():
            continue
        entry = line[3:].strip()
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        if entry.startswith('"') and entry.endswith('"'):
            entry = entry[1:-1]
        if plan_rel is not None and entry == plan_rel:
            continue
        dirty.append(entry)
    return dirty


def plan_next(path: Path, root: Path) -> int:
    parsed, errors = parse_plan(read_plan(path))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if parsed["pending_decisions"]:
        print(
            "ERROR: plan still has pending decisions: " + ", ".join(parsed["pending_decisions"]),
            file=sys.stderr,
        )
        return 1
    dirty = working_tree_dirty(root, path)
    if dirty:
        print(json.dumps({"ok": False, "reason": "dirty working tree", "dirty": dirty[:50]}, indent=2))
        return 2
    remaining = [item for item in parsed["checklist"] if not item["done"]]
    if not remaining:
        print(json.dumps({"ok": True, "next": None, "remaining": 0}, indent=2))
        return 3
    item = remaining[0]
    print(
        json.dumps(
            {
                "ok": True,
                "next": {k: v for k, v in item.items() if k != "line"},
                "remaining": len(remaining),
                "head": (git(root, "rev-parse", "HEAD") or "").strip(),
            },
            indent=2,
        )
    )
    return 0


def plan_tick(path: Path, item_id: str, note: str, verified: str) -> int:
    text = read_plan(path)
    parsed, errors = parse_plan(text)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    for value, label in ((note, "note"), (verified, "verified")):
        if not value.strip() or "\n" in value or "|" in value:
            fail(f"{label} must be one non-empty line without '|'")
    target = next((item for item in parsed["checklist"] if item["id"] == item_id), None)
    if target is None:
        fail(f"unknown checklist item {item_id}")
    if target["done"]:
        fail(f"{item_id} is already ticked")
    lines = text.splitlines(keepends=True)
    # Locate the exact line again in the full document rather than trusting section offsets.
    for index, line in enumerate(lines):
        match = CHECK_ITEM_RE.match(line.rstrip("\n"))
        if match and match.group(2) == item_id:
            lines[index] = line.replace("- [ ] ", "- [x] ", 1)
            stamp = dt.date.today().isoformat()
            lines.insert(index + 1, f"  - done: {stamp} | {note.strip()} | verified: {verified.strip()}\n")
            break
    else:
        fail(f"could not locate {item_id} in the plan")
    new_text = "".join(lines)
    _, errors = parse_plan(new_text)
    if errors:
        fail("tick would produce an invalid plan: " + "; ".join(errors))
    atomic_write(path, new_text)
    print(json.dumps({"ok": True, "ticked": item_id}, indent=2))
    return 0


def atomic_write(path: Path, text: str) -> None:
    directory = path.parent
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


# --------------------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    scan_parser = sub.add_parser("scan", help="produce the read-only signal inventory")
    scan_parser.add_argument("--root", required=True)
    scan_parser.add_argument("--out", help="write JSON here instead of stdout (must be outside the root or named .untangle-scan.json)")
    scan_parser.add_argument("--stale-days", type=int, default=90)

    plan_parser = sub.add_parser("plan", help="validate or advance a plan file")
    plan_sub = plan_parser.add_subparsers(dest="plan_command", required=True)
    check = plan_sub.add_parser("check")
    check.add_argument("--plan", required=True)
    nxt = plan_sub.add_parser("next")
    nxt.add_argument("--plan", required=True)
    nxt.add_argument("--root", required=True)
    tick = plan_sub.add_parser("tick")
    tick.add_argument("--plan", required=True)
    tick.add_argument("--item", required=True)
    tick.add_argument("--note", required=True)
    tick.add_argument("--verified", required=True)

    args = parser.parse_args(argv)
    if args.command == "scan":
        root = authorized_root(args.root)
        if args.stale_days < 1:
            fail("--stale-days must be positive")
        inventory = scan(root, args.stale_days)
        payload = json.dumps(inventory, indent=2, sort_keys=True)
        if args.out:
            out = Path(os.path.abspath(os.path.expanduser(args.out)))
            try:
                inside = out.relative_to(root)
            except ValueError:
                inside = None
            if inside is not None and out.name != ".untangle-scan.json":
                fail("--out inside the repository must be named .untangle-scan.json")
            atomic_write(out, payload + "\n")
            print(json.dumps({"ok": True, "out": str(out), "file_count": inventory["file_count"]}))
        else:
            print(payload)
        return 0
    plan_path = Path(os.path.abspath(os.path.expanduser(args.plan)))
    if args.plan_command == "check":
        return plan_check(plan_path)
    if args.plan_command == "next":
        return plan_next(plan_path, authorized_root(args.root))
    if args.plan_command == "tick":
        return plan_tick(plan_path, args.item, args.note, args.verified)
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
