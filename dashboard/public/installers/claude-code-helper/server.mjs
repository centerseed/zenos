import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { createServer } from "node:http";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";

const PORT = Number.parseInt(process.env.PORT || "4317", 10);
const HOST = "127.0.0.1";
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || "").split(",").map((x) => x.trim()).filter(Boolean);
const LOCAL_HELPER_TOKEN = (process.env.LOCAL_HELPER_TOKEN || "").trim();
const ALLOWED_CWDS = (process.env.ALLOWED_CWDS || "").split(",").map((x) => x.trim()).filter(Boolean);
const DEFAULT_CWD = (process.env.DEFAULT_CWD || process.cwd()).trim();
const ALLOWED_MODELS = new Set(["sonnet", "opus", "haiku"]);
const DEFAULT_MODEL = ALLOWED_MODELS.has(String(process.env.DEFAULT_MODEL || "").trim().toLowerCase())
  ? String(process.env.DEFAULT_MODEL || "").trim().toLowerCase()
  : "sonnet";
const HELPER_TOOLS = process.env.HELPER_TOOLS ?? "";
const SESSION_STATE_FILE = path.join(homedir(), ".zenos-cowork-helper", "sessions.json");

/** @type {Map<string, { sessionId: string, sessionName: string, cwd: string, updatedAt: string }>} */
const sessions = new Map();
/** @type {Map<string, import("node:child_process").ChildProcess>} */
const running = new Map();

function loadSessions() {
  try {
    const raw = readFileSync(SESSION_STATE_FILE, "utf8");
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return;
    for (const [conversationId, value] of Object.entries(parsed)) {
      if (!value || typeof value !== "object") continue;
      const row = /** @type {{ sessionId?: string, sessionName?: string, cwd?: string, updatedAt?: string }} */ (value);
      if (!row.sessionName || !row.cwd) continue;
      sessions.set(conversationId, {
        sessionId: row.sessionId || randomUUID(),
        sessionName: row.sessionName,
        cwd: row.cwd,
        updatedAt: row.updatedAt || new Date().toISOString(),
      });
    }
  } catch {
    // no-op
  }
}

function saveSessions() {
  try {
    const folder = path.dirname(SESSION_STATE_FILE);
    mkdirSync(folder, { recursive: true });
    const payload = {};
    for (const [conversationId, row] of sessions.entries()) {
      payload[conversationId] = row;
    }
    writeFileSync(SESSION_STATE_FILE, JSON.stringify(payload, null, 2), "utf8");
  } catch (error) {
    console.error("saveSessions failed:", error);
  }
}

function sendJson(res, statusCode, body, origin = "") {
  if (origin) res.setHeader("Access-Control-Allow-Origin", origin);
  if (!origin) res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type,X-Local-Helper-Token");
  res.setHeader("Access-Control-Allow-Private-Network", "true");
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.statusCode = statusCode;
  res.end(JSON.stringify(body));
}

function sendSse(res, event, data) {
  res.write(`event: ${event}\n`);
  res.write(`data: ${JSON.stringify(data)}\n\n`);
}

function isOriginAllowed(origin) {
  if (!origin) return true;
  if (ALLOWED_ORIGINS.length === 0) return true;
  return ALLOWED_ORIGINS.includes(origin);
}

function assertAuthorized(req) {
  const origin = String(req.headers.origin || "");
  if (ALLOWED_ORIGINS.length > 0 && !origin) {
    return { ok: false, code: 403, message: "Origin required", origin: "" };
  }
  if (!isOriginAllowed(origin)) {
    return { ok: false, code: 403, message: "Origin not allowed", origin: "" };
  }
  if (LOCAL_HELPER_TOKEN) {
    const token = String(req.headers["x-local-helper-token"] || "").trim();
    if (!token || token !== LOCAL_HELPER_TOKEN) {
      return { ok: false, code: 401, message: "Invalid helper token", origin };
    }
  }
  return { ok: true, code: 200, message: "ok", origin };
}

