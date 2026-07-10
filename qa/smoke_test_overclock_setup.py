#!/usr/bin/env python3
"""Install overclock-setup from the local marketplace in an isolated config."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


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
        run("plugin", "install", "overclock-setup@overclock", "--scope", "user", env=env)
        rows = json.loads(run("plugin", "list", "--json", env=env))
        matches = [row for row in rows if row.get("id") == "overclock-setup@overclock"]
        if len(matches) != 1 or not matches[0].get("enabled"):
            raise SystemExit("overclock-setup was not installed and enabled exactly once")
        details = run("plugin", "details", "overclock-setup@overclock", env=env)
        if "setup" not in details:
            raise SystemExit("installed plugin details do not list the setup skill")
    print("OK: isolated marketplace install exposes overclock-setup:setup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
