const DEFAULT_HELPER_BASE_URL = "http://127.0.0.1:4317";
const DEFAULT_HELPER_MODEL = "sonnet";
const HELPER_BASE_STORAGE_KEY = "zenos.copilot.helperBaseUrl";
const HELPER_TOKEN_STORAGE_KEY = "zenos.copilot.helperToken";
const HELPER_CWD_STORAGE_KEY = "zenos.copilot.cwd";
const HELPER_MODEL_STORAGE_KEY = "zenos.copilot.model";
const LEGACY_HELPER_BASE_STORAGE_KEY = "zenos.marketing.cowork.helperBaseUrl";
const LEGACY_HELPER_TOKEN_STORAGE_KEY = "zenos.marketing.cowork.helperToken";
const LEGACY_HELPER_CWD_STORAGE_KEY = "zenos.marketing.cowork.cwd";
const LEGACY_HELPER_MODEL_STORAGE_KEY = "zenos.marketing.cowork.model";

type LocalNetworkRequestInit = RequestInit & {
  targetAddressSpace?: "local" | "loopback";
};

export interface CoworkCapabilityCheck {
  mcpOk: boolean;
  skillsLoaded: string[];
  missingSkills?: string[];
  allowedTools?: string[];
  redactionRulesVersion?: string;
}

export interface CoworkWorkspaceProbe {
  ok: boolean;
  message?: string;
  partnerId?: string;
  partnerEmail?: string;
  workspaceId?: string;
  workspaceName?: string;
  availableWorkspaces?: Array<{ id: string; name: string }>;
}

export interface CoworkPermissionRequest {
  toolName: string;
  timeoutSeconds: number;
}

export interface CoworkPermissionResult {
  toolName: string;
  approved: boolean;
  reason?: string;
}

export type CoworkStreamEvent =
  | { type: "message"; requestId?: string; line: string }
  | { type: "stderr"; requestId?: string; text: string }
  | { type: "done"; requestId?: string; code?: number; signal?: string }
  | { type: "capability_check"; capability: CoworkCapabilityCheck }
  | {
      type: "graph_context_loaded";
      payload: {
        l2_count: number;
        l3_count: number;
        truncated: boolean;
        fallback_mode: "normal" | "l1_tags_only";
      };
    }
  | { type: "permission_request"; request: CoworkPermissionRequest }
  | { type: "permission_result"; result: CoworkPermissionResult }
  | { type: "error"; message: string };

function readStorageWithFallback(primaryKey: string, legacyKey: string): string | null {
  if (typeof window === "undefined") return null;
  const storage = window.localStorage;
  const primaryValue = storage.getItem(primaryKey);
  if (primaryValue) return primaryValue;
  return storage.getItem(legacyKey);
}

export function getDefaultHelperBaseUrl(): string {
  if (typeof window === "undefined") return DEFAULT_HELPER_BASE_URL;
  return (
    readStorageWithFallback(HELPER_BASE_STORAGE_KEY, LEGACY_HELPER_BASE_STORAGE_KEY) ||
    DEFAULT_HELPER_BASE_URL
  );
}

export function setDefaultHelperBaseUrl(url: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(HELPER_BASE_STORAGE_KEY, url.trim());
}

export function getDefaultHelperToken(): string {
  if (typeof window === "undefined") return "";
  return readStorageWithFallback(HELPER_TOKEN_STORAGE_KEY, LEGACY_HELPER_TOKEN_STORAGE_KEY) || "";
}

