import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { createServer } from "node:http";
import { cpSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { execSync } from "node:child_process";
import { homedir } from "node:os";
import path from "node:path";
import {
  createRuntimeState,
  findConflictingRuns,
  findRunForCancel,
  registerRun,
  unregisterRun,
} from "./runtime-state.mjs";

const PORT = Number.parseInt(process.env.PORT || "4317", 10);
const HOST = "127.0.0.1";
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || "").split(",").map((x) => x.trim()).filter(Boolean);
const LOCAL_HELPER_TOKEN = (process.env.LOCAL_HELPER_TOKEN || "").trim();
const ALLOWED_CWDS = (process.env.ALLOWED_CWDS || "").split(",").map((x) => x.trim()).filter(Boolean);
const DEFAULT_CWD = (process.env.DEFAULT_CWD || ALLOWED_CWDS[0] || process.cwd()).trim();
const ALLOWED_MODELS = new Set(["sonnet", "opus", "haiku"]);
const DEFAULT_MODEL = ALLOWED_MODELS.has(String(process.env.DEFAULT_MODEL || "").trim().toLowerCase())
  ? String(process.env.DEFAULT_MODEL || "").trim().toLowerCase()
  : "sonnet";
const LOG_CLAUDE_IO = String(process.env.LOG_CLAUDE_IO || "1").trim() !== "0";
const CLAUDE_BIN = String(process.env.CLAUDE_BIN || "claude").trim() || "claude";
const CLAUDE_BIN_ARGS = String(process.env.CLAUDE_BIN_ARGS || "")
  .split(/\s+/)
  .map((item) => item.trim())
  .filter(Boolean);
const HELPER_TOOLS = process.env.HELPER_TOOLS ?? "";
const ZENOS_API_KEY = String(process.env.ZENOS_API_KEY || "").trim();
const ZENOS_PROJECT = String(process.env.ZENOS_PROJECT || "").trim();
const ZENOS_MCP_URL = String(
  process.env.ZENOS_MCP_URL || "https://zenos-mcp-165893875709.asia-east1.run.app/mcp"
).trim();
const ZENOS_SKILLS_RAW_BASE = String(
  process.env.ZENOS_SKILLS_RAW_BASE || "https://raw.githubusercontent.com/centerseed/zenos/main"
).trim();
const SESSION_STATE_FILE = path.join(homedir(), ".zenos-cowork-helper", "sessions.json");
const SESSION_TTL_MS = Math.max(
  60_000,
  Number.parseInt(process.env.SESSION_TTL_MINUTES || "55", 10) * 60 * 1000 || 55 * 60 * 1000
);
const PERMISSION_TIMEOUT_SECONDS = Math.max(
  1,
  Number.parseInt(process.env.PERMISSION_TIMEOUT_SECONDS || "60", 10) || 60
);
const EXPECTED_MARKETING_SKILLS = [
  "/marketing-intel",
  "/marketing-plan",
  "/marketing-generate",
  "/marketing-adapt",
  "/marketing-publish",
];
const EXPECTED_CRM_SKILLS = [
  "/crm-briefing",
  "/crm-debrief",
];
const EXPECTED_PROJECT_SKILLS = [
  "/triage",
];
const EXPECTED_ZENOS_RELEASE_SKILLS = [
  "/zenos-governance",
  "/zenos-capture",
  "/zenos-sync",
];
const EXPECTED_GOVERNANCE_FILES = [
  "skills/governance/document-governance.md",
  "skills/governance/task-governance.md",
];
const REDACTION_RULES_VERSION = process.env.REDACTION_RULES_VERSION || "2026-04-14";

function buildSkillAssetDescriptor(name, relativePath) {
  const normalizedPath = Array.isArray(relativePath) ? relativePath : String(relativePath).split("/");
  return {
    name,
    relativePath: normalizedPath,
    remoteUrl: `${ZENOS_SKILLS_RAW_BASE}/${normalizedPath.join("/")}`,
  };
}

