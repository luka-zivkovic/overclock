#!/usr/bin/env python3
"""Read-only scanner for interface-label drift, tuned for React + shadcn/ui apps.

Walks a project, extracts user-facing strings, and reports:

- terms the project's glossaries reject: UX.md's "Rejected synonyms" column, the "Aliases:"
  lines of a CONCEPTS.md kept by project-vocabulary, and the "_Avoid_:" lines of a CONTEXT.md;
- generic labels (OK, Submit, Click here);
- filler copy that should not ship (lorem ipsum, "text goes here", TODO and FIXME markers);
- verb and noun synonym clusters;
- casing against the recorded policy;
- banned words in error-like strings, exclamation marks, and trailing periods on labels;
- the navigation labels, for comparing nav, breadcrumb, and page title.

JSX/TSX is read with a brace-aware scanner, so it sees text that a plain regex misses:

- labels inside handlers such as onClick={() => save()};
- labels next to icon children such as <Plus /> Add;
- both branches of a ternary label;
- object-literal nav configs;
- sonner toasts and zod or react-hook-form messages.

shadcn components are classified by role: action, link, nav, title, description, field, error,
status, or option. Vue, Svelte, HTML, and i18n JSON/YAML use lighter extractors. The scanner never
writes to the tree and makes no network requests. Standard library only.

Usage:
    scan_labels.py PATH [--format md|json] [--ux UX.md] [--prop NAME ...]
                        [--term CANONICAL=REJECTED,REJECTED ...] [--exclude GLOB ...]
                        [--max-file-kb N]
"""
from __future__ import annotations

import argparse
import fnmatch
import html
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

JSX_EXT = {".jsx", ".tsx", ".js", ".mjs"}
SCRIPT_EXT = {".ts", ".mts", ".cts"} | JSX_EXT
MARKUP_EXT = {".vue", ".svelte", ".html", ".htm", ".astro", ".mdx"}
I18N_EXT = {".json", ".yaml", ".yml"}
DEFAULT_EXCLUDES = [
    "node_modules", "dist", "build", "out", ".next", ".nuxt", ".svelte-kit", ".git", "vendor",
    "coverage", "target", "__pycache__", ".venv", "venv", "*.min.*", "*.test.*", "*.spec.*",
    "*.stories.*", "*.d.ts", "package.json", "package-lock.json", "tsconfig*.json",
    "pnpm-lock.yaml", "yarn.lock", "*.config.*", ".eslintrc*", "*.snap", "components.json",
]

# ---------------------------------------------------------------------------
# Roles. Explicit shadcn/Radix and HTML names first, then suffix heuristics.

ACTION_TAGS = {
    "button", "Button", "DropdownMenuItem", "DropdownMenuCheckboxItem", "DropdownMenuRadioItem",
    "DropdownMenuSubTrigger", "ContextMenuItem", "ContextMenuCheckboxItem", "MenubarItem",
    "MenubarTrigger", "CommandItem", "TabsTrigger", "ToggleGroupItem", "Toggle",
    "AlertDialogAction", "AlertDialogCancel", "DialogClose", "SheetClose", "DrawerClose",
    "AccordionTrigger", "CollapsibleTrigger", "PaginationPrevious", "PaginationNext",
    "PaginationLink", "CarouselPrevious", "CarouselNext", "InputGroupButton",
}
LINK_TAGS = {"a", "Link", "NavLink"}
NAV_TAGS = {
    "SidebarMenuButton", "SidebarMenuSubButton", "SidebarGroupLabel", "NavigationMenuLink",
    "NavigationMenuTrigger", "BreadcrumbLink", "BreadcrumbPage",
}
TITLE_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6", "title", "CardTitle", "DialogTitle", "SheetTitle",
    "DrawerTitle", "AlertDialogTitle", "AlertTitle", "EmptyTitle", "ItemTitle", "FieldTitle",
}
DESCRIPTION_TAGS = {
    "CardDescription", "DialogDescription", "SheetDescription", "DrawerDescription",
    "AlertDialogDescription", "AlertDescription", "EmptyDescription", "FormDescription",
    "FieldDescription", "ItemDescription",
}
FIELD_TAGS = {"label", "Label", "FormLabel", "FieldLabel", "FieldLegend", "legend"}
ERROR_TAGS = {"FormMessage", "FieldError"}
OPTION_TAGS = {"option", "SelectItem"}
SKIP_TEXT_TAGS = {"code", "pre", "kbd", "samp", "script", "style", "svg", "path", "Kbd"}
ACTIONABLE_ROLES = {"action", "link", "nav", "option"}
LABEL_ROLES = ACTIONABLE_ROLES | {"title", "field"}

# Attributes and props that carry interface text. --prop and UX.md "Label props" extend this.
LABEL_ATTRS = {
    "label", "title", "placeholder", "aria-label", "alt", "tooltip", "description", "heading",
    "subtitle", "hint", "helperText", "helpText", "caption", "message", "errorMessage",
    "errorText", "emptyText", "emptyMessage", "confirmText", "confirmLabel", "cancelText",
    "cancelLabel", "actionLabel", "submitLabel", "submitText", "buttonText", "buttonLabel",
    "loadingText", "successMessage",
}
ATTR_ROLE = {
    "placeholder": "field", "description": "description", "helperText": "description",
    "helpText": "description", "hint": "description", "heading": "title", "subtitle": "description",
    "message": "error", "errorMessage": "error", "errorText": "error", "successMessage": "status",
    "loadingText": "status", "confirmText": "action", "confirmLabel": "action",
    "cancelText": "action", "cancelLabel": "action", "actionLabel": "action",
    "submitLabel": "action", "submitText": "action", "buttonText": "action",
    "buttonLabel": "action",
}
# Object-literal keys that carry interface text (nav configs, table columns, toasts, forms).
OBJECT_KEYS = LABEL_ATTRS | {
    "cta", "secondaryCta", "required", "required_error", "invalid_type_error", "loading",
    "success", "error",
}
OBJECT_KEY_ROLE = {
    **ATTR_ROLE, "cta": "action", "secondaryCta": "action", "required": "error",
    "required_error": "error", "invalid_type_error": "error", "loading": "status",
    "success": "status", "error": "error",
}
# "loading"/"success"/"error" are only read inside toast.promise(...) option objects.
TOAST_PROMISE_KEYS = {"loading", "success", "error"}
ZOD_METHODS = (
    "min", "max", "length", "email", "url", "uuid", "cuid", "cuid2", "regex", "nonempty",
    "startsWith", "endsWith", "includes", "refine", "superRefine", "int", "positive",
    "negative", "nonnegative", "nonpositive", "gt", "gte", "lt", "lte", "multipleOf",
    "datetime", "date", "time", "ip", "trim",
)

