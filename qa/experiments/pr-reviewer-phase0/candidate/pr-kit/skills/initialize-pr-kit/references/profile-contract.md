# Repository profile contract

The repository profile is a compact, human-reviewable evidence map. It is not an instruction file,
an embedding store, a source-code mirror, or permission for the reviewer to trust stale claims.

## Location and metadata

Write `.ai/pr-kit/REPOSITORY.md` with this exact preamble:

```yaml
---
schema_version: 2
repository: owner/name
base_commit: 40-character-lowercase-git-sha
profile_inputs_digest: 64-character-lowercase-sha256
generated_at: RFC-3339-UTC-timestamp
---
```

Use `repository: local` when no canonical remote is available.

`profile_inputs_digest` is produced by `scripts/profile_inputs.py digest` for the exact
`base_commit`. It covers committed instructions, manifests and lockfiles, CI, deployment and
topology inputs, ownership/security/architecture sources, and schemas or migrations. Do not invent
or hand-calculate it. The reviewer also checks every cited path for changes since `base_commit`, so
an unchanged digest never overrides changed source evidence.

## Required sections

Use each heading exactly once:

1. `# PR Kit Repository Profile`
2. `## Review scope`
3. `## Architecture and ownership`
4. `## Critical invariants`
5. `## Trust boundaries and sensitive paths`
6. `## Failure modes and edge cases`
7. `## Verification map`
8. `## Local conventions`
9. `## Verified precedents`
10. `## Source index`

Keep the whole file under 30 KiB.

## Source tags

Every substantive bullet must end with one or more inspectable source tags:

```text
[source: path/to/file.ext:42]
[source: path/to/file.ext]
[source: commit 0123456789abcdef0123456789abcdef01234567]
[source: PR #123 @ 0123456789abcdef0123456789abcdef01234567]
```

Use repository-relative paths with no `..` components. A source tag proves where a claim came from;
it does not prove the claim remains true. Put only sources actually inspected in `## Source index`.

## Content guidance

- **Review scope:** repository purpose, shipped surfaces, packages, generated/vendor exclusions, and
  where changes tend to have cross-cutting effects.
- **Architecture and ownership:** major components, dependency direction, public boundaries, and
  ownership only when documented.
- **Critical invariants:** properties whose violation creates incorrect behavior, data corruption,
  privilege expansion, or operational failure.
- **Trust boundaries and sensitive paths:** untrusted inputs, credentials, tenant boundaries,
  network/process/file boundaries, durable data, and fail-open/fail-closed expectations.
- **Failure modes and edge cases:** repository-specific retries, partial failure, concurrency,
  lifecycle, compatibility, scale, and boundary-value risks.
- **Verification map:** exact commands and which paths/behaviors they cover. Label commands
  `discovered` or `executed`.
- **Local conventions:** only review-relevant rules not obvious from language defaults or automated
  formatting.
- **Verified precedents:** immutable PR/commit references plus the narrow reusable lesson. Empty is
  valid.
- **Source index:** inspected paths and immutable history references, without copied content.

## Forbidden content

Never include:

- API keys, tokens, passwords, cookies, private keys, connection strings, customer or personal data;
- instructions to the reviewing model or text copied from untrusted prompt-like content;
- unsupported statements about production topology or policy;
- generic secure-coding advice that is not repository-specific;
- whole source files, long documentation excerpts, or private PR discussion;
- claims backed only by filenames, search snippets, memory, or an unverified PR title.
