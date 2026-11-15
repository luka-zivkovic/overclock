#!/usr/bin/env python3
"""Git facts for a product audit: when each part of a project arrived and where work went.

    python3 history.py --root DIR [--window-days N] [--depth N]

Prints JSON. It only reads: no file is written and nothing in the repository changes.
Reading these numbers off `git log` by hand is slow and easy to get wrong (renames reset
dates, one commit touches many directories), which is why this is a script.

What it reports:

  history         newest and oldest commit dates, commit count, how many days ago the newest
                  commit was, whether the clone is shallow, and uncommitted-change counts
  by_quarter      commits and new files per quarter
  areas           directories with the day their first file appeared (carried across
                  renames), last change, total commits, commits inside the recent window
                  (also split by month), and file count; top-level directories first
  recent_commits  every commit inside the recent window: date, subject, directories touched

"Recent" means the last N days before the newest commit (default 180), not before today;
the output states the exact dates.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

SKIP = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", ".nuxt",
    ".svelte-kit", ".turbo", ".vercel", "target", "vendor", "coverage", "Pods", ".gradle",
}
MAX_AREAS = 60
MAX_COMMITS = 80
MAX_TOUCHED = 10


def git(root: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(
            ["git", "-c", "core.quotepath=off", *args], cwd=root, capture_output=True, text=True,
            check=False, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except OSError:
        return None
    return done.stdout if done.returncode == 0 else None


def quarter(date: str) -> str:
    return f"{date[:4]}-Q{(int(date[5:7]) - 1) // 3 + 1}"


def collect(root: Path, window_days: int, depth: int) -> dict:
    head = git(root, "log", "-1", "--format=%H%x09%ad", "--date=short")
    if not head or "\t" not in head:
        return {"git": False, "note": "Not a git repository, or it has no commits. Ask the owner how the project grew."}
    sha, head_date = head.strip().split("\t", 1)
    newest = dt.date.fromisoformat(head_date)
    cutoff = newest - dt.timedelta(days=window_days)
    log = git(
        root, "log", "--no-merges", "--reverse", "-M", "--relative", "--name-status",
        "--date=short", "--format=@%H%x09%ad%x09%s",
    ) or ""

    first_seen: dict[str, str] = {}      # file -> day it first appeared, carried across renames
    last_change: dict[str, str] = {}
    area_commits: Counter[str] = Counter()
    area_recent: Counter[str] = Counter()
    area_months: dict[str, Counter[str]] = {}
    commits_by_quarter: Counter[str] = Counter()
    files_by_quarter: Counter[str] = Counter()
    recent: list[dict] = []
    total = recent_total = 0
    oldest = date = None
    subject = ""
    in_window = False
    touched: set[str] = set()
    places: Counter[str] = Counter()

    def close_commit() -> None:
        for area in touched:
            area_commits[area] += 1
            if in_window:
                area_recent[area] += 1
                area_months.setdefault(area, Counter())[date[:7]] += 1
        if in_window and date is not None:
            # Show the most specific places first: a feature folder says more than "." or "docs".
            ranked = sorted(places, key=lambda p: (p.startswith(".") or p == ".", -p.count("/"), -places[p], p))
            entry = {"date": date, "subject": subject[:100], "touched": sorted(ranked[:MAX_TOUCHED])}
            if len(places) > MAX_TOUCHED:
                entry["more_places"] = len(places) - MAX_TOUCHED
            recent.append(entry)
        touched.clear()
        places.clear()

    for line in log.splitlines():
        if not line:
            continue
        if line.startswith("@"):
            close_commit()
            parts = line[1:].split("\t", 2)
            date = parts[1] if len(parts) > 1 else None
            subject = parts[2] if len(parts) > 2 else ""
            if date is None:
                continue
            oldest = oldest or date
            in_window = dt.date.fromisoformat(date) >= cutoff
            total += 1
            recent_total += int(in_window)
            commits_by_quarter[quarter(date)] += 1
            continue
        if date is None:
            continue
        fields = line.split("\t")
        status = fields[0]
        if status[0] in "RC" and len(fields) >= 3:
            old, path = fields[1], fields[2]
            origin = first_seen.get(old, date)
            if status[0] == "R":
                first_seen.pop(old, None)
                last_change.pop(old, None)
            first_seen[path] = origin
        elif len(fields) >= 2:
            path = fields[1]
            if status[0] == "D":
                first_seen.pop(path, None)
                last_change.pop(path, None)
                continue
            if path not in first_seen:
                first_seen[path] = date
                files_by_quarter[quarter(date)] += 1
        else:
            continue
        last_change[path] = date
        segments = path.split("/")[:-1]
        for level in range(1, min(len(segments), depth) + 1):
            touched.add("/".join(segments[:level]))
        places["/".join(segments[:depth]) or "."] += 1
    close_commit()

    # Describe the directories that exist now.
    files: Counter[str] = Counter()
    for current, names, filenames in os.walk(root):
        names[:] = sorted(n for n in names if n not in SKIP and not n.startswith("."))
        relative = Path(current).relative_to(root).parts
        for level in range(1, min(len(relative), depth) + 1):
            files["/".join(relative[:level])] += len(filenames)
    arrived: dict[str, str] = {}
    changed: dict[str, str] = {}
    for path, day in first_seen.items():
        segments = path.split("/")[:-1]
        for level in range(1, min(len(segments), depth) + 1):
            area = "/".join(segments[:level])
            if area in files:
                arrived[area] = min(day, arrived.get(area, day))
                changed[area] = max(last_change.get(path, day), changed.get(area, day))
    areas = []
    for area, count in files.items():
        parent = area.rpartition("/")[0]
        if parent and count >= 0.8 * files.get(parent, 0):
            continue  # the parent holds little else, so one row says it all
        row = {
            "path": area, "files": count, "first_seen": arrived.get(area), "last_change": changed.get(area),
            "commits": area_commits.get(area, 0), "recent_commits": area_recent.get(area, 0),
        }
        if area in area_months:
            row["recent_by_month"] = dict(sorted(area_months[area].items()))
        areas.append(row)
    areas.sort(key=lambda a: ("/" in a["path"], -a["recent_commits"], -a["commits"], a["path"]))

    status = git(root, "status", "--porcelain", "--", ".") or ""
    dirty = [entry for entry in status.splitlines() if entry.strip()]
    quarters = sorted(set(commits_by_quarter) | set(files_by_quarter))
    recent.reverse()
    shallow = (git(root, "rev-parse", "--is-shallow-repository") or "").strip() == "true"
    notes = []
    if shallow:
        notes.append(
            "This clone is shallow: anything dated at the oldest commit may be older than it looks. "
            "Use release notes for real dates, or fetch the full history."
        )
    if newest - dt.date.fromisoformat(oldest or head_date) < dt.timedelta(days=window_days):
        notes.append(
            "The whole history fits inside the recent window, so recent_commits equals commits. "
            "Read recent_by_month to see where work moved, or pass a shorter --window-days."
        )
    return {
        "git": True,
        "notes": notes,
        "history": {
            "head": sha[:10],
            "newest_commit": head_date,
            "oldest_commit": oldest,
            "days_since_newest_commit": (dt.date.today() - newest).days,
            "commits": total,
            "shallow_clone": shallow,
            "uncommitted": {
                "modified": sum(1 for entry in dirty if not entry.startswith("??")),
                "untracked": sum(1 for entry in dirty if entry.startswith("??")),
            },
        },
        "recent_window": {"days": window_days, "from": cutoff.isoformat(), "to": head_date},
        "recent_commit_count": recent_total,
        "by_quarter": [
            {"quarter": q, "commits": commits_by_quarter.get(q, 0), "new_files": files_by_quarter.get(q, 0)} for q in quarters
        ],
        "areas": areas[:MAX_AREAS],
        "areas_not_shown": max(0, len(areas) - MAX_AREAS),
        "recent_commits": recent[:MAX_COMMITS],
        "recent_commits_not_shown": max(0, len(recent) - MAX_COMMITS),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".")
    parser.add_argument("--window-days", type=int, default=180, help="how far back 'recent' reaches from the newest commit")
    parser.add_argument("--depth", type=int, default=3, help="how many directory levels to report")
    args = parser.parse_args(argv)
    root = Path(os.path.abspath(os.path.expanduser(args.root)))
    if not root.is_dir():
        print(f"ERROR: not a directory: {root}", file=sys.stderr)
        return 1
    if args.window_days < 1 or args.depth < 1:
        print("ERROR: --window-days and --depth must be positive", file=sys.stderr)
        return 1
    print(json.dumps(collect(root, args.window_days, args.depth), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