GENERIC_LABELS = {
    "ok", "okay", "yes", "no", "submit", "click here", "here", "learn more", "read more", "more",
    "go", "done", "next", "continue", "confirm", "proceed",
}
# Generic only when committing something; Next/Continue are fine on wizard steps.
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
    "home": ["home", "dashboard", "overview"],
    "profile": ["profile", "my account", "account settings"],
    "cancel-noun": ["subscription", "plan", "membership"],
}
BANNED_ERROR_WORDS = [
    "please", "sorry", "oops", "whoops", "invalid", "illegal", "forbidden", "error occurred",
    "an error has occurred", "something went wrong", "unexpected error", "fatal", "exception",
    "null", "undefined", "failed to",
]
# Copy that is a stand-in, not a decision. TBD is left out: "Date: TBD" is often deliberate.
FILLER_RE = re.compile(r"\blorem ipsum\b|\bdolor sit amet\b|\b(?:dummy|filler) (?:text|copy|content)\b", re.I)
# "Title goes here" is filler in shipped copy but a normal hint inside an input placeholder.
STUB_RE = re.compile(r"\b(?:text|copy|content|title|headline|description) goes here\b"
                     r"|\byour (?:text|copy|content|title|headline) here\b", re.I)
MARKER_RE = re.compile(r"(?<![\w-])(?:TODO|FIXME)(?![\w-])")

PLACEHOLDER = "‹x›"
CODE_LIKE = re.compile(
    r"[{}<>$`|\\]|=>|://|^\s*[\W_]+\s*$|^[A-Z0-9_]{3,}$|^[a-z]+[A-Z]\w*$|^[a-z0-9_.-]+$"
)
CLASS_TOKEN = re.compile(r"^[a-z0-9:_/\[\]().#%!-]+$")
TAG_NAME = re.compile(r"[A-Za-z_$][\w$.:-]*")
ATTR_NAME = re.compile(r"[A-Za-z_$][\w$:.-]*")
JSX_PREFIX_WORDS = {"return", "yield", "case", "default", "await", "in", "of", "typeof", "else", "do"}

# Regex extractors for non-JSX markup (Vue, Svelte, HTML, MDX, Astro).
TAG_TEXT = re.compile(r"<\s*([A-Za-z][\w.-]*)([^<>]*)>\s*([^<>{}]+?)\s*<\s*/\s*\1\s*>", re.S)
ATTR_STRING = re.compile(r"\b([A-Za-z-]+)\s*=\s*([\"'])((?:(?!\2).){2,200})\2")
JSON_STRING_LEAF = re.compile(r"\"((?:[^\"\\]|\\.)*)\"\s*:\s*\"((?:[^\"\\]|\\.)*)\"")
YAML_LEAF = re.compile(r"^\s*([\w.-]+)\s*:\s*[\"']?([^\"'#\n]{2,200}?)[\"']?\s*(?:#.*)?$")


@dataclass
class UIString:
    text: str
    file: str
    line: int
    kind: str      # element | expr | attr | object | toast | validation | markup | i18n
    context: str   # tag, attribute, object key, or call
    role: str      # action | link | nav | title | description | field | error | status | option | text
    button_like: bool
    error_like: bool


def role_for_tag(tag: str, attrs: dict[str, str]) -> str:
    if tag in NAV_TAGS:
        return "nav"
    if tag in ACTION_TAGS:
        return "action"
    if tag in LINK_TAGS:
        return "link"
    if tag in TITLE_TAGS:
        return "title"
    if tag in DESCRIPTION_TAGS:
        return "description"
    if tag in FIELD_TAGS:
        return "field"
    if tag in ERROR_TAGS or attrs.get("role") == "alert":
        return "error"
    if tag in OPTION_TAGS:
        return "option"
    base = tag.rsplit(".", 1)[-1]
    if base.endswith("Button"):
        return "action"
    if base.endswith("Title") or base.endswith("Heading"):
        return "title"
    if base.endswith("Description"):
        return "description"
    if "text-destructive" in attrs.get("className", ""):
        return "error"
    return "text"


# ---------------------------------------------------------------------------
# Text cleaning

def clean(text: str) -> str | None:
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    text = re.sub(r"\s+([,.;:!?…])", r"\1", text)
    if len(text) < 2 or len(text) > 200:
        return None
    bare = text.replace(PLACEHOLDER, " ").strip()
    if not re.search(r"[A-Za-z]", bare):
        return None
    if CODE_LIKE.search(bare):
        return None
    tokens = bare.split()
    if tokens and all(CLASS_TOKEN.match(t) for t in tokens) and any("-" in t or ":" in t for t in tokens):
        return None  # a Tailwind class list, not copy
    if len(tokens) == 1 and bare.islower() and len(bare) < 3:
        return None
    return text


def line_of(source: str, index: int) -> int:
    return source.count("\n", 0, index) + 1


# ---------------------------------------------------------------------------
# JavaScript lexing helpers shared by the JSX scanner and the object/toast/zod passes.

def skip_quoted(src: str, i: int) -> int:
    quote = src[i]
    i += 1
    n = len(src)
    while i < n:
        c = src[i]
        if c == "\\":
            i += 2
            continue
        if c == quote or c == "\n":
            return i + 1
        i += 1
    return n


def skip_template(src: str, i: int) -> int:
    i += 1
    n = len(src)
    while i < n:
        c = src[i]
        if c == "\\":
            i += 2
            continue
        if c == "`":
            return i + 1
        if c == "$" and i + 1 < n and src[i + 1] == "{":
            i = skip_balanced_js(src, i + 1)
            continue
        i += 1
    return n


def skip_balanced_js(src: str, i: int) -> int:
    """src[i] is an opening bracket; return the index just past its match."""
    pairs = {"{": "}", "(": ")", "[": "]"}
    stack = [pairs[src[i]]]
    i += 1
    n = len(src)
    while i < n and stack:
        c = src[i]
        if c in "\"'":
            i = skip_quoted(src, i)
            continue
        if c == "`":
            i = skip_template(src, i)
            continue
        if c == "/" and i + 1 < n and src[i + 1] in "/*":
            i = skip_comment(src, i)
            continue
        if c in pairs:
            stack.append(pairs[c])
        elif c == stack[-1]:
            stack.pop()
        i += 1
    return i


def skip_comment(src: str, i: int) -> int:
    if src.startswith("//", i):
        j = src.find("\n", i)
        return len(src) if j < 0 else j
    j = src.find("*/", i + 2)
    return len(src) if j < 0 else j + 2


def prev_significant(src: str, i: int) -> tuple[str, int]:
    j = i - 1
    while j >= 0 and src[j] in " \t\r\n":
        j -= 1
    return (src[j] if j >= 0 else "", j)


def regex_allowed(src: str, i: int) -> bool:
    ch, _ = prev_significant(src, i)
    return ch == "" or ch in "(,=:[!&|?{};+-*%<>~^"


