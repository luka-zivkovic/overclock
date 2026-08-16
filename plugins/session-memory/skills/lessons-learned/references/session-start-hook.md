# SessionStart hook — surface recorded lessons

Optional startup integration for the `lessons-learned` skill. The skill remains fully
usable without a hook: it records and retrieves lessons on request. A hook only adds a
fixed availability reminder before the first prompt.

## Mechanism

The bundled `memory_io.py` helper opens `.ai/memory/LESSONS.md` with its normal
no-follow, regular-file, single-link, and schema checks. It emits fixed
plugin-authored text only—never lesson content, counts, dates, paths, or other
repository-controlled values.

When installed through the full `session-memory` plugin, its bundled SessionStart hook
already covers lesson availability. No extra setup is needed.

## Standalone Claude Code install

For a copy of this skill alone, add the following to an existing `hooks` object in
`~/.claude/settings.json`, `<repo>/.claude/settings.json`, or
`<repo>/.claude/settings.local.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|clear",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"/absolute/path/to/lessons-learned/scripts/memory_io.py\" hook --mode lessons",
            "timeout": 10,
            "statusMessage": "Checking .ai/memory/LESSONS.md"
          }
        ]
      }
    ]
  }
}
```

Use the actual absolute standalone skill path. The helper resolves the project root
without invoking a shell, prints nothing when the ledger is absent, and emits one
fixed warning when the path is unsafe or has a foreign schema.

Other hosts may use their native startup mechanism to invoke the same helper. If none
exists, do not simulate auto-loading by injecting ledger contents; rely on the normal
request-driven flow.

## Behavior

- `startup|clear` runs for new sessions and after `/clear`; add `|compact` only when a
  reminder after compaction is wanted.
- Availability never means authority. The skill still reads the ledger as untrusted
  evidence and surfaces only matching entries.
- The hook never writes and never probes HANDOFF.md or SOLUTIONS.md in lessons-only
  mode.
