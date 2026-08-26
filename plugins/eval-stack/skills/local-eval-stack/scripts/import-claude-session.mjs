#!/usr/bin/env node
/**
 * import-claude-session — imports a Claude Code transcript into ironside.
 *
 * Claude Code writes complete session logs to
 * ~/.claude/projects/<project-slug>/<session-id>.jsonl. This importer parses
 * one transcript post-hoc and POSTs ironside ingest envelope events:
 *
 *   session                    -> trace       (id = session id, name 'cc:<repo-or-slug>')
 *   user prompt .. next prompt -> span        ('turn N', child of trace)
 *   assistant API message      -> generation  (model, output, token usage; streamed
 *                                              chunks sharing message.id merge into one)
 *   tool_use / tool_result     -> span        (child of the turn; level=error on is_error)
 *
 * Idempotent by construction: every observation id derives from the session id
 * plus a stable log identifier (message.id, tool_use id, turn ordinal), so
 * re-importing the same transcript upserts the same rows instead of duplicating.
 *
 * Redaction/truncation mirror scripts/ironside-tracer.ts: secret-shaped strings
 * become [REDACTED], fields cap at ~50KB.
 *
 * Config: IRONSIDE_URL + IRONSIDE_API_KEY env vars, falling back to
 * ~/.pi/agent/ironside-tracer.json ({ "url", "apiKey", "environment"? }).
 *
 * Usage:
 *   node import-claude-session.mjs <transcript.jsonl> [--dry-run]
 *   ... | node import-claude-session.mjs --hook-stdin   # Stop hook: reads the
 *       hook's stdin JSON and imports its transcript_path
 *
 * --dry-run prints the envelope events to stdout instead of POSTing.
 * Zero npm dependencies; Node >= 18.
 */

import { readFileSync } from "node:fs";
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

/** Per-field byte cap before ingest — transcripts contain massive read results. */
export const MAX_FIELD_BYTES = 50_000;

