#!/usr/bin/env python3
"""Fail if a skill's markdown cites a bundled file that does not exist.

SKILL.md and reference docs point at bundled material (`references/x.md`,
`templates/x.md`, `scripts/x.py`, `assets/x.html`). A pointer to a file that
was renamed or never shipped fails silently at runtime — the model just never
loads the material. This check makes a dangling pointer a CI failure.

Scope: every ``*.md`` under ``plugins/*/skills/<skill>/``. A citation is any
``references/…``, ``templates/…``, ``scripts/…``, or ``assets/…`` path
segment; it must resolve inside that skill's directory. Skipped: URLs,
``<placeholder>`` text, wildcard paths, and bare directory mentions. A
``${VAR}``-prefixed path (e.g. ``"${CLAUDE_SKILL_DIR}/scripts/x.py"``) is
still checked — the segment after the variable names a real bundled file. To
mention such a path in prose WITHOUT asserting it exists (an example output
name, a cross-skill mention), use a wildcard (``references/*.md``) or an
angle-bracket placeholder (``<scripts/example.py>``).

Inspired by compound-engineering's validate-doc-claims (see
docs/skill-authoring-notes.md).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "qa"))
from eval_contract import resolve_suite  # noqa: E402

CITATION = re.compile(
    r"(?:(?<=\}/)|(?<![\w/.<-]))((?:references|templates|scripts|assets)/[A-Za-z0-9_.-]+"
    r"(?:/[A-Za-z0-9_.-]+)*\.[A-Za-z0-9]+)"
)
EVIDENCE_BANNER = re.compile(
    r"\|\s*(\d+) declared live cases\s*\|\s*"
    r"(\d+) shipped skill distributions\s*\|"
)


def cited_paths(text: str) -> set[str]:
    found = set()
    for match in CITATION.finditer(text):
        path = match.group(1)
        # A wildcard or placeholder is documentation, not a citation.
        if "*" in path or "<" in path or ">" in path:
            continue
        found.add(path)
    return found


def check_skill(skill_dir: Path, display_base: Path) -> list[str]:
    failures = []
    for md in sorted(skill_dir.rglob("*.md")):
        text = md.read_text(encoding="utf-8")
        for cited in sorted(cited_paths(text)):
            if not (skill_dir / cited).is_file():
                rel_md = md.relative_to(display_base)
                failures.append(f"{rel_md}: cites missing file {cited}")
    return failures


def check_evidence_banner() -> list[str]:
    """Keep README evidence totals synchronized with shipped suites."""
    skill_dirs = sorted(
        path
        for path in (REPO / "plugins").glob("*/skills/*")
        if (path / "SKILL.md").is_file()
    )
    eval_root = REPO / "qa" / "evals"
    resolved_suites: set[Path] = set()
    missing = []
    for skill_dir in skill_dirs:
        plugin = skill_dir.parents[1].name
        eval_path = eval_root / plugin / f"{skill_dir.name}.evals.json"
        if not eval_path.is_file():
            missing.append(f"{plugin}/{skill_dir.name}")
            continue
        try:
            resolved_suites.add(resolve_suite(eval_path, eval_root))
        except ValueError as exc:
            return [str(exc)]
    if missing:
        return [
            "README evidence count cannot be derived; missing eval suites for "
            + ", ".join(missing)
        ]
    case_count = sum(
        len(json.loads(path.read_text(encoding="utf-8"))["evals"])
        for path in resolved_suites
    )
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    match = EVIDENCE_BANNER.search(readme)
    expected = (case_count, len(skill_dirs))
    if match is None:
        return [
            "README needs an evidence banner formatted as "
            f"'| {expected[0]} declared live cases | "
            f"{expected[1]} shipped skill distributions |'"
        ]
    declared = (int(match.group(1)), int(match.group(2)))
    if declared != expected:
        return [
            f"README evidence banner says {declared[0]} cases/{declared[1]} "
            f"distributions; repository has {expected[0]}/{expected[1]}"
        ]
    return []


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else REPO / "plugins"
    skill_dirs = sorted(p for p in root.glob("*/skills/*") if p.is_dir())
    if not skill_dirs:
        print(f"ERROR: no skill directories under {root}", file=sys.stderr)
        return 1
    failures = []
    for skill_dir in skill_dirs:
        failures.extend(check_skill(skill_dir, root))
    if root == (REPO / "plugins").resolve():
        failures.extend(check_evidence_banner())
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    print(f"OK: doc claims resolve in {len(skill_dirs)} skill dir(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
