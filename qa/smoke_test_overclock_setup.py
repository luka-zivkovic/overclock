#!/usr/bin/env python3
"""Install newly published Overclock packages from an isolated local marketplace."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACKAGES = {
    "overclock-setup": {"setup"},
    "critical-thinking": {"critical-thinking", "independent-research"},
    "discipline-gates": {"test-discipline", "git-archaeologist"},
}


def run(*args: str, env: dict[str, str]) -> str:
    completed = subprocess.run(
        ["claude", *args],
        cwd=REPO,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return completed.stdout


def main() -> int:
    with tempfile.TemporaryDirectory() as temp:
        env = dict(os.environ)
        env["CLAUDE_CONFIG_DIR"] = temp
        run("plugin", "marketplace", "add", str(REPO), env=env)
        for package in PACKAGES:
            run("plugin", "install", f"{package}@overclock", "--scope", "user", env=env)
        rows = json.loads(run("plugin", "list", "--json", env=env))
        for package, expected_skills in PACKAGES.items():
            plugin_id = f"{package}@overclock"
            matches = [row for row in rows if row.get("id") == plugin_id]
            if len(matches) != 1 or not matches[0].get("enabled"):
                raise SystemExit(f"{package} was not installed and enabled exactly once")
            details = run("plugin", "details", plugin_id, env=env)
            missing = sorted(skill for skill in expected_skills if skill not in details)
            if missing:
                raise SystemExit(f"{package} details omit skills: {', '.join(missing)}")
    print("OK: isolated marketplace install exposes setup, critical-thinking, and discipline-gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
