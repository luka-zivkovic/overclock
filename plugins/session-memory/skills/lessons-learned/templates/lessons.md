# LESSONS.md template

Fill-in-ready skeleton for `.ai/memory/LESSONS.md`. Copy the skeleton when creating the file for the first time; copy the entry block when appending a new lesson. Replace every `<...>` placeholder with real content. Keep field order exactly as shown — the contract requires stable ordering, and updates edit `Count`/`Last reinforced` in place rather than appending duplicates. Target under 200 lines total.

## Skeleton

```markdown
<!-- memory-schema: v1 -->
# Lessons

## <Short imperative lesson title, e.g. "Use pnpm, not npm">
- **When:** <trigger condition — the concrete situation where this lesson applies>
- **Wrong:** <the approach that failed or was corrected>
- **Right:** <the approach to use instead>
- **Evidence:** <[user-correction] or [agent-observed] plus what actually happened>
- **Count:** 1
- **Last reinforced:** <ISO-8601 date>
```

## Entry rules

- One `##` section per lesson; new lessons are appended at the end.
- A repeat of an existing lesson (matched on meaning, not wording) edits that entry's `Count` and `Last reinforced` in place — never append a duplicate.
- A contradiction (user changed their mind) rewrites the existing entry to the new position, resets `Count` to 1, and notes the reversal in `Evidence`.
- `When:` must describe a recognizable situation, because it is the matching key for surfacing lessons at task start.
- No secrets, tokens, or credentials in any field — redact as `<redacted: ...>`.

## Worked example

```markdown
<!-- memory-schema: v1 -->
# Lessons

## Use pnpm, not npm
- **When:** installing, adding, or updating JS dependencies in this repo
- **Wrong:** running `npm install` / `npm i <pkg>` — creates package-lock.json, which conflicts with the committed pnpm-lock.yaml and breaks CI
- **Right:** use `pnpm install` / `pnpm add <pkg>`; the repo is a pnpm workspace
- **Evidence:** [user-correction] 2026-06-03: "no, don't use npm here, this is a pnpm workspace"; [user-correction] 2026-06-10: "stop running npm install — I already told you this" after npm install regenerated package-lock.json
- **Count:** 2
- **Last reinforced:** 2026-06-10
```