def skip_regex(src: str, i: int) -> int:
    i += 1
    n = len(src)
    in_class = False
    while i < n:
        c = src[i]
        if c == "\\":
            i += 2
            continue
        if c == "\n":
            return i
        if c == "[":
            in_class = True
        elif c == "]":
            in_class = False
        elif c == "/" and not in_class:
            i += 1
            while i < n and src[i].isalpha():
                i += 1
            return i
        i += 1
    return n


def jsx_allowed(src: str, i: int) -> bool:
    if i + 1 >= len(src) or not (src[i + 1].isalpha() or src[i + 1] in "_$>"):
        return False
    ch, j = prev_significant(src, i)
    if ch == "" or ch in "(,=:[!&|?{};>}":
        return True
    if ch.isalnum() or ch in "_$":
        k = j
        while k >= 0 and (src[k].isalnum() or src[k] in "_$"):
            k -= 1
        return src[k + 1:j + 1] in JSX_PREFIX_WORDS
    return False


def literal_text(src: str, i: int, j: int) -> str:
    raw = src[i + 1:j - 1]
    if src[i] == "`":
        raw = re.sub(r"\$\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", PLACEHOLDER, raw)
    return raw


def ui_literals(src: str, start: int, end: int) -> list[tuple[str, int]]:
    """String and template literals in src[start:end] that read as interface copy.

    A literal counts when it opens the range or follows ?, :, &&, ||, ??, or a grouping paren.
    Literals passed as later call arguments (format(d, "MMM d")), used as call keys (t("key")),
    or compared against (x === "running") are skipped.
    """
    found: list[tuple[str, int]] = []
    i = start
    while i < end:
        c = src[i]
        if c == "/" and i + 1 < end and src[i + 1] in "/*":
            i = skip_comment(src, i)
            continue
        if c == "<" and jsx_allowed(src, i):
            # Nested JSX in an expression is emitted by the JSX scanner itself.
            close = find_jsx_end(src, i, end)
            if close > i:
                i = close
                continue
        if c in "\"'`":
            j = skip_template(src, i) if c == "`" else skip_quoted(src, i)
            at_start = src[start:i].strip() == ""
            ch, k = prev_significant(src, i)
            called = k > 0 and (src[k - 1].isalnum() or src[k - 1] in "_$.")
            grouping = ch == "(" and not called
            compared = src[j:end].lstrip().startswith(("==", "!="))
            if (at_start or ch in "?:&|{" or grouping) and not compared:
                found.append((literal_text(src, i, j), i))
            i = j
            continue
        i += 1
    return found


def top_level_args(src: str, start: int, end: int) -> list[tuple[int, int]]:
    """Split src[start:end] (a call's argument list) at top-level commas."""
    spans = []
    i = seg = start
    while i < end:
        c = src[i]
        if c in "\"'":
            i = skip_quoted(src, i)
            continue
        if c == "`":
            i = skip_template(src, i)
            continue
        if c in "([{":
            i = skip_balanced_js(src, i)
            continue
        if c == ",":
            spans.append((seg, i))
            seg = i + 1
        i += 1
    spans.append((seg, end))
    return spans


def find_jsx_end(src: str, i: int, end: int) -> int:
    parser = JSXParser(src)
    element, j = parser.parse_element(i, end)
    return j if element is not None else i


# ---------------------------------------------------------------------------
# JSX scanner

@dataclass
class Node:
    kind: str                 # text | expr | element
    start: int
    end: int
    text: str = ""
    element: "Element | None" = None


@dataclass
class Element:
    tag: str
    start: int
    attrs: list[tuple[str, str, int, int]]   # (name, kind "str"|"expr"|"bool", value start, value end)
    children: list[Node]
    role: str = "text"
    nested_actionable: bool = False


class JSXParser:
    def __init__(self, src: str) -> None:
        self.src = src
        self.elements: list[Element] = []

    def scan_js(self, i: int, end: int, stops: str = "") -> int:
        src = self.src
        depth = 0
        while i < end:
            c = src[i]
            if c in "\"'":
                i = skip_quoted(src, i)
                continue
            if c == "`":
                i = skip_template(src, i)
                continue
            if c == "/" and i + 1 < end and src[i + 1] in "/*":
                i = skip_comment(src, i)
                continue
            if c == "/" and regex_allowed(src, i):
                i = skip_regex(src, i)
                continue
            if c == "<" and jsx_allowed(src, i):
                element, j = self.parse_element(i, end)
                if element is not None:
                    i = j
                    continue
            if c in "([{":
                depth += 1
            elif c in ")]}":
                if depth == 0:
                    if c in stops:
                        return i
                    return i
                depth -= 1
            elif depth == 0 and c in stops:
                return i
            i += 1
        return end

    def parse_element(self, i: int, end: int) -> tuple[Element | None, int]:
        src = self.src
        start = i
        i += 1
        if i < end and src[i] == ">":
            tag = ""  # fragment
            i += 1
            element = Element(tag, start, [], [])
            ok, i = self.parse_children(element, i, end)
            if not ok:
                return None, start
            self.elements.append(element)
            return element, i
        match = TAG_NAME.match(src, i)
        if not match:
            return None, start
        tag = match.group(0)
        i = match.end()
        attrs: list[tuple[str, str, int, int]] = []
        while i < end:
            while i < end and src[i] in " \t\r\n":
                i += 1
            if i >= end:
                return None, start
            c = src[i]
            if src.startswith("/>", i):
                element = Element(tag, start, attrs, [])
                self.elements.append(element)
                return element, i + 2
            if c == ">":
                element = Element(tag, start, attrs, [])
                ok, j = self.parse_children(element, i + 1, end)
                if not ok:
                    return None, start
                self.elements.append(element)
                return element, j
            if c == "{":
                j = self.scan_js(i + 1, end, "}")
                if j >= end:
                    return None, start
                i = j + 1
                continue
            name_match = ATTR_NAME.match(src, i)
            if not name_match:
                return None, start
            name = name_match.group(0)
            i = name_match.end()
            while i < end and src[i] in " \t\r\n":
                i += 1
            if i < end and src[i] == "=":
                i += 1
                while i < end and src[i] in " \t\r\n":
                    i += 1
                if i >= end:
                    return None, start
                if src[i] in "\"'":
                    quote = src[i]
                    j = src.find(quote, i + 1, end)
                    if j < 0:
                        return None, start
                    attrs.append((name, "str", i + 1, j))
                    i = j + 1
                elif src[i] == "{":
                    j = self.scan_js(i + 1, end, "}")
                    if j >= end:
                        return None, start
                    attrs.append((name, "expr", i + 1, j))
                    i = j + 1
                elif src[i] == "<":
                    element, j = self.parse_element(i, end)
                    if element is None:
                        return None, start
                    i = j
                else:
                    return None, start
            else:
                attrs.append((name, "bool", i, i))
        return None, start

    def parse_children(self, element: Element, i: int, end: int) -> tuple[bool, int]:
        src = self.src
        text_start = i
        while i < end:
            c = src[i]
            if c == "{":
                self._flush_text(element, text_start, i)
                j = self.scan_js(i + 1, end, "}")
                if j >= end:
                    return False, i
                element.children.append(Node("expr", i + 1, j))
                i = j + 1
                text_start = i
                continue
            if c == "<":
                if src.startswith("</", i):
                    self._flush_text(element, text_start, i)
                    close = src.find(">", i)
                    if close < 0 or close >= end:
                        return False, i
                    return True, close + 1
                child, j = self.parse_element(i, end)
                if child is not None:
                    self._flush_text(element, text_start, i)
                    element.children.append(Node("element", i, j, element=child))
                    i = j
                    text_start = i
                    continue
            i += 1
        return False, i

    def _flush_text(self, element: Element, start: int, end: int) -> None:
        if end > start and self.src[start:end].strip():
            element.children.append(Node("text", start, end, text=self.src[start:end]))


