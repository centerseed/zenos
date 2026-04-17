export const API_BASE =
  process.env.NEXT_PUBLIC_MCP_API_URL ||
  "https://zenos-mcp-165893875709.asia-east1.run.app";

export const ACTIVE_WORKSPACE_STORAGE_KEY = "zenos.activeWorkspaceId";

type ApiResponseType = "json" | "text" | "void" | "response";

interface ApiRequestOptions extends Omit<RequestInit, "body"> {
  body?: BodyInit | null;
  json?: unknown;
  responseType?: ApiResponseType;
  retryWithSameOrigin?: boolean;
  token?: string | null;
  useWorkspace?: boolean;
}

export function getStoredActiveWorkspaceId(): string | null {
  if (typeof window === "undefined") return null;
  const storage = window.localStorage;
  if (!storage || typeof storage.getItem !== "function") return null;
  return storage.getItem(ACTIVE_WORKSPACE_STORAGE_KEY);
}

export function setActiveWorkspaceId(workspaceId: string | null): void {
  if (typeof window === "undefined") return;
  if (!workspaceId) {
    window.localStorage.removeItem(ACTIVE_WORKSPACE_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(ACTIVE_WORKSPACE_STORAGE_KEY, workspaceId);
}

export function serializeJsonBody(value: unknown): string {
  return JSON.stringify(value, (_key, innerValue) =>
    innerValue instanceof Date ? innerValue.toISOString() : innerValue
  );
}

export function hydrateDateFields<T>(obj: T, dateFields: ReadonlySet<string>): T {
  if (obj === null || obj === undefined) return obj;
  if (Array.isArray(obj)) {
    obj.forEach((item) => hydrateDateFields(item, dateFields));
    return obj;
  }
  if (typeof obj === "object") {
    for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
      if (dateFields.has(key) && typeof value === "string") {
        (obj as Record<string, unknown>)[key] = new Date(value);
      } else if (value !== null && typeof value === "object") {
        hydrateDateFields(value, dateFields);
      }
    }
  }
  return obj;
}

function isNetworkFailure(error: unknown): boolean {
  return (
    error instanceof TypeError &&
    /failed to fetch|network/i.test(String(error.message || ""))
  );
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const json = await response.json();
    if (typeof json === "string") return json;
    if (json && typeof json === "object") {
      const body = json as Record<string, unknown>;
      const detail = body.message ?? body.error ?? body.detail;
      if (typeof detail === "string" && detail.trim()) return detail;
      return JSON.stringify(body);
    }
  } catch {
    // Ignore JSON parse failure and fall back to text.
  }

  try {
    const text = await response.text();
    if (text.trim()) return text;
  } catch {
    // Ignore text parse failure and fall back to status text.
  }

  return response.statusText || "";
}

function buildRequestInit({
  body,
  cache,
  headers,
  json,
  token,
  useWorkspace = true,
  ...rest
}: ApiRequestOptions): RequestInit {
  const activeWorkspaceId = useWorkspace ? getStoredActiveWorkspaceId() : null;
  const baseHeaders: Record<string, string> = {};

  if (token) {
    baseHeaders.Authorization = `Bearer ${token}`;
  }
  if (activeWorkspaceId) {
    baseHeaders["X-Active-Workspace-Id"] = activeWorkspaceId;
  }
  if (json !== undefined) {
    baseHeaders["Content-Type"] = "application/json";
  }

  return {
    ...rest,
    ...(cache ? { cache } : {}),
    headers: {
      ...baseHeaders,
      ...(headers ?? {}),
    },
    ...(json !== undefined
      ? { body: serializeJsonBody(json) }
      : body !== undefined
        ? { body }
        : {}),
  };
}

export async function apiRequest<T = unknown>(
  path: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  const {
    responseType = "json",
    retryWithSameOrigin = true,
    ...requestOptions
  } = options;
  const init = buildRequestInit(requestOptions);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch (error) {
    const canRetry =
      retryWithSameOrigin &&
      API_BASE.startsWith("http") &&
      path.startsWith("/") &&
      isNetworkFailure(error);
    if (!canRetry) throw error;
    response = await fetch(path, init);
  }

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(`API ${path}: ${response.status}${detail ? ` - ${detail}` : ""}`);
  }

  if (responseType === "response") {
    return response as T;
  }
  if (responseType === "void" || response.status === 204) {
    return undefined as T;
  }
  if (responseType === "text") {
    return (await response.text()) as T;
  }
  return (await response.json()) as T;
}
