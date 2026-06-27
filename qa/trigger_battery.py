#!/usr/bin/env python3
"""Trigger-battery scored loop (objective tier) — optimize a skill's frontmatter
`description` for routing precision.

For each description VARIANT: install the skill with that description into a fresh
cwd, run each battery prompt as a `claude -p` session, and detect — BEHAVIORALLY —
whether the skill fired: did the run write the skill's contract file
(.ai/memory/LESSONS.md) in its cwd? Writing to native ~/.claude memory, or nowhere,
counts as NOT fired. No judge needed — routing is mechanically observable.

Score = correct routing decisions / total (should-trigger wants fired; should-not
wants silent). The winning variant is the description we'd ship. This is one round
of the loop (score variants -> pick best); a full loop regenerates candidates from
the losers and repeats until no improvement.

Usage: qa/trigger_battery.py qa/trigger-battery/lessons-learned.json [--model M]
Local only. Writes results under qa/_work/trigger-battery/. Nothing is committed.
"""
from __future__ import annotations
import argparse, json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "plugins/session-memory/skills"
CONTRACT_FILE = ".ai/memory/LESSONS.md"   # the behavioral signal for lessons-learned

ALLOWED = "Skill,Read,Glob,Grep,Bash(ls*),Bash(cat*),Bash(mkdir*),Write,Edit"


def swap_description(text: str, desc: str) -> str:
    return re.sub(r"(?m)^description:.*$", "description: " + desc, text, count=1)


def run_prompt(skill: str, desc: str, prompt: str, model: str) -> bool:
    """Fresh cwd, skill installed with `desc`, run the prompt, return True if the
    skill's contract file was written (it fired)."""
    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        dst = wd / ".claude" / "skills" / skill
        shutil.copytree(SKILLS / skill, dst)
        sm = dst / "SKILL.md"
        sm.write_text(swap_description(sm.read_text(encoding="utf-8"), desc), encoding="utf-8")
        subprocess.run(
            ["claude", "-p", prompt, "--model", model, "--output-format", "json",
             "--no-session-persistence", "--allowedTools", ALLOWED],
            cwd=wd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return (wd / CONTRACT_FILE).exists()


def score(skill: str, desc: str, battery: dict, model: str) -> dict:
    rows = []
    for p in battery["should_trigger"]:
        rows.append(("should", p, run_prompt(skill, desc, p, model)))
    for p in battery["should_not"]:
        rows.append(("should_not", p, run_prompt(skill, desc, p, model)))
    correct = sum(1 for kind, _, fired in rows if (kind == "should") == fired)
    return {"correct": correct, "total": len(rows), "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("battery", type=Path)
    ap.add_argument("--model", default="claude-sonnet-4-6")
    args = ap.parse_args()

    b = json.loads(args.battery.read_text())
    skill = b["skill"]
    out = REPO / "qa/_work/trigger-battery"
    out.mkdir(parents=True, exist_ok=True)

    print(f"Trigger battery for {skill}  (model={args.model})")
    print(f"{len(b['should_trigger'])} should-trigger + {len(b['should_not'])} should-not "
          f"x {len(b['variants'])} variants\n")

    scores = {}
    for label, desc in b["variants"].items():
        print(f"-- scoring variant: {label}")
        r = score(skill, desc, b, args.model)
        scores[label] = r
        for kind, prompt, fired in r["rows"]:
            ok = "OK " if (kind == "should") == fired else "MISS"
            want = "fire" if kind == "should" else "silent"
            got = "fired" if fired else "silent"
            print(f"     [{ok}] want {want:6} got {got:6} | {prompt[:58]}")
        print(f"   => {label}: {r['correct']}/{r['total']}\n")

    (out / f"{skill}.results.json").write_text(json.dumps(scores, indent=1))
    ranked = sorted(scores.items(), key=lambda kv: kv[1]["correct"], reverse=True)
    base = scores.get("baseline", {}).get("correct", -1)
    print("scoreboard:")
    for label, r in ranked:
        delta = r["correct"] - base if base >= 0 and label != "baseline" else 0
        tag = "  <- baseline" if label == "baseline" else (f"  (+{delta} vs baseline)" if delta > 0 else (f"  ({delta} vs baseline)" if delta < 0 else "  (= baseline)"))
        print(f"  {r['correct']}/{r['total']}  {label}{tag}")
    win_label, win = ranked[0]
    if win_label == "baseline" or win["correct"] <= base:
        print(f"\nDECISION: keep baseline ({base}/{win['total']}) — no candidate beat it. "
              f"Losers go to rejected-edit memory; next round regenerates from them.")
    else:
        print(f"\nDECISION: accept '{win_label}' ({win['correct']}/{win['total']} vs "
              f"baseline {base}/{win['total']}). Ship as the new description; re-run to confirm.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
