#!/usr/bin/env python3
"""Check the requested output shape; semantic quality remains subjective.

Two skeletons are recognised. ``v1`` is the 0.1.0 draft shape (Goal, assumptions, reframings,
"The core"). ``v2`` is the shipped shape: Goal, Wall, Inventory, assumptions, reframings with an
optional ``accepts:`` tag, and "The stack". A file is v2 when its second line starts with
``**Wall:**``.
"""

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
HEADING = re.compile(r"(\d+)\. \*\*(.+?)\*\* · breaks: (.+?)(?: · accepts: (.+?))?(?: · oblique: (.+))?")


def check(path: Path) -> dict:
    text = path.read_text()
    head, rest = text.split("\n\n", 1)
    head_lines = head.splitlines()
    assert head_lines[0].startswith("**Goal:** "), path
    skeleton = "v2" if len(head_lines) > 1 else "v1"
    if skeleton == "v2":
        assert len(head_lines) == 3, (path, "goal, wall, inventory")
        assert head_lines[1].startswith("**Wall:** ") and re.search(r"\d", head_lines[1]), (path, "wall with a number")
        assert head_lines[2].startswith("**Inventory:** "), path
        for field in ("surplus:", "fixed:", "ratings:", "freedoms:"):
            assert field in head_lines[2], (path, field)
    assumptions_text, rest = rest.split("\n\n**Reframings, ranked:**\n\n")
    assert assumptions_text.startswith("**Assumptions the standard approach makes:**\n"), path
    assumptions = assumptions_text.splitlines()[1:]
    assert 5 <= len(assumptions) <= 8 and all(x.startswith("- ") for x in assumptions), path
    assumption_set = {x[2:] for x in assumptions}
    closer = "\n\n**The stack:** " if skeleton == "v2" else "\n\n**The core:** "
    body, core = rest.split(closer)
    entries = body.split("\n\n")
    assert 4 <= len(entries) <= 6, path
    broken = set()
    names = []
    obliques = []
    accepts = 0
    untested = 0
    for index, entry in enumerate(entries, 1):
        lines = entry.splitlines()
        assert len(lines) == 3, (path, index, "heading, paragraph, grounding")
        match = HEADING.fullmatch(lines[0])
        assert match, (path, index, "heading")
        number, name, assumption, accepted, oblique = match.groups()
        assert int(number) == index and 3 <= len(name.split()) <= 5, (path, index, "name")
        assert assumption in assumption_set and assumption not in broken, (path, index, "assumption")
        broken.add(assumption)
        names.append(name)
        paragraph = lines[1].strip()
        assert 2 <= len(re.split(r"(?<=[.!?])\s+(?=[A-Z])", paragraph)) <= 4, (path, index, "sentences")
        assert "cost" in paragraph.lower(), (path, index, "stated cost")
        assert re.match(r"   Grounding: (Precedent|Argument|Untested): \S", lines[2]), (path, index, "grounding")
        untested += "Grounding: Untested:" in lines[2]
        accepts += bool(accepted)
        if oblique:
            assert oblique in CONSTRAINTS, (path, index, "oblique constraint")
            obliques.append(oblique)
    assert obliques, (path, "oblique survivor")
    assert any(name in core for name in names) and "risk" in core.lower(), (path, "closing section")
    if skeleton == "v2":
        assert "accepts" in core and re.search(r"\d", core), (path, "stack names its accepted constraint and a number")
    return {
        "file": path.name, "skeleton": skeleton, "assumptions": len(assumptions),
        "reframings": len(entries), "oblique": obliques, "accepts": accepts, "untested": untested,
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    names = ("game-harness.md", "trace-annotation.md", "game-harness-v2.md", "trace-annotation-v2.md")
    results = [check(root / name) for name in names if (root / name).exists()]
    assert sum(result["untested"] for result in results) >= 1
    for result in results:
        print(result)