def attr_value_text(src: str, attr: tuple[str, str, int, int]) -> str:
    return src[attr[2]:attr[3]] if attr[1] == "str" else ""


class JSXEmitter:
    def __init__(self, src: str, rel: str, parser: JSXParser, extra_props: set[str],
                 out: list[UIString]) -> None:
        self.src, self.rel, self.parser, self.out = src, rel, parser, out
        self.label_attrs = LABEL_ATTRS | extra_props
        self.consumed: set[int] = set()

    def run(self) -> None:
        for element in self.parser.elements:
            simple_attrs = {name: attr_value_text(self.src, a) for a in element.attrs for name in [a[0]]}
            element.role = role_for_tag(element.tag, simple_attrs)
        for element in self.parser.elements:
            element.nested_actionable = any(
                d.role in ACTIONABLE_ROLES for d in self.descendants(element)
            )
        for element in sorted(self.parser.elements, key=lambda e: e.start):
            self.emit_attrs(element)
            if element.role != "text":
                if element.role in ACTIONABLE_ROLES and element.nested_actionable:
                    continue  # e.g. DropdownMenuTrigger asChild > Button: report the inner control
                self.emit_composed(element)
        for element in self.parser.elements:
            if element.tag in SKIP_TEXT_TAGS:
                continue  # code samples and keyboard hints are not interface copy
            for node in element.children:
                if node.kind == "text" and node.start not in self.consumed:
                    self.add(node.text, node.start, "element", element.tag or "fragment", "text")
                if node.kind == "expr" and node.start not in self.consumed:
                    for literal, pos in ui_literals(self.src, node.start, node.end):
                        self.add(literal, pos, "expr", element.tag or "fragment", "text")

    def descendants(self, element: Element):
        for node in element.children:
            if node.element is not None:
                yield node.element
                yield from self.descendants(node.element)

    def composed_pieces(self, element: Element, alternatives: list[tuple[str, int]]) -> list[str]:
        pieces: list[str] = []
        for node in element.children:
            if node.kind == "text":
                pieces.append(node.text)
                self.consumed.add(node.start)
            elif node.kind == "expr":
                self.consumed.add(node.start)
                expr = self.src[node.start:node.end].strip()
                literals = ui_literals(self.src, node.start, node.end)
                whole = re.fullmatch(r"([\"'])(.*)\1", expr, re.S)
                if whole and len(literals) == 1:
                    pieces.append(literals[0][0])
                elif expr.startswith("`") and expr.endswith("`") and len(literals) == 1:
                    pieces.append(literals[0][0])
                else:
                    pieces.append(PLACEHOLDER)
                    alternatives.extend(literals)
            elif node.element is not None:
                child = node.element
                if child.role in ACTIONABLE_ROLES:
                    continue
                if child.tag in SKIP_TEXT_TAGS:
                    pieces.append(PLACEHOLDER)
                    continue
                pieces.extend(self.composed_pieces(child, alternatives))
        return pieces

    def emit_composed(self, element: Element) -> None:
        alternatives: list[tuple[str, int]] = []
        pieces = self.composed_pieces(element, alternatives)
        text = " ".join(p.strip() for p in pieces if p.strip())
        first_text = next((n.start for n in element.children if n.kind == "text"), element.start)
        if text and text.replace(PLACEHOLDER, "").strip():
            self.add(text, first_text, "element", element.tag or "fragment", element.role)
        for literal, pos in alternatives:
            self.add(literal, pos, "expr", element.tag or "fragment", element.role)

    def emit_attrs(self, element: Element) -> None:
        custom = element.tag[:1].isupper()
        for name, kind, start, end in element.attrs:
            if name not in self.label_attrs and name.lower() not in self.label_attrs:
                continue
            if name in ATTR_ROLE:
                role = ATTR_ROLE[name]
            elif name in ("aria-label", "label", "tooltip"):
                role = element.role if element.role != "text" else ("field" if name == "label" else "text")
            elif name == "title":
                # title on a layout component is its heading (<SectionHead title>); on HTML
                # elements and controls (<Button title>) it is a tooltip.
                role = "title" if custom and element.role in ("text", "title") else "text"
            else:
                role = "text"
            if kind == "str":
                self.add(self.src[start:end], start, "attr", name, role)
            elif kind == "expr":
                for literal, pos in ui_literals(self.src, start, end):
                    self.add(literal, pos, "attr", name, role)

    def add(self, text: str, index: int, kind: str, context: str, role: str) -> None:
        cleaned = clean(text)
        if not cleaned:
            return
        offset = len(text) - len(text.lstrip())
        self.out.append(UIString(
            cleaned, self.rel, line_of(self.src, index + offset), kind, context, role,
            role in ACTIONABLE_ROLES, role == "error",
        ))


# ---------------------------------------------------------------------------
# Script passes: object-literal labels, sonner toasts, zod and react-hook-form messages.

OBJECT_KEY_RE = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*:(?!:)")
DEFAULT_RE = re.compile(r"(?<![\w$.\-])([A-Za-z_$][\w$]*)\s*=\s*[\"'`]")
TOAST_RE = re.compile(r"\btoast(?:\.(\w+))?\s*\(")
ZOD_RE = re.compile(r"\.(" + "|".join(ZOD_METHODS) + r")\s*\(")


def value_end(src: str, i: int) -> int:
    """End of an object-literal value that starts at i (the next top-level , or closing bracket)."""
    n = len(src)
    while i < n:
        c = src[i]
        if c in "\"'":
            i = skip_quoted(src, i)
            continue
        if c == "`":
            i = skip_template(src, i)
            continue
        if c in "([{":
            i = skip_balanced_js(src, i)
            continue
        if c in ",)]}\n;" and not (c == "\n" and src[i:].lstrip()[:1] in "?:"):
            return i
        i += 1
    return n


