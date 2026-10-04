#!/usr/bin/env python3
"""Find requests the user repeats across agent sessions, as evidence for skill proposals.

`scan` reads Claude Code, Codex, and Pi session logs, keeps only prompts a person typed (dropping
injected context, tool results, command output, subagent and headless runs), redacts secrets,
collapses repeats within one session, clusters recurring requests and corrections across sessions,
and matches each cluster against installed skills. It prints one JSON report and writes nothing.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness_common import discover, display, read_json, redact, resolve_roots  # noqa: E402

SCHEMA = "skill-scout/v1"
SUPPORTED = ("claude-code", "codex", "pi")
UNSUPPORTED = {"cursor": "Cursor keeps chats in SQLite", "opencode": "OpenCode splits sessions across many small files"}
MAX_PROMPT_CHARS = 4_000
MAX_SAMPLE_CHARS = 300
MAX_CLUSTERS = 12
MAX_TOPICS = 5
TOPIC_SAMPLES = 2
MAX_SAMPLES = 5
MAX_PROMPTS = 6_000
MAX_TOKENS_PER_PROMPT = 150
TEMP_PREFIXES = ("/tmp/", "/var/folders/", "/private/var/folders/", "/private/tmp/")

STOPWORDS = set("""
a about after again all also am an and any are as at be because been before being but by can could
did do does doing don't done for from get got had has have having here how i i'd i'll i'm if in into
is it it's its just let let's like me more most my no not now of off ok okay on once only or other our
out over please pls so some such than that the their them then there these they this those through to
too up us very want wanted was we were what when where which while who why will with would yes yeah
yep you your you're can't hey hi thanks thank cool great good nice perfect sure go ahead continue
proceed lgtm right also maybe really still something anything thing things way kind bit lot little
""".split())
CORRECTION_RE = re.compile(
    r"^(?:no\b|nope\b|wrong\b|stop\b|don't\b|do not\b|that's not\b|that is not\b|not like that\b|"
    r"why did you\b|you (?:forgot|missed|didn't|did not|keep|always|never|broke)\b|i (?:said|told you|asked)\b|"
    r"again[,!.]|actually[, ]|instead[, ]|please don't\b|never\b)",
    re.IGNORECASE,
)
# Imperative verbs grouped by intent, read from the first content word of a request. Two requests
# that open with verbs from different groups ("fix the importer" / "explain the importer") are
# different asks about one topic, not a repeat. Words that usually open a noun phrase ("release
# notes", "log file", "cache layer") are deliberately absent.
ACTION_GROUPS = {
    "produce": "write draft generate create compose prepare produce summarize summarise outline put",
    "modify": "update add bump change edit append insert adjust",
    "fix": "fix repair resolve debug troubleshoot",
    "explain": "explain describe clarify",
    "inspect": "review check audit inspect verify assess evaluate",
    "restructure": "refactor restructure simplify rewrite reorganize reorganise split move rename extract inline",
    "remove": "delete remove drop deprecate",
    "integrate": "rebase merge pull sync",
    "investigate": "investigate diagnose profile trace",
    "optimize": "optimize optimise",
    "deploy": "deploy publish ship",
    "migrate": "migrate port upgrade downgrade",
    "implement": "implement build",
    "install": "install configure",
    "revert": "revert undo",
    "test": "test",
    "double": "mock stub",
    "translate": "translate localize",
    "convert": "convert",
    "format": "format lint",
    "paginate": "paginate",
    "validate": "validate sanitize",
    "throttle": "throttle",
    "retry": "retry",
    "commit": "commit",
}
ACTION_OF = {word: group for group, words in ACTION_GROUPS.items() for word in words.split()}
FILLERS = set("can could would will you please pls kindly let let's lets now ok okay so then also just hey hi "
              "help me i i'd we need want to quickly go ahead and".split())
APPROVAL_RE = re.compile(r"^(?:y|yes|yeah|yep|ok|okay|sure|go|go ahead|continue|proceed|do it|lgtm|thanks|thank you)[.! ]*$", re.I)
CLAUDE_INJECTED_PREFIXES = (
    "<task-notification", "<agent-message", "<local-command-stdout", "<local-command-stderr",
    "<bash-input", "<bash-stdout", "<bash-stderr", "<user-memory-input", "Caveat: The messages below",
    "[Request interrupted", "This session is being continued from a previous conversation",
    "<command-message",
)
CODEX_INJECTED_PREFIXES = (
    "<environment_context", "<user_instructions", "# AGENTS.md instructions", "<user_shell_command",
    "<turn_aborted", "<subagent", "<skill",
)


def now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def parse_time(value: object) -> _dt.datetime | None:
    if isinstance(value, (int, float)):
        return _dt.datetime.fromtimestamp(value / 1000 if value > 1e11 else value, _dt.timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=_dt.timezone.utc)


def text_blocks(content: object) -> tuple[str, bool]:
    """(joined text, has_tool_result) for string or block-list message content."""
    if isinstance(content, str):
        return content, False
    parts, tool_result = [], False
    for block in content if isinstance(content, list) else []:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind in {"tool_result", "toolResult", "function_call_output"}:
            tool_result = True
        elif kind in {"text", "input_text"} and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "\n".join(parts), tool_result


def strip_injected(text: str) -> str:
    text = re.sub(r"<system-reminder>.*?</system-reminder>", " ", text, flags=re.S)
    text = re.sub(r"<pasted_content[^>]*>.*?</pasted_content>", " [pasted text] ", text, flags=re.S)
    return text.strip()


class Session:
    def __init__(self, harness: str, path: Path, roots: dict) -> None:
        self.harness = harness
        self.id = path.stem
        self.path = display(path, roots)
        self.cwd: str | None = None
        self.automated = False
        self.prompts: list[dict] = []
        self.slash: Counter = Counter()
        self.skills: Counter = Counter()
        self.unknown: Counter = Counter()
        self.dropped: Counter = Counter()
        self.parse_errors = 0
        self.last_was_assistant = False

    def add_prompt(self, text: str, when: _dt.datetime | None) -> None:
        text = strip_injected(text)
        if not text:
            self.dropped["empty"] += 1
            return
        if APPROVAL_RE.match(text):
            self.dropped["approval"] += 1
            return
        kind = "correction" if self.last_was_assistant and CORRECTION_RE.match(text) else "request"
        self.prompts.append({"text": text[:MAX_PROMPT_CHARS], "when": when, "kind": kind})


def skill_from_path(text: str) -> list[str]:
    return re.findall(r"/skills/([A-Za-z0-9_.-]+)/SKILL\.md", text)


def parse_claude(path: Path, roots: dict) -> Session:
    session = Session("claude-code", path, roots)
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if '"user"' not in line and '"assistant"' not in line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                session.parse_errors += 1
                continue
            if not isinstance(record, dict):
                continue
            if session.cwd is None and isinstance(record.get("cwd"), str):
                session.cwd = record["cwd"]
            entrypoint = record.get("entrypoint")
            if isinstance(entrypoint, str) and entrypoint.startswith("sdk"):
                session.automated = True
            kind = record.get("type")
            if kind == "assistant":
                session.last_was_assistant = True
                content = (record.get("message") or {}).get("content")
                for block in content if isinstance(content, list) else []:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    data = block.get("input") if isinstance(block.get("input"), dict) else {}
                    if block.get("name") == "Skill" and isinstance(data.get("skill"), str):
                        session.skills[data["skill"].lstrip("/")] += 1
                    elif block.get("name") == "Read" and isinstance(data.get("file_path"), str):
                        for name in skill_from_path(data["file_path"]):
                            session.skills[name] += 1
                continue
            if kind != "user":
                continue
            if record.get("isSidechain") is True:
                session.dropped["subagent"] += 1
                continue
            if record.get("isMeta") is True or record.get("isCompactSummary") is True:
                session.dropped["injected"] += 1
                continue
            origin = record.get("origin")
            if isinstance(origin, dict) and origin.get("kind") not in (None, "human"):
                session.dropped["injected"] += 1
                continue
            text, tool_result = text_blocks((record.get("message") or {}).get("content"))
            if tool_result:
                session.dropped["tool_result"] += 1
                continue
            text = strip_injected(text)
            stripped = text.lstrip()
            command = re.search(r"<command-name>/?([^<]+)</command-name>", text)
            if command:
                name = command.group(1).strip()
                session.slash[name] += 1
                args = re.search(r"<command-args>(.*?)</command-args>", text, re.S)
                if args and len(args.group(1).split()) >= 3:
                    session.add_prompt(f"/{name} {args.group(1)}", parse_time(record.get("timestamp")))
                session.last_was_assistant = False
                continue
            if stripped.startswith(CLAUDE_INJECTED_PREFIXES):
                session.dropped["injected" if not stripped.startswith(("<local-command", "<bash-")) else "command_output"] += 1
                continue
            session.add_prompt(text, parse_time(record.get("timestamp")))
            session.last_was_assistant = False
    return session


def parse_codex(path: Path, roots: dict) -> Session:
    session = Session("codex", path, roots)
    fallback: list[tuple[str, _dt.datetime | None]] = []
    saw_event = False
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                session.parse_errors += 1
                continue
            if not isinstance(record, dict):
                continue
            kind = record.get("type")
            payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
            when = parse_time(record.get("timestamp"))
            if kind == "session_meta":
                session.id = str(payload.get("id") or session.id)
                session.cwd = session.cwd or (payload.get("cwd") if isinstance(payload.get("cwd"), str) else None)
                originator = str(payload.get("originator", "")) + " " + str(payload.get("source", ""))
                if "exec" in originator:
                    session.automated = True
            elif kind == "turn_context":
                session.cwd = session.cwd or (payload.get("cwd") if isinstance(payload.get("cwd"), str) else None)
            elif kind == "event_msg":
                event = payload.get("type")
                if event == "user_message" and isinstance(payload.get("message"), str):
                    saw_event = True
                    message = payload["message"]
                    if message.lstrip().startswith(CODEX_INJECTED_PREFIXES):
                        session.dropped["injected"] += 1
                        continue
                    for name in re.findall(r"(?<![\w$])\$([a-z0-9][a-z0-9-]{1,63})\b", message):
                        session.skills[name] += 1
                    for name in re.findall(r"(?:^|\s)/prompts:([A-Za-z0-9_-]+)", message):
                        session.slash[f"prompts:{name}"] += 1
                    session.add_prompt(message, when)
                    session.last_was_assistant = False
                elif event == "agent_message":
                    session.last_was_assistant = True
                elif event in {"task_started", "task_complete", "token_count", "turn_aborted", "agent_reasoning",
                               "exec_command_end", "exec_command_begin", "patch_apply_end", "mcp_tool_call_end"}:
                    pass
                else:
                    session.unknown[f"event_msg:{event}"] += 1
            elif kind == "response_item":
                item = payload.get("type")
                if item == "message" and payload.get("role") == "user":
                    text, _ = text_blocks(payload.get("content"))
                    fallback.append((text, when))
                elif item == "message" and payload.get("role") == "assistant":
                    session.last_was_assistant = True
                elif item in {"function_call", "local_shell_call", "custom_tool_call"}:
                    for name in skill_from_path(json.dumps(payload)):
                        session.skills[name] += 1
            elif kind not in {"compacted", "turn_context"}:
                session.unknown[str(kind)] += 1
    if not saw_event:
        for text, when in fallback:
            if text.lstrip().startswith(CODEX_INJECTED_PREFIXES):
                session.dropped["injected"] += 1
            else:
                session.add_prompt(text, when)
    return session


def parse_pi(path: Path, roots: dict) -> Session:
    session = Session("pi", path, roots)
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                session.parse_errors += 1
                continue
            if not isinstance(record, dict):
                continue
            kind = record.get("type")
            if kind == "session":
                session.id = str(record.get("id") or session.id)
                session.cwd = record.get("cwd") if isinstance(record.get("cwd"), str) else None
                continue
            if kind != "message":
                if kind not in {"model_change", "thinking_level_change", "usage", "compaction", "branch_summary",
                                "custom", "custom_message", "label", "context_edit", "session_info"}:
                    session.unknown[str(kind)] += 1
                continue
            message = record.get("message") if isinstance(record.get("message"), dict) else {}
            role = message.get("role")
            if role == "assistant":
                session.last_was_assistant = True
                for block in message.get("content") if isinstance(message.get("content"), list) else []:
                    if isinstance(block, dict) and block.get("type") == "toolCall":
                        for name in skill_from_path(json.dumps(block.get("arguments", {}))):
                            session.skills[name] += 1
                continue
            if role != "user":
                if role not in {"toolResult", "system", "custom", "bashExecution", "branchSummary", "compactionSummary"}:
                    session.unknown[f"role:{role}"] += 1
                continue
            text, _ = text_blocks(message.get("content"))
            for name in re.findall(r'<skill name="([^"]+)"', text):
                session.skills[name] += 1
            text = re.sub(r"<skill name=\"[^\"]+\"[^>]*>.*?</skill>", " ", text, flags=re.S).strip()
            session.add_prompt(text, parse_time(record.get("timestamp")) or parse_time(message.get("timestamp")))
            session.last_was_assistant = False
    return session


PARSERS = {"claude-code": parse_claude, "codex": parse_codex, "pi": parse_pi}


def session_files(harness: str, roots: dict) -> tuple[Path, list[Path], int]:
    """(root, candidate files, skipped subagent files) for one harness."""
    if harness == "claude-code":
        root = Path(roots["claude-code"]) / "projects"
        files = sorted(root.glob("*/*.jsonl")) if root.is_dir() else []
        subagent = [path for path in files if path.name.startswith("agent-")]
        nested = len(list(root.glob("*/*/subagents/*.jsonl"))) if root.is_dir() else 0
        return root, [path for path in files if not path.name.startswith("agent-")], len(subagent) + nested
    if harness == "codex":
        root = Path(roots["codex"]) / "sessions"
        return root, sorted(root.rglob("rollout-*.jsonl")) if root.is_dir() else [], 0
    agent = Path(roots["pi"])
    settings, _ = read_json(agent / "settings.json")
    configured = settings.get("sessionDir") if isinstance(settings, dict) else None
    root = Path(configured).expanduser() if isinstance(configured, str) and configured.startswith(("/", "~")) else agent / "sessions"
    return root, sorted(root.rglob("*.jsonl")) if root.is_dir() else [], 0


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------


def stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > 5 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def normalize(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\S*[/\\]\S*", " ", text)
    text = re.sub(r"\b[0-9a-f]{7,}\b|\b\d+\b", " ", text.lower())
    return text


def tokens(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for word in re.findall(r"[a-z][a-z0-9'-]+", normalize(text)):
        word = word.strip("'-")
        if len(word) < 3 or word in STOPWORDS:
            continue
        seen.setdefault(stem(word), None)
        if len(seen) >= MAX_TOKENS_PER_PROMPT:
            break
    return list(seen)


def lemma(word: str) -> str:
    for suffix, replacement in (("ing", ""), ("ing", "e"), ("ied", "y"), ("ed", ""), ("ed", "e"), ("es", ""), ("s", "")):
        if word.endswith(suffix) and word[: len(word) - len(suffix)] + replacement in ACTION_OF:
            return word[: len(word) - len(suffix)] + replacement
    return word


def action(text: str) -> str | None:
    """Intent group of a request's opening verb, after polite fillers; None when it opens otherwise."""
    for word in re.findall(r"[a-z']+", normalize(text)):
        if word in FILLERS:
            continue
        return ACTION_OF.get(lemma(word))
    return None


