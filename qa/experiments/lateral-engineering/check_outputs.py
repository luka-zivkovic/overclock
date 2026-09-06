#!/usr/bin/env python3
"""Check the requested output shape; semantic quality remains subjective."""

from pathlib import Path
import re


CONSTRAINTS = {
    "must work offline",
    "buildable with 1995 technology",
    "operated by someone who can't code",
    "must get better as it fails more",
    "runs on the smallest machine in the building",
    "survives the team being fired",
    "explainable in one sentence to a child",
    "costs zero at rest",
    "reversible at any point",
    "what you'd build if you had to demo tomorrow",
}


def check(path: Path) -> dict:
    text = path.read_text()
    goal, rest = text.split("\n\n", 1)
    assert goal.startswith("**Goal:** ") and "\n" not in goal, path
    assumptions_text, rest = rest.split("\n\n**Reframings, ranked:**\n\n")
    assert assumptions_text.startswith("**Assumptions the standard approach makes:**\n"), path
    assumptions = assumptions_text.splitlines()[1:]
    assert 5 <= len(assumptions) <= 8 and all(x.startswith("- ") for x in assumptions), path
    assumption_set = {x[2:] for x in assumptions}
    body, core = rest.split("\n\n**The core:** ")
    entries = body.split("\n\n")
    assert 4 <= len(entries) <= 6, path
    broken = set()
    names = []
    obliques = []
    untested = 0
    for index, entry in enumerate(entries, 1):
        lines = entry.splitlines()
        assert len(lines) == 3, (path, index, "heading, paragraph, grounding")
        match = re.fullmatch(r"(\d+)\. \*\*(.+)\*\* · breaks: (.+?)(?: · oblique: (.+))?", lines[0])
        assert match, (path, index, "heading")
        number, name, assumption, oblique = match.groups()
        assert int(number) == index and 3 <= len(name.split()) <= 5, (path, index, "name")
        assert assumption in assumption_set and assumption not in broken, (path, index, "assumption")
        broken.add(assumption)
        names.append(name)
        paragraph = lines[1].strip()
        assert 2 <= len(re.split(r"(?<=[.!?])\s+(?=[A-Z])", paragraph)) <= 4, (path, index, "sentences")
        assert "cost" in paragraph.lower(), (path, index, "stated cost")
        assert re.match(r"   Grounding: (Precedent|Argument|Untested): \S", lines[2]), (path, index, "grounding")
        untested += "Grounding: Untested:" in lines[2]
        if oblique:
            assert oblique in CONSTRAINTS, (path, index, "oblique constraint")
            obliques.append(oblique)
    assert obliques, (path, "oblique survivor")
    assert any(name in core for name in names) and "risk" in core.lower(), (path, "core")
    return {"file": path.name, "assumptions": len(assumptions), "reframings": len(entries), "oblique": obliques, "untested": untested}


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    results = [check(root / name) for name in ("game-harness.md", "trace-annotation.md")]
    assert sum(result["untested"] for result in results) >= 1
    for result in results:
        print(result)