export function setDefaultHelperToken(token: string): void {
  if (typeof window === "undefined") return;
  const trimmed = token.trim();
  if (!trimmed) {
    window.localStorage.removeItem(HELPER_TOKEN_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(HELPER_TOKEN_STORAGE_KEY, trimmed);
}

export function getDefaultHelperCwd(): string {
  if (typeof window === "undefined") return "";
  return readStorageWithFallback(HELPER_CWD_STORAGE_KEY, LEGACY_HELPER_CWD_STORAGE_KEY) || "";
}

export function setDefaultHelperCwd(cwd: string): void {
  if (typeof window === "undefined") return;
  const trimmed = cwd.trim();
  if (!trimmed) {
    window.localStorage.removeItem(HELPER_CWD_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(HELPER_CWD_STORAGE_KEY, trimmed);
}

export function getDefaultHelperModel(): string {
  if (typeof window === "undefined") return DEFAULT_HELPER_MODEL;
  return (
    readStorageWithFallback(HELPER_MODEL_STORAGE_KEY, LEGACY_HELPER_MODEL_STORAGE_KEY) ||
    DEFAULT_HELPER_MODEL
  );
}

export function setDefaultHelperModel(model: string): void {
  if (typeof window === "undefined") return;
  const trimmed = model.trim();
  if (!trimmed) {
    window.localStorage.removeItem(HELPER_MODEL_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(HELPER_MODEL_STORAGE_KEY, trimmed);
}

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.trim().replace(/\/+$/, "");
}

function inferHelperAddressSpace(baseUrl: string): "local" | "loopback" {
  try {
    const host = new URL(baseUrl).hostname.trim().toLowerCase();
    if (
      host === "localhost" ||
      host === "::1" ||
      host === "[::1]" ||
      host.startsWith("127.")
    ) {
      return "loopback";
    }
  } catch {
    // Fall back to local below if URL parsing fails.
  }
  return "local";
}

function buildHelperFetchInit(baseUrl: string, init: RequestInit): LocalNetworkRequestInit {
  // Chrome's Local Network Access protection can block HTTPS dashboard -> localhost helper
  // unless the request is explicitly annotated with the target address space.
  return {
    ...init,
    targetAddressSpace: inferHelperAddressSpace(baseUrl),
  };
}

async function parseJsonSafely<T>(res: Response): Promise<T | null> {
  try {
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function checkCoworkHelperHealth(baseUrl: string, token?: string, workspaceId?: string): Promise<{
  ok: boolean;
  status: string;
  message?: string;
  capability?: CoworkCapabilityCheck | null;
  workspaceProbe?: CoworkWorkspaceProbe | null;
}> {
  const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
  const healthUrl = new URL(`${normalizedBaseUrl}/health`);
  if (workspaceId?.trim()) {
    healthUrl.searchParams.set("workspace_id", workspaceId.trim());
  }
  const headers: Record<string, string> = {};
  if (token?.trim()) headers["X-Local-Helper-Token"] = token.trim();

  try {
    const res = await fetch(
      healthUrl.toString(),
      buildHelperFetchInit(normalizedBaseUrl, { method: "GET", headers })
    );
    const body = await parseJsonSafely<{
      status?: string;
      message?: string;
      capability?: {
        mcp_ok?: boolean;
        skills_loaded?: string[];
        missing_skills?: string[];
        allowed_tools?: string[];
        redaction_rules_version?: string;
      };
      workspace_probe?: {
        ok?: boolean;
        message?: string;
        partner_id?: string;
        partner_email?: string;
        workspace_id?: string;
        workspace_name?: string;
        available_workspaces?: Array<{ id?: string; name?: string }>;
      };
    }>(res);
    const capability = body?.capability
      ? {
          mcpOk: Boolean(body.capability.mcp_ok),
          skillsLoaded: Array.isArray(body.capability.skills_loaded) ? body.capability.skills_loaded : [],
          missingSkills: Array.isArray(body.capability.missing_skills) ? body.capability.missing_skills : [],
          allowedTools: Array.isArray(body.capability.allowed_tools) ? body.capability.allowed_tools : [],
          redactionRulesVersion:
            typeof body.capability.redaction_rules_version === "string"
              ? body.capability.redaction_rules_version
              : undefined,
        }
      : null;
    const workspaceProbe = body?.workspace_probe
      ? {
          ok: Boolean(body.workspace_probe.ok),
          message:
            typeof body.workspace_probe.message === "string"
              ? body.workspace_probe.message
              : undefined,
          partnerId:
            typeof body.workspace_probe.partner_id === "string"
              ? body.workspace_probe.partner_id
              : undefined,
          partnerEmail:
            typeof body.workspace_probe.partner_email === "string"
              ? body.workspace_probe.partner_email
              : undefined,
          workspaceId:
            typeof body.workspace_probe.workspace_id === "string"
              ? body.workspace_probe.workspace_id
              : undefined,
          workspaceName:
            typeof body.workspace_probe.workspace_name === "string"
              ? body.workspace_probe.workspace_name
              : undefined,
          availableWorkspaces: Array.isArray(body.workspace_probe.available_workspaces)
            ? body.workspace_probe.available_workspaces.map((workspace) => ({
                id: String(workspace?.id || ""),
                name: String(workspace?.name || ""),
              }))
            : [],
        }
      : null;
    if (!res.ok) {
      return {
        ok: false,
        status: "error",
        message: body?.message || `helper responded ${res.status}`,
        capability,
        workspaceProbe,
      };
    }
    return {
      ok: true,
      status: body?.status || "ok",
      message: body?.message,
      capability,
      workspaceProbe,
    };
  } catch (error) {
    return {
      ok: false,
      status: "offline",
      message: error instanceof Error ? error.message : "helper unavailable",
      capability: null,
      workspaceProbe: null,
    };
  }
}

function parseSseChunk(chunk: string): Array<{ event: string; data: string }> {
  const items: Array<{ event: string; data: string }> = [];
  const blocks = chunk.split("\n\n");
  for (const block of blocks) {
    const lines = block.split("\n");
    let event = "";
    const dataLines: string[] = [];
    for (const line of lines) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    if (!event || dataLines.length === 0) continue;
    items.push({ event, data: dataLines.join("\n") });
  }
  return items;
}

export async function streamCoworkChat(params: {
  baseUrl: string;
  token?: string;
  mode: "start" | "continue";
  conversationId: string;
  prompt: string;
  model?: string;
  cwd?: string;
  maxTurns?: number;
  onEvent: (event: CoworkStreamEvent) => void;
  signal?: AbortSignal;
}): Promise<void> {
  const {
    baseUrl,
    token,
    mode,
    conversationId,
    prompt,
    model,
    cwd,
    maxTurns,
    onEvent,
    signal,
  } = params;
  const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
  const path = mode === "start" ? "/v1/chat/start" : "/v1/chat/continue";
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token?.trim()) headers["X-Local-Helper-Token"] = token.trim();

  const payload: Record<string, unknown> = {
    conversationId,
    prompt,
  };
  if (model?.trim()) payload.model = model.trim();
  if (cwd?.trim()) payload.cwd = cwd.trim();
  if (maxTurns && Number.isFinite(maxTurns)) payload.maxTurns = maxTurns;

  const res = await fetch(
    `${normalizedBaseUrl}${path}`,
    buildHelperFetchInit(normalizedBaseUrl, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal,
    })
  );
  if (!res.ok) {
    const body = await parseJsonSafely<{ message?: string; error?: string }>(res);
    throw new Error(body?.message || body?.error || `helper responded ${res.status}`);
  }
  if (!res.body) {
    throw new Error("helper response has no stream body");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let splitIndex = buffer.indexOf("\n\n");
    while (splitIndex >= 0) {
      const one = buffer.slice(0, splitIndex);
      buffer = buffer.slice(splitIndex + 2);
      const parsed = parseSseChunk(`${one}\n\n`);
      for (const part of parsed) {
        try {
          const payloadData = JSON.parse(part.data) as Record<string, unknown>;
          if (part.event === "message") {
            onEvent({
              type: "message",
              requestId: typeof payloadData.requestId === "string" ? payloadData.requestId : undefined,
              line: String(payloadData.line || ""),
            });
          } else if (part.event === "stderr") {
            onEvent({
              type: "stderr",
              requestId: typeof payloadData.requestId === "string" ? payloadData.requestId : undefined,
              text: String(payloadData.text || ""),
            });
          } else if (part.event === "done") {
            onEvent({
              type: "done",
              requestId: typeof payloadData.requestId === "string" ? payloadData.requestId : undefined,
              code: typeof payloadData.code === "number" ? payloadData.code : undefined,
              signal: typeof payloadData.signal === "string" ? payloadData.signal : undefined,
            });
          } else if (part.event === "capability_check") {
            onEvent({
              type: "capability_check",
              capability: {
                mcpOk: Boolean(payloadData.mcp_ok),
                skillsLoaded: Array.isArray(payloadData.skills_loaded) ? payloadData.skills_loaded.map(String) : [],
                missingSkills: Array.isArray(payloadData.missing_skills) ? payloadData.missing_skills.map(String) : [],
                allowedTools: Array.isArray(payloadData.allowed_tools) ? payloadData.allowed_tools.map(String) : [],
                redactionRulesVersion:
                  typeof payloadData.redaction_rules_version === "string"
                    ? payloadData.redaction_rules_version
                    : undefined,
              },
            });
          } else if (part.event === "permission_request") {
            onEvent({
              type: "permission_request",
              request: {
                toolName: String(payloadData.tool_name || ""),
                timeoutSeconds:
                  typeof payloadData.timeout_seconds === "number"
                    ? payloadData.timeout_seconds
                    : Number(payloadData.timeout_seconds || 60),
              },
            });
          } else if (part.event === "permission_result") {
            onEvent({
              type: "permission_result",
              result: {
                toolName: String(payloadData.tool_name || ""),
                approved: Boolean(payloadData.approved),
                reason: typeof payloadData.reason === "string" ? payloadData.reason : undefined,
              },
            });
          }
        } catch {
          onEvent({ type: "error", message: "Invalid SSE payload from helper" });
        }
      }
      splitIndex = buffer.indexOf("\n\n");
    }
  }
}

export async function cancelCoworkRequest(params: {
  baseUrl: string;
  token?: string;
  requestId?: string;
  conversationId?: string;
}): Promise<void> {
  const requestId = params.requestId?.trim();
  const conversationId = params.conversationId?.trim();
  if (!requestId && !conversationId) {
    throw new Error("requestId or conversationId is required");
  }
  const normalizedBaseUrl = normalizeBaseUrl(params.baseUrl);
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (params.token?.trim()) headers["X-Local-Helper-Token"] = params.token.trim();
  const body: Record<string, string> = {};
  if (requestId) body.requestId = requestId;
  if (conversationId) body.conversationId = conversationId;
  const res = await fetch(
    `${normalizedBaseUrl}/v1/chat/cancel`,
    buildHelperFetchInit(normalizedBaseUrl, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    })
  );
  if (!res.ok) {
    const body = await parseJsonSafely<{ message?: string; error?: string }>(res);
    throw new Error(body?.message || body?.error || `helper responded ${res.status}`);
  }
}