def enclosing_object_keys(src: str, index: int) -> set[str]:
    depth = 0
    j = index
    while j >= 0:
        c = src[j]
        if c == "}":
            depth += 1
        elif c == "{":
            if depth == 0:
                break
            depth -= 1
        j -= 1
    if j < 0:
        return set()
    close = skip_balanced_js(src, j)
    return {m.group(1) for m in OBJECT_KEY_RE.finditer(src[j:close])}


def scan_script_passes(src: str, rel: str, extra_props: set[str], out: list[UIString]) -> None:
    keys = OBJECT_KEYS | extra_props
    promise_spans = []
    for m in TOAST_RE.finditer(src):
        method = m.group(1) or ""
        open_paren = m.end() - 1
        close = skip_balanced_js(src, open_paren)
        if method == "promise":
            promise_spans.append((open_paren, close))
            continue
        first_end = value_end(src, open_paren + 1)
        role = "error" if method == "error" else "status"
        for literal, pos in ui_literals(src, open_paren + 1, first_end):
            add_plain(out, src, rel, literal, pos, "toast", f"toast.{method}" if method else "toast", role)
    for m in OBJECT_KEY_RE.finditer(src):
        key = m.group(1)
        if key not in keys:
            continue
        if key in TOAST_PROMISE_KEYS and not any(s < m.start() < e for s, e in promise_spans):
            continue
        # Skip TypeScript annotations (label: string) and ternary branches (x ? title : y).
        before, _ = prev_significant(src, m.start())
        if before == "?":
            continue
        start = m.end()
        while start < len(src) and src[start] in " \t\r\n":
            start += 1  # the value may start on the next line
        end = value_end(src, start)
        literals = ui_literals(src, start, end)
        if not literals:
            continue
        siblings = enclosing_object_keys(src, m.start())
        role = OBJECT_KEY_ROLE.get(key, "text")
        if key in ("title", "label", "name") and siblings & {"url", "href", "to", "path"}:
            role = "nav"
        elif key == "label" and "value" in siblings:
            role = "option"
        elif key == "title" and role == "text":
            role = "title"
        for literal, pos in literals:
            add_plain(out, src, rel, literal, pos, "object", key, role)
    for m in DEFAULT_RE.finditer(src):
        # Destructured prop defaults: function SetupLedger({ title = "Set up your evaluator" }).
        if m.group(1) not in keys:
            continue
        quote_at = m.end() - 1
        j = skip_template(src, quote_at) if src[quote_at] == "`" else skip_quoted(src, quote_at)
        role = OBJECT_KEY_ROLE.get(m.group(1), "title" if m.group(1) == "title" else "text")
        add_plain(out, src, rel, literal_text(src, quote_at, j), quote_at, "object", m.group(1), role)
    if re.search(r"""from\s+["']zod["']|\bz\.object\(""", src):
        for m in ZOD_RE.finditer(src):
            open_paren = m.end() - 1
            close = skip_balanced_js(src, open_paren)
            # .email("Enter an email"), .min(1, "Enter a name"), .regex(/x/, "Use letters"):
            # a message is any argument that is exactly one string literal.
            for arg_start, arg_end in top_level_args(src, open_paren + 1, close - 1):
                arg = src[arg_start:arg_end].strip()
                if len(arg) >= 2 and arg[0] in "\"'`" and arg[-1] == arg[0]:
                    pos = src.index(arg[0], arg_start)
                    end_pos = skip_template(src, pos) if arg[0] == "`" else skip_quoted(src, pos)
                    add_plain(out, src, rel, literal_text(src, pos, end_pos), pos, "validation",
                              f".{m.group(1)}", "error")


def add_plain(out: list[UIString], src: str, rel: str, text: str, index: int, kind: str,
              context: str, role: str) -> None:
    cleaned = clean(text)
    if not cleaned:
        return
    out.append(UIString(cleaned, rel, line_of(src, index), kind, context, role,
                        role in ACTIONABLE_ROLES, role == "error"))


# ---------------------------------------------------------------------------
# Markup (Vue, Svelte, HTML) and i18n extractors

def scan_markup(rel: str, source: str, extra_props: set[str], out: list[UIString]) -> None:
    label_attrs = {a.lower() for a in LABEL_ATTRS | extra_props}
    for m in TAG_TEXT.finditer(source):
        tag, attrs, text = m.group(1), m.group(2), m.group(3)
        role = role_for_tag(tag, {"role": "alert"} if 'role="alert"' in attrs else {})
        add_plain(out, source, rel, text, m.start(3), "markup", tag, role)
    for m in ATTR_STRING.finditer(source):
        attr, value = m.group(1), m.group(3)
        if attr.lower() not in label_attrs:
            continue
        add_plain(out, source, rel, value, m.start(3), "markup", attr, ATTR_ROLE.get(attr, "text"))


def scan_i18n(path: str, rel: str, source: str, out: list[UIString]) -> None:
    ext = os.path.splitext(path)[1].lower()
    button_hint = re.compile(r"(button|btn|cta|action|submit|confirm|cancel|primary|secondary)", re.I)
    error_hint = re.compile(r"(error|invalid|fail|validation|warning|denied|forbidden)", re.I)

    def role_for_key(key: str) -> str:
        if error_hint.search(key):
            return "error"
        if button_hint.search(key):
            return "action"
        return "text"

    if ext == ".json":
        for m in JSON_STRING_LEAF.finditer(source):
            key, value = m.group(1), m.group(2)
            decoded = value.encode().decode("unicode_escape", errors="ignore")
            add_plain(out, source, rel, decoded, m.start(2), "i18n", key, role_for_key(key))
    else:
        for i, raw in enumerate(source.splitlines(), 1):
            m = YAML_LEAF.match(raw)
            if not m or m.group(2).strip() in {"|", ">"}:
                continue
            cleaned = clean(m.group(2))
            if cleaned:
                role = role_for_key(m.group(1))
                out.append(UIString(cleaned, rel, i, "i18n", m.group(1), role,
                                    role in ACTIONABLE_ROLES, role == "error"))


# ---------------------------------------------------------------------------
# Walking

def is_excluded(path: str, patterns: list[str]) -> bool:
    parts = path.replace("\\", "/").split("/")
    return any(fnmatch.fnmatch(part, pat) for part in parts for pat in patterns) or any(
        fnmatch.fnmatch(path.replace("\\", "/"), pat) for pat in patterns
    )


