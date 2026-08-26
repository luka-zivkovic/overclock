/**
 * ironside-tracer — traces every pi session into the local ironside instance.
 *
 * Mapping (see ~/Projects/pi-ironside-tracer-brief.md):
 *   pi session        -> trace   (id = session id; sessionId groups; metadata.cwd/.repo)
 *   assistant turn    -> span    (child of trace)
 *   LLM call          -> generation (model, output, usageDetails, costDetails)
 *   tool execution    -> span    (child of the turn span; level=error on failure)
 *
 * Contract: ironside trace-envelope v1 (~/Projects/ironside/spec/trace-envelope-v1.md).
 * Upserts are full-row replace, so every update re-sends all fields.
 * Traces settle via a quiet-period watermark (300s) — no finalize event, but
 * we flush on agent_end and session_shutdown so the watermark ticks from the
 * real end of activity.
 *
 * Config: ~/.pi/agent/ironside-tracer.json
 *   { "url": "http://localhost:18788", "apiKey": "ironside_sk_...", "environment": "dev" }
 * (contains a key — never sync/commit this file).
 *
 * Kill switch: IRONSIDE_TRACER_DISABLE=1
 *
 * Fail-open is non-negotiable: tracing must never break a session. Every
 * handler swallows errors; network failures are logged once and dropped.
 *
 * The session->envelope mapping is a pure function (mapTracerEvent) so it can
 * be driven headlessly — see ~/.pi/agent/ironside-tracer.test.ts.
 */

import { randomUUID } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

export interface TracerConfig {
  url: string;
  apiKey: string;
  environment?: string;
}

export const DEFAULT_CONFIG_PATH = join(homedir(), ".pi", "agent", "ironside-tracer.json");

/** Loads the tracer config. Returns null (tracing disabled) on any problem — fail open. */
export function loadTracerConfig(path: string = DEFAULT_CONFIG_PATH): TracerConfig | null {
  try {
    const raw = JSON.parse(readFileSync(path, "utf8")) as Record<string, unknown>;
    if (
      typeof raw.url === "string" &&
      raw.url.length > 0 &&
      typeof raw.apiKey === "string" &&
      raw.apiKey.length > 0
    ) {
      return {
        url: raw.url.replace(/\/+$/, ""),
        apiKey: raw.apiKey,
        ...(typeof raw.environment === "string" && raw.environment.length > 0
          ? { environment: raw.environment }
          : {})
      };
    }
  } catch {
    // missing/unreadable/invalid JSON -> disabled
  }
  return null;
}

// ---------------------------------------------------------------------------
// Privacy + size caps
// ---------------------------------------------------------------------------

/** Per-field byte cap before ingest — sessions contain massive read results. */
export const MAX_FIELD_BYTES = 50_000;

