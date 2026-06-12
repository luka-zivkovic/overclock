# SessionStart hook — auto-load parked memory at session start

Shared reference for the session-handoff and lessons-learned skills. Both skills ship a byte-identical copy of this file.

Skills are routed by matching the user's message, so a handoff sitting on disk does nothing by itself: a user who opens a new session and does not say "resume" starts cold even with a perfect HANDOFF.md present. This hook closes that gap. It is **optional** — both skills work without it — and it is the only mechanism by which parked memory surfaces without the user asking.

## Mechanism

A `SessionStart` hook runs a shell command when a session starts; whatever the command prints to stdout is injected into the session's context before the first prompt. Skills cannot enable hooks themselves — the snippet below must live in a `settings.json` that you control.

## Install

**Installed via the `session-memory` plugin (overclock marketplace)?** The hook is bundled in the plugin's `hooks/hooks.json` and is already active — no setup needed. Disable it by disabling the plugin, or override by removing the plugin and installing the skills standalone with the snippet below.

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
            "command": "sh -c 'r=$(git rev-parse --show-toplevel 2>/dev/null || pwd); m=\"$r/.ai/memory\"; if [ -f \"$m/HANDOFF.md\" ]; then d=$(sed -n \"s/^Saved: //p\" \"$m/HANDOFF.md\" | head -1); echo \"Parked session handoff at .ai/memory/HANDOFF.md (saved: ${d:-unknown}). If the first user message relates to that prior work, offer to resume it via the session-handoff skill. If it is an unrelated new task, mention the parked handoff in one line and move on.\"; fi; if [ -f \"$m/LESSONS.md\" ]; then echo \"$(grep -c \"^## \" \"$m/LESSONS.md\") project lesson(s) recorded in .ai/memory/LESSONS.md - before acting, consult entries whose When condition matches the work.\"; fi'",
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

1. Resolves the repository root (`git rev-parse --show-toplevel`, falling back to the cwd) so it honors the contract's monorepo-root rule.
2. If `HANDOFF.md` exists: emits its `Saved:` date plus a two-sentence instruction — offer to resume if the first message relates to the prior work; otherwise mention the parked handoff in one line only. It does not inject the handoff body; the resume flow reads and verifies the file properly.
3. If `LESSONS.md` exists: emits the lesson count plus an instruction to consult entries whose **When** condition matches the work.
4. Prints nothing when neither file exists — zero noise in projects that do not use these skills.

## Behavior notes

- `matcher: "startup|clear"` fires on new sessions and after `/clear`. Add `|compact` if you also want the reminder after context compaction (the in-flight conversation usually still knows about its own handoff, so this is off by default).
- The injected text is an instruction to *offer* resuming, not to resume. The user keeps control; an unrelated first message gets a one-line mention at most.
- The hook never writes anything. All writes remain governed by the memory contract.
- If the hook is not installed, surfacing degrades gracefully: resume happens when the user asks, and lessons surface during resume, on request, or when a skill is active for another reason.