def scan_file(full: str, rel: str, source: str, extra_props: set[str], out: list[UIString]) -> None:
    ext = os.path.splitext(full)[1].lower()
    if ext in SCRIPT_EXT:
        before = len(out)
        if ext in JSX_EXT and "<" in source:
            try:
                parser = JSXParser(source)
                i, n = 0, len(source)
                while i < n:
                    # A stray closing bracket ends scan_js early; resume after it.
                    i = parser.scan_js(i, n) + 1
                JSXEmitter(source, rel, parser, extra_props, out).run()
            except (RecursionError, IndexError, ValueError):
                del out[before:]
                scan_markup(rel, source, extra_props, out)
        scan_script_passes(source, rel, extra_props, out)
    elif ext in MARKUP_EXT:
        scan_markup(rel, source, extra_props, out)
    elif ext in I18N_EXT:
        scan_i18n(full, rel, source, out)


def walk(root: str, excludes: list[str], max_bytes: int, extra_props: set[str]) -> list[UIString]:
    found: list[UIString] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames
            if not is_excluded(os.path.relpath(os.path.join(dirpath, d), root), excludes)
            and not os.path.islink(os.path.join(dirpath, d))
        )
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if os.path.islink(full) or is_excluded(rel, excludes):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in SCRIPT_EXT | MARKUP_EXT | I18N_EXT:
                continue
            try:
                if os.path.getsize(full) > max_bytes:
                    continue
                with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                    source = fh.read()
            except OSError:
                continue
            scan_file(full, rel, source, extra_props, found)
    unique: dict[tuple[str, int, str, str], UIString] = {}
    for s in found:
        unique.setdefault((s.file, s.line, s.text, s.context), s)
    return list(unique.values())


# ---------------------------------------------------------------------------
# UX.md: glossary rejected synonyms, casing policy, scanner props

def find_up(start: Path, name: str) -> Path | None:
    directory = start if start.is_dir() else start.parent
    for candidate in [directory, *directory.parents]:
        if (candidate / name).is_file():
            return candidate / name
        if (candidate / ".git").exists():
            break
    return None


def find_ux(start: Path) -> Path | None:
    return find_up(start, "UX.md")


def ux_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = defaultdict(list)
    current = ""
    for line in text.splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            current = heading.group(1).strip().lower()
            continue
        sections[current].append(line)
    return sections


def table_rows(lines: list[str]) -> list[list[str]]:
    rows = []
    for line in lines:
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        rows.append(cells)
    return rows[1:] if rows else []


def split_terms(cell: str) -> list[str]:
    cell = re.sub(r"\([^)]*\)", "", cell)
    return [t.strip().strip("`*_\"'") for t in re.split(r"[,;/]", cell) if t.strip().strip("`*_\"'")]


def parse_ux(text: str) -> dict:
    sections = ux_sections(text)
    glossary: dict[str, list[str]] = {}
    for cells in table_rows(sections.get("glossary", [])):
        if not cells or not cells[0] or cells[0].startswith("("):
            continue
        rejected = split_terms(cells[2]) if len(cells) > 2 else []
        term = cells[0].strip("`*_")
        glossary[term] = [r for r in rejected if r.lower() != term.lower()]
    casing = None
    for line in sections.get("casing", []):
        low = line.lower()
        if any(k in low for k in ("label", "button", "heading")):
            if "title case" in low:
                casing = "title"
            elif "sentence case" in low:
                casing = "sentence"
            if casing:
                break
    props: set[str] = set()
    excludes: list[str] = []
    for line in sections.get("scanner", []):
        m = re.match(r"^\s*[-*]\s*([^:]+):\s*(.+)$", line)
        if not m:
            continue
        key = m.group(1).strip().lower()
        if m.group(2).strip().startswith("("):
            continue  # template placeholder, not a setting
        values = [v.strip().strip("`") for v in m.group(2).split(",") if v.strip()]
        if key.startswith("label prop"):
            props.update(values)
        elif key.startswith("exclude"):
            excludes.extend(values)
    return {"glossary": glossary, "casing": casing, "props": props, "excludes": excludes}


# ---------------------------------------------------------------------------
# Domain glossaries: CONCEPTS.md (project-vocabulary) and CONTEXT.md

QUOTED = re.compile(r"[\"“”]([^\"“”]{1,60})[\"“”]")
NOT_A_TERM = {"", "none", "n/a", "-", "—"}


def unfenced(text: str) -> list[str]:
    lines, fenced = [], False
    for line in text.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            fenced = not fenced
        elif not fenced:
            lines.append(line)
    return lines


def alias_terms(value: str, term: str) -> list[str]:
    out: list[str] = []
    for part in QUOTED.findall(value) or re.split(r"[,;/]", value):
        part = re.sub(r"^\s*(?:formerly|previously|also|aka|was|or)\b", "", part.strip(), flags=re.I)
        part = part.strip().strip(".`*_ ")
        if part.lower() not in NOT_A_TERM and part.lower() != term.lower() and part not in out:
            out.append(part)
    return out


def parse_concepts(text: str) -> dict[str, list[str]]:
    """Retired aliases from project-vocabulary's CONCEPTS.md: "## Term [context]" then "Aliases:"."""
    glossary: dict[str, list[str]] = {}
    term = None
    for line in unfenced(text):
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            name = re.sub(r"\s*\[[^\]]*\]\s*$", "", heading.group(1)).strip()
            term = None if "<" in name or name.lower().startswith("flagged ambiguit") else name
            continue
        alias = re.match(r"^\s*Aliases?\s*:\s*(.+)$", line, re.I)
        if term and alias and "<" not in alias.group(1):
            glossary.setdefault(term, []).extend(alias_terms(alias.group(1), term))
    return {t: v for t, v in glossary.items() if v}


def parse_context(text: str) -> dict[str, list[str]]:
    """Avoided words from a CONTEXT.md glossary: "**Term**:" then "_Avoid_: a, b"."""
    glossary: dict[str, list[str]] = {}
    term = None
    for line in unfenced(text):
        head = re.match(r"^\s*\*\*([^*]+?)\*\*\s*:", line)
        if head:
            term = head.group(1).strip()
            continue
        avoid = re.match(r"^\s*[_*]Avoid[_*]\s*:\s*(.+)$", line, re.I)
        if term and avoid:
            words = [w for w in split_terms(avoid.group(1)) if w.lower() not in NOT_A_TERM | {term.lower()}]
            glossary.setdefault(term, []).extend(words)
    return {t: v for t, v in glossary.items() if v}


def merge_glossary(glossary: dict[str, list[str]], sources: dict[str, list[str]],
                   entries: dict[str, list[str]], source: str) -> None:
    for canonical, words in entries.items():
        key = next((k for k in glossary if k.lower() == canonical.lower()), canonical)
        known = glossary.setdefault(key, [])
        for word in words:
            if word.lower() not in {k.lower() for k in known}:
                known.append(word)
        if source not in sources.setdefault(key, []):
            sources[key].append(source)


# ---------------------------------------------------------------------------
# Analysis

