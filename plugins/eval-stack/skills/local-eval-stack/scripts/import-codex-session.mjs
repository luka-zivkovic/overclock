#!/usr/bin/env node
/**
 * import-codex-session — imports a Codex rollout into ironside.
 *
 * Codex writes complete session logs to
 * ~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<id>.jsonl (first record:
 * session_meta). This importer parses one rollout post-hoc and POSTs ironside
 * ingest envelope events:
 *
 *   session_meta                       -> trace       (id = rollout id, name 'codex:<repo-or-dir>')
 *   task_started .. task_complete/
 *     turn_aborted                     -> span        ('turn N', id = the log's turn_id)
 *   response_item message (assistant)  -> generation  (output text; model from turn_context;
 *                                                      token usage from the following token_count)
 *   custom/function/local_shell call
 *     + matching *_call_output         -> span        (child of the turn, paired by call_id)
 *   mcp_tool_call_end                  -> span        (start back-dated by reported duration)
 *   patch_apply_end                    -> span        (level=error when success=false)
 *
 * Best-effort by design: unknown record/payload types are skipped and counted
 * to stderr, never a crash. Known-but-deliberately-unmapped types (encrypted
 * reasoning, world_state, compaction bookkeeping, streamed agent_message
 * duplicates of the final response_item) are skipped silently.
 *
 * Idempotent by construction: observation ids derive from the rollout id plus
 * stable log identifiers (turn_id, call_id, response item id), so re-importing
 * the same rollout upserts the same rows instead of duplicating.
 *
 * Redaction/truncation mirror scripts/ironside-tracer.ts: secret-shaped strings
 * become [REDACTED], fields cap at ~50KB.
 *
 * Config: IRONSIDE_URL + IRONSIDE_API_KEY env vars, falling back to
 * ~/.pi/agent/ironside-tracer.json ({ "url", "apiKey", "environment"? }).
 *
 * Usage:
 *   node import-codex-session.mjs <rollout.jsonl> [--dry-run]
 *   node import-codex-session.mjs --latest [--dry-run]   # newest rollout under
 *       ~/.codex/sessions (for a notify hook, which gets no rollout path)
 *
 * --dry-run prints the envelope events to stdout instead of POSTing.
 * Zero npm dependencies; Node >= 18.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { basename, join } from "node:path";
import { pathToFileURL } from "node:url";

// ---------------------------------------------------------------------------
// Config (env first, tracer config file as fallback)
// ---------------------------------------------------------------------------

export const DEFAULT_CONFIG_PATH = join(homedir(), ".pi", "agent", "ironside-tracer.json");

/** Resolves { url, apiKey, environment? } from env vars, then the tracer config file. */
export function resolveConfig(env = process.env, configPath = DEFAULT_CONFIG_PATH) {
  let fileConfig = {};
  try {
    const raw = JSON.parse(readFileSync(configPath, "utf8"));
    if (raw && typeof raw === "object") fileConfig = raw;
  } catch {
    // missing/unreadable file -> env vars must carry it
  }
  const url = env.IRONSIDE_URL || (typeof fileConfig.url === "string" ? fileConfig.url : "");
  const apiKey =
    env.IRONSIDE_API_KEY || (typeof fileConfig.apiKey === "string" ? fileConfig.apiKey : "");
  if (!url || !apiKey) return null;
  const environment =
    typeof fileConfig.environment === "string" && fileConfig.environment.length > 0
      ? fileConfig.environment
      : undefined;
  return { url: url.replace(/\/+$/, ""), apiKey, ...(environment ? { environment } : {}) };
}

// ---------------------------------------------------------------------------
// Privacy + size caps (ported from scripts/ironside-tracer.ts)
// ---------------------------------------------------------------------------

/** Per-field byte cap before ingest — rollouts contain massive command outputs. */
export const MAX_FIELD_BYTES = 50_000;

