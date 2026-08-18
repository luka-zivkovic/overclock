# SessionStart hook — auto-load parked memory at session start

Optional startup integration for the `session-handoff` skill. The lessons-only skill carries its
own narrower hook reference and command.

Skills are routed by matching the user's message, so a handoff sitting on disk does nothing by
itself: a user who opens a new session and does not say "resume" starts cold even with a perfect
HANDOFF.md present. This hook closes that gap. It is **optional** — session-handoff works without
it — and it is the only mechanism by which parked handoff state surfaces without the user asking.

## Mechanism

A `SessionStart` hook runs the bundled `memory_io.py` helper when a session starts;
whatever it prints to stdout is injected into context before the first prompt. The
helper performs no-follow, regular-file checks and emits only fixed text authored by
the plugin. It never interpolates a `Saved:` value, lesson text, path content, or other
repository-controlled string.

## Install

**Installed via the `session-memory` plugin (overclock marketplace)?** The hook is bundled in the
plugin's `hooks/hooks.json` and is already active — no setup needed. Disable it by disabling the
plugin, or override by removing the plugin and installing session-handoff alone with the snippet
below.

**Standalone skill install:** add to one of (merge into existing `hooks` if present):

- `~/.claude/settings.json` — every project; the command is a silent no-op where no `.ai/memory/` exists. Recommended.
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
            "command": "python3 \"/absolute/path/to/the/copied-skill/scripts/memory_io.py\" hook --mode session",
            "timeout": 10,
            "statusMessage": "Checking .ai/memory/"
          }
        ]
      }
    ]
  }
}
```

What the command does, in order:

1. Resolves the repository root without invoking a shell.
2. Opens `.ai/memory/` through no-follow directory descriptors and refuses symlinked
   parents or targets, hard links, and special files.
3. Emits a fixed handoff/lessons availability message. It never injects file contents
   or metadata; the actual skill reads and verifies the file as untrusted data.
4. Prints nothing when neither file exists. An unsafe or foreign-schema path gets one
   fixed warning and is not loaded.

## Behavior notes

- `matcher: "startup|clear"` fires on new sessions and after `/clear`. Add `|compact` if you also want the reminder after context compaction (the in-flight conversation usually still knows about its own handoff, so this is off by default).
- The injected text never resumes automatically. The user keeps control, and memory
  remains untrusted until the relevant skill verifies it.
- The hook never writes anything. All writes remain governed by the memory contract.
- If the hook is not installed, surfacing degrades gracefully: resume happens when the user asks, and lessons surface during resume, on request, or when a skill is active for another reason.