def casing_of(text: str, proper: set[str]) -> str:
    words = [w for w in re.findall(r"[A-Za-z][\w'’-]*", text.replace(PLACEHOLDER, " "))]
    words = [w for w in words if w not in proper]
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


def word_span(term: str, text: str) -> list[tuple[int, int]]:
    pattern = r"(?<![\w'])" + re.escape(term) + r"(?:s|es)?(?![\w'])"
    return [(m.start(), m.end()) for m in re.finditer(pattern, text, re.I)]


def is_filler(s: UIString) -> bool:
    if FILLER_RE.search(s.text) or MARKER_RE.search(s.text):
        return True
    return s.context != "placeholder" and bool(STUB_RE.search(s.text))


def analyze(strings: list[UIString], glossary: dict[str, list[str]], casing_policy: str | None,
            proper_terms: set[str] | None = None) -> dict:
    labels = [s for s in strings if s.role in LABEL_ROLES and short(s.text, 8)]
    actions = [s for s in strings if s.role in ACTIONABLE_ROLES]
    generic, review = [], []
    for s in actions:
        key = s.text.lower().rstrip(".!…")
        if key in GENERIC_LABELS:
            (review if key in REVIEW_ONLY else generic).append(s)

    verb_clusters: dict[str, dict[str, list[UIString]]] = defaultdict(lambda: defaultdict(list))
    for s in strings:
        if s.role not in LABEL_ROLES or not short(s.text, 4):
            continue
        low = s.text.lower()
        for cluster, terms in VERB_CLUSTERS.items():
            for term in terms:
                if low == term or low.startswith(term + " ") or (low.endswith(" " + term) and len(low.split()) <= 2):
                    verb_clusters[cluster][term].append(s)
                    break
    noun_clusters: dict[str, dict[str, list[UIString]]] = defaultdict(lambda: defaultdict(list))
    for s in strings:
        if not short(s.text, 6):
            continue
        for cluster, terms in NOUN_CLUSTERS.items():
            for term in terms:
                if word_span(term, s.text):
                    noun_clusters[cluster][term].append(s)
                    break

    rejected: dict[str, dict[str, list[UIString]]] = defaultdict(lambda: defaultdict(list))
    terms = {c.lower() for c in glossary}
    for canonical, synonyms in glossary.items():
        seen: set[int] = set()
        # Longest synonym first, so "Golden set" claims a string before "golden" does.
        for synonym in sorted(synonyms, key=len, reverse=True):
            if synonym.lower() in terms:
                continue  # "don't confuse with Live Artifact" is not a ban on the term Live Artifact
            for index, s in enumerate(strings):
                if index in seen:
                    continue
                spans = word_span(synonym, s.text)
                covered = [c for term in glossary for c in word_span(term, s.text)]
                # "Review guide" is not drift from "guide": skip matches inside any glossary term.
                keep = [sp for sp in spans if not any(c[0] <= sp[0] and sp[1] <= c[1] for c in covered)]
                if keep:
                    rejected[canonical][synonym].append(s)
                    seen.add(index)

    # Words the UI capitalizes on purpose. Domain glossaries name concepts but do not set casing.
    proper = {w for term in (glossary if proper_terms is None else proper_terms)
              for w in term.split() if w[:1].isupper()}
    policy = casing_policy or "sentence"
    counts: dict[str, int] = defaultdict(int)
    deviations = []
    for s in labels:
        if s.context == "placeholder":
            continue  # format hints such as name@example.com are not labels
        c = casing_of(s.text, proper)
        if c == "single":
            continue
        counts[c] += 1
        if c != policy:
            deviations.append(s)

    error_strings = [s for s in strings if s.error_like or any(
        word_span(w, s.text) for w in ("try again", "must", "can't", "cannot", "couldn't"))]
    banned = []
    for s in error_strings:
        hits = [w for w in BANNED_ERROR_WORDS if word_span(w, s.text)]
        if hits:
            banned.append((s, hits))
    filler = [s for s in strings if is_filler(s)]
    exclamations = [s for s in strings if "!" in s.text.replace("!=", "")]
    trailing = [s for s in labels if short(s.text, 4) and s.text.endswith(".") and not s.text.endswith("..")]
    navigation = [s for s in strings if s.role == "nav"]
    roles: dict[str, int] = defaultdict(int)
    for s in strings:
        roles[s.role] += 1
    return {
        "inventory": strings,
        "roles": dict(sorted(roles.items())),
        "labels": labels,
        "generic": generic,
        "review": review,
        "filler": filler,
        "drift_verbs": {c: v for c, v in verb_clusters.items() if len(v) >= 2},
        "drift_nouns": {c: v for c, v in noun_clusters.items() if len(v) >= 2},
        "rejected": {c: dict(v) for c, v in rejected.items()},
        "casing": {"policy": policy, "counts": dict(counts), "deviations": deviations},
        "banned": banned,
        "exclamations": exclamations,
        "trailing": trailing,
        "navigation": navigation,
    }


# ---------------------------------------------------------------------------
# Rendering

def loc(s: UIString) -> str:
    return f"{s.file}:{s.line}"