def jaccard(left: set, right: set) -> float:
    return len(left & right) / len(left | right) if left or right else 0.0


def cluster(prompts: list[dict], threshold: float) -> list[list[int]]:
    """Cohesive clusters over token sets, in time order.

    A prompt joins the cluster it matches best only when it is close to at least one member
    (similarity >= threshold) and to the cluster as a whole (mean similarity >= 60% of threshold),
    so unrelated prompts cannot chain through one bridging prompt. A request never joins a cluster
    whose opening verb belongs to a different action group.
    """
    sets = [set(item["tokens"]) for item in prompts]
    frequency = Counter(token for item in sets for token in item)
    common = {token for token, count in frequency.items() if count > max(20, len(prompts) // 5)}
    order = sorted(range(len(prompts)), key=lambda index: (prompts[index].get("when") or now()).timestamp())
    clusters: list[dict] = []
    index: dict[str, set[int]] = defaultdict(set)
    for position in order:
        item = sets[position]
        verb = prompts[position].get("action")
        candidates = set().union(*(index[token] for token in item - common)) if item - common else set()
        best, best_key = None, (0.0, 0.0)
        for cluster_id in candidates:
            entry = clusters[cluster_id]
            if verb and entry["action"] and verb != entry["action"]:
                continue
            members = entry["members"][-30:]
            scores = [jaccard(item, sets[member]) for member in members if len(item & sets[member]) >= 2]
            if not scores:
                continue
            key = (max(scores), sum(scores) / len(members))
            if key[0] >= threshold and key[1] >= threshold * 0.6 and key > best_key:
                best, best_key = cluster_id, key
        if best is None:
            clusters.append({"members": [], "action": verb, "verbs": Counter()})
            best = len(clusters) - 1
        entry = clusters[best]
        entry["members"].append(position)
        if verb:
            entry["verbs"][verb] += 1
            entry["action"] = entry["verbs"].most_common(1)[0][0]
        for token in item - common:
            index[token].add(best)
    return merge_fragments(clusters, sets, common, threshold)


def merge_fragments(clusters: list[dict], sets: list[set], common: set, threshold: float) -> list[list[int]]:
    """Join clusters that formed separately in time but match each other on average."""
    parent = list(range(len(clusters)))

    def find(item: int) -> int:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    vocab = [set().union(*(sets[member] for member in entry["members"])) - common for entry in clusters]
    index: dict[str, list[int]] = defaultdict(list)
    for cluster_id, words in enumerate(vocab):
        if len(clusters[cluster_id]["members"]) >= 2:
            for word in words:
                index[word].append(cluster_id)
    for left in range(len(clusters)):
        if len(clusters[left]["members"]) < 2:
            continue
        shared = Counter(other for word in vocab[left] for other in index[word] if other > left)
        for right, overlap in shared.items():
            if overlap < 2:
                continue
            if clusters[left]["action"] and clusters[right]["action"] and clusters[left]["action"] != clusters[right]["action"]:
                continue
            scores = [jaccard(sets[a], sets[b]) for a in clusters[left]["members"][:15] for b in clusters[right]["members"][:15]]
            if max(scores) >= threshold and sum(scores) / len(scores) >= threshold * 0.6:
                parent[find(left)] = find(right)
    merged: dict[int, list[int]] = defaultdict(list)
    for cluster_id, entry in enumerate(clusters):
        merged[find(cluster_id)].extend(entry["members"])
    return list(merged.values())


def installed_matches(terms: list[str], installed: list[dict]) -> list[dict]:
    wanted = set(terms)
    matches = []
    for item in installed:
        vocabulary = set(tokens(item["name"].replace("-", " ") + " " + re.split(r"(?i)\bdo not\b|\bdon't\b|\bNOT\b", item["description"])[0]))
        shared = wanted & vocabulary
        if len(shared) >= 2 and len(shared) / max(1, len(wanted)) >= 0.3:
            matches.append({"name": item["name"], "harness": item["harness"], "score": round(len(shared) / len(wanted), 2),
                            "shared": sorted(shared)})
    return sorted(matches, key=lambda match: -match["score"])[:3]


def summarize(groups: list[list[int]], prompts: list[dict], kind: str, *, min_sessions: int, min_count: int,
              installed: list[dict], sessions: dict[str, "Session"], roots: dict) -> list[dict]:
    clusters = []
    for group in groups:
        members = [prompts[index] for index in group]
        by_session = {member["session"] for member in members}
        if len(by_session) < min_sessions or len(members) < min_count:
            continue
        counts = Counter(token for member in members for token in member["tokens"])
        terms = [token for token, _ in counts.most_common(15)]
        core = [token for token, count in counts.most_common() if count * 2 >= len(members)]
        sample_sets = [set(member["tokens"]) for member in members[:20]]
        pairs = [jaccard(a, b) for i, a in enumerate(sample_sets) for b in sample_sets[i + 1:]]
        dates = sorted(member["when"] for member in members if member["when"])
        newest = sorted(members, key=lambda item: -(item["when"] or now()).timestamp())
        first_per_session, seen_sessions = [], set()
        for member in newest:
            if member["session"] not in seen_sessions:
                seen_sessions.add(member["session"])
                first_per_session.append(member)
        chosen = {id(member) for member in first_per_session}
        ordered = first_per_session + [member for member in newest if id(member) not in chosen]
        samples = []
        for member in ordered:
            if len(samples) >= MAX_SAMPLES:
                break
            text = redact(re.sub(r"\s+", " ", member["text"]).strip())
            if any(sample["text"].rstrip("…") == text[:MAX_SAMPLE_CHARS] for sample in samples):
                continue
            samples.append({"text": text[:MAX_SAMPLE_CHARS] + ("…" if len(text) > MAX_SAMPLE_CHARS else ""),
                            "session": member["session"], "harness": member["harness"],
                            "date": member["when"].date().isoformat() if member["when"] else None})
        token_sets = [set(member["tokens"]) for member in members]
        verbatim = len(token_sets) > 1 and min(jaccard(token_sets[0], other) for other in token_sets[1:]) >= 0.85
        co_invoked = Counter()
        for session_id in by_session:
            co_invoked.update(sessions[session_id].skills)
        projects = Counter(member["project"] for member in members if member["project"])
        clusters.append({
            "kind": kind, "prompts": len(members), "sessions": len(by_session),
            "harnesses": sorted({member["harness"] for member in members}),
            "projects": [project for project, _ in projects.most_common(5)],
            "first": dates[0].date().isoformat() if dates else None,
            "last": dates[-1].date().isoformat() if dates else None,
            "terms": terms[:8], "core_terms": core[:10], "verbatim": verbatim,
            "cohesion": round(sum(pairs) / len(pairs), 2) if pairs else 1.0,
            "rank_score": round(len(by_session) * min(1.0, len(core) / 4), 2),
            "median_words": sorted(len(member["text"].split()) for member in members)[len(members) // 2],
            "samples": samples,
            "installed_matches": installed_matches(terms, installed),
            "skills_used_in_these_sessions": [name for name, _ in co_invoked.most_common(5)],
        })
    return clusters


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------


def installed_skills(roots: dict, projects: list[Path], harnesses: list[str]) -> list[dict]:
    rows, seen = [], set()
    for harness in harnesses:
        for project in [None, *projects]:
            found = discover(harness, roots, project)
            for item in found["skills"] + found["commands"]:
                key = (harness, item["name"], item.get("origin"))
                if key in seen:
                    continue
                seen.add(key)
                rows.append({"harness": harness, "name": item["name"], "kind": item["kind"],
                             "scope": item["scope"], "origin": item.get("origin"),
                             "model_invoked": item["model_invoked"],
                             "description": re.sub(r"\s+", " ", redact(item["description"]))[:240]})
    return rows


def scan(args: argparse.Namespace) -> dict:
    started = time.monotonic()
    bytes_read = 0
    roots = resolve_roots(Path(args.home) if args.home else None)
    selected = SUPPORTED if args.harness in (None, "auto", "all") else tuple(
        item.strip() for item in args.harness.split(",") if item.strip())
    for item in selected:
        if item not in SUPPORTED:
            reason = UNSUPPORTED.get(item, "unknown harness")
            raise SystemExit(f"unsupported harness {item}: {reason}; choose from {', '.join(SUPPORTED)}")
    cutoff = now() - _dt.timedelta(days=args.days) if args.days > 0 else None
    project_filter = Path(args.project).resolve() if args.project else None
    coverage: dict = {"harnesses": {}, "dropped": Counter(), "unsupported": UNSUPPORTED,
                      "window_days": args.days or None, "project": display(project_filter, roots) if project_filter else None}
    sessions: dict[str, Session] = {}
    prompts: list[dict] = []
    slash, skills_used = Counter(), Counter()
    for harness in selected:
        root, files, subagents = session_files(harness, roots)
        stats = {"root": display(root, roots), "files": len(files), "sessions": 0, "automated": 0,
                 "subagent_files": subagents, "outside_window": 0, "other_projects": 0, "parse_errors": 0,
                 "unknown_records": Counter()}
        if cutoff:
            recent = []
            for path in files:
                try:
                    modified = _dt.datetime.fromtimestamp(path.stat().st_mtime, _dt.timezone.utc)
                except OSError:
                    continue
                if modified >= cutoff:
                    recent.append((modified, path))
                else:
                    stats["outside_window"] += 1
        else:
            recent = [(_dt.datetime.fromtimestamp(path.stat().st_mtime, _dt.timezone.utc), path) for path in files]
        recent.sort(reverse=True)
        if len(recent) > args.max_sessions:
            stats["over_session_cap"] = len(recent) - args.max_sessions
        for _, path in recent[: args.max_sessions]:
            try:
                bytes_read += path.stat().st_size
                session = PARSERS[harness](path, roots)
            except OSError:
                stats["parse_errors"] += 1
                continue
            stats["parse_errors"] += session.parse_errors
            stats["unknown_records"].update(session.unknown)
            coverage["dropped"].update(session.dropped)
            cwd = session.cwd or ""
            if session.automated or cwd.startswith(TEMP_PREFIXES):
                if not args.include_automated:
                    stats["automated"] += 1
                    coverage["dropped"]["automated_session"] += len(session.prompts)
                    continue
            if project_filter and not (cwd == str(project_filter) or cwd.startswith(str(project_filter) + os.sep)):
                stats["other_projects"] += 1
                continue
            stats["sessions"] += 1
            key = f"{harness}:{session.id}"
            sessions[key] = session
            slash.update(session.slash)
            skills_used.update(session.skills)
            kept: list[dict] = []
            for prompt in session.prompts:
                if cutoff and prompt["when"] and prompt["when"] < cutoff:
                    continue
                words = tokens(redact(prompt["text"]))
                if len(words) < 2:
                    coverage["dropped"]["too_short"] += 1
                    continue
                if any(jaccard(set(words), set(other["tokens"])) >= 0.85 for other in kept):
                    coverage["dropped"]["repeat_in_session"] += 1
                    continue
                kept.append({**prompt, "tokens": words, "session": key, "harness": harness,
                             "action": action(prompt["text"]) if prompt["kind"] == "request" else None,
                             "project": display(Path(cwd), roots) if cwd else None})
            prompts.extend(kept)
        stats["unknown_records"] = dict(stats["unknown_records"].most_common(10))
        coverage["harnesses"][harness] = stats
    prompts.sort(key=lambda item: item["when"] or now(), reverse=True)
    if len(prompts) > MAX_PROMPTS:
        coverage["dropped"]["over_prompt_cap"] = len(prompts) - MAX_PROMPTS
        prompts = prompts[:MAX_PROMPTS]
    coverage["prompts_kept"] = len(prompts)
    coverage["dropped"] = dict(coverage["dropped"])
    cwd_counts = Counter(session.cwd for session in sessions.values() if session.cwd)
    project_dirs = [Path(cwd) for cwd, _ in cwd_counts.most_common(10) if Path(cwd).is_dir()]
    installed = installed_skills(roots, project_dirs, list(selected))
    requests = [item for item in prompts if item["kind"] == "request"]
    corrections = [item for item in prompts if item["kind"] == "correction"]
    found = summarize(cluster(requests, args.threshold), requests, "request", min_sessions=args.min_sessions,
                      min_count=args.min_count, installed=installed, sessions=sessions, roots=roots)
    found += summarize(cluster(corrections, args.threshold), corrections, "correction",
                       min_sessions=args.min_sessions, min_count=max(2, args.min_count - 1),
                       installed=installed, sessions=sessions, roots=roots)
    # A repeated request re-states several specifics; a cluster held together by one or two shared
    # words is usually a topic the user works on, not a request. Rank by sessions weighted by core size.
    found.sort(key=lambda item: (-item["rank_score"], -item["sessions"], -item["prompts"]))
    # Repeated requests restate the same specifics; topics are subjects the user keeps returning to
    # with different asks. Topics get their own small budget so they never crowd out requests.
    repeats = [item for item in found if (len(item["core_terms"]) >= 4 and item["cohesion"] >= 0.45)
               or item["cohesion"] >= 0.6]
    topics = [item for item in found if item not in repeats]
    for index, item in enumerate(repeats[:MAX_CLUSTERS], 1):
        item["id"] = f"C{index}"
    for index, item in enumerate(topics[:MAX_TOPICS], 1):
        item["id"] = f"T{index}"
        item["samples"] = item["samples"][:TOPIC_SAMPLES]
        for key in ("installed_matches", "skills_used_in_these_sessions", "verbatim", "median_words"):
            item.pop(key, None)
    retention = None
    settings, _ = read_json(Path(roots["claude-code"]) / "settings.json")
    if "claude-code" in selected:
        days = settings.get("cleanupPeriodDays") if isinstance(settings, dict) else None
        retention = f"Claude Code deletes transcripts after {days if isinstance(days, int) else 30} days (cleanupPeriodDays)"
    coverage["retention"] = retention
    coverage["sessions_kept"] = len(sessions)
    coverage["bytes_read"] = bytes_read
    coverage["elapsed_seconds"] = round(time.monotonic() - started, 2)
    return {
        "schema": SCHEMA,
        "generated_at": now().replace(microsecond=0).isoformat(),
        "thresholds": {"min_sessions": args.min_sessions, "min_count": args.min_count, "similarity": args.threshold},
        "coverage": coverage,
        "usage": {
            "slash_commands": [{"name": name, "count": count} for name, count in slash.most_common(20)],
            "skills_invoked": [{"name": name, "count": count} for name, count in skills_used.most_common(20)],
        },
        "installed": {harness: sorted({item["name"] for item in installed if item["harness"] == harness})
                      for harness in selected},
        "clusters": repeats[:MAX_CLUSTERS],
        "clusters_omitted": max(0, len(repeats) - MAX_CLUSTERS),
        "topics": topics[:MAX_TOPICS],
        "topics_omitted": max(0, len(topics) - MAX_TOPICS),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("scan", help="cluster recurring requests across session history")
    run.add_argument("--home", help="read a copied home directory instead of the current user's")
    run.add_argument("--harness", default="auto", help="comma-separated: claude-code, codex, pi (default: all)")
    run.add_argument("--days", type=int, default=30, help="look back this many days; 0 for everything (default 30)")
    run.add_argument("--project", help="only sessions whose working directory is inside this path")
    run.add_argument("--max-sessions", type=int, default=400, help="newest session files per harness (default 400)")
    run.add_argument("--min-sessions", type=int, default=2, help="sessions a pattern must span (default 2)")
    run.add_argument("--min-count", type=int, default=3, help="prompts a pattern must contain (default 3)")
    run.add_argument("--threshold", type=float, default=0.45, help="token-set similarity to link prompts (default 0.45)")
    run.add_argument("--include-automated", action="store_true", help="keep headless and temp-directory sessions")
    args = parser.parse_args(argv)
    if args.min_sessions < 1 or args.min_count < 1 or not 0 < args.threshold <= 1:
        raise SystemExit("thresholds must be positive and similarity must be in (0, 1]")
    json.dump(scan(args), sys.stdout, indent=1, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
