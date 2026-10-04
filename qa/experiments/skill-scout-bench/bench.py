#!/usr/bin/env python3
"""Scaling benchmark for the skill-scout helper with planted ground truth.

Generates synthetic Claude Code, Codex, and Pi histories at several sizes, plants recurring intents
with realistic paraphrases (plus one intent that recurs inside a single session only), mixes in
unique noise requests, bulky tool output, injected records, headless runs, and subagent
transcripts carrying planted text, then runs `skill_scout.py scan` and scores the report:

- recall: eligible intents (two or more sessions) that surface as a cluster
- session recall: sessions the matching cluster covers out of the sessions that carry the intent
- fragmentation: extra clusters for the same intent
- false positives: the single-session intent, or clusters made only of noise
- leakage: a cluster spanning more sessions than were planted means contamination was counted
- cost inputs: wall time, peak memory of the helper, bytes read, and report size in tokens

Nothing here calls a model. Run: python3 qa/experiments/skill-scout-bench/bench.py [--scales 50,200,600]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "plugins/skill-scout/skills/skill-scout/scripts/skill_scout.py"
SECRET = "ghp_" + "Bench0Secret0" + "Q" * 24

INTENTS = {
    "release-notes": ("request", 0.10, [
        "Write release notes for everything merged since the last tag, grouped into features, fixes and chores, with PR links",
        "can you draft the release notes since the last tag? group by features / fixes / chores and link the PRs",
        "release notes please: merged PRs since last tag, grouped features fixes chores, PR links",
        "draft release notes since the last tag grouped by features, fixes, chores with links to each PR",
        "need release notes for the merged PRs since the last tag, features fixes chores sections, link every PR",
        "put together the release notes from the last tag to now, split into features, fixes and chores",
        "generate release notes covering PRs merged after the latest tag; features, fixes, chores; link each one",
    ]),
    "pr-description": ("request", 0.07, [
        "write a PR description for this branch summarizing the changes and the testing notes",
        "write the pull request description for this branch: summary of changes plus testing notes",
        "PR description for this branch please, summarize the changes and add testing notes",
        "draft a pull request description for my branch with a change summary and how I tested it",
        "can you write up the PR description, summary of what changed on this branch and testing notes",
    ]),
    "changelog-bump": ("request", 0.05, [
        "update CHANGELOG.md with the new entries and bump the patch version in package.json",
        "add the changes to the changelog and bump the package version (patch)",
        "bump the patch version and add a changelog entry for what we just did",
        "changelog entry plus patch version bump in package.json please",
    ]),
    "rebase-conflicts": ("request", 0.04, [
        "rebase this branch onto main and resolve the merge conflicts, keep our changes where they clash",
        "rebase on main and fix the conflicts, prefer our side when both changed",
        "pull latest main, rebase my branch, and resolve conflicts keeping our version",
    ]),
    "security-diff": ("request", 0.03, [
        "review my staged diff for security problems: injection, secrets, unsafe deserialization, auth bypass",
        "check the current diff for security issues like injection, leaked secrets, auth bypass, unsafe deserialization",
        "security review of my changes: look for injection, secrets in code, deserialization, and auth bypasses",
    ]),
    "pnpm-correction": ("correction", 0.04, [
        "no, don't use npm here, use pnpm for installs",
        "no, use pnpm not npm for installs in this repo",
        "stop using npm for installs, it's pnpm",
        "again, pnpm for installs, not npm",
    ]),
    "no-comments-correction": ("correction", 0.03, [
        "don't add comments that just restate the code",
        "stop adding comments that restate what the code does",
        "no, remove those comments, they only restate the code",
    ]),
}
SINGLE_SESSION = ("request", [
    "migrate the legacy cron jobs in ops/cron to the new scheduler service and delete the old crontab",
    "migrate the remaining legacy cron jobs to the scheduler service, then delete the old crontab",
    "finish migrating legacy cron jobs to the scheduler service and remove the crontab",
])
VERBS = ["fix", "explain", "refactor", "rename", "optimize", "document", "investigate", "profile", "simplify",
         "split", "merge", "delete", "move", "rewrite", "debug", "trace", "audit", "port", "mock", "stub",
         "paginate", "cache", "validate", "sanitize", "throttle", "retry", "localize", "version", "deprecate", "inline"]
THINGS = ["websocket reconnect loop", "billing webhook handler", "invoice pdf renderer", "dark mode toggle",
          "search indexer", "avatar upload", "password reset email", "feature flag client", "rate limiter",
          "csv importer", "graphql resolver", "session store", "audit log writer", "image thumbnailer",
          "geo lookup", "slack notifier", "oauth callback", "cart total", "tax calculator", "sitemap builder",
          "metrics exporter", "queue consumer", "cron parser", "markdown sanitizer", "date picker",
          "push notification", "pdf exporter", "currency formatter", "admin dashboard", "retry backoff"]
DETAILS = ["when the server returns 503", "for the mobile layout", "under heavy load", "on safari only",
           "after the last deploy", "for unicode input", "with an empty payload", "in the staging cluster",
           "for legacy accounts", "behind the proxy", "when the token expires", "during the nightly batch",
           "for europe customers", "with two currencies", "after a timeout", "on first login",
           "when offline", "with large files", "in dry run mode", "for archived projects"]
# Varied noise: many more subjects and conditions, so topic repeats are as rare as in real use.
QUALIFIERS = ["legacy", "new", "admin", "public", "internal", "mobile", "beta", "async", "shared", "tenant",
              "nightly", "partner", "v2", "regional", "cached", "batch", "guest", "premium", "draft", "audit"]
EXTRA_DETAILS = ["since the schema change", "for the iOS client", "with feature flags off", "in the docker build",
                 "for the reporting team", "after the library upgrade", "with read replicas", "in local dev",
                 "for the onboarding flow", "when retries run out", "under the new pricing", "for the api gateway",
                 "with strict mode on", "behind the cdn", "for long running jobs", "in the monorepo",
                 "with the old client", "for scheduled exports", "during failover", "on windows"]
APPROVALS = ["yes", "continue", "go ahead", "ok do it", "thanks", "lgtm"]
FILLER = ("lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore "
          "et dolore magna aliqua ut enim ad minim veniam quis nostrud exercitation ullamco laboris ")


def stamp(when: dt.datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def write_jsonl(path: Path, records: list[dict], when: dt.datetime) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = "".join(json.dumps(record) + "\n" for record in records)
    path.write_text(data, encoding="utf-8")
    import os
    os.utime(path, (when.timestamp(), when.timestamp()))
    return len(data)


def build(home: Path, sessions: int, rng: random.Random, installed: int, noise: str = "dense") -> dict:
    """Write one synthetic history; return the ground truth."""
    now = dt.datetime.now(dt.timezone.utc)
    truth = {name: set() for name in INTENTS}
    truth["single-session"] = set()
    if noise == "varied":
        subjects = [f"{qualifier} {thing}" for qualifier in QUALIFIERS for thing in THINGS]
        conditions = DETAILS + EXTRA_DETAILS
        noise_pool = [f"{rng.choice(VERBS)} the {subject} {rng.choice(conditions)}" for subject in subjects for _ in range(8)]
        noise_pool = list(dict.fromkeys(noise_pool))
    else:
        noise_pool = [f"{verb} the {thing} {detail}" for verb in VERBS for thing in THINGS for detail in DETAILS]
    rng.shuffle(noise_pool)
    harnesses = ["claude-code"] * 12 + ["codex"] * 5 + ["pi"] * 3
    single_session_index = rng.randrange(sessions)
    total_bytes = 0
    for skill_index in range(installed):
        directory = home / ".claude" / "skills" / f"helper-{skill_index:03d}"
        directory.mkdir(parents=True, exist_ok=True)
        thing = THINGS[skill_index % len(THINGS)]
        (directory / "SKILL.md").write_text(
            f"---\nname: helper-{skill_index:03d}\ndescription: \"Work on the {thing}: diagnose, change, and verify "
            f"it. Use when the user asks about the {thing} or its tests. Do not use for unrelated modules.\"\n---\n\nSteps.\n")
    pr_skill = home / ".claude" / "skills" / "pr-description"
    pr_skill.mkdir(parents=True, exist_ok=True)
    (pr_skill / "SKILL.md").write_text(
        "---\nname: pr-description\ndescription: \"Write a pull request description from the branch diff: summary "
        "of changes, testing notes, and risks. Use when the user asks for a PR description. Do not use for release "
        "notes.\"\n---\n\nSteps.\n")
    for index in range(sessions):
        harness = harnesses[index % len(harnesses)]
        when = now - dt.timedelta(days=rng.uniform(0.2, 28))
        session_id = f"{harness}-{index:05d}"
        prompts: list[tuple[str, str]] = []
        for name, (kind, rate, variants) in INTENTS.items():
            forced = index < 2 * len(INTENTS) and index // 2 == list(INTENTS).index(name)
            if forced or rng.random() < rate:
                text = rng.choice(variants)
                if name == "release-notes" and rng.random() < 0.2:
                    text += f" and push with GITHUB_TOKEN={SECRET}"
                prompts.append((kind, text))
                truth[name].add(session_id)
        if index == single_session_index:
            for text in SINGLE_SESSION[1]:
                prompts.append(("request", text))
            truth["single-session"].add(session_id)
        for _ in range(rng.randint(3, 9)):
            prompts.append(("request", noise_pool.pop()))
        for _ in range(rng.randint(0, 3)):
            prompts.append(("request", rng.choice(APPROVALS)))
        rng.shuffle(prompts)
        # Corrections only count after an assistant turn, so keep them out of first position.
        if prompts and prompts[0][0] == "correction":
            prompts.append(prompts.pop(0))
        tool_text = (FILLER * 20)[: rng.randint(1500, 4000)]
        leak_text = INTENTS["release-notes"][2][0]
        total_bytes += write_session(home, harness, session_id, when, prompts, tool_text, leak_text, rng)
    # Contamination that must never be counted: headless runs, subagents, and codex exec rollouts.
    for index in range(max(2, sessions // 10)):
        when = now - dt.timedelta(days=rng.uniform(0.2, 28))
        planted = [("request", rng.choice(INTENTS["release-notes"][2])), ("request", rng.choice(INTENTS["changelog-bump"][2]))]
        total_bytes += write_session(home, "claude-code", f"headless-{index:04d}", when, planted, "x", "", rng, entrypoint="sdk-cli")
        total_bytes += write_session(home, "codex", f"exec-{index:04d}", when, planted, "x", "", rng, originator="codex_exec")
        sub = home / ".claude" / "projects" / "-Users-dev-app" / f"parent-{index}" / "subagents" / "agent-1.jsonl"
        total_bytes += write_jsonl(sub, [{"type": "user", "isSidechain": True, "timestamp": stamp(when),
                                          "message": {"role": "user", "content": planted[0][1]}}], when)
    return {"truth": {name: sorted(ids) for name, ids in truth.items()}, "bytes": total_bytes}


def write_session(home: Path, harness: str, session_id: str, when: dt.datetime, prompts: list[tuple[str, str]],
                  tool_text: str, leak_text: str, rng: random.Random, *, entrypoint: str = "cli",
                  originator: str = "codex_cli_rs") -> int:
    cwd = rng.choice(["/Users/dev/app", "/Users/dev/api", "/Users/dev/site"])
    clock = when
    if harness == "claude-code":
        base = {"sessionId": session_id, "cwd": cwd, "entrypoint": entrypoint, "userType": "external"}
        records = []
        for kind, text in prompts:
            clock += dt.timedelta(minutes=3)
            records.append({**base, "type": "user", "timestamp": stamp(clock), "origin": {"kind": "human"},
                            "message": {"role": "user", "content": text}})
            for call in range(rng.randint(1, 4)):
                records.append({**base, "type": "assistant", "timestamp": stamp(clock), "message": {"role": "assistant",
                                "content": [{"type": "tool_use", "id": f"t{call}", "name": "Read", "input": {"file_path": "/x"}}]}})
                records.append({**base, "type": "user", "timestamp": stamp(clock), "message": {"role": "user",
                                "content": [{"type": "tool_result", "tool_use_id": f"t{call}", "content": tool_text + leak_text}]}})
            records.append({**base, "type": "assistant", "timestamp": stamp(clock),
                            "message": {"role": "assistant", "content": [{"type": "text", "text": "Done. " + tool_text[:400]}]}})
        records.append({**base, "type": "user", "isMeta": True, "timestamp": stamp(clock),
                        "message": {"role": "user", "content": leak_text or "meta"}})
        slug = "-" + cwd.strip("/").replace("/", "-")
        return write_jsonl(home / ".claude" / "projects" / slug / f"{session_id}.jsonl", records, when)
    if harness == "codex":
        records = [{"timestamp": stamp(clock), "type": "session_meta", "payload": {"id": session_id, "cwd": cwd, "originator": originator}},
                   {"timestamp": stamp(clock), "type": "event_msg", "payload": {"type": "user_message",
                    "message": f"<environment_context>cwd: {cwd}</environment_context>"}}]
        for kind, text in prompts:
            clock += dt.timedelta(minutes=3)
            records.append({"timestamp": stamp(clock), "type": "response_item", "payload": {"type": "message", "role": "user",
                            "content": [{"type": "input_text", "text": text}]}})
            records.append({"timestamp": stamp(clock), "type": "event_msg", "payload": {"type": "user_message", "message": text}})
            records.append({"timestamp": stamp(clock), "type": "response_item", "payload": {"type": "function_call_output",
                            "call_id": "c", "output": tool_text + leak_text}})
            records.append({"timestamp": stamp(clock), "type": "event_msg", "payload": {"type": "agent_message", "message": "Done."}})
        path = home / ".codex" / "sessions" / when.strftime("%Y/%m/%d") / f"rollout-{when.strftime('%Y-%m-%dT%H-%M-%S')}-{session_id}.jsonl"
        return write_jsonl(path, records, when)
    records = [{"type": "session", "version": 3, "id": session_id, "timestamp": stamp(clock), "cwd": cwd}]
    for position, (kind, text) in enumerate(prompts):
        clock += dt.timedelta(minutes=3)
        records.append({"type": "message", "id": f"u{position}", "timestamp": stamp(clock),
                        "message": {"role": "user", "content": [{"type": "text", "text": text}]}})
        records.append({"type": "message", "id": f"r{position}", "timestamp": stamp(clock),
                        "message": {"role": "toolResult", "toolCallId": "c", "content": [{"type": "text", "text": tool_text + leak_text}]}})
        records.append({"type": "message", "id": f"a{position}", "timestamp": stamp(clock),
                        "message": {"role": "assistant", "content": [{"type": "text", "text": "Done."}]}})
    slug = "--" + cwd.strip("/").replace("/", "-") + "--"
    return write_jsonl(home / ".pi" / "agent" / "sessions" / slug / f"{when.strftime('%Y-%m-%dT%H-%M-%S')}_{session_id}.jsonl", records, when)


def variant_owner(text: str) -> str:
    clean = text.split(" and push with GITHUB_TOKEN")[0].rstrip("…")
    for name, (_, _, variants) in INTENTS.items():
        if any(clean.startswith(variant[: max(20, len(clean) - 5)]) or variant.startswith(clean[:60]) for variant in variants):
            return name
    if any(variant.startswith(clean[:60]) for variant in SINGLE_SESSION[1]):
        return "single-session"
    return "noise"


def score(report: dict, truth: dict) -> dict:
    mapped: dict[str, list[dict]] = {}
    spurious = 0
    for cluster in report["clusters"]:
        owners = [variant_owner(sample["text"]) for sample in cluster["samples"]]
        owner = max(set(owners), key=owners.count)
        if owner == "noise":
            spurious += 1
        else:
            mapped.setdefault(owner, []).append(cluster)
    # Each planted session carries one prompt per intent, so prompts equal sessions. The helper's
    # defaults need three prompts in two sessions (two prompts for corrections).
    eligible = [name for name, (kind, _, _) in INTENTS.items()
                if len(truth[name]) >= (2 if kind == "correction" else 3)]
    rows = {}
    for name in eligible:
        clusters = mapped.get(name, [])
        best = max((cluster["sessions"] for cluster in clusters), default=0)
        rows[name] = {"planted_sessions": len(truth[name]), "found_sessions": best,
                      "clusters": len(clusters), "leak": best > len(truth[name])}
    found = [name for name, row in rows.items() if row["found_sessions"] > 0]
    return {
        "recall": f"{len(found)}/{len(eligible)}",
        "session_recall": round(sum(min(row["found_sessions"], row["planted_sessions"]) for row in rows.values())
                                / max(1, sum(row["planted_sessions"] for row in rows.values())), 3),
        "fragmented": sum(max(0, row["clusters"] - 1) for row in rows.values()),
        "single_session_reported": "single-session" in mapped,
        "noise_clusters": spurious,
        "precision": round(sum(len(clusters) for clusters in mapped.values() if clusters) /
                           max(1, len(report["clusters"])), 3),
        "leaks": [name for name, row in rows.items() if row["leak"]],
        "per_intent": rows,
    }


def run(scale: int, seed: int, installed: int, noise: str = "dense") -> dict:
    rng = random.Random(seed + scale)
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        generated = build(home, scale, rng, installed, noise)
        before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        started = time.monotonic()
        result = subprocess.run([sys.executable, str(SCRIPT), "scan", "--home", str(home)],
                                capture_output=True, text=True, timeout=1800)
        elapsed = time.monotonic() - started
        if result.returncode != 0:
            raise SystemExit(result.stderr)
        rss_kb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        report = json.loads(result.stdout)
    raw = result.stdout
    sections = {key: len(json.dumps(report[key])) for key in ("coverage", "usage", "installed", "clusters", "topics")}
    metrics_only = {"helper_elapsed": report["coverage"].get("elapsed_seconds")}
    metrics = score(report, generated["truth"])
    return {
        "noise": noise, "sessions": scale, "installed_skills": installed + 1, "history_mb": round(generated["bytes"] / 1e6, 1),
        "wall_seconds": round(elapsed, 2), "peak_rss_mb": round(max(rss_kb, before) / 1024, 1),
        "report_chars": len(raw), "report_tokens_est": len(raw) // 4,
        "section_chars": sections, "clusters": len(report["clusters"]),
        "topics": len(report["topics"]), "planted_in_topics": sum(
            1 for topic in report["topics"]
            if variant_owner(topic["samples"][0]["text"]) != "noise"),
        "secret_leaked": SECRET in raw or SECRET[4:20].lower() in raw.lower(), **metrics_only, **metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scales", default="50,200,600")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--installed", type=int, default=60, help="synthetic installed skills (default 60)")
    parser.add_argument("--noise", default="dense,varied", help="dense (adversarial topic repeats), varied, or both")
    args = parser.parse_args()
    rows = [run(int(scale), args.seed, args.installed, noise)
            for noise in args.noise.split(",") for scale in args.scales.split(",")]
    json.dump(rows, sys.stdout, indent=1)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