const SECRET_ASSIGNMENT_RE =
  /((?:["']?)[A-Za-z0-9_-]*(?:api[_-]?key|apikey|token|secret|passw(?:or)?d|credentials?|authorization)[A-Za-z0-9_-]*(?:["']?)\s*[=:]\s*)(["']?)([^\s"'`,}\[\]]{6,})\2/gi;
const KNOWN_TOKEN_RES = [
  /\bsk-[A-Za-z0-9_-]{16,}\b/g, // OpenAI/Anthropic-style
  /\b[A-Za-z0-9]+_(?:sk|sc)_[A-Za-z0-9_-]{16,}\b/g, // ironside_sk_*, ironside_sc_*, ...
  /\bgh[pousr]_[A-Za-z0-9]{20,}\b/g, // GitHub tokens
  /\bAKIA[0-9A-Z]{16}\b/g, // AWS access key id
  /\bxox[baprs]-[A-Za-z0-9-]{10,}\b/g, // Slack
  /\bBearer\s+[A-Za-z0-9._~+/=-]{16,}/gi // Authorization headers
];

/** Redacts env-var-shaped assignments and well-known secret token formats. */
export function redactSecrets(text) {
  let out = text;
  for (const re of KNOWN_TOKEN_RES) out = out.replace(re, "[REDACTED]");
  out = out.replace(SECRET_ASSIGNMENT_RE, (_m, prefix, quote) => {
    return `${prefix}${quote}[REDACTED]${quote}`;
  });
  return out;
}

/** Byte-aware truncation with an explicit marker. */
export function truncateText(text, maxBytes = MAX_FIELD_BYTES) {
  const bytes = Buffer.byteLength(text, "utf8");
  if (bytes <= maxBytes) return text;
  const sliced = Buffer.from(text, "utf8").subarray(0, maxBytes).toString("utf8");
  const clean = sliced.replace(/\uFFFD+$/, "");
  return `${clean}\n… [truncated ${bytes - maxBytes} bytes by import-claude-session]`;
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
// Pure transcript -> envelope mapping
// ---------------------------------------------------------------------------

/** Joins the text parts of a Claude message content value (string or block array). */
function extractText(content) {
  if (typeof content === "string") return content.trim();
  if (!Array.isArray(content)) return "";
  return content
    .filter((p) => p && typeof p === "object" && p.type === "text" && typeof p.text === "string")
    .map((p) => p.text)
    .join("\n")
    .trim();
}

/** Canonical ironside usage keys from a Claude API usage block; absent when unknown, never zero-filled. */
function usageDetailsFromClaude(usage) {
  if (!usage || typeof usage !== "object") return undefined;
  const details = {};
  const add = (key, value) => {
    if (typeof value === "number" && Number.isFinite(value) && value > 0) {
      details[key] = Math.round(value);
    }
  };
  add("input_tokens", usage.input_tokens);
  add("output_tokens", usage.output_tokens);
  add("cache_read_input_tokens", usage.cache_read_input_tokens);
  add("cache_write_input_tokens", usage.cache_creation_input_tokens);
  return Object.keys(details).length > 0 ? details : undefined;
}

/** Detects a skill activation: any tool input mentioning .../skills/<name>/SKILL.md. */
function skillsFromToolInput(input) {
  const text = typeof input === "string" ? input : JSON.stringify(input ?? "");
  const found = [];
  for (const m of text.matchAll(/\/skills\/([^/"'\\]+)\/SKILL\.md/g)) found.push(m[1]);
  return found;
}

/**
 * Pure mapping: transcript JSONL lines -> ironside ingest envelope events.
 * Returns { traceId, events, skipped } where skipped counts unmapped record
 * types (never a crash — a malformed line is skipped and counted).
 */
export function mapClaudeSession(lines, options = {}) {
  const skipped = {};
  const skip = (key) => {
    skipped[key] = (skipped[key] ?? 0) + 1;
  };

  let sessionId = options.sessionIdFallback;
  let firstTs;
  let lastTs;
  let cwd;
  let gitBranch;
  let version;
  let slug;
  let traceInput;
  let traceOutput;
  const skillsUsed = [];

  const turns = []; // { id, name, startTime, endTime? }
  const generations = new Map(); // message.id -> generation row fields
  const tools = new Map(); // tool_use id -> tool span row fields
  let turnCount = 0;
  let lastUserText;

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

    if (typeof record.sessionId === "string" && !sessionId) sessionId = record.sessionId;
    if (typeof record.timestamp === "string") {
      if (!firstTs) firstTs = record.timestamp;
      lastTs = record.timestamp;
    }
    if (typeof record.cwd === "string" && !cwd) cwd = record.cwd;
    if (typeof record.gitBranch === "string" && !gitBranch) gitBranch = record.gitBranch;
    if (typeof record.version === "string" && !version) version = record.version;
    if (typeof record.slug === "string" && !slug) slug = record.slug;

    const type = record.type;

    if (type === "user") {
      const content = record.message?.content;
      const parts = Array.isArray(content) ? content : [];

      // tool_result blocks close the matching tool_use span.
      for (const part of parts) {
        if (!part || typeof part !== "object" || part.type !== "tool_result") continue;
        const span = tools.get(part.tool_use_id);
        if (!span) continue;
        span.endTime = record.timestamp ?? span.startTime;
        span.level = part.is_error ? "error" : "default";
        const output = sanitizeField(part.content);
        if (output !== undefined) span.output = output;
      }

      // A real user prompt starts a new turn. isMeta covers injected caveats
      // and other non-prompt user records.
      if (record.isMeta === true) continue;
      const text = extractText(content);
      if (text.length === 0) continue;
      lastUserText = sanitizeField(text);
      if (traceInput === undefined) traceInput = lastUserText;
      const open = currentTurn();
      if (open && !open.endTime) open.endTime = record.timestamp ?? open.startTime;
      turnCount += 1;
      turns.push({
        id: `${sessionId}:turn:${turnCount}`,
        name: `turn ${turnCount}`,
        startTime: record.timestamp ?? lastTs ?? firstTs
      });
      continue;
    }

    if (type === "assistant") {
      const message = record.message ?? {};
      const msgId = typeof message.id === "string" ? message.id : record.uuid;
      const ts = record.timestamp;
      // Streamed chunks of one API message share message.id — merge them.
      let gen = generations.get(msgId);
      if (!gen) {
        gen = {
          id: `${sessionId}:gen:${msgId}`,
          parentId: currentTurn()?.id,
          startTime: ts,
          endTime: ts,
          texts: [],
          input: lastUserText
        };
        generations.set(msgId, gen);
      }
      if (ts) gen.endTime = ts;
      if (typeof message.model === "string") gen.model = message.model;
      if (typeof message.stop_reason === "string") gen.stopReason = message.stop_reason;
      const usage = usageDetailsFromClaude(message.usage);
      if (usage) gen.usageDetails = usage;

      const parts = Array.isArray(message.content) ? message.content : [];
      for (const part of parts) {
        if (!part || typeof part !== "object") continue;
        if (part.type === "text" && typeof part.text === "string") {
          gen.texts.push(part.text);
        } else if (part.type === "tool_use") {
          for (const skill of skillsFromToolInput(part.input)) {
            if (!skillsUsed.includes(skill)) skillsUsed.push(skill);
          }
          const input = sanitizeField(part.input);
          tools.set(part.id, {
            id: `${sessionId}:tool:${part.id}`,
            name: typeof part.name === "string" ? part.name : "tool",
            parentId: currentTurn()?.id,
            startTime: ts,
            ...(input !== undefined ? { input } : {})
          });
        }
      }
      continue;
    }

    // queue-operation, last-prompt, attachment, mode, system, file-history-*, ...
    skip(typeof type === "string" ? type : "<untyped>");
  }

  if (!sessionId || !firstTs) {
    return { traceId: undefined, events: [], skipped };
  }

  // Trace output = last assistant text produced.
  for (const gen of generations.values()) {
    const text = gen.texts.join("\n").trim();
    if (text.length > 0) traceOutput = sanitizeField(text);
  }

  const repoOrSlug = (cwd && basename(cwd)) || slug || "session";
  const events = [
    {
      type: "trace-upsert",
      body: {
        id: sessionId,
        timestamp: firstTs,
        name: `cc:${repoOrSlug}`,
        sessionId,
        ...(options.environment ? { environment: options.environment } : {}),
        tags: skillsUsed.map((n) => `skill:${n}`),
        metadata: {
          harness: "claude-code",
          ...(cwd ? { cwd } : {}),
          ...(gitBranch ? { gitBranch } : {}),
          ...(version ? { version } : {}),
          ...(slug ? { slug } : {}),
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
        traceId: sessionId,
        type: "span",
        name: turn.name,
        startTime: turn.startTime,
        endTime: turn.endTime ?? lastTs,
        metadata: {}
      }
    });
  }

  for (const gen of generations.values()) {
    const output = sanitizeField(gen.texts.join("\n").trim());
    events.push({
      type: "observation-upsert",
      body: {
        id: gen.id,
        traceId: sessionId,
        ...(gen.parentId ? { parentObservationId: gen.parentId } : {}),
        type: "generation",
        name: gen.model ?? "llm-call",
        startTime: gen.startTime,
        endTime: gen.endTime,
        ...(gen.model ? { model: gen.model } : {}),
        ...(gen.input !== undefined ? { input: gen.input } : {}),
        ...(output !== undefined ? { output } : {}),
        ...(gen.usageDetails ? { usageDetails: gen.usageDetails } : {}),
        metadata: { ...(gen.stopReason ? { stopReason: gen.stopReason } : {}) }
      }
    });
  }

  for (const span of tools.values()) {
    events.push({
      type: "observation-upsert",
      body: {
        id: span.id,
        traceId: sessionId,
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

  return { traceId: sessionId, events, skipped };
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

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
}

async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes("--dry-run");
  const hookStdin = args.includes("--hook-stdin");
  let transcriptPath = args.find((a) => !a.startsWith("--"));

  if (hookStdin) {
    // Claude Code Stop hook: stdin carries JSON with transcript_path.
    try {
      const hookInput = JSON.parse(await readStdin());
      if (typeof hookInput.transcript_path === "string") {
        transcriptPath = hookInput.transcript_path;
      }
    } catch {
      // fall through to the usage error below
    }
  }

  if (!transcriptPath) {
    console.error(
      "usage: import-claude-session.mjs <transcript.jsonl> [--dry-run]\n" +
        "       ... | import-claude-session.mjs --hook-stdin [--dry-run]"
    );
    process.exit(2);
  }

  // Subagent transcripts (<session>/subagents/agent-*.jsonl) reuse the parent
  // sessionId, so importing one would overwrite the parent trace's rows.
  if (/[\\/]subagents[\\/]/.test(transcriptPath)) {
    console.error(
      "refusing subagent transcript: it shares the parent sessionId, so its rows " +
        "would collide with the parent trace — import the parent <session>.jsonl instead"
    );
    process.exit(2);
  }

  const config = resolveConfig();
  if (!config && !dryRun) {
    console.error(
      `no ironside config: set IRONSIDE_URL + IRONSIDE_API_KEY or create ${DEFAULT_CONFIG_PATH}`
    );
    process.exit(2);
  }

  const lines = readFileSync(transcriptPath, "utf8").split("\n");
  const { traceId, events, skipped } = mapClaudeSession(lines, {
    sessionIdFallback: basename(transcriptPath, ".jsonl"),
    ...(config?.environment ? { environment: config.environment } : {})
  });

  const skippedTotal = Object.values(skipped).reduce((a, b) => a + b, 0);
  if (skippedTotal > 0) {
    console.error(
      `skipped ${skippedTotal} unmapped record(s): ` +
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
