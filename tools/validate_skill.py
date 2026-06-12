#!/usr/bin/env python3
"""Validate a SKILL.md skill folder against the real Agent Skills spec.

Calibrated to the documented Claude Code skill frontmatter, not a narrow subset:
`name` is OPTIONAL (defaults to the directory name), `description` is recommended,
and many fields are valid (allowed-tools, argument-hint, when_to_use, arguments,
disable-model-invocation, user-invocable, disallowed-tools, model, effort, context,
agent, hooks, paths, shell). Plugin skills namespace the name as `plugin:skill`, and
`description` may be a multi-line YAML block scalar.

So this returns (errors, warnings): errors are things that actually break loading
(no/!malformed frontmatter delimiters, no content at all); everything about quality,
length, and style is a warning, not a failure.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Optional leading `plugin:` namespace, then lowercase/digits/hyphens.
NAME_RE = re.compile(r"^([a-z0-9][a-z0-9-]*:)?[a-z0-9][a-z0-9-]{0,62}$")
BLOCK_SCALAR = {'>', '|', '>-', '|-', '>+', '|+'}


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Tolerant frontmatter parse: top-level `key:` lines only.

    Indented continuation lines (folded/literal block scalars) and nested maps/lists
    (e.g. compatibility.requires) belong to the preceding key and never raise. This
    matches real-world skills like n8n's, which the old line-splitting parser rejected.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        raise ValueError('SKILL.md must start with YAML frontmatter delimited by ---')
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == '---'), None)
    if end is None:
        raise ValueError('SKILL.md must contain a closing --- frontmatter delimiter')

    data: dict[str, str] = {}
    cur, in_block = None, False
    for line in lines[1:end]:
        if not line.strip():
            continue
        m = re.match(r"^(\S[^:]*?):(.*)$", line)
        if m and not line[0].isspace():  # a top-level key
            key, val = m.group(1).strip(), m.group(2).strip()
            if val in BLOCK_SCALAR:
                data[key], cur, in_block = '', key, True
            else:
                data[key], cur, in_block = val.strip('"\''), key, False
        elif cur is not None and in_block:  # continuation of a block scalar
            data[cur] = (data[cur] + ' ' + line.strip()).strip()
        # else: nested map/list under a non-block key — opaque, ignored
    return data, '\n'.join(lines[end + 1:])


def validate(path: Path, max_body_lines: int, max_chars: int) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    skill_file = path / 'SKILL.md'
    if not skill_file.exists():
        return [f'{skill_file} does not exist'], []

    text = skill_file.read_text(encoding='utf-8')
    try:
        fm, body = parse_frontmatter(text)
    except ValueError as exc:
        return [str(exc)], []

    name = fm.get('name')
    if name:
        if not NAME_RE.match(name):
            warnings.append(f'name {name!r} is unusual; expected lowercase/digits/hyphens, '
                            'optionally plugin-namespaced (plugin:skill)')
        else:
            bare = name.split(':')[-1]
            if path.name not in {bare, 'codex-skill', 'claude-skill'}:
                warnings.append(f'folder name {path.name!r} differs from skill name {name!r}')

    desc = fm.get('description', '')
    if not desc:
        warnings.append('no description — recommended so Claude can route to the skill')
    elif len(desc) < 40:
        warnings.append('description is short; make it specific enough to trigger the skill')

    body_lines = body.strip().splitlines()
    if not body.strip() and not desc:
        errors.append('skill has neither a description nor body content')
    if len(body_lines) > max_body_lines:
        warnings.append(f'body has {len(body_lines)} lines; move detail into references/ '
                        f'(soft limit {max_body_lines})')
    if len(text) > max_chars:
        warnings.append(f'SKILL.md has {len(text)} chars; move detail into references/ '
                        f'(soft limit {max_chars})')

    headings = [line.strip() for line in body_lines if line.startswith('#')]
    duplicates = sorted({h for h in headings if headings.count(h) > 1})
    if duplicates:
        warnings.append(f'duplicate headings: {duplicates}')

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('skill_dir', type=Path)
    parser.add_argument('--max-body-lines', type=int, default=500)
    parser.add_argument('--max-chars', type=int, default=20000)
    args = parser.parse_args()

    errors, warnings = validate(args.skill_dir, args.max_body_lines, args.max_chars)
    for w in warnings:
        print(f'WARN: {w}')
    for e in errors:
        print(f'ERROR: {e}', file=sys.stderr)
    if errors:
        return 1
    suffix = f' ({len(warnings)} warning(s))' if warnings else ''
    print(f'OK: {args.skill_dir}{suffix}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