const SECRET_ASSIGNMENT_RE =
  /\b([A-Za-z0-9_-]*(?:api[_-]?key|apikey|token|secret|passw(?:or)?d|credentials?|authorization)[A-Za-z0-9_-]*)(\s*[=:]\s*)(["']?)[^\s"'`]{6,}\3/gi;
const KNOWN_TOKEN_RES = [
  /\bsk-[A-Za-z0-9_-]{16,}\b/g, // OpenAI/Anthropic-style
  /\b[A-Za-z0-9]+_sk_[A-Za-z0-9]{16,}\b/g, // ironside_sk_*, coeval_sk_*, ...
  /\bgh[pousr]_[A-Za-z0-9]{20,}\b/g, // GitHub tokens
  /\bAKIA[0-9A-Z]{16}\b/g, // AWS access key id
  /\bxox[baprs]-[A-Za-z0-9-]{10,}\b/g, // Slack
  /\bBearer\s+[A-Za-z0-9._~+/=-]{16,}/g // Authorization headers
];

/** Redacts env-var-shaped assignments and well-known secret token formats. */
export function redactSecrets(text) {
  let out = text.replace(SECRET_ASSIGNMENT_RE, (_m, key, sep, quote) => {
    return `${key}${sep}${quote}[REDACTED]${quote}`;
  });
  for (const re of KNOWN_TOKEN_RES) out = out.replace(re, "[REDACTED]");
  return out;
}

/** Byte-aware truncation with an explicit marker. */
export function truncateText(text, maxBytes = MAX_FIELD_BYTES) {
  const bytes = Buffer.byteLength(text, "utf8");
  if (bytes <= maxBytes) return text;
  const sliced = Buffer.from(text, "utf8").subarray(0, maxBytes).toString("utf8");
  const clean = sliced.replace(/\uFFFD+$/, "");
  return `${clean}\n… [truncated ${bytes - maxBytes} bytes by import-codex-session]`;
}

/** Stringifies, redacts, and caps a field value for ingest. */
export function sanitizeField(value) {
  if (value === undefined || value === null) return undefined;
  let text;
  if (typeof value === "string") {
    text = value;
  } else {
    try {
      text = JSON.stringify(value);
    } catch {
      text = String(value);
    }
  }
  if (text.length === 0) return undefined;
  return truncateText(redactSecrets(text));
}

// ---------------------------------------------------------------------------
// Pure rollout -> envelope mapping
// ---------------------------------------------------------------------------

/** Joins the text parts of a Codex content array (input_text/output_text blocks). */
function extractText(content) {
  if (typeof content === "string") return content.trim();
  if (!Array.isArray(content)) return "";
  return content
    .filter((p) => p && typeof p === "object" && typeof p.text === "string")
    .map((p) => p.text)
    .join("\n")
    .trim();
}

/** Canonical ironside usage keys from a token_count usage block; absent when unknown, never zero-filled. */
function usageDetailsFromCodex(usage) {
  if (!usage || typeof usage !== "object") return undefined;
  const details = {};
  const add = (key, value) => {
    if (typeof value === "number" && Number.isFinite(value) && value > 0) {
      details[key] = Math.round(value);
    }
  };
  add("input_tokens", usage.input_tokens);
  add("output_tokens", usage.output_tokens);
  add("cache_read_input_tokens", usage.cached_input_tokens);
  add("cache_write_input_tokens", usage.cache_write_input_tokens);
  add("reasoning_output_tokens", usage.reasoning_output_tokens);
  add("total_tokens", usage.total_tokens);
  return Object.keys(details).length > 0 ? details : undefined;
}

/** Detects a skill activation: any tool input mentioning .../skills/<name>/SKILL.md. */
function skillsFromToolInput(input) {
  const text = typeof input === "string" ? input : JSON.stringify(input ?? "");
  const found = [];
  for (const m of text.matchAll(/\/skills\/([^/"'\\]+)\/SKILL\.md/g)) found.push(m[1]);
  return found;
}

// Payload/record types we understand and deliberately do not map. Everything
// outside this list and the mapped set counts as unknown on stderr.
const KNOWN_UNMAPPED = new Set([
  "world_state", // full instruction/context snapshot, huge and not an act
  "compacted", // context-compaction bookkeeping
  "turn_context", // consumed for model only
  "session_meta", // consumed for the trace
  "response_item:reasoning", // encrypted_content — nothing readable to map
  "response_item:message(user)", // event_msg:user_message already covers it
  "response_item:message(developer)", // injected instructions, not session activity
  "response_item:message(system)",
  "event_msg:agent_message", // streamed duplicate of response_item:message(assistant)
  "event_msg:agent_reasoning", // summary headlines only
  "event_msg:agent_reasoning_delta",
  "event_msg:agent_message_delta",
  "event_msg:token_count", // consumed for generation usage
  "event_msg:task_started", // consumed for turn spans
  "event_msg:task_complete", // consumed for turn spans
  "event_msg:user_message", // consumed for trace input
  "event_msg:context_compacted",
  "event_msg:thread_settings_applied",
  "event_msg:mcp_tool_call_begin" // the *_end record carries everything
]);

const CALL_TYPES = new Set(["custom_tool_call", "function_call", "local_shell_call"]);
const CALL_OUTPUT_TYPES = new Set([
  "custom_tool_call_output",
  "function_call_output",
  "local_shell_call_output"
]);

/**
 * Pure mapping: rollout JSONL lines -> ironside ingest envelope events.
 * Returns { traceId, events, skipped } where skipped counts unknown record
 * types (never a crash — a malformed line is skipped and counted).
 */
export function mapCodexSession(lines, options = {}) {
  const skipped = {};
  const skip = (key) => {
    skipped[key] = (skipped[key] ?? 0) + 1;
  };

  let traceId;
  let sessionId;
  let firstTs;
  let lastTs;
  let cwd;
  let meta = {};
  let traceInput;
  let traceOutput;
  let model;
  const skillsUsed = [];

  const turns = []; // { id, name, startTime, endTime? }
  const generations = []; // ordered; usage attaches from the following token_count
  const tools = new Map(); // call_id -> tool span row fields
  const extraSpans = []; // mcp calls, patch applies
  let turnCount = 0;
  let lastUserText;
  let gensAwaitingUsage = [];

  const currentTurn = () => (turns.length > 0 ? turns[turns.length - 1] : undefined);

  for (const line of lines) {
    if (!line.trim()) continue;
    let record;
    try {
      record = JSON.parse(line);
    } catch {
      skip("<unparsable line>");
      continue;
    }
    if (!record || typeof record !== "object") {
      skip("<non-object line>");
      continue;
    }

    const ts = typeof record.timestamp === "string" ? record.timestamp : undefined;
    if (ts) {
      if (!firstTs) firstTs = ts;
      lastTs = ts;
    }

    const type = record.type;
    const payload = record.payload && typeof record.payload === "object" ? record.payload : {};

    if (type === "session_meta") {
      // Repeats on resume — first one wins for identity, later ones only fill gaps.
      if (!traceId && typeof payload.id === "string") traceId = payload.id;
      if (!sessionId) sessionId = payload.session_id ?? payload.id;
      if (!cwd && typeof payload.cwd === "string") cwd = payload.cwd;
      meta = {
        ...meta,
        ...(typeof payload.originator === "string" ? { originator: payload.originator } : {}),
        ...(typeof payload.cli_version === "string" ? { cliVersion: payload.cli_version } : {}),
        ...(typeof payload.model_provider === "string"
          ? { modelProvider: payload.model_provider }
          : {}),
        ...(payload.git && typeof payload.git.branch === "string"
          ? { gitBranch: payload.git.branch }
          : {})
      };
      continue;
    }

    if (type === "turn_context") {
      if (typeof payload.model === "string") model = payload.model;
      if (!cwd && typeof payload.cwd === "string") cwd = payload.cwd;
      continue;
    }

    if (type === "event_msg") {
      const kind = payload.type;

      if (kind === "task_started") {
        const open = currentTurn();
        if (open && !open.endTime) open.endTime = ts ?? open.startTime;
        turnCount += 1;
        turns.push({
          id: typeof payload.turn_id === "string" ? payload.turn_id : `${traceId}:turn:${turnCount}`,
          name: `turn ${turnCount}`,
          startTime: ts ?? lastTs ?? firstTs
        });
        continue;
      }

      if (kind === "task_complete" || kind === "turn_aborted") {
        const open = currentTurn();
        if (open && !open.endTime) open.endTime = ts ?? open.startTime;
        if (typeof payload.last_agent_message === "string" && payload.last_agent_message.length > 0) {
          traceOutput = sanitizeField(payload.last_agent_message);
        }
        continue;
      }

      if (kind === "user_message") {
        if (typeof payload.message === "string" && payload.message.length > 0) {
          lastUserText = sanitizeField(payload.message);
          if (traceInput === undefined) traceInput = lastUserText;
        }
        continue;
      }

      if (kind === "token_count") {
        // token_count follows the API response whose items we just saw; attach
        // its per-call usage to generations emitted since the previous count.
        const usage = usageDetailsFromCodex(payload.info?.last_token_usage);
        if (usage) {
          for (const gen of gensAwaitingUsage) gen.usageDetails = usage;
        }
        gensAwaitingUsage = [];
        continue;
      }

      if (kind === "mcp_tool_call_end") {
        const invocation = payload.invocation ?? {};
        const durationMs =
          (payload.duration?.secs ?? 0) * 1000 + Math.round((payload.duration?.nanos ?? 0) / 1e6);
        const startTime =
          ts && durationMs > 0 ? new Date(Date.parse(ts) - durationMs).toISOString() : ts;
        const ok = payload.result?.Ok;
        const isError = payload.result?.Err !== undefined || ok?.isError === true;
        const input = sanitizeField(invocation.arguments);
        const output = sanitizeField(ok ? extractText(ok.content) || ok : payload.result?.Err);
        extraSpans.push({
          id: `${traceId}:tool:${payload.call_id ?? `mcp-${extraSpans.length}`}`,
          name: [invocation.server, invocation.tool].filter(Boolean).join(".") || "mcp-tool",
          parentId: currentTurn()?.id,
          startTime: startTime ?? lastTs,
          endTime: ts ?? lastTs,
          level: isError ? "error" : "default",
          ...(input !== undefined ? { input } : {}),
          ...(output !== undefined ? { output } : {})
        });
        continue;
      }

      if (kind === "patch_apply_end") {
        const output = sanitizeField(payload.stdout || payload.stderr);
        const changedFiles =
          payload.changes && typeof payload.changes === "object"
            ? sanitizeField(Object.keys(payload.changes))
            : undefined;
        extraSpans.push({
          id: `${traceId}:patch:${payload.call_id ?? extraSpans.length}`,
          name: "apply_patch",
          parentId: currentTurn()?.id,
          startTime: ts ?? lastTs,
          endTime: ts ?? lastTs,
          level: payload.success === false ? "error" : "default",
          ...(changedFiles !== undefined ? { input: changedFiles } : {}),
          ...(output !== undefined ? { output } : {})
        });
        continue;
      }

      if (KNOWN_UNMAPPED.has(`event_msg:${kind}`)) continue;
      skip(`event_msg:${typeof kind === "string" ? kind : "<untyped>"}`);
      continue;
    }

    if (type === "response_item") {
      const kind = payload.type;

      if (kind === "message") {
        if (payload.role !== "assistant") continue; // user/developer/system: known-unmapped
        const text = extractText(payload.content);
        const gen = {
          id: `${traceId}:gen:${payload.id ?? generations.length}`,
          parentId: currentTurn()?.id,
          startTime: ts ?? lastTs,
          endTime: ts ?? lastTs,
          ...(model ? { model } : {}),
          ...(lastUserText !== undefined ? { input: lastUserText } : {}),
          ...(text.length > 0 ? { output: sanitizeField(text) } : {})
        };
        generations.push(gen);
        gensAwaitingUsage.push(gen);
        if (text.length > 0) traceOutput = sanitizeField(text);
        continue;
      }

      if (CALL_TYPES.has(kind)) {
        const rawInput = payload.input ?? payload.arguments ?? payload.action;
        for (const skill of skillsFromToolInput(rawInput)) {
          if (!skillsUsed.includes(skill)) skillsUsed.push(skill);
        }
        const input = sanitizeField(rawInput);
        const callId = payload.call_id ?? payload.id ?? `call-${tools.size}`;
        tools.set(callId, {
          id: `${traceId}:tool:${callId}`,
          name: typeof payload.name === "string" ? payload.name : kind,
          parentId: currentTurn()?.id,
          startTime: ts ?? lastTs,
          ...(input !== undefined ? { input } : {})
        });
        continue;
      }

      if (CALL_OUTPUT_TYPES.has(kind)) {
        const span = payload.call_id ? tools.get(payload.call_id) : undefined;
        if (!span) {
          skip(`response_item:${kind}(no matching call)`);
          continue;
        }
        span.endTime = ts ?? span.startTime;
        const output = sanitizeField(extractText(payload.output) || payload.output);
        if (output !== undefined) span.output = output;
        continue;
      }

      if (KNOWN_UNMAPPED.has(`response_item:${kind}`)) continue;
      skip(`response_item:${typeof kind === "string" ? kind : "<untyped>"}`);
      continue;
    }

    if (KNOWN_UNMAPPED.has(type)) continue;
    skip(typeof type === "string" ? type : "<untyped>");
  }

  if (!traceId || !firstTs) {
    return { traceId: undefined, events: [], skipped };
  }

  const events = [
    {
      type: "trace-upsert",
      body: {
        id: traceId,
        timestamp: firstTs,
        name: `codex:${(cwd && basename(cwd)) || "session"}`,
        sessionId: sessionId ?? traceId,
        ...(options.environment ? { environment: options.environment } : {}),
        tags: skillsUsed.map((n) => `skill:${n}`),
        metadata: {
          harness: "codex",
          ...(cwd ? { cwd } : {}),
          ...meta,
          ...(skillsUsed.length > 0 ? { skills: skillsUsed.join(",") } : {})
        },
        ...(traceInput !== undefined ? { input: traceInput } : {}),
        ...(traceOutput !== undefined ? { output: traceOutput } : {})
      }
    }
  ];

  for (const turn of turns) {
    events.push({
      type: "observation-upsert",
      body: {
        id: turn.id,
        traceId,
        type: "span",
        name: turn.name,
        startTime: turn.startTime,
        endTime: turn.endTime ?? lastTs,
        metadata: {}
      }
    });
  }

  for (const gen of generations) {
    events.push({
      type: "observation-upsert",
      body: {
        id: gen.id,
        traceId,
        ...(gen.parentId ? { parentObservationId: gen.parentId } : {}),
        type: "generation",
        name: gen.model ?? "llm-call",
        startTime: gen.startTime,
        endTime: gen.endTime,
        ...(gen.model ? { model: gen.model } : {}),
        ...(gen.input !== undefined ? { input: gen.input } : {}),
        ...(gen.output !== undefined ? { output: gen.output } : {}),
        ...(gen.usageDetails ? { usageDetails: gen.usageDetails } : {}),
        metadata: {}
      }
    });
  }

  for (const span of [...tools.values(), ...extraSpans]) {
    events.push({
      type: "observation-upsert",
      body: {
        id: span.id,
        traceId,
        ...(span.parentId ? { parentObservationId: span.parentId } : {}),
        type: "span",
        name: span.name,
        startTime: span.startTime,
        endTime: span.endTime ?? lastTs,
        level: span.level ?? "default",
        ...(span.input !== undefined ? { input: span.input } : {}),
        ...(span.output !== undefined ? { output: span.output } : {}),
        metadata: {}
      }
    });
  }

  return { traceId, events, skipped };
}

// ---------------------------------------------------------------------------
// Delivery (batched POSTs, ingest hard cap 500 events per request)
// ---------------------------------------------------------------------------

export const MAX_EVENTS_PER_REQUEST = 500;

export async function postEvents(config, events, fetchImpl = fetch) {
  for (let i = 0; i < events.length; i += MAX_EVENTS_PER_REQUEST) {
    const chunk = events.slice(i, i + MAX_EVENTS_PER_REQUEST);
    const res = await fetchImpl(`${config.url}/api/v1/ingest`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${config.apiKey}`
      },
      body: JSON.stringify({ events: chunk })
    });
    if (!res.ok) {
      throw new Error(`ingest request failed: HTTP ${res.status} ${await res.text()}`);
    }
  }
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

export const DEFAULT_SESSIONS_DIR = join(homedir(), ".codex", "sessions");

/** Newest rollout-*.jsonl under ~/.codex/sessions (notify hooks get no path). */
export function findLatestRollout(root = DEFAULT_SESSIONS_DIR) {
  let latest;
  const walk = (dir) => {
    let entries;
    try {
      entries = readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(path);
      } else if (entry.name.startsWith("rollout-") && entry.name.endsWith(".jsonl")) {
        const mtime = statSync(path).mtimeMs;
        if (!latest || mtime > latest.mtime) latest = { path, mtime };
      }
    }
  };
  walk(root);
  return latest?.path;
}

async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes("--dry-run");
  let rolloutPath = args.find((a) => !a.startsWith("--"));

  if (!rolloutPath && args.includes("--latest")) {
    rolloutPath = findLatestRollout();
    if (!rolloutPath) {
      console.error(`no rollout found under ${DEFAULT_SESSIONS_DIR}`);
      process.exit(1);
    }
    console.error(`latest rollout: ${rolloutPath}`);
  }

  if (!rolloutPath) {
    console.error("usage: import-codex-session.mjs <rollout.jsonl> [--dry-run]\n" +
      "       import-codex-session.mjs --latest [--dry-run]");
    process.exit(2);
  }

  const config = resolveConfig();
  if (!config && !dryRun) {
    console.error(
      `no ironside config: set IRONSIDE_URL + IRONSIDE_API_KEY or create ${DEFAULT_CONFIG_PATH}`
    );
    process.exit(2);
  }

  const lines = readFileSync(rolloutPath, "utf8").split("\n");
  const { traceId, events, skipped } = mapCodexSession(lines, {
    ...(config?.environment ? { environment: config.environment } : {})
  });

  const skippedTotal = Object.values(skipped).reduce((a, b) => a + b, 0);
  if (skippedTotal > 0) {
    console.error(
      `skipped ${skippedTotal} unknown record(s): ` +
        Object.entries(skipped)
          .map(([k, v]) => `${k}=${v}`)
          .join(", ")
    );
  }
  if (events.length === 0) {
    console.error("no mappable events found — nothing to import");
    process.exit(1);
  }

  if (dryRun) {
    console.log(JSON.stringify({ events }, null, 2));
    console.error(`dry-run: ${events.length} event(s) for trace ${traceId}`);
    return;
  }

  await postEvents(config, events);
  console.error(`imported trace ${traceId}: ${events.length} event(s) -> ${config.url}`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(String(error?.message ?? error));
    process.exit(1);
  });
}