// Env-var-shaped assignments (API_KEY=..., token: "...") and well-known token
// formats. Starting point: casefile's secret-env-read patterns.
const SECRET_ASSIGNMENT_RE =
  /((?:["']?)[A-Za-z0-9_-]*(?:api[_-]?key|apikey|token|secret|passw(?:or)?d|credentials?|authorization)[A-Za-z0-9_-]*(?:["']?)\s*[=:]\s*)(["']?)([^\s"'`,}\[\]]{6,})\2/gi;
const KNOWN_TOKEN_RES: RegExp[] = [
  /\bsk-[A-Za-z0-9_-]{16,}\b/g, // OpenAI/Anthropic-style
  /\b[A-Za-z0-9]+_(?:sk|sc)_[A-Za-z0-9_-]{16,}\b/g, // ironside_sk_*, ironside_sc_*, ...
  /\bgh[pousr]_[A-Za-z0-9]{20,}\b/g, // GitHub tokens
  /\bAKIA[0-9A-Z]{16}\b/g, // AWS access key id
  /\bxox[baprs]-[A-Za-z0-9-]{10,}\b/g, // Slack
  /\bBearer\s+[A-Za-z0-9._~+/=-]{16,}/gi // Authorization headers
];

/** Redacts env-var-shaped assignments and well-known secret token formats. */
export function redactSecrets(text: string): string {
  let out = text;
  for (const re of KNOWN_TOKEN_RES) out = out.replace(re, "[REDACTED]");
  out = out.replace(SECRET_ASSIGNMENT_RE, (_m, prefix: string, quote: string) => {
    return `${prefix}${quote}[REDACTED]${quote}`;
  });
  return out;
}

/** Byte-aware truncation with an explicit marker. */
export function truncateText(text: string, maxBytes: number = MAX_FIELD_BYTES): string {
  const bytes = Buffer.byteLength(text, "utf8");
  if (bytes <= maxBytes) return text;
  const sliced = Buffer.from(text, "utf8").subarray(0, maxBytes).toString("utf8");
  // strip a possibly-broken trailing code point artifact (replacement char)
  const clean = sliced.replace(/\uFFFD+$/, "");
  return `${clean}\n… [truncated ${bytes - maxBytes} bytes by ironside-tracer]`;
}

/** Stringifies, redacts, and caps a field value for ingest. */
export function sanitizeField(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  let text: string;
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
// Pure session -> envelope mapping
// ---------------------------------------------------------------------------

export type IngestEventType = "trace-upsert" | "observation-upsert" | "score-upsert";

export interface IngestRequestEvent {
  type: IngestEventType;
  body: Record<string, unknown>;
}

/** Token/cost usage as pi reports it on assistant messages. */
export interface PiUsage {
  input?: number;
  output?: number;
  cacheRead?: number;
  cacheWrite?: number;
  reasoning?: number;
  totalTokens?: number;
  cost?: {
    input?: number;
    output?: number;
    cacheRead?: number;
    cacheWrite?: number;
    total?: number;
  };
}

/** Normalized pi session events the mapper consumes. `at` is epoch ms. */
export type TracerEvent =
  | {
      kind: "session_start";
      sessionId: string;
      cwd: string;
      repo?: string;
      environment?: string;
      at: number;
    }
  | { kind: "user_message"; text: string; at: number }
  | { kind: "turn_start"; at: number }
  | {
      kind: "assistant_message";
      text: string;
      model?: string;
      provider?: string;
      stopReason?: string;
      errorMessage?: string;
      usage?: PiUsage;
      /** When the assistant message started streaming (epoch ms). */
      startedAt?: number;
      at: number;
    }
  | { kind: "tool_start"; toolCallId: string; toolName: string; args: unknown; at: number }
  | {
      kind: "tool_end";
      toolCallId: string;
      toolName: string;
      output: unknown;
      isError: boolean;
      at: number;
    }
  | { kind: "turn_end"; at: number }
  | { kind: "session_end"; at: number };

interface TraceFields {
  id: string;
  timestamp: string; // fixed at session start; never re-stamped
  name: string;
  sessionId: string;
  environment?: string;
  tags: string[];
  metadata: Record<string, string>;
  input?: string;
  output?: string;
}

interface OpenToolSpan {
  id: string;
  name: string;
  startTime: string;
  input?: string;
  parentId?: string;
}

export interface TracerState {
  trace: TraceFields | null;
  turnCount: number;
  currentTurn: { id: string; name: string; startTime: string } | null;
  openTools: Record<string, OpenToolSpan>;
  lastUserText?: string;
  skillsUsed: string[];
}

export function initialTracerState(): TracerState {
  return { trace: null, turnCount: 0, currentTurn: null, openTools: {}, skillsUsed: [] };
}

/**
 * Detect a skill activation from a read of its SKILL.md. Matches any
 * .../skills/<name>/SKILL.md path (pi global, .agents, .claude, project
 * .pi, overclock plugin layouts all share this shape).
 */
export function skillFromReadPath(args: unknown): string | undefined {
  if (typeof args !== "object" || args === null) return undefined;
  const path = (args as { path?: unknown }).path;
  if (typeof path !== "string") return undefined;
  const m = path.match(/\/skills\/([^/]+)\/SKILL\.md$/);
  return m ? m[1] : undefined;
}

function iso(epochMs: number): string {
  return new Date(epochMs).toISOString();
}

/** Full-row trace-upsert body — re-sends every field (ReplacingMergeTree has no field merge). */
function traceUpsert(t: TraceFields): IngestRequestEvent {
  return {
    type: "trace-upsert",
    body: {
      id: t.id,
      timestamp: t.timestamp,
      name: t.name,
      sessionId: t.sessionId,
      ...(t.environment ? { environment: t.environment } : {}),
      tags: t.tags,
      metadata: t.metadata,
      ...(t.input !== undefined ? { input: t.input } : {}),
      ...(t.output !== undefined ? { output: t.output } : {})
    }
  };
}

/** Builds usageDetails with canonical keys; values int + positive, absent when unknown (never zero-filled). */
function usageDetails(usage: PiUsage | undefined): Record<string, number> | undefined {
  if (!usage) return undefined;
  const details: Record<string, number> = {};
  const add = (key: string, value: number | undefined) => {
    if (typeof value === "number" && Number.isFinite(value) && value > 0) {
      details[key] = Math.round(value);
    }
  };
  add("input_tokens", usage.input);
  add("output_tokens", usage.output);
  add("cache_read_input_tokens", usage.cacheRead);
  add("cache_write_input_tokens", usage.cacheWrite);
  add("reasoning_output_tokens", usage.reasoning);
  add("total_tokens", usage.totalTokens);
  return Object.keys(details).length > 0 ? details : undefined;
}

function costDetails(usage: PiUsage | undefined): Record<string, number> | undefined {
  const cost = usage?.cost;
  if (!cost) return undefined;
  const details: Record<string, number> = {};
  const add = (key: string, value: number | undefined) => {
    if (typeof value === "number" && Number.isFinite(value) && value > 0) details[key] = value;
  };
  add("input", cost.input);
  add("output", cost.output);
  add("cache_read", cost.cacheRead);
  add("cache_write", cost.cacheWrite);
  add("total", cost.total);
  return Object.keys(details).length > 0 ? details : undefined;
}

/** Full-row span upsert for a tool span (no output yet / with output at end). */
function toolSpanRow(
  traceId: string,
  span: OpenToolSpan,
  end?: { endTime: string; output?: string; isError: boolean }
): IngestRequestEvent {
  return {
    type: "observation-upsert",
    body: {
      id: span.id,
      traceId,
      ...(span.parentId ? { parentObservationId: span.parentId } : {}),
      type: "span",
      name: span.name,
      startTime: span.startTime,
      ...(span.input !== undefined ? { input: span.input } : {}),
      ...(end
        ? {
            endTime: end.endTime,
            level: end.isError ? "error" : "default",
            ...(end.output !== undefined ? { output: end.output } : {})
          }
        : {}),
      metadata: {}
    }
  };
}

function turnSpanRow(
  traceId: string,
  turn: { id: string; name: string; startTime: string },
  endTime?: string
): IngestRequestEvent {
  return {
    type: "observation-upsert",
    body: {
      id: turn.id,
      traceId,
      type: "span",
      name: turn.name,
      startTime: turn.startTime,
      ...(endTime ? { endTime } : {}),
      metadata: {}
    }
  };
}

/**
 * Pure mapping: (state, pi session event) -> (new state, ingest envelope events).
 * No I/O, no clocks (timestamps ride in on the event), injectable id generator.
 */
export function mapTracerEvent(
  state: TracerState,
  event: TracerEvent,
  newId: () => string = () => randomUUID()
): { state: TracerState; events: IngestRequestEvent[] } {
  const s: TracerState = {
    ...state,
    trace: state.trace ? { ...state.trace, metadata: { ...state.trace.metadata } } : null,
    currentTurn: state.currentTurn ? { ...state.currentTurn } : null,
    openTools: { ...state.openTools }
  };
  const events: IngestRequestEvent[] = [];

  switch (event.kind) {
    case "session_start": {
      const repoOrDir = event.repo ?? basename(event.cwd);
      s.trace = {
        id: event.sessionId,
        timestamp: iso(event.at),
        name: `pi:${repoOrDir}`,
        sessionId: event.sessionId,
        ...(event.environment ? { environment: event.environment } : {}),
        tags: [],
        metadata: {
          harness: "pi",
          cwd: event.cwd,
          ...(event.repo ? { repo: event.repo } : {})
        }
      };
      s.turnCount = 0;
      s.currentTurn = null;
      s.openTools = {};
      events.push(traceUpsert(s.trace));
      break;
    }

    case "user_message": {
      if (!s.trace) break;
      const text = sanitizeField(event.text);
      s.lastUserText = text;
      if (s.trace.input === undefined && text !== undefined) {
        s.trace.input = text;
        events.push(traceUpsert(s.trace));
      }
      break;
    }

    case "turn_start": {
      if (!s.trace) break;
      // Defensive: a dangling turn (shouldn't happen) gets closed rather than leaked.
      if (s.currentTurn) {
        events.push(turnSpanRow(s.trace.id, s.currentTurn, iso(event.at)));
      }
      s.turnCount += 1;
      s.currentTurn = {
        id: newId(),
        name: `turn ${s.turnCount}`,
        startTime: iso(event.at)
      };
      events.push(turnSpanRow(s.trace.id, s.currentTurn));
      break;
    }

    case "assistant_message": {
      if (!s.trace) break;
      const output = sanitizeField(event.text);
      const usage = usageDetails(event.usage);
      const cost = costDetails(event.usage);
      const level =
        event.stopReason === "error"
          ? "error"
          : event.stopReason === "aborted"
            ? "warning"
            : "default";
      events.push({
        type: "observation-upsert",
        body: {
          id: newId(),
          traceId: s.trace.id,
          ...(s.currentTurn ? { parentObservationId: s.currentTurn.id } : {}),
          type: "generation",
          name: event.model ?? "llm-call",
          startTime: iso(event.startedAt ?? event.at),
          endTime: iso(event.at),
          level,
          ...(event.errorMessage ? { statusMessage: truncateText(event.errorMessage, 2000) } : {}),
          ...(event.model ? { model: event.model } : {}),
          ...(s.lastUserText !== undefined ? { input: s.lastUserText } : {}),
          ...(output !== undefined ? { output } : {}),
          ...(usage ? { usageDetails: usage } : {}),
          ...(cost ? { costDetails: cost } : {}),
          metadata: {
            ...(event.provider ? { provider: event.provider } : {}),
            ...(event.stopReason ? { stopReason: event.stopReason } : {})
          }
        }
      });
      if (output !== undefined) {
        s.trace.output = output;
        events.push(traceUpsert(s.trace));
      }
      break;
    }

    case "tool_start": {
      if (!s.trace) break;
      // Skill activation: a read of any SKILL.md tags the whole trace, so
      // sessions are filterable by the skills they used.
      if (event.toolName === "read") {
        const skill = skillFromReadPath(event.args);
        if (skill && !s.skillsUsed.includes(skill)) {
          s.skillsUsed = [...s.skillsUsed, skill];
          s.trace.tags = s.skillsUsed.map((n) => `skill:${n}`);
          s.trace.metadata = { ...s.trace.metadata, skills: s.skillsUsed.join(",") };
          events.push(traceUpsert(s.trace));
        }
      }
      const input = sanitizeField(event.args);
      const span: OpenToolSpan = {
        id: newId(),
        name: event.toolName,
        startTime: iso(event.at),
        ...(input !== undefined ? { input } : {}),
        ...(s.currentTurn ? { parentId: s.currentTurn.id } : {})
      };
      s.openTools[event.toolCallId] = span;
      events.push(toolSpanRow(s.trace.id, span));
      break;
    }

    case "tool_end": {
      if (!s.trace) break;
      const span: OpenToolSpan = s.openTools[event.toolCallId] ?? {
        id: newId(),
        name: event.toolName,
        startTime: iso(event.at),
        ...(s.currentTurn ? { parentId: s.currentTurn.id } : {})
      };
      delete s.openTools[event.toolCallId];
      const output = sanitizeField(event.output);
      events.push(
        toolSpanRow(s.trace.id, span, {
          endTime: iso(event.at),
          isError: event.isError,
          ...(output !== undefined ? { output } : {})
        })
      );
      break;
    }

    case "turn_end": {
      if (!s.trace || !s.currentTurn) break;
      events.push(turnSpanRow(s.trace.id, s.currentTurn, iso(event.at)));
      s.currentTurn = null;
      break;
    }

    case "session_end": {
      if (!s.trace) break;
      // Close anything left open (aborted tools/turns), then re-send the trace
      // so the settle watermark ticks from the real end of the session.
      for (const [toolCallId, span] of Object.entries(s.openTools)) {
        events.push(toolSpanRow(s.trace.id, span, { endTime: iso(event.at), isError: false }));
        delete s.openTools[toolCallId];
      }
      if (s.currentTurn) {
        events.push(turnSpanRow(s.trace.id, s.currentTurn, iso(event.at)));
        s.currentTurn = null;
      }
      events.push(traceUpsert(s.trace));
      break;
    }
  }

  return { state: s, events };
}

// ---------------------------------------------------------------------------
// Batcher (vendored shape of @ironside/sdk's EventBatcher, zero deps)
// ---------------------------------------------------------------------------

export interface IngestBatcherOptions {
  url: string;
  apiKey: string;
  maxBatchSize?: number;
  flushIntervalMs?: number;
  requestTimeoutMs?: number;
  fetchImpl?: typeof fetch;
  onError?: (error: unknown) => void;
}

const DEFAULT_MAX_BATCH_SIZE = 50;
const DEFAULT_FLUSH_INTERVAL_MS = 5000;
const DEFAULT_REQUEST_TIMEOUT_MS = 10_000;
const MAX_EVENTS_PER_REQUEST = 500; // ingest hard cap per batch

/**
 * Buffers ingest events and flushes to POST /api/v1/ingest in the background.
 * Failures are reported via onError, never thrown — a tracer must never be
 * the reason a session fails.
 */
export class IngestBatcher {
  private readonly options: Required<Pick<IngestBatcherOptions, "url" | "apiKey">> &
    IngestBatcherOptions;
  private readonly maxBatchSize: number;
  private readonly fetchImpl: typeof fetch;
  private readonly onError: (error: unknown) => void;
  private buffer: IngestRequestEvent[] = [];
  private timer: ReturnType<typeof setInterval> | null = null;
  private inFlight: Promise<void> = Promise.resolve();
  private closed = false;

  constructor(options: IngestBatcherOptions) {
    this.options = { ...options, url: options.url.replace(/\/+$/, "") };
    this.maxBatchSize = options.maxBatchSize ?? DEFAULT_MAX_BATCH_SIZE;
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.onError = options.onError ?? ((error) => console.error("[ironside-tracer]", error));
    this.timer = setInterval(
      () => void this.flush(),
      options.flushIntervalMs ?? DEFAULT_FLUSH_INTERVAL_MS
    );
    // Never keep the pi process alive because of the tracer.
    this.timer.unref?.();
  }

  enqueue(event: IngestRequestEvent): void {
    if (this.closed) return;
    this.buffer.push(event);
    if (this.buffer.length >= this.maxBatchSize) void this.flush();
  }

  /** Sends whatever is buffered. Never rejects. */
  async flush(): Promise<void> {
    if (this.buffer.length === 0) return;
    const events = this.buffer;
    this.buffer = [];
    this.inFlight = this.inFlight.then(() => this.send(events));
    await this.inFlight;
  }

  private async send(events: IngestRequestEvent[]): Promise<void> {
    for (let i = 0; i < events.length; i += MAX_EVENTS_PER_REQUEST) {
      const chunk = events.slice(i, i + MAX_EVENTS_PER_REQUEST);
      try {
        const res = await this.fetchImpl(`${this.options.url}/api/v1/ingest`, {
          method: "POST",
          headers: {
            "content-type": "application/json",
            authorization: `Bearer ${this.options.apiKey}`
          },
          body: JSON.stringify({ events: chunk }),
          signal: AbortSignal.timeout(this.options.requestTimeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS)
        });
        if (!res.ok) {
          this.onError(new Error(`ingest request failed: HTTP ${res.status}`));
        }
      } catch (error) {
        this.onError(error);
      }
    }
  }

  /** Stops the timer and flushes remaining events. Never rejects. */
  async close(): Promise<void> {
    this.closed = true;
    if (this.timer) clearInterval(this.timer);
    const events = this.buffer;
    this.buffer = [];
    if (events.length > 0) {
      this.inFlight = this.inFlight.then(() => this.send(events));
    }
    await this.inFlight;
  }
}

// ---------------------------------------------------------------------------
// pi extension wiring
// ---------------------------------------------------------------------------

/** Walks up from cwd looking for a .git entry; returns the repo dir name. */
function findRepoName(cwd: string): string | undefined {
  try {
    let dir = cwd;
    for (let i = 0; i < 40; i++) {
      if (existsSync(join(dir, ".git"))) return basename(dir);
      const parent = dirname(dir);
      if (parent === dir) break;
      dir = parent;
    }
  } catch {
    // fail open
  }
  return undefined;
}

function extractText(content: unknown): string {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .filter(
      (part): part is { type: "text"; text: string } =>
        typeof part === "object" &&
        part !== null &&
        (part as { type?: unknown }).type === "text" &&
        typeof (part as { text?: unknown }).text === "string"
    )
    .map((part) => part.text)
    .join("\n")
    .trim();
}

function extractToolOutput(result: unknown): unknown {
  if (result === undefined || result === null) return undefined;
  const content = (result as { content?: unknown }).content;
  if (Array.isArray(content)) {
    const text = extractText(content);
    if (text.length > 0) return text;
  }
  return result;
}

export default function ironsideTracer(pi: ExtensionAPI) {
  if (process.env.IRONSIDE_TRACER_DISABLE === "1") return;

  const config = loadTracerConfig();
  if (!config) {
    console.error(
      `[ironside-tracer] no valid config at ${DEFAULT_CONFIG_PATH} — tracing disabled`
    );
    return;
  }

  let state = initialTracerState();
  let batcher: IngestBatcher | null = null;
  let errorLogged = false;

  // Log the first delivery/mapping error, then go quiet — no retry storms,
  // no per-event noise. Tracing silently degrades to a no-op.
  const logOnce = (error: unknown) => {
    if (errorLogged) return;
    errorLogged = true;
    console.error("[ironside-tracer] trace delivery failed (further errors suppressed):", error);
  };

  const feed = (event: TracerEvent) => {
    try {
      if (!batcher) return;
      const result = mapTracerEvent(state, event);
      state = result.state;
      for (const ingestEvent of result.events) batcher.enqueue(ingestEvent);
    } catch (error) {
      logOnce(error);
    }
  };

  pi.on("session_start", (_event, ctx) => {
    try {
      state = initialTracerState();
      if (!batcher) {
        batcher = new IngestBatcher({ url: config.url, apiKey: config.apiKey, onError: logOnce });
      }
      const repo = findRepoName(ctx.cwd);
      feed({
        kind: "session_start",
        sessionId: ctx.sessionManager.getSessionId(),
        cwd: ctx.cwd,
        ...(repo ? { repo } : {}),
        ...(config.environment ? { environment: config.environment } : {}),
        at: Date.now()
      });
    } catch (error) {
      logOnce(error);
    }
  });

  pi.on("before_agent_start", (event) => {
    feed({ kind: "user_message", text: event.prompt, at: Date.now() });
  });

  pi.on("turn_start", (event) => {
    feed({ kind: "turn_start", at: event.timestamp || Date.now() });
  });

  pi.on("message_end", (event) => {
    try {
      const message = event.message as {
        role?: string;
        content?: unknown;
        model?: string;
        provider?: string;
        stopReason?: string;
        errorMessage?: string;
        usage?: PiUsage;
        timestamp?: number;
      };
      if (message.role !== "assistant") return;
      feed({
        kind: "assistant_message",
        text: extractText(message.content),
        ...(message.model ? { model: message.model } : {}),
        ...(message.provider ? { provider: message.provider } : {}),
        ...(message.stopReason ? { stopReason: message.stopReason } : {}),
        ...(message.errorMessage ? { errorMessage: message.errorMessage } : {}),
        ...(message.usage ? { usage: message.usage } : {}),
        ...(typeof message.timestamp === "number" ? { startedAt: message.timestamp } : {}),
        at: Date.now()
      });
    } catch (error) {
      logOnce(error);
    }
  });

  pi.on("tool_execution_start", (event) => {
    feed({
      kind: "tool_start",
      toolCallId: event.toolCallId,
      toolName: event.toolName,
      args: event.args,
      at: Date.now()
    });
  });

  pi.on("tool_execution_end", (event) => {
    feed({
      kind: "tool_end",
      toolCallId: event.toolCallId,
      toolName: event.toolName,
      output: extractToolOutput(event.result),
      isError: event.isError,
      at: Date.now()
    });
  });

  pi.on("turn_end", () => {
    feed({ kind: "turn_end", at: Date.now() });
  });

  pi.on("agent_end", async () => {
    try {
      await batcher?.flush();
    } catch (error) {
      logOnce(error);
    }
  });

  pi.on("session_shutdown", async () => {
    try {
      feed({ kind: "session_end", at: Date.now() });
      const current = batcher;
      batcher = null;
      if (current) await current.close();
    } catch (error) {
      logOnce(error);
    }
  });
}