def render_md(root: str, r: dict, policy_note: str) -> str:
    lines = [f"# Label scan: {root}", ""]
    role_summary = ", ".join(f"{k} {v}" for k, v in r["roles"].items())
    lines.append(f"Strings found: {len(r['inventory'])} ({role_summary}). Read-only report; "
                 "clusters are evidence, not verdicts.")
    lines.append(f"Policy: {policy_note}")
    lines.append("")
    lines.append("## Rejected terms (project glossary)")
    sources = r.get("glossary_sources", {})
    if not r["rejected"]:
        lines.append("None." if sources else "No glossary: add UX.md or CONCEPTS.md, or pass --term.")
    for canonical, synonyms in r["rejected"].items():
        origin = f" ({', '.join(sources[canonical])})" if sources.get(canonical) else ""
        lines.append(f"- **{canonical}**{origin} ← " + ", ".join(f"`{t}` ×{len(v)}" for t, v in synonyms.items()))
        for t, v in synonyms.items():
            for s in v[:6]:
                lines.append(f"  - `{s.text}` at {loc(s)} ({s.role})")
            if len(v) > 6:
                lines.append(f"  - … {len(v) - 6} more `{t}`")
    lines.append("")
    lines.append("## Generic labels")
    if not r["generic"]:
        lines.append("None.")
    for s in r["generic"]:
        lines.append(f"- `{s.text}` at {loc(s)} ({s.role}: {s.context}) — replace with verb + object")
    if r["review"]:
        lines.append("")
        lines.append("Review (fine on wizard steps, wrong on committing actions):")
        for s in r["review"]:
            lines.append(f"- `{s.text}` at {loc(s)} ({s.role}: {s.context})")
    lines.append("")
    lines.append("## Filler copy (stand-in text that should not ship)")
    if not r["filler"]:
        lines.append("None.")
    for s in r["filler"][:20]:
        lines.append(f"- `{s.text}` at {loc(s)} ({s.role}: {s.context})")
    if len(r["filler"]) > 20:
        lines.append(f"- … {len(r['filler']) - 20} more")
    lines.append("")
    lines.append("## Verb clusters (same action, different words?)")
    if not r["drift_verbs"]:
        lines.append("None.")
    for cluster, terms in r["drift_verbs"].items():
        lines.append(f"- **{cluster}**: " + ", ".join(f"`{t}` ×{len(v)}" for t, v in terms.items()))
        for t, v in terms.items():
            for s in v[:5]:
                lines.append(f"  - `{s.text}` at {loc(s)} ({s.role})")
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
    casing = r["casing"]
    lines.append(f"## Casing (policy: {casing['policy']} case)")
    total = sum(casing["counts"].values())
    if total == 0:
        lines.append("No multi-word labels found.")
    else:
        lines.append("- " + ", ".join(f"{k}: {v}" for k, v in sorted(casing["counts"].items())))
        for s in casing["deviations"][:20]:
            lines.append(f"  - `{s.text}` at {loc(s)} ({s.role})")
        if len(casing["deviations"]) > 20:
            lines.append(f"  - … {len(casing['deviations']) - 20} more")
    lines.append("")
    lines.append("## Banned words in error-like strings")
    if not r["banned"]:
        lines.append("None.")
    for s, hits in r["banned"]:
        lines.append(f"- `{s.text}` at {loc(s)} ({s.context}) — {', '.join(hits)}")
    lines.append("")
    lines.append("## Exclamation marks")
    if not r["exclamations"]:
        lines.append("None.")
    for s in r["exclamations"][:20]:
        lines.append(f"- `{s.text}` at {loc(s)} ({s.role})")
    lines.append("")
    lines.append("## Trailing period on short labels")
    if not r["trailing"]:
        lines.append("None.")
    for s in r["trailing"]:
        lines.append(f"- `{s.text}` at {loc(s)} ({s.role})")
    lines.append("")
    lines.append("## Navigation labels (compare with breadcrumbs and page titles)")
    if not r["navigation"]:
        lines.append("None found.")
    for s in r["navigation"][:60]:
        lines.append(f"- `{s.text}` at {loc(s)} ({s.kind}: {s.context})")
    if len(r["navigation"]) > 60:
        lines.append(f"- … {len(r['navigation']) - 60} more")
    lines.append("")
    return "\n".join(lines)


def render_json(root: str, r: dict, policy_note: str) -> str:
    def ser(items):
        return [asdict(s) for s in items]
    payload = {
        "root": root,
        "policy": policy_note,
        "counts": {"strings": len(r["inventory"]), "labels": len(r["labels"]), "roles": r["roles"]},
        "glossary_sources": r.get("glossary_sources", {}),
        "rejected": {c: {t: ser(v) for t, v in terms.items()} for c, terms in r["rejected"].items()},
        "generic": ser(r["generic"]),
        "review": ser(r["review"]),
        "filler": ser(r["filler"]),
        "drift_verbs": {c: {t: ser(v) for t, v in terms.items()} for c, terms in r["drift_verbs"].items()},
        "drift_nouns": {c: {t: ser(v) for t, v in terms.items()} for c, terms in r["drift_nouns"].items()},
        "casing": {"policy": r["casing"]["policy"], "counts": r["casing"]["counts"],
                   "deviations": ser(r["casing"]["deviations"])},
        "banned": [{"string": asdict(s), "words": hits} for s, hits in r["banned"]],
        "exclamations": ser(r["exclamations"]),
        "trailing": ser(r["trailing"]),
        "navigation": ser(r["navigation"]),
        "inventory": ser(r["inventory"]),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="project directory to scan (read-only)")
    parser.add_argument("--format", choices=("md", "json"), default="md")
    parser.add_argument("--ux", help="UX.md to read (default: nearest UX.md from PATH up to the git root)")
    parser.add_argument("--prop", action="append", default=[], help="extra prop or key that carries UI text (repeatable)")
    parser.add_argument("--term", action="append", default=[],
                        help="glossary entry CANONICAL=REJECTED,REJECTED (repeatable; adds to UX.md)")
    parser.add_argument("--exclude", action="append", default=[], help="extra glob to exclude (repeatable)")
    parser.add_argument("--max-file-kb", type=int, default=512)
    args = parser.parse_args(argv)

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    ux_path = Path(args.ux).resolve() if args.ux else find_ux(Path(root))
    ux = {"glossary": {}, "casing": None, "props": set(), "excludes": []}
    if ux_path is not None:
        if not ux_path.is_file():
            print(f"UX.md not found: {ux_path}", file=sys.stderr)
            return 2
        ux = parse_ux(ux_path.read_text(encoding="utf-8", errors="ignore"))
    glossary: dict[str, list[str]] = {}
    sources: dict[str, list[str]] = {}
    merge_glossary(glossary, sources, ux["glossary"], "UX.md")
    term_entries: dict[str, list[str]] = {}
    for entry in args.term:
        canonical, _, rejected = entry.partition("=")
        if canonical.strip() and rejected.strip():
            term_entries.setdefault(canonical.strip(), []).extend(split_terms(rejected))
    merge_glossary(glossary, sources, term_entries, "--term")
    proper_terms = set(glossary)
    domain_notes = []
    for name, parse in (("CONCEPTS.md", parse_concepts), ("CONTEXT.md", parse_context)):
        path = find_up(Path(root), name)
        if path is not None:
            entries = parse(path.read_text(encoding="utf-8", errors="ignore"))
            merge_glossary(glossary, sources, entries, name)
            domain_notes.append(f"{name} at {path} (terms with retired words: {len(entries)})")
    props = set(args.prop) | set(ux["props"])
    strings = walk(root, DEFAULT_EXCLUDES + ux["excludes"] + args.exclude, args.max_file_kb * 1024, props)
    report = analyze(strings, glossary, ux["casing"], proper_terms)
    report["glossary_sources"] = sources
    if ux_path is not None:
        policy_note = (f"UX.md at {ux_path} (glossary terms: {len(ux['glossary'])}; casing: "
                       f"{(ux['casing'] or 'sentence') + ' case'}{'' if ux['casing'] else ' (default)'})")
    else:
        policy_note = "no UX.md found; defaults: sentence case"
    for note in domain_notes:
        policy_note += f"; {note}"
    if args.term:
        policy_note += f"; --term entries: {len(args.term)}"
    print(render_md(root, report, policy_note) if args.format == "md" else render_json(root, report, policy_note))
    return 0


if __name__ == "__main__":
    sys.exit(main())