const EXPECTED_SKILL_ASSETS = [
  ...EXPECTED_MARKETING_SKILLS.map((skill) =>
    buildSkillAssetDescriptor(skill, ["skills", "release", "workflows", skill.replace(/^\//, ""), "SKILL.md"])
  ),
  ...EXPECTED_CRM_SKILLS.map((skill) =>
    buildSkillAssetDescriptor(skill, ["skills", "release", "workflows", skill.replace(/^\//, ""), "SKILL.md"])
  ),
  ...EXPECTED_PROJECT_SKILLS.map((skill) =>
    buildSkillAssetDescriptor(skill, ["skills", "release", "workflows", skill.replace(/^\//, ""), "SKILL.md"])
  ),
  ...EXPECTED_ZENOS_RELEASE_SKILLS.map((skill) =>
    buildSkillAssetDescriptor(skill, ["skills", "release", skill.replace(/^\//, ""), "SKILL.md"])
  ),
  ...EXPECTED_GOVERNANCE_FILES.map((filePath) =>
    buildSkillAssetDescriptor(filePath, filePath.split("/"))
  ),
];

/** @type {Map<string, { sessionId: string, sessionName: string, cwd: string, createdAt: string, updatedAt: string }>} */
const sessions = new Map();
const runtimeState = createRuntimeState();

function loadSessions() {
  try {
    const raw = readFileSync(SESSION_STATE_FILE, "utf8");
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return;
    for (const [conversationId, value] of Object.entries(parsed)) {
      if (!value || typeof value !== "object") continue;
      const row = /** @type {{ sessionId?: string, sessionName?: string, cwd?: string, createdAt?: string, updatedAt?: string }} */ (value);
      if (!row.sessionName || !row.cwd) continue;
      sessions.set(conversationId, {
        sessionId: row.sessionId || randomUUID(),
        sessionName: row.sessionName,
        cwd: row.cwd,
        createdAt: row.createdAt || row.updatedAt || new Date().toISOString(),
        updatedAt: row.updatedAt || new Date().toISOString(),
      });
    }
  } catch {
    // no-op
  }
}

function isSessionExpired(row) {
  const startedAt = Date.parse(row.createdAt || row.updatedAt || "");
  if (!Number.isFinite(startedAt)) return true;
  return Date.now() - startedAt > SESSION_TTL_MS;
}

function createSessionRecord(conversationId, cwd) {
  const now = new Date().toISOString();
  return {
    sessionId: randomUUID(),
    sessionName: `web-${conversationId}`,
    cwd,
    createdAt: now,
    updatedAt: now,
  };
}

function purgeExpiredSessions() {
  let changed = false;
  for (const [conversationId, row] of sessions.entries()) {
    if (!isSessionExpired(row)) continue;
    sessions.delete(conversationId);
    changed = true;
  }
  if (changed) {
    saveSessions();
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

function resolveSession(conversationId, cwd, mode) {
  purgeExpiredSessions();
  const current = sessions.get(conversationId);
  if (mode === "continue" && current) {
    if (!current.sessionId) {
      current.sessionId = randomUUID();
    }
    if (cwd && current.cwd !== cwd) {
      current.cwd = cwd;
    }
    current.updatedAt = new Date().toISOString();
    sessions.set(conversationId, current);
    saveSessions();
    return { session: current, resumed: true };
  }

  const created = createSessionRecord(conversationId, cwd);
  sessions.set(conversationId, created);
  saveSessions();
  return { session: created, resumed: false };
}

function buildEnv() {
  const env = { ...process.env };
  delete env.ANTHROPIC_API_KEY;
  return env;
}

function createLineMirror(prefix, writer) {
  let buffer = "";
  return {
    push(chunk) {
      buffer += chunk.toString("utf8");
      let lineEnd = buffer.indexOf("\n");
      while (lineEnd >= 0) {
        const line = buffer.slice(0, lineEnd).replace(/\r$/, "");
        buffer = buffer.slice(lineEnd + 1);
        writer(`${prefix}${line}\n`);
        lineEnd = buffer.indexOf("\n");
      }
    },
    flush() {
      if (!buffer.length) return;
      writer(`${prefix}${buffer.replace(/\r$/, "")}\n`);
      buffer = "";
    },
  };
}

function stopChildProcess(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  child.kill("SIGTERM");
  setTimeout(() => {
    if (child.exitCode === null && child.signalCode === null) {
      child.kill("SIGKILL");
    }
  }, 250);
}

function stopRun(run, reason) {
  const detached = unregisterRun(runtimeState, run.requestId) || run;
  console.warn(
    `[runtime] stopping request ${detached.requestId} (${detached.conversationId}) because ${reason}`
  );
  stopChildProcess(detached.child);
}

// ── Workspace Bootstrap ─────────────────────────────────────────────────────
// On startup, if ZENOS_API_KEY is set, auto-generate .claude/mcp.json and
// .claude/settings.local.json in every ALLOWED_CWDS workspace so spawned
// Claude CLI sessions have MCP access and tool permissions out of the box.
// No manual file copying needed — any new user just sets ZENOS_API_KEY.

// Both local MCP (mcp__zenos__*) and Claude.ai MCP (mcp__claude_ai_zenos__*)
// prefixes — CLI may use either depending on which server connects first.
const ZENOS_TOOL_NAMES = [
  "search", "get", "write", "confirm", "analyze", "task", "plan",
  "journal_read", "journal_write", "read_source", "setup", "governance_guide",
  "list_workspaces", "find_gaps", "suggest_policy", "common_neighbors",
  "batch_update_sources", "upload_attachment",
];
const ZENOS_MCP_TOOLS = [
  ...ZENOS_TOOL_NAMES.map((t) => `mcp__zenos__${t}`),
  ...ZENOS_TOOL_NAMES.map((t) => `mcp__claude_ai_zenos__${t}`),
];

// Helper's own ZenOS project root (2 levels up from tools/claude-cowork-helper/)
const HELPER_PROJECT_ROOT = path.resolve(new URL(".", import.meta.url).pathname, "../..");

function bootstrapWorkspace(cwd) {
  if (!ZENOS_API_KEY) return;
  const claudeDir = path.join(cwd, ".claude");
  mkdirSync(claudeDir, { recursive: true });

  // 1. MCP config — always bind zenos server to the current user's API key
  const mcpPath = path.join(claudeDir, "mcp.json");
  const existingMcp = safeReadJson(mcpPath);
  const projectMcpPath = path.join(HELPER_PROJECT_ROOT, ".claude", "mcp.json");
  const projectMcp = safeReadJson(projectMcpPath);
  const desiredMcp = {
    mcpServers: {
      ...(projectMcp?.mcpServers || {}),
      ...(existingMcp?.mcpServers || {}),
      zenos: {
        type: "http",
        url: `${ZENOS_MCP_URL}?api_key=${ZENOS_API_KEY}`,
      },
    },
  };
  if (JSON.stringify(existingMcp || {}) !== JSON.stringify(desiredMcp)) {
    writeFileSync(mcpPath, JSON.stringify(desiredMcp, null, 2), "utf8");
    console.log(`[bootstrap] Wrote user-scoped MCP config → ${mcpPath}`);
  }

  // 2. Permissions — auto-approve ZenOS MCP tools
  const settingsLocalPath = path.join(claudeDir, "settings.local.json");
  const existingSettings = safeReadJson(settingsLocalPath) || {};
  const existingAllow = existingSettings?.permissions?.allow || [];
  const missing = ZENOS_MCP_TOOLS.filter((t) => !existingAllow.includes(t));
  if (missing.length > 0) {
    existingSettings.permissions = existingSettings.permissions || {};
    existingSettings.permissions.allow = [...new Set([...existingAllow, ...ZENOS_MCP_TOOLS])];
    writeFileSync(settingsLocalPath, JSON.stringify(existingSettings, null, 2), "utf8");
    console.log(`[bootstrap] Updated ${settingsLocalPath} — added ${missing.length} tools`);
  }

  // 3. allowedTools for helper's own permission interception
  const settingsPath = path.join(claudeDir, "settings.json");
  const existingHelperSettings = safeReadJson(settingsPath) || {};
  const existingAllowed = existingHelperSettings?.allowedTools || [];
  const helperMissing = ZENOS_MCP_TOOLS.filter((t) => !existingAllowed.includes(t));
  if (helperMissing.length > 0) {
    existingHelperSettings.allowedTools = [...new Set([...existingAllowed, ...ZENOS_MCP_TOOLS])];
    writeFileSync(settingsPath, JSON.stringify(existingHelperSettings, null, 2), "utf8");
    console.log(`[bootstrap] Updated ${settingsPath} — added ${helperMissing.length} tools`);
  }

  // 4. Ensure workflow + governance files exist in workspace
  for (const asset of EXPECTED_SKILL_ASSETS) {
    const dstPath = path.join(cwd, ...asset.relativePath);
    if (existsSync(dstPath)) continue;
    const srcPath = path.join(HELPER_PROJECT_ROOT, ...asset.relativePath);
    try {
      mkdirSync(path.dirname(dstPath), { recursive: true });
      if (existsSync(srcPath)) {
        cpSync(srcPath, dstPath, { recursive: false });
        console.log(`[bootstrap] Copied ${asset.name} (local)`);
        continue;
      }
      execSync(`curl -fsSL "${asset.remoteUrl}" -o "${dstPath}"`, { timeout: 10000 });
      console.log(`[bootstrap] Downloaded ${asset.name} (remote)`);
    } catch {
      console.warn(`[bootstrap] Could not get ${asset.name} — skipping`);
    }
  }
}

// Bootstrap all configured workspaces on startup
if (ZENOS_API_KEY) {
  const dirs = ALLOWED_CWDS.length > 0 ? ALLOWED_CWDS : [DEFAULT_CWD];
  for (const dir of dirs) {
    try { bootstrapWorkspace(dir); } catch (e) { console.error(`[bootstrap] Failed for ${dir}:`, e.message); }
  }
} else {
  console.warn("[bootstrap] ZENOS_API_KEY not set — skipping workspace bootstrap. MCP tools will not be available.");
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function safeReadJson(filePath) {
  try {
    return JSON.parse(readFileSync(filePath, "utf8"));
  } catch {
    return null;
  }
}

function loadAllowedTools(cwd) {
  const settingsPath = path.join(cwd, ".claude", "settings.json");
  const parsed = safeReadJson(settingsPath);
  const allowed = parsed?.allowedTools;
  if (!Array.isArray(allowed)) return [];
  return allowed.map((item) => String(item || "").trim()).filter(Boolean);
}

function loadSkills(cwd, expectedAssets) {
  return expectedAssets
    .filter((asset) => {
      const workspacePath = path.join(cwd, ...asset.relativePath);
      const helperPath = path.join(HELPER_PROJECT_ROOT, ...asset.relativePath);
      return existsSync(workspacePath) || existsSync(helperPath);
    })
    .map((asset) => asset.name);
}

function isAllowedTool(toolName, allowedTools) {
  const normalizedTool = String(toolName || "").trim().toLowerCase();
  if (!normalizedTool) return false;
  return allowedTools.some((entry) => {
    const normalizedEntry = String(entry || "").trim().toLowerCase();
    if (!normalizedEntry) return false;
    if (normalizedEntry === normalizedTool) return true;
    if (normalizedEntry.includes("(")) return false;
    const baseName = normalizedEntry.split("(", 1)[0]?.trim();
    return Boolean(baseName) && baseName === normalizedTool;
  });
}

function buildCapabilitySnapshot(cwd) {
  const allowedTools = loadAllowedTools(cwd);
  const allExpected = EXPECTED_SKILL_ASSETS;
  const skillsLoaded = loadSkills(cwd, allExpected);
  const expectedNames = allExpected.map((asset) => asset.name);
  const missingSkills = expectedNames.filter((skill) => !skillsLoaded.includes(skill));
  const mcpOk = allowedTools.some((tool) => tool.startsWith("mcp__zenos__"));
  return {
    mcp_ok: mcpOk,
    skills_loaded: skillsLoaded,
    missing_skills: missingSkills,
    allowed_tools: allowedTools,
    redaction_rules_version: REDACTION_RULES_VERSION,
  };
}

function getDashboardApiBase() {
  return ZENOS_MCP_URL.replace(/\/mcp(?:\?.*)?$/i, "");
}

async function buildWorkspaceProbe(activeWorkspaceId) {
  if (!ZENOS_API_KEY) {
    return {
      ok: false,
      message: "ZENOS_API_KEY not set",
    };
  }

  try {
    const headers = {
      Authorization: `Bearer ${ZENOS_API_KEY}`,
    };
    if (activeWorkspaceId) {
      headers["X-Active-Workspace-Id"] = activeWorkspaceId;
    }
    const response = await fetch(`${getDashboardApiBase()}/api/partner/me`, {
      method: "GET",
      headers,
    });
    const body = await response.json().catch(() => null);
    if (!response.ok || !body) {
      return {
        ok: false,
        message: body?.message || `workspace probe failed (${response.status})`,
      };
    }
    const available = Array.isArray(body.availableWorkspaces) ? body.availableWorkspaces : [];
    const activeId = typeof body.activeWorkspaceId === "string" ? body.activeWorkspaceId : "";
    const activeWorkspace =
      available.find((workspace) => String(workspace?.id || "") === activeId) || null;
    return {
      ok: true,
      partner_id: typeof body.id === "string" ? body.id : "",
      partner_email: typeof body.email === "string" ? body.email : "",
      workspace_id: activeId,
      workspace_name:
        typeof activeWorkspace?.name === "string"
          ? activeWorkspace.name
          : typeof body.displayName === "string"
            ? body.displayName
            : "",
      available_workspaces: available.map((workspace) => ({
        id: String(workspace?.id || ""),
        name: String(workspace?.name || ""),
      })),
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "workspace probe failed",
    };
  }
}

function resolveMcpConfigPath(cwd) {
  const explicit = String(process.env.MCP_CONFIG_PATH || "").trim();
  if (explicit && existsSync(explicit)) {
    return explicit;
  }
  const candidates = [
    path.join(cwd, ".claude", "mcp.json"),
    path.join(cwd, ".mcp.json"),
  ];
  return candidates.find((candidate) => existsSync(candidate)) || null;
}

function extractPermissionTool(text) {
  const quoted = text.match(/["'`]([^"'`]+)["'`]/);
  if (quoted?.[1]) return quoted[1].trim();
  const mcpMatch = text.match(/(mcp__[\w:.-]+)/i);
  if (mcpMatch?.[1]) return mcpMatch[1];
  const toolMatch = text.match(/\b(Bash|Read|Edit|Write|WebSearch|Grep|Glob|LS)\b/i);
  return toolMatch?.[1] || "unknown";
}

function classifyPermissionLine(text) {
  const normalized = text.toLowerCase();
  if (!normalized.includes("permission") && !normalized.includes("allow")) return null;
  const toolName = extractPermissionTool(text);
  if (/timed out|timeout|auto-reject|auto reject|denied|rejected/i.test(text)) {
    return { kind: "result", toolName, approved: false, reason: /timed out|timeout/i.test(text) ? "timeout" : "denied" };
  }
  if (/approved|allowed|granted/i.test(text)) {
    return { kind: "result", toolName, approved: true, reason: "approved" };
  }
  if (/request|confirm|approval required|awaiting/i.test(text)) {
    return { kind: "request", toolName };
  }
  return null;
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
  const { session, resumed } = resolveSession(conversationId, cwd, mode);
  const requestId = randomUUID();
  const allowedTools = loadAllowedTools(session.cwd);

  for (const conflict of findConflictingRuns(runtimeState, {
    conversationId,
    sessionId: session.sessionId,
  })) {
    stopRun(conflict, "superseded");
  }

  const args = ["-p", "--verbose", "--output-format", "stream-json", "--include-partial-messages"];
  const mcpConfigPath = resolveMcpConfigPath(session.cwd);
  if (mcpConfigPath) {
    args.push("--mcp-config", mcpConfigPath);
  }
  args.push("--model", model);
  if (HELPER_TOOLS.trim()) {
    args.push("--tools", HELPER_TOOLS);
  }
  if (maxTurns && Number.isFinite(maxTurns)) {
    args.push("--max-turns", String(maxTurns));
  }
  if (mode === "continue" && resumed) {
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
  sendSse(res, "capability_check", buildCapabilitySnapshot(session.cwd));

  const child = spawn(CLAUDE_BIN, [...CLAUDE_BIN_ARGS, ...args], {
    cwd: session.cwd,
    env: buildEnv(),
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (LOG_CLAUDE_IO) {
    console.log(
      `[claude-run] cwd=${session.cwd} bin=${CLAUDE_BIN} args=${JSON.stringify([...CLAUDE_BIN_ARGS, ...args])}`
    );
  }
  registerRun(runtimeState, {
    requestId,
    conversationId,
    sessionId: session.sessionId,
    child,
  });

  let stdoutBuffer = "";
  let permissionState = null;
  let permissionTimer = null;
  const stdoutMirror = createLineMirror("[claude stdout] ", (line) => process.stdout.write(line));
  const stderrMirror = createLineMirror("[claude stderr] ", (line) => process.stderr.write(line));

  function clearPermissionTimer() {
    if (permissionTimer) {
      clearTimeout(permissionTimer);
      permissionTimer = null;
    }
  }

  function beginPermissionWait(toolName) {
    clearPermissionTimer();
    permissionState = { toolName, pending: true };
    sendSse(res, "permission_request", {
      tool_name: toolName,
      timeout_seconds: PERMISSION_TIMEOUT_SECONDS,
    });
    permissionTimer = setTimeout(() => {
      if (!permissionState?.pending) return;
      permissionState.pending = false;
      sendSse(res, "permission_result", {
        tool_name: toolName,
        approved: false,
        reason: "timeout",
      });
    }, PERMISSION_TIMEOUT_SECONDS * 1000);
  }

  function finishPermission(toolName, approved, reason) {
    clearPermissionTimer();
    permissionState = { toolName, pending: false };
    sendSse(res, "permission_result", {
      tool_name: toolName,
      approved,
      reason,
    });
  }

  child.stdout.on("data", (chunk) => {
    if (LOG_CLAUDE_IO) stdoutMirror.push(chunk);
    if (permissionState?.pending) {
      finishPermission(permissionState.toolName, true, "approved");
    }
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
    if (LOG_CLAUDE_IO) stderrMirror.push(chunk);
    const text = chunk.toString("utf8");
    const permission = classifyPermissionLine(text);
    if (permission?.kind === "request") {
      if (isAllowedTool(permission.toolName, allowedTools)) {
        return;
      }
      beginPermissionWait(permission.toolName);
    }
    if (permission?.kind === "result") {
      if (isAllowedTool(permission.toolName, allowedTools) && permission.approved) {
        return;
      }
      finishPermission(permission.toolName, permission.approved, permission.reason);
    }
    sendSse(res, "stderr", {
      requestId,
      text,
    });
  });

  child.on("close", (code, signal) => {
    if (LOG_CLAUDE_IO) {
      stdoutMirror.flush();
      stderrMirror.flush();
      console.log(`[claude-exit] requestId=${requestId} code=${typeof code === "number" ? code : "null"} signal=${signal || "null"}`);
    }
    clearPermissionTimer();
    unregisterRun(runtimeState, requestId);
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
    if (LOG_CLAUDE_IO) {
      stdoutMirror.flush();
      stderrMirror.flush();
    }
    clearPermissionTimer();
    unregisterRun(runtimeState, requestId);
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
    let capability;
    try {
      capability = buildCapabilitySnapshot(resolveCwd(DEFAULT_CWD));
    } catch {
      capability = buildCapabilitySnapshot(DEFAULT_CWD);
    }
    const requestedWorkspaceId = String(url.searchParams.get("workspace_id") || "").trim();
    const workspaceProbe = await buildWorkspaceProbe(requestedWorkspaceId || undefined);
    sendJson(
      res,
      200,
      {
        status: "ok",
        sessions: sessions.size,
        running: runtimeState.running.size,
        capability,
        workspace_probe: workspaceProbe,
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
        maxTurns: Number.isFinite(body.maxTurns) ? Number(body.maxTurns) : 10,
      });
      return;
    } catch (error) {
      sendJson(res, 400, { status: "error", message: String(error.message || error) }, auth.origin);
      return;
    }
  }

  if (req.method === "POST" && pathname === "/v1/chat/cancel") {
    try {
      const body = /** @type {{ requestId?: string, conversationId?: string }} */ (await parseRequestJson(req));
      const requestId = String(body.requestId || "").trim();
      const conversationId = String(body.conversationId || "").trim();
      if (!requestId && !conversationId) {
        sendJson(res, 400, { status: "error", message: "requestId or conversationId is required" }, auth.origin);
        return;
      }
      const run = findRunForCancel(runtimeState, { requestId, conversationId });
      if (!run) {
        sendJson(res, 404, { status: "error", message: "request not found" }, auth.origin);
        return;
      }
      stopRun(run, "cancelled");
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
