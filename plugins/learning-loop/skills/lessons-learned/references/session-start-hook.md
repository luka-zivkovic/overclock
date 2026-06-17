# SessionStart hook — auto-surface recorded lessons at session start

Reference for the lessons-learned skill's bundled hook.

Skills are routed by matching the user's message, so lessons sitting on disk do nothing by themselves: a user who opens a new session and does not ask about lessons starts without them in context, even with a full LESSONS.md present. This hook closes that gap. It is the only mechanism by which recorded lessons surface without the user asking.

## Mechanism

A `SessionStart` hook runs a shell command when a session starts; whatever the command prints to stdout is injected into the session's context before the first prompt. Skills cannot enable hooks themselves — the snippet below must live in a `hooks.json`/`settings.json` that is loaded for the session.

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
            "command": "sh -c 'r=$(git rev-parse --show-toplevel 2>/dev/null || pwd); m=\"$r/.ai/memory\"; if [ -f \"$m/LESSONS.md\" ]; then echo \"$(grep -c \"^## \" \"$m/LESSONS.md\") project lesson(s) recorded in .ai/memory/LESSONS.md - before acting, consult entries whose When condition matches the work.\"; fi'",
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

1. Resolves the repository root (`git rev-parse --show-toplevel`, falling back to the cwd) so it honors the contract's monorepo-root rule.
2. If `LESSONS.md` exists: emits the lesson count plus an instruction to consult entries whose **When** condition matches the work.
3. Prints nothing when the file does not exist — zero noise in projects that do not use this skill.

## Behavior notes

- `matcher: "startup|clear"` fires on new sessions and after `/clear`. Add `|compact` if you also want the reminder after context compaction (the in-flight conversation usually still knows about its own lessons, so this is off by default).
- The injected text is an instruction to *consult* matching lessons, not to act on all of them blindly — surface only entries whose **When** matches the work at hand.
- The hook never writes anything. All writes remain governed by the memory contract.
- If the hook is not installed, surfacing degrades gracefully: lessons surface within an active session once the skill is loaded, and on request.
- **Running the `session-memory` plugin too?** Its hook already emits this same lesson-count line (plus a handoff line). Installing both plugins double-counts the lessons output. Pick one: `session-memory` if you want handoff + lessons, `learning-loop` if you want only the learning loop.