function parseRequestJson(req) {
  return new Promise((resolve, reject) => {
    let raw = "";
    req.on("data", (chunk) => {
      raw += chunk.toString("utf8");
      if (raw.length > 1024 * 1024) {
        reject(new Error("request body too large"));
      }
    });
    req.on("end", () => {
      if (!raw.trim()) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(raw));
      } catch {
        reject(new Error("invalid JSON"));
      }
    });
    req.on("error", (err) => reject(err));
  });
}

function resolveCwd(inputCwd) {
  const candidate = String(inputCwd || "").trim() || DEFAULT_CWD;
  if (ALLOWED_CWDS.length === 0) return candidate;
  for (const allowed of ALLOWED_CWDS) {
    if (candidate === allowed || candidate.startsWith(`${allowed}${path.sep}`)) {
      return candidate;
    }
  }
  throw new Error("cwd not allowed");
}

function resolveModel(inputModel) {
  const candidate = String(inputModel || "").trim().toLowerCase();
  if (!candidate) return DEFAULT_MODEL;
  if (!ALLOWED_MODELS.has(candidate)) {
    throw new Error("model must be one of: sonnet, opus, haiku");
  }
  return candidate;
}

function getOrCreateSession(conversationId, cwd) {
  const current = sessions.get(conversationId);
  if (current) {
    if (!current.sessionId) {
      current.sessionId = randomUUID();
    }
    if (cwd && current.cwd !== cwd) {
      current.cwd = cwd;
      current.updatedAt = new Date().toISOString();
      sessions.set(conversationId, current);
      saveSessions();
    }
    return current;
  }
  const sessionName = `web-${conversationId}`;
  const created = {
    sessionId: randomUUID(),
    sessionName,
    cwd,
    updatedAt: new Date().toISOString(),
  };
  sessions.set(conversationId, created);
  saveSessions();
  return created;
}

function buildEnv() {
  const env = { ...process.env };
  delete env.ANTHROPIC_API_KEY;
  return env;
}

function startStreamingRun({
  req,
  res,
  origin,
  mode,
  conversationId,
  prompt,
  model,
  cwd,
  maxTurns,
}) {
  const session = getOrCreateSession(conversationId, cwd);
  const requestId = randomUUID();

  const args = ["-p", "--verbose", "--output-format", "stream-json", "--include-partial-messages"];
  args.push("--model", model);
  args.push("--tools", HELPER_TOOLS);
  if (maxTurns && Number.isFinite(maxTurns)) {
    args.push("--max-turns", String(maxTurns));
  }
  if (mode === "continue") {
    args.push("--resume", session.sessionId);
  } else {
    args.push("--session-id", session.sessionId, "--name", session.sessionName);
  }
  args.push(prompt);

  res.setHeader("Access-Control-Allow-Origin", origin || "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type,X-Local-Helper-Token");
  res.setHeader("Access-Control-Allow-Private-Network", "true");
  res.setHeader("Content-Type", "text/event-stream; charset=utf-8");
  res.setHeader("Cache-Control", "no-cache, no-transform");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders?.();

  const child = spawn("claude", args, {
    cwd: session.cwd,
    env: buildEnv(),
    stdio: ["ignore", "pipe", "pipe"],
  });
  running.set(requestId, child);

  let stdoutBuffer = "";
  child.stdout.on("data", (chunk) => {
    stdoutBuffer += chunk.toString("utf8");
    let lineEnd = stdoutBuffer.indexOf("\n");
    while (lineEnd >= 0) {
      const line = stdoutBuffer.slice(0, lineEnd).trim();
      stdoutBuffer = stdoutBuffer.slice(lineEnd + 1);
      if (line) sendSse(res, "message", { requestId, line });
      lineEnd = stdoutBuffer.indexOf("\n");
    }
  });

  child.stderr.on("data", (chunk) => {
    sendSse(res, "stderr", {
      requestId,
      text: chunk.toString("utf8"),
    });
  });

  child.on("close", (code, signal) => {
    running.delete(requestId);
    if (stdoutBuffer.trim()) {
      sendSse(res, "message", { requestId, line: stdoutBuffer.trim() });
      stdoutBuffer = "";
    }
    sendSse(res, "done", {
      requestId,
      code: typeof code === "number" ? code : null,
      signal: signal || null,
    });
    res.end();
  });

  child.on("error", (error) => {
    running.delete(requestId);
    sendSse(res, "stderr", {
      requestId,
      text: String(error.message || error),
    });
    sendSse(res, "done", { requestId, code: 1, signal: null });
    res.end();
  });

  req.on("close", () => {
    // Keep process running if browser closed. User can cancel explicitly.
  });
}

