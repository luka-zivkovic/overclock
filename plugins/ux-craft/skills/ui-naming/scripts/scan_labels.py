#!/usr/bin/env python3
"""Read-only scanner for interface-label drift.

Walks a project, extracts user-facing strings from JSX/TSX, Vue, Svelte, HTML, and i18n
JSON/YAML files, and reports synonym clusters, generic labels, mixed casing, banned words in
error-like strings, and trailing punctuation on labels. It never writes to the tree and makes no
network requests. Standard library only.

Usage:
    scan_labels.py PATH [--format md|json] [--exclude GLOB ...] [--max-file-kb N]
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass

MARKUP_EXT = {".jsx", ".tsx", ".js", ".ts", ".vue", ".svelte", ".html", ".htm", ".astro", ".mdx"}
I18N_EXT = {".json", ".yaml", ".yml"}
DEFAULT_EXCLUDES = [
    "node_modules", "dist", "build", "out", ".next", ".nuxt", ".svelte-kit", ".git", "vendor",
    "coverage", "target", "__pycache__", ".venv", "venv", "*.min.*", "*.test.*", "*.spec.*",
    "*.stories.*", "*.d.ts", "package.json", "package-lock.json", "tsconfig*.json",
    "pnpm-lock.yaml", "yarn.lock", "*.config.*", ".eslintrc*", "*.snap",
]
LABEL_ATTRS = {
    "label", "title", "placeholder", "aria-label", "arialabel", "alt", "tooltip", "helpertext",
    "helptext", "description", "buttontext", "confirmtext", "canceltext", "submittext",
    "emptytext", "heading", "subtitle", "hint", "errormessage", "errortext", "message",
}
BUTTON_TAGS = {
    "button", "a", "menuitem", "dropdownitem", "tab", "link", "iconbutton", "menuitemoption",
    "listitembutton", "chip", "fab", "navlink", "actionbutton",
}
BUTTON_KEY_HINT = re.compile(r"(button|btn|cta|action|submit|confirm|cancel|primary|secondary)", re.I)
ERROR_KEY_HINT = re.compile(r"(error|invalid|fail|validation|warning|denied|forbidden)", re.I)
ERROR_TAG_HINT = re.compile(r"(error|invalid|alert|danger|warning)", re.I)

GENERIC_LABELS = {
    "ok", "okay", "yes", "no", "submit", "click here", "here", "learn more", "read more", "more",
    "go", "done", "next", "continue", "confirm", "proceed",
}
# Generic only when committing something; Next/Continue are fine on wizard steps, so they are
# reported separately as "review".
REVIEW_ONLY = {"next", "continue", "done", "confirm", "proceed"}

VERB_CLUSTERS = {
    "delete-remove": ["delete", "remove", "trash", "discard", "erase", "destroy"],
    "save-apply": ["save", "apply", "update", "submit", "store", "persist"],
    "create-add": ["create", "add", "new"],
    "edit-modify": ["edit", "modify", "change", "alter"],
    "cancel-close": ["cancel", "close", "dismiss", "abort"],
    "ok-acknowledge": ["ok", "okay", "got it", "understood", "fine"],
    "send-submit": ["send", "submit", "dispatch"],
    "sign-in": ["sign in", "log in", "login", "signin", "logon"],
    "sign-out": ["sign out", "log out", "logout", "signout"],
    "sign-up": ["sign up", "register", "create account", "join", "signup"],
    "search-find": ["search", "find", "look up", "lookup"],
    "enable-disable": ["enable", "turn on", "activate"],
    "disable": ["disable", "turn off", "deactivate"],
    "retry-refresh": ["retry", "try again", "refresh", "reload"],
    "download-export": ["download", "export"],
    "upload-import": ["upload", "import"],
}
NOUN_CLUSTERS = {
    "settings": ["settings", "preferences", "options", "configuration", "config"],
    "workspace": ["workspace", "team", "organization", "organisation", "org", "company", "account"],
    "member-user": ["member", "user", "person", "people", "collaborator", "teammate"],
    "project": ["project", "board", "space", "folder"],
    "notification": ["notification", "alert", "message"],
    "help": ["help", "support", "docs", "documentation", "faq"],
    "home": ["home", "dashboard", "overview", "start"],
    "profile": ["profile", "my account", "account settings"],
    "cancel-noun": ["subscription", "plan", "membership"],
}
BANNED_ERROR_WORDS = [
    "please", "sorry", "oops", "whoops", "invalid", "illegal", "forbidden", "error occurred",
    "an error has occurred", "something went wrong", "unexpected error", "fatal", "exception",
    "null", "undefined", "failed to",
]

CODE_LIKE = re.compile(r"[{}<>$`|\\]|=>|://|^\s*[\W_]+\s*$|^[A-Z0-9_]{3,}$|^[a-z]+[A-Z]\w*$|^[a-z0-9_.-]+$")
TAG_TEXT = re.compile(r"<\s*([A-Za-z][\w.-]*)([^<>]*)>\s*([^<>{}]+?)\s*<\s*/\s*\1\s*>", re.S)
ATTR_STRING = re.compile(r"\b([A-Za-z-]+)\s*=\s*([\"'])((?:(?!\2).){2,200})\2")
JSX_ATTR_TEMPLATE = re.compile(r"\b([A-Za-z-]+)\s*=\s*\{\s*([\"'])((?:(?!\2).){2,200})\2\s*\}")
JSON_STRING_LEAF = re.compile(r"\"((?:[^\"\\]|\\.)*)\"\s*:\s*\"((?:[^\"\\]|\\.)*)\"")
YAML_LEAF = re.compile(r"^\s*([\w.-]+)\s*:\s*[\"']?([^\"'#\n]{2,200}?)[\"']?\s*(?:#.*)?$")


@dataclass
class UIString:
    text: str
    file: str
    line: int
    kind: str      # tag | attr | i18n
    context: str   # tag name, attribute name, or i18n key
    button_like: bool
    error_like: bool


def is_excluded(path: str, patterns: list[str]) -> bool:
    parts = path.replace("\\", "/").split("/")
    return any(fnmatch.fnmatch(part, pat) for part in parts for pat in patterns)


def clean(text: str) -> str | None:
    text = re.sub(r"\s+", " ", text).strip().strip(" ")
    if len(text) < 2 or len(text) > 200:
        return None
    if CODE_LIKE.search(text):
        return None
    if not re.search(r"[A-Za-z]", text):
        return None
    words = text.split()
    if len(words) == 1 and (text.islower() and len(text) < 3):
        return None
    return text


def line_of(source: str, index: int) -> int:
    return source.count("\n", 0, index) + 1


def scan_markup(path: str, rel: str, source: str, out: list[UIString]) -> None:
    for m in TAG_TEXT.finditer(source):
        tag, attrs, text = m.group(1), m.group(2), m.group(3)
        cleaned = clean(text)
        if not cleaned:
            continue
        tag_l = tag.lower()
        button_like = (
            tag_l in BUTTON_TAGS
            or tag_l.endswith("button")
            or 'role="button"' in attrs
            or "role='button'" in attrs
        )
        error_like = bool(ERROR_TAG_HINT.search(tag)) or bool(ERROR_TAG_HINT.search(attrs))
        out.append(UIString(cleaned, rel, line_of(source, m.start(3)), "tag", tag, button_like, error_like))
    for regex in (ATTR_STRING, JSX_ATTR_TEMPLATE):
        for m in regex.finditer(source):
            attr, value = m.group(1), m.group(3)
            attr_key = attr.lower().replace("_", "").replace("-", "")
            if attr_key not in LABEL_ATTRS and attr.lower() not in LABEL_ATTRS:
                continue
            cleaned = clean(value)
            if not cleaned:
                continue
            button_like = bool(BUTTON_KEY_HINT.search(attr))
            error_like = bool(ERROR_KEY_HINT.search(attr))
            out.append(UIString(cleaned, rel, line_of(source, m.start(3)), "attr", attr, button_like, error_like))


def scan_i18n(path: str, rel: str, source: str, out: list[UIString]) -> None:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        for m in JSON_STRING_LEAF.finditer(source):
            key, value = m.group(1), m.group(2)
            cleaned = clean(value.encode().decode("unicode_escape", errors="ignore"))
            if not cleaned:
                continue
            out.append(UIString(cleaned, rel, line_of(source, m.start(2)), "i18n", key,
                                bool(BUTTON_KEY_HINT.search(key)), bool(ERROR_KEY_HINT.search(key))))
    else:
        for i, raw in enumerate(source.splitlines(), 1):
            m = YAML_LEAF.match(raw)
            if not m:
                continue
            key, value = m.group(1), m.group(2)
            cleaned = clean(value)
            if not cleaned or value.strip() in {"|", ">"}:
                continue
            out.append(UIString(cleaned, rel, i, "i18n", key,
                                bool(BUTTON_KEY_HINT.search(key)), bool(ERROR_KEY_HINT.search(key))))


def walk(root: str, excludes: list[str], max_bytes: int) -> list[UIString]:
    found: list[UIString] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not is_excluded(os.path.join(dirpath, d), excludes)
                       and not os.path.islink(os.path.join(dirpath, d))]
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if os.path.islink(full) or is_excluded(rel, excludes):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in MARKUP_EXT and ext not in I18N_EXT:
                continue
            try:
                if os.path.getsize(full) > max_bytes:
                    continue
                with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                    source = fh.read()
            except OSError:
                continue
            if ext in MARKUP_EXT:
                scan_markup(full, rel, source, found)
            else:
                scan_i18n(full, rel, source, found)
    return found


def casing_of(text: str) -> str:
    words = [w for w in re.findall(r"[A-Za-z][\w'’-]*", text)]
    if len(words) < 2:
        return "single"
    long_words = [w for w in words[1:] if len(w) > 3]
    if not long_words:
        return "single"
    caps = sum(1 for w in long_words if w[0].isupper())
    if caps == len(long_words):
        return "title"
    if caps == 0 and words[0][0].isupper():
        return "sentence"
    if caps == 0 and words[0][0].islower():
        return "lower"
    return "mixed"


def short(text: str, n: int = 4) -> bool:
    return len(text.split()) <= n


def word_in(term: str, text: str) -> bool:
    return re.search(r"(?<![\w'])" + re.escape(term) + r"(?![\w'])", text, re.I) is not None


def analyze(strings: list[UIString]) -> dict:
    labels = [s for s in strings if s.button_like or (s.kind == "tag" and short(s.text, 3))]
    generic, review = [], []
    for s in labels:
        key = s.text.lower().rstrip(".!…")
        if key in GENERIC_LABELS:
            (review if key in REVIEW_ONLY else generic).append(s)

    verb_clusters: dict[str, dict[str, list[UIString]]] = defaultdict(lambda: defaultdict(list))
    for s in strings:
        if not short(s.text, 4):
            continue
        low = s.text.lower()
        for cluster, terms in VERB_CLUSTERS.items():
            for term in terms:
                if low == term or low.startswith(term + " ") or low.endswith(" " + term) and len(low.split()) <= 2:
                    verb_clusters[cluster][term].append(s)
                    break
    noun_clusters: dict[str, dict[str, list[UIString]]] = defaultdict(lambda: defaultdict(list))
    for s in strings:
        if not short(s.text, 6):
            continue
        for cluster, terms in NOUN_CLUSTERS.items():
            for term in terms:
                if word_in(term, s.text) or word_in(term + "s", s.text):
                    noun_clusters[cluster][term].append(s)
                    break
    drift_verbs = {c: v for c, v in verb_clusters.items() if len(v) >= 2}
    drift_nouns = {c: v for c, v in noun_clusters.items() if len(v) >= 2}

    casing = defaultdict(list)
    for s in labels:
        c = casing_of(s.text)
        if c in {"title", "sentence", "lower", "mixed"}:
            casing[c].append(s)

    error_strings = [s for s in strings if s.error_like or any(word_in(w, s.text) for w in ("try again", "must", "can't", "cannot", "couldn't"))]
    banned = []
    for s in error_strings:
        hits = [w for w in BANNED_ERROR_WORDS if word_in(w, s.text)]
        if hits:
            banned.append((s, hits))

    trailing = [s for s in labels if short(s.text, 4) and s.text.endswith(".")]

    return {
        "inventory": strings,
        "labels": labels,
        "generic": generic,
        "review": review,
        "drift_verbs": drift_verbs,
        "drift_nouns": drift_nouns,
        "casing": casing,
        "banned": banned,
        "trailing": trailing,
    }


def loc(s: UIString) -> str:
    return f"{s.file}:{s.line}"


def render_md(root: str, r: dict) -> str:
    lines = [f"# Label scan: {root}", ""]
    lines.append(f"Strings found: {len(r['inventory'])} (label-like: {len(r['labels'])}). Read-only report; "
                 "clusters are evidence, not verdicts.")
    lines.append("")
    lines.append("## Generic labels")
    if not r["generic"]:
        lines.append("None.")
    for s in r["generic"]:
        lines.append(f"- `{s.text}` at {loc(s)} ({s.kind}: {s.context}) — replace with verb + object")
    if r["review"]:
        lines.append("")
        lines.append("Review (fine on wizard steps, wrong on committing actions):")
        for s in r["review"]:
            lines.append(f"- `{s.text}` at {loc(s)} ({s.kind}: {s.context})")
    lines.append("")
    lines.append("## Verb clusters (same action, different words?)")
    if not r["drift_verbs"]:
        lines.append("None.")
    for cluster, terms in r["drift_verbs"].items():
        lines.append(f"- **{cluster}**: " + ", ".join(f"`{t}` ×{len(v)}" for t, v in terms.items()))
        for t, v in terms.items():
            for s in v[:5]:
                lines.append(f"  - `{s.text}` at {loc(s)}")
            if len(v) > 5:
                lines.append(f"  - … {len(v) - 5} more `{t}`")
    lines.append("")
    lines.append("## Noun clusters (same concept, different words?)")
    if not r["drift_nouns"]:
        lines.append("None.")
    for cluster, terms in r["drift_nouns"].items():
        lines.append(f"- **{cluster}**: " + ", ".join(f"`{t}` ×{len(v)}" for t, v in terms.items()))
        for t, v in terms.items():
            for s in v[:3]:
                lines.append(f"  - `{s.text}` at {loc(s)}")
            if len(v) > 3:
                lines.append(f"  - … {len(v) - 3} more `{t}`")
    lines.append("")
    lines.append("## Casing among label-like strings")
    total = sum(len(v) for v in r["casing"].values())
    if total == 0:
        lines.append("No multi-word labels found.")
    else:
        for c in ("sentence", "title", "lower", "mixed"):
            n = len(r["casing"].get(c, []))
            if n:
                lines.append(f"- {c}: {n} ({100 * n // total}%)")
        majority = max(r["casing"], key=lambda k: len(r["casing"][k]))
        minority = [s for c, v in r["casing"].items() if c != majority for s in v]
        if minority:
            lines.append(f"- Majority is **{majority}**. Minority examples to review:")
            for s in minority[:15]:
                lines.append(f"  - `{s.text}` at {loc(s)} ({casing_of(s.text)})")
            if len(minority) > 15:
                lines.append(f"  - … {len(minority) - 15} more")
    lines.append("")
    lines.append("## Banned words in error-like strings")
    if not r["banned"]:
        lines.append("None.")
    for s, hits in r["banned"]:
        lines.append(f"- `{s.text}` at {loc(s)} — {', '.join(hits)}")
    lines.append("")
    lines.append("## Trailing period on short labels")
    if not r["trailing"]:
        lines.append("None.")
    for s in r["trailing"]:
        lines.append(f"- `{s.text}` at {loc(s)}")
    lines.append("")
    return "\n".join(lines)


def render_json(root: str, r: dict) -> str:
    def ser(items):
        return [asdict(s) for s in items]
    payload = {
        "root": root,
        "counts": {"strings": len(r["inventory"]), "labels": len(r["labels"])},
        "generic": ser(r["generic"]),
        "review": ser(r["review"]),
        "drift_verbs": {c: {t: ser(v) for t, v in terms.items()} for c, terms in r["drift_verbs"].items()},
        "drift_nouns": {c: {t: ser(v) for t, v in terms.items()} for c, terms in r["drift_nouns"].items()},
        "casing": {c: ser(v) for c, v in r["casing"].items()},
        "banned": [{"string": asdict(s), "words": hits} for s, hits in r["banned"]],
        "trailing": ser(r["trailing"]),
        "inventory": ser(r["inventory"]),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="project directory to scan (read-only)")
    parser.add_argument("--format", choices=("md", "json"), default="md")
    parser.add_argument("--exclude", action="append", default=[], help="extra glob to exclude (repeatable)")
    parser.add_argument("--max-file-kb", type=int, default=512)
    args = parser.parse_args(argv)

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    strings = walk(root, DEFAULT_EXCLUDES + args.exclude, args.max_file_kb * 1024)
    report = analyze(strings)
    print(render_md(root, report) if args.format == "md" else render_json(root, report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
