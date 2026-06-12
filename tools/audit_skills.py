#!/usr/bin/env python3
"""Audit existing skills in a repository against the skill-mastery playbook.

Discovers every SKILL.md under a root, runs structural + heuristic checks that need
no model (the discipline layer), and prints a triage report: per-skill grade, the
specific gaps, a suggested verifiability tier, and whether the skill looks worth the
full loop or just the lite path. Use it as the on-ramp when dropping this repo into a
codebase that already has skills.

  python3 scripts/audit_skills.py .                       # audit the current repo
  python3 scripts/audit_skills.py ~/some-repo --json      # machine-readable
  python3 scripts/audit_skills.py . --out inventory.md     # seed an inventory file

This is mechanical triage, not a quality verdict. A clean structural grade does not
mean the skill works — that is what evals are for.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Reuse the single-skill validator's parser + structural checks.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_skill import parse_frontmatter, validate as structural_validate  # noqa: E402

SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', 'records',
             '.skill-mastery'}

# Heuristic section cues (lowercased heading text contains any token).
FAILURE_CUES = ('failure', 'pitfall', 'gotcha', 'common mistake', 'anti-pattern', 'guardrail')
CONSTRAINT_CUES = ('output', 'constraint', 'format', 'must', 'rule')
OBJECTIVE_CUES = re.compile(r"\b(test|exit code|exact|json|schema|compile|lint|typecheck|diff)\b", re.I)


def estimate_tokens(text: str) -> int:
    return len(text) // 4  # rough chars-per-token


def discover(root: Path) -> list[Path]:
    """Find SKILL.md files with a pruning walk.

    os.walk lets us prune heavy dirs (node_modules, .git) instead of walking the
    whole monorepo and filtering after — essential on big repos like n8n. We do NOT
    follow symlinks, so a symlinked skill dir (n8n's .claude/skills -> plugins/...)
    is found once via its real location, not triple-counted. A final dedupe by real
    path guards against any remaining aliasing."""
    by_real: dict[Path, Path] = {}
    for dirpath, dirnames, filenames in os.walk(root):  # followlinks=False (default)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if 'SKILL.md' in filenames:
            p = Path(dirpath) / 'SKILL.md'
            try:
                real = p.resolve()
            except OSError:
                continue
            by_real.setdefault(real, p)
    return sorted(by_real.values())


def recommendation_for(grade: str, findings: list[tuple[str, str]], suggested_tier: str, path: str) -> dict:
    """Turn mechanical findings into an operator-facing next action."""
    messages = [m.lower() for _, m in findings]
    if grade == 'FAIL':
        verdict = 'revise'
        patch = 'fix structural loading errors first'
    elif grade == 'PASS':
        verdict = 'keep'
        patch = 'optional lite polish only; add/refresh smoke tests'
    elif any('heterogeneous' in m or 'split' in m for m in messages):
        verdict = 'split'
        patch = 'split mixed workflows into focused skills'
    elif any('very thin' in m or 'description' in m or 'failure modes' in m or 'constraints' in m for m in messages):
        verdict = 'revise'
        patch = 'lite patch: tighten routing, constraints, and known failure modes'
    elif any('bloated' in m or 'large inline' in m for m in messages):
        verdict = 'revise'
        patch = 'lite patch: move bulky detail into references/scripts'
    else:
        verdict = 'keep'
        patch = 'add/refresh smoke tests; no optimizer needed'

    full_loop = suggested_tier in {'objective', 'rubric'} and grade != 'FAIL'
    path_hint = 'possible later' if full_loop else 'no'
    if verdict == 'keep':
        next_command = f'python3 scripts/lite_improve.py {Path(path).parent}'
    elif verdict == 'revise':
        next_command = f'python3 scripts/lite_improve.py {Path(path).parent}'
    elif verdict == 'split':
        next_command = f'python3 scripts/lite_improve.py {Path(path).parent} --name split-{Path(path).parent.name}'
    else:
        next_command = 'retire unused/superseded skill, or run lite_improve if it is still needed'

    return {
        'verdict': verdict,
        'recommended_path': 'lite' if verdict in {'keep', 'revise', 'split'} else 'retire',
        'suggested_patch_type': patch,
        'full_loop': path_hint,
        'next_command': next_command,
    }


def audit_one(skill_md: Path) -> dict:
    """Return structured triage for one skill."""
    findings: list[tuple[str, str]] = []
    text = skill_md.read_text(encoding='utf-8', errors='replace')
    skill_dir = skill_md.parent

    # 1. Structural validity (reuse the single-skill validator). Errors are real
    # breakage (FAIL); spec-calibrated quality/style issues come back as warnings.
    errs, warns = structural_validate(skill_dir, max_body_lines=500, max_chars=20000)
    for err in errs:
        findings.append(('FAIL', f'structural: {err}'))
    for warn in warns:
        findings.append(('WARN', f'structural: {warn}'))

    # Parse what we can even if structural checks failed.
    name = skill_dir.name
    body = text
    try:
        fm, body = parse_frontmatter(text)
        name = fm.get('name', skill_dir.name)
        desc = fm.get('description', '')
        if 0 < len(desc) < 40:
            findings.append(('WARN', 'description is too thin to route reliably (<40 chars)'))
        if desc and not re.search(r"\b(use when|when |for )\b", desc, re.I):
            findings.append(('INFO', 'description states what, not when — add trigger conditions'))
    except ValueError:
        pass  # already reported as a structural FAIL

    # 2. Token budget (SkillOpt artifacts run ~300–2000 tokens).
    tokens = estimate_tokens(body)
    if tokens < 120:
        findings.append(('WARN', f'~{tokens} tokens: very thin — may not warrant a skill (see when-to-optimize)'))
    if tokens > 2000:
        findings.append(('WARN', f'~{tokens} tokens: bloated — move detail into references/ (progressive disclosure)'))

    headings = [h.lower() for h in re.findall(r"^#+\s*(.+?)\s*$", body, re.M)]
    heading_blob = ' '.join(headings)

    # 3. Known-failure-modes section.
    if not any(cue in heading_blob for cue in FAILURE_CUES):
        findings.append(('WARN', 'no failure-modes/guardrails section — the recurring mistakes the skill should prevent'))

    # 4. Output constraints / rules section.
    if not any(cue in heading_blob for cue in CONSTRAINT_CUES):
        findings.append(('INFO', 'no explicit output-constraints/rules section'))

    # 5. Protected slow-update region.
    if not re.search(r"^#+\s*slow-update", body, re.M | re.I):
        findings.append(('INFO', 'no protected ## Slow-update region — add one before iterating'))

    # 6. Progressive disclosure: big inline code/table blocks that belong in references.
    big_blocks = [b for b in re.findall(r"```.*?```", body, re.S) if b.count('\n') > 40]
    if big_blocks:
        findings.append(('INFO', f'{len(big_blocks)} large inline code block(s) >40 lines — consider references/'))

    has_resources = any((skill_dir / d).is_dir() for d in ('references', 'scripts', 'assets'))
    if tokens > 1200 and not has_resources:
        findings.append(('INFO', 'long skill with no references/scripts/assets — likely under-using progressive disclosure'))

    # Suggested verifiability tier (a hint, not a decision).
    if OBJECTIVE_CUES.search(body):
        suggested_tier = 'objective'
    elif any(cue in heading_blob for cue in CONSTRAINT_CUES):
        suggested_tier = 'rubric'
    else:
        suggested_tier = 'subjective'

    grade = 'FAIL' if any(s == 'FAIL' for s, _ in findings) else \
            'WARN' if any(s == 'WARN' for s, _ in findings) else 'PASS'

    result = {
        'name': name,
        'path': str(skill_md),
        'grade': grade,
        'tokens': tokens,
        'suggested_tier': suggested_tier,
        'findings': [{'severity': s, 'message': m} for s, m in findings],
    }
    result.update(recommendation_for(grade, findings, suggested_tier, str(skill_md)))
    return result


def render_markdown(results: list[dict], root: Path) -> str:
    lines = [f'# Skill audit — `{root}`', '']
    if not results:
        lines.append('No `SKILL.md` files found.')
        return '\n'.join(lines)
    counts = {g: sum(1 for r in results if r['grade'] == g) for g in ('PASS', 'WARN', 'FAIL')}
    lines.append(f"{len(results)} skill(s): {counts['PASS']} PASS, {counts['WARN']} WARN, {counts['FAIL']} FAIL")
    lines.append('')
    lines.append('| Skill | Grade | Verdict | ~Tokens | Tier hint | Findings | Next action |')
    lines.append('|-------|-------|---------|---------|-----------|----------|-------------|')
    for r in results:
        lines.append(
            f"| {r['name']} | {r['grade']} | {r['verdict']} | {r['tokens']} | "
            f"{r['suggested_tier']} | {len(r['findings'])} | `{r['next_command']}` |"
        )
    lines.append('')
    for r in results:
        if not r['findings']:
            continue
        lines.append(f"## {r['name']} — {r['grade']}")
        lines.append(f"`{r['path']}`")
        lines.append('')
        for f in r['findings']:
            lines.append(f"- **{f['severity']}** {f['message']}")
        lines.append(f"- **VERDICT** {r['verdict']} via `{r['recommended_path']}` path.")
        lines.append(f"- **SUGGESTED PATCH** {r['suggested_patch_type']}.")
        lines.append(f"- **NEXT COMMAND** `{r['next_command']}`")
        lines.append(f"- **FULL LOOP?** {r['full_loop']} — only after the ROI gate in `docs/when-to-optimize.md`.")
        lines.append('')
    lines.append('---')
    lines.append('Next: run the listed `lite_improve.py` command for one keeper. The full scored loop '
                 'is secondary; use it only when reuse, verifier, and recurring failures justify it.')
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path, nargs='?', default=Path('.'))
    parser.add_argument('--json', action='store_true', help='emit JSON instead of Markdown')
    parser.add_argument('--out', type=Path, default=None, help='also write the report to this file')
    parser.add_argument('--fail-on', choices=['none', 'warn', 'fail'], default='none',
                        help='exit non-zero if any skill is at/above this grade (for CI)')
    args = parser.parse_args()

    skills = discover(args.root)
    results = [audit_one(p) for p in skills]

    report = json.dumps(results, indent=2) if args.json else render_markdown(results, args.root)
    print(report)
    if args.out:
        args.out.write_text(report + '\n', encoding='utf-8')
        print(f'\nWROTE: {args.out}', file=sys.stderr)

    if args.fail_on != 'none':
        threshold = {'warn': {'WARN', 'FAIL'}, 'fail': {'FAIL'}}[args.fail_on]
        if any(r['grade'] in threshold for r in results):
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