loadSessions();
saveSessions();

const server = createServer(async (req, res) => {
  const origin = String(req.headers.origin || "");
  const url = new URL(req.url || "/", `http://${HOST}:${PORT}`);
  const pathname = url.pathname;

  if (req.method === "OPTIONS") {
    if (!isOriginAllowed(origin)) {
      sendJson(res, 403, { status: "error", message: "Origin not allowed" }, "");
      return;
    }
    sendJson(res, 200, { status: "ok" }, origin);
    return;
  }

  const auth = assertAuthorized(req);
  if (!auth.ok) {
    sendJson(res, auth.code, { status: "error", message: auth.message }, auth.origin);
    return;
  }

  if (req.method === "GET" && pathname === "/health") {
    sendJson(
      res,
      200,
      {
        status: "ok",
        sessions: sessions.size,
        running: running.size,
      },
      auth.origin
    );
    return;
  }

  if (req.method === "POST" && (pathname === "/v1/chat/start" || pathname === "/v1/chat/continue")) {
    try {
      const body = /** @type {{ conversationId?: string, prompt?: string, model?: string, cwd?: string, maxTurns?: number }} */ (
        await parseRequestJson(req)
      );
      const conversationId = String(body.conversationId || "").trim();
      const prompt = String(body.prompt || "").trim();
      if (!conversationId || !prompt) {
        sendJson(res, 400, { status: "error", message: "conversationId and prompt are required" }, auth.origin);
        return;
      }
      const model = resolveModel(body.model);
      const cwd = resolveCwd(body.cwd);
      const mode = pathname.endsWith("/continue") ? "continue" : "start";
      startStreamingRun({
        req,
        res,
        origin: auth.origin,
        mode,
        conversationId,
        prompt,
        model,
        cwd,
        maxTurns: Number.isFinite(body.maxTurns) ? Number(body.maxTurns) : 6,
      });
      return;
    } catch (error) {
      sendJson(res, 400, { status: "error", message: String(error.message || error) }, auth.origin);
      return;
    }
  }

  if (req.method === "POST" && pathname === "/v1/chat/cancel") {
    try {
      const body = /** @type {{ requestId?: string }} */ (await parseRequestJson(req));
      const requestId = String(body.requestId || "").trim();
      if (!requestId) {
        sendJson(res, 400, { status: "error", message: "requestId is required" }, auth.origin);
        return;
      }
      const child = running.get(requestId);
      if (!child) {
        sendJson(res, 404, { status: "error", message: "request not found" }, auth.origin);
        return;
      }
      child.kill("SIGTERM");
      sendJson(res, 200, { status: "ok" }, auth.origin);
      return;
    } catch (error) {
      sendJson(res, 400, { status: "error", message: String(error.message || error) }, auth.origin);
      return;
    }
  }

  sendJson(res, 404, { status: "error", message: "not found" }, auth.origin);
});

server.listen(PORT, HOST, () => {
  console.log(`Cowork helper listening at http://${HOST}:${PORT}`);
});
