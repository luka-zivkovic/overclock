#!/usr/bin/env python3
"""Record the execution configuration shared by both arms of a value comparison."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def harness_hash() -> str:
    qa = Path(__file__).resolve().parent
    paths = [*qa.glob("*.sh"), *qa.glob("*.py"), *qa.joinpath("fixtures").rglob("*")]
    digest = hashlib.sha256()
    for path in sorted(paths):
        if not path.is_file() or path.name.startswith("test_") or "__pycache__" in path.parts:
            continue
        for part in (path.relative_to(qa).as_posix().encode(), path.read_bytes()):
            digest.update(len(part).to_bytes(8, "big"))
            digest.update(part)
    return digest.hexdigest()


def main() -> None:
    if len(sys.argv) != 8:
        raise SystemExit("usage: eval_runtime.py OUT CLI_VERSION MODEL EFFORT JUDGE ALLOWED AVAILABLE")
    output, version, model, effort, judge, allowed, available = sys.argv[1:]
    value = dict(schema_version=1, claude_version=version,
                 eval_model=model or "cli-default", eval_effort=effort or "cli-default",
                 judge_model=judge, allowed_tools=allowed, available_tools=available,
                 harness_sha256=harness_hash())
    with Path(output).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
