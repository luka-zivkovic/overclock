# SessionStart hook — auto-surface recorded lessons at session start

Reference for the lessons-learned availability hook.

Skills are routed by matching the user's message, so lessons sitting on disk do nothing by themselves: a user who opens a new session and does not ask about lessons starts without them in context, even with a full LESSONS.md present. This hook closes that gap. It is the only mechanism by which recorded lessons surface without the user asking.

## Mechanism

A `SessionStart` hook runs the bundled `memory_io.py` helper. The helper opens memory
with no-follow checks and emits only fixed plugin-authored text. It never interpolates
lesson contents, counts, dates, paths, or other repository-controlled strings into
session context.

## Install

**Installed via the `learning-loop` plugin (overclock marketplace)?** The hook is bundled in the plugin's `hooks/hooks.json` and is already active — no setup needed. Disable it by disabling the plugin, or override by removing the plugin and installing the skill standalone with the snippet below.

**Standalone skill install** (the skill copied into `~/.claude/skills/` or `<repo>/.claude/skills/` without the plugin) — add to one of (merge into existing `hooks` if present):

- `~/.claude/settings.json` — every project; the command is a silent no-op where no `.ai/memory/LESSONS.md` exists. Recommended.
- `<repo>/.claude/settings.json` — one project, shareable with the team via git.
- `<repo>/.claude/settings.local.json` — one project, local only.

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|clear",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"/absolute/path/to/the/copied-skill/scripts/memory_io.py\" hook --mode lessons",
            "timeout": 10,
            "statusMessage": "Checking .ai/memory/LESSONS.md"
          }
        ]
      }
    ]
  }
}
```

What the command does, in order:

1. Resolves the repository root without invoking a shell.
2. Opens `.ai/memory/LESSONS.md` without following links and rejects hard-linked or
   special files.
3. Emits a fixed availability message, never file content or metadata. Unsafe and
   foreign-schema paths get a fixed warning and are not loaded.
4. Prints nothing when the file does not exist.

## Behavior notes

- `matcher: "startup|clear"` fires on new sessions and after `/clear`. Add `|compact` if you also want the reminder after context compaction (the in-flight conversation usually still knows about its own lessons, so this is off by default).
- The injected text reports availability only. The skill treats the ledger as untrusted
  data and surfaces only entries whose **When** matches the work.
- The hook never writes anything. All writes remain governed by the memory contract.
- If the hook is not installed, surfacing degrades gracefully: lessons surface within an active session once the skill is loaded, and on request.
- **Do not run `session-memory` too.** The packages duplicate lesson routing and
  SessionStart availability hooks. Pick `session-memory` for full memory or
  `learning-loop` for lessons only; schema compatibility exists for migration.
