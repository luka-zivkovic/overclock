# Rule catalog

Every helper finding carries one of these ids. Severity is fixed per rule unless noted. Read this
when the user asks why something was flagged or whether a finding applies to them.

## Safety

| Rule | Severity | Meaning |
| --- | --- | --- |
| `secret/literal-in-config` | high; critical when the file is tracked by git | A settings `env` value, provider key, or similar holds a literal secret instead of a reference. Rotate it. |
| `secret/mcp-literal` | high | An MCP server's env, headers, arguments, URL, or bearer token holds a literal secret. Only key names are reported. |
| `secret/credential-file-permissions` | medium | The harness credential store is readable by other accounts. |
| `perm/bypass-mode` | high | Codex `approval_policy = never` with `danger-full-access`, OpenCode `permission: "allow"`, or `bypassPermissions` in Claude Code: no approval prompt before tool calls. |
| `perm/broad-allow` | high for a full shell or an interpreter; medium for network or destructive commands; low for edits anywhere | An allow rule pre-approves far more than its author likely meant. `Bash(python3:*)` approves any Python program. |
| `perm/unsandboxed` / `perm/never-ask` / `perm/sandbox-network` | medium / low / low | Codex posture pieces that are fine alone in a container but widen the blast radius on a workstation. |
| `perm/project-mcp-autoapprove` | medium | `enableAllProjectMcpServers` starts any server a cloned repository declares. |
| `perm/trusted-broad-path` | medium | Codex trusts the home directory or `/`, so every repository beneath it is trusted. |
| `hooks/remote-exec` | critical | A hook pipes downloaded content into a shell. |
| `hooks/network` | medium | A hook sends or fetches data over the network on every matching event. |
| `mcp/unpinned-package` | medium | An MCP server launches `npx`, `uvx`, `bunx`, `pipx`, or `docker run` without a pinned version or digest, so each start may run new code. |
| `mcp/insecure-http` | medium | An MCP server uses plain HTTP to a non-loopback host. |
| `supply/unpinned-package` | medium | A Pi package or OpenCode plugin is installed without a pinned version or ref. |
| `skills/unsafe-basic` | high or medium | Basic per-skill checks when casefile did not scan the skill: download-and-execute, hidden Unicode, instruction-override phrases. |
| `casefile/<rule>` | casefile critical → high; injection and supply-chain warnings → medium; other warnings → low | Findings from an installed casefile scan of each skill and plugin. Declared capabilities such as network calls are expected for some skills; judge them against the skill's purpose. |
| `posture/no-approval-gate`, `posture/default-permissions` | info | Pi never asks before tool calls; OpenCode has no explicit bash permission. Context, not a defect. |

## Coherence

| Rule | Severity | Meaning |
| --- | --- | --- |
| `perm/allow-deny-conflict` | medium | The same rule is in allow and deny (or ask). Deny and ask win, so the allow line misleads. |
| `perm/dead-allow` | low | A broader deny rule makes an allow rule unreachable. |
| `settings/scope-override` | medium for permission and sandbox keys, low otherwise | A scalar setting differs between user, project, local, or managed scope. Precedence: managed > local > project > user. |
| `skills/duplicate-name` | medium when copies differ, low when identical | One harness discovers the same skill name more than once. It loads one copy; edits to the others do nothing. |
| `skills/cross-harness-drift` | medium | Harnesses load different copies of the same skill, so they behave differently. |
| `skills/plugin-overlap` | medium | Two plugins, or a plugin and a local skill, ship the same skill name. |
| `skills/shadows-builtin` | low | A skill or command has a built-in command's name. |
| `hooks/stacked` | medium for blocking events, low for context injection | Hooks from different sources fire on the same event and matcher. |
| `mcp/duplicate-name` | low | One server name has different definitions in different scopes. |
| `instructions/split-sources` | low | CLAUDE.md and AGENTS.md are maintained separately while harnesses that read each are both in use. |
| `agents/duplicate-name` | low | A subagent name is defined in more than one scope. |
| `judged/routing-collision`, `judged/contradiction` | medium or low | Model-confirmed findings; see judging.md in this directory. |

## Hygiene

| Rule | Severity | Meaning |
| --- | --- | --- |
| `hooks/missing-script` | high | A hook's script path does not exist, so the hook fails on every matching event. |
| `settings/parse-error` | medium | A configuration file does not parse and is ignored. |
| `instructions/missing-import` | medium | A CLAUDE.md `@path` import does not resolve. |
| `skills/invalid-frontmatter` | medium | A skill lacks a parseable frontmatter block with a description. |
| `skills/description-too-long` | medium | A description exceeds 1,024 characters. |
| `skills/name-mismatch` | low | Outside Claude Code, the declared name differs from the directory name. |
| `plugins/enabled-missing` | low | A plugin is enabled in settings but not installed. |

## Context

| Rule | Severity | Meaning |
| --- | --- | --- |
| `context/always-loaded` | low at 12,000 tokens, medium at 20,000 | Instruction files plus model-invoked skill descriptions that load every session. |
| `context/many-mcp` | low | More than eight MCP servers are configured for one harness. |
| `hooks/every-tool-call` | low | A PreToolUse or PostToolUse hook has no matcher. |

## Where each harness keeps configuration

- **Claude Code:** managed settings, `~/.claude/settings.json`, project `.claude/settings.json`
  and `.claude/settings.local.json`, `~/.claude.json` and `.mcp.json` for MCP, CLAUDE.md chain
  with `@` imports and `.claude/rules/`, skills, commands, agents, and enabled plugins.
- **Codex:** `$CODEX_HOME/config.toml` and project `.codex/config.toml` (approval, sandbox,
  profiles, MCP, trusted projects, notify), `rules/*.rules`, AGENTS.md chain, skills under
  `$CODEX_HOME/skills`, `~/.agents/skills`, and project `.agents/skills`.
- **Pi:** `~/.pi/agent` and project `.pi` settings, `mcp.json`, `models.json`, extensions,
  packages, prompts, skills, AGENTS.md or CLAUDE.md chain, SYSTEM.md and APPEND_SYSTEM.md.
- **Cursor:** `~/.cursor/cli-config.json`, project `.cursor/cli.json`, `mcp.json`, `hooks.json`,
  rules, agents, skills, and commands. Account-synced rules are not on disk.
- **OpenCode:** user and project `opencode.json(c)` (permission, MCP, plugins, providers,
  instructions), agents, commands, plugins, and skills, including the Claude-compatible skill
  directories OpenCode also reads.
