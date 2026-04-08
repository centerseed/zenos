/**
 * API layer — all data fetching goes through the ZenOS REST API.
 * Replaces direct Firestore SDK calls. All functions require a Firebase ID token.
 */
import type { Entity, Relationship, Blindspot, Task, TaskComment, Partner, QualitySignals, ImpactChainHop } from "@/types";
import { getPartnerWorkspaceRole } from "@/lib/partner";

export const API_BASE =
  process.env.NEXT_PUBLIC_MCP_API_URL ||
  "https://zenos-mcp-165893875709.asia-east1.run.app";

const DATE_FIELDS = new Set([
  "createdAt", "updatedAt", "completedAt", "dueDate", "lastReviewedAt", "generatedAt",
]);

/** Recursively convert ISO date strings to Date objects in-place */
function hydrateDates<T>(obj: T): T {
  if (obj === null || obj === undefined) return obj;
  if (Array.isArray(obj)) {
    obj.forEach(hydrateDates);
    return obj;
  }
  if (typeof obj === "object") {
    for (const [key, val] of Object.entries(obj as Record<string, unknown>)) {
      if (DATE_FIELDS.has(key) && typeof val === "string") {
        (obj as Record<string, unknown>)[key] = new Date(val);
      } else if (val !== null && typeof val === "object") {
        hydrateDates(val);
      }
    }
  }
  return obj;
}

async function apiFetch<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`API ${path}: ${res.status}`);
  const data = await res.json();
  return hydrateDates(data) as T;
}

function normalizePartner(data: Record<string, unknown>): Partner {
  const rawAccessMode = data.accessMode ?? data.access_mode;
  const authorizedEntityIds = Array.isArray(data.authorizedEntityIds) ? data.authorizedEntityIds : [];
  const normalizedAccessMode =
    rawAccessMode === "internal" || rawAccessMode === "scoped" || rawAccessMode === "unassigned"
      ? rawAccessMode
      : undefined;
  const normalizedWorkspaceRole =
    data.workspaceRole ?? data.workspace_role;
  const workspaceRole = getPartnerWorkspaceRole({
    accessMode: normalizedAccessMode,
    authorizedEntityIds,
    isAdmin: Boolean(data.isAdmin),
    workspaceRole:
      normalizedWorkspaceRole === "owner" ||
      normalizedWorkspaceRole === "member" ||
      normalizedWorkspaceRole === "guest"
        ? normalizedWorkspaceRole
        : undefined,
  });
  // Trust the server-provided accessMode when it is a valid value.
  // Re-deriving from authorizedEntityIds.length loses the "scoped" state when
  // the guest has no entity list yet (workspace_role="guest" + empty IDs).
  const resolvedAccessMode =
    normalizedAccessMode ??
    (workspaceRole === "owner" || workspaceRole === "member"
      ? "internal"
      : authorizedEntityIds.length > 0
        ? "scoped"
        : "unassigned");
  return hydrateDates({
    ...data,
    accessMode: resolvedAccessMode,
    workspaceRole,
    isAdmin: Boolean(data.isAdmin) || workspaceRole === "owner",
    authorizedEntityIds,
    sharedPartnerId: data.sharedPartnerId ?? data.shared_partner_id ?? null,
  }) as Partner;
}

/** Fetch all product entities */
export async function getProjectEntities(token: string): Promise<Entity[]> {
  const res = await apiFetch<{ entities: Entity[] }>("/api/data/entities?type=product", token);
  return res.entities;
}

/** Fetch a single entity by ID */
export async function getEntity(
  token: string,
  entityId: string
): Promise<Entity | null> {
  try {
    const res = await apiFetch<{ entity: Entity }>(`/api/data/entities/${entityId}`, token);
    return res.entity;
  } catch {
    return null;
  }
}

export interface EntityContextResponse {
  entity: Entity;
  impact_chain: ImpactChainHop[];
  reverse_impact_chain: ImpactChainHop[];
}

/** Fetch a single entity together with impact chain context */
export async function getEntityContext(
  token: string,
  entityId: string
): Promise<EntityContextResponse | null> {
  try {
    return await apiFetch<EntityContextResponse>(`/api/data/entities/${entityId}`, token);
  } catch {
    return null;
  }
}

/** Fetch child entities of a parent */
export async function getChildEntities(
  token: string,
  parentId: string
): Promise<Entity[]> {
  const result = await apiFetch<{ entities: Entity[]; count: number }>(
    `/api/data/entities/${parentId}/children`,
    token
  );
  return result.entities;
}

/** Count child entities of a parent */
export async function countChildEntities(
  token: string,
  parentId: string
): Promise<number> {
  const result = await apiFetch<{ entities: Entity[]; count: number }>(
    `/api/data/entities/${parentId}/children`,
    token
  );
  return result.count;
}

/** Fetch all entities (all types) */
export async function getAllEntities(token: string): Promise<Entity[]> {
  const res = await apiFetch<{ entities: Entity[] }>("/api/data/entities", token);
  return res.entities;
}

/** Fetch relationships for an entity */
export async function getRelationships(
  token: string,
  entityId: string
): Promise<Relationship[]> {
  const res = await apiFetch<{ relationships: Relationship[] }>(
    `/api/data/entities/${entityId}/relationships`,
    token
  );
  return res.relationships;
}

/** Fetch all relationships */
export async function getAllRelationships(token: string): Promise<Relationship[]> {
  const res = await apiFetch<{ relationships: Relationship[] }>("/api/data/relationships", token);
  return res.relationships;
}

/** Fetch blindspots related to an entity */
export async function getBlindspots(
  token: string,
  entityId: string
): Promise<Blindspot[]> {
  const res = await apiFetch<{ blindspots: Blindspot[] }>(
    `/api/data/blindspots?entity_id=${entityId}`,
    token
  );
  return res.blindspots;
}

/** Fetch all blindspots */
export async function getAllBlindspots(token: string): Promise<Blindspot[]> {
  const res = await apiFetch<{ blindspots: Blindspot[] }>("/api/data/blindspots", token);
  return res.blindspots;
}

/** Fetch tasks with optional filters */
export async function getTasks(
  token: string,
  filters?: {
    statuses?: string[];
    assignee?: string;
    createdBy?: string;
  }
): Promise<Task[]> {
  const params = new URLSearchParams();
  if (filters?.statuses && filters.statuses.length > 0) {
    for (const s of filters.statuses) {
      params.append("status", s);
    }
  }
  if (filters?.assignee) params.set("assignee", filters.assignee);
  if (filters?.createdBy) params.set("created_by", filters.createdBy);

  const qs = params.toString();
  const res = await apiFetch<{ tasks: Task[] }>(`/api/data/tasks${qs ? `?${qs}` : ""}`, token);
  return res.tasks;
}

/** Fetch tasks linked to an entity */
export async function getTasksByEntity(
  token: string,
  entityId: string
): Promise<Task[]> {
  const res = await apiFetch<{ tasks: Task[] }>(`/api/data/tasks/by-entity/${entityId}`, token);
  return res.tasks;
}

/** Fetch the current partner (auth) */
export async function getPartnerMe(token: string): Promise<Partner> {
  const res = await apiFetch<{ partner: Partner }>("/api/partner/me", token);
  return normalizePartner(res.partner as unknown as Record<string, unknown>);
}

export async function getPartners(token: string): Promise<Partner[]> {
  const res = await apiFetch<{ partners: Partner[] }>("/api/partners", token);
  return (res.partners ?? []).map((partner) => normalizePartner(partner as unknown as Record<string, unknown>));
}

export async function updatePartnerScope(
  token: string,
  partnerId: string,
  data: { roles: string[]; department: string; accessMode?: Partner["accessMode"]; authorizedEntityIds?: string[] }
): Promise<Partner> {
  const res = await fetch(`${API_BASE}/api/partners/${partnerId}/scope`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      ...data,
      access_mode: data.accessMode,
    }),
  });
  if (!res.ok) throw new Error(`API /api/partners/${partnerId}/scope: ${res.status}`);
  return normalizePartner(await res.json() as Record<string, unknown>);
}

export async function getDepartments(token: string): Promise<string[]> {
  const res = await apiFetch<{ departments: string[] }>("/api/departments", token);
  return res.departments;
}

export async function createDepartment(token: string, name: string): Promise<string[]> {
  const res = await fetch(`${API_BASE}/api/departments`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(`API /api/departments: ${res.status}`);
  const data = await res.json();
  return data.departments ?? [];
}

export async function renameDepartment(token: string, currentName: string, nextName: string): Promise<string[]> {
  const res = await fetch(`${API_BASE}/api/departments/${encodeURIComponent(currentName)}`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ name: nextName }),
  });
  if (!res.ok) throw new Error(`API /api/departments/${currentName}: ${res.status}`);
  const data = await res.json();
  return data.departments ?? [];
}

export async function deleteDepartment(token: string, name: string, fallback = "all"): Promise<string[]> {
  const res = await fetch(
    `${API_BASE}/api/departments/${encodeURIComponent(name)}?fallback=${encodeURIComponent(fallback)}`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
  if (!res.ok) throw new Error(`API /api/departments/${name}: ${res.status}`);
  const data = await res.json();
  return data.departments ?? [];
}

export async function updateEntityVisibility(
  token: string,
  entityId: string,
  data: {
    visibility: Entity["visibility"];
    visible_to_roles?: string[];
    visible_to_members?: string[];
    visible_to_departments?: string[];
  }
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/entities/${entityId}/visibility`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`API /api/entities/${entityId}/visibility: ${res.status}`);
}

/** Request a signed upload URL for a task attachment */
export async function uploadTaskAttachment(
  token: string,
  taskId: string,
  data: { filename: string; content_type: string; description?: string }
): Promise<{ attachment_id: string; proxy_url: string; signed_put_url: string }> {
  const res = await fetch(`${API_BASE}/api/data/tasks/${taskId}/attachments`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Upload attachment failed: ${res.status}`);
  return res.json();
}

/** Upload file directly to GCS using a signed PUT URL */
export async function uploadToSignedUrl(
  signedUrl: string,
  file: File
): Promise<void> {
  const res = await fetch(signedUrl, {
    method: "PUT",
    headers: { "Content-Type": file.type },
    body: file,
  });
  if (!res.ok) throw new Error(`GCS upload failed: ${res.status}`);
}

/** Add a link attachment to a task */
export async function addLinkAttachment(
  token: string,
  taskId: string,
  data: { url: string; filename?: string; description?: string }
): Promise<{ attachment_id: string }> {
  const res = await fetch(`${API_BASE}/api/data/tasks/${taskId}/attachments`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ type: "link", ...data }),
  });
  if (!res.ok) throw new Error(`Add link attachment failed: ${res.status}`);
  return res.json();
}

/** Fetch quality signals: search_unused and summary_poor flags */
export async function getQualitySignals(token: string): Promise<QualitySignals> {
  return apiFetch<QualitySignals>("/api/data/quality-signals", token);
}

/** Create a new task */
export async function createTask(
  token: string,
  data: {
    title: string;
    description?: string;
    priority?: string;
    assignee?: string;
    due_date?: string;
    project?: string;
  }
): Promise<Task> {
  const res = await fetch(`${API_BASE}/api/data/tasks`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Create task failed: ${res.status}`);
  const body = await res.json();
  return hydrateDates(body.task ?? body) as Task;
}

/** Update an existing task (partial update) */
export async function updateTask(
  token: string,
  taskId: string,
  updates: {
    status?: string;
    title?: string;
    description?: string;
    priority?: string;
    assignee?: string;
    due_date?: string | null;
    result?: string;
  }
): Promise<Task> {
  const res = await fetch(`${API_BASE}/api/data/tasks/${taskId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(updates),
  });
  if (!res.ok) throw new Error(`Update task failed: ${res.status}`);
  const body = await res.json();
  return hydrateDates(body.task ?? body) as Task;
}

/** Confirm a task (approve or reject) */
export async function confirmTask(
  token: string,
  taskId: string,
  data: {
    action: "approve" | "reject";
    rejection_reason?: string;
  }
): Promise<Task> {
  const res = await fetch(`${API_BASE}/api/data/tasks/${taskId}/confirm`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Confirm task failed: ${res.status}`);
  const body = await res.json();
  return hydrateDates(body.task ?? body) as Task;
}

/** Fetch comments for a task */
export async function getTaskComments(token: string, taskId: string): Promise<TaskComment[]> {
  const res = await apiFetch<{ comments: Array<{
    id: string; task_id: string; partner_id: string; author_name: string; content: string; created_at: string;
  }> }>(`/api/data/tasks/${taskId}/comments`, token);
  return res.comments.map((c) => hydrateDates({
    id: c.id,
    taskId: c.task_id,
    partnerId: c.partner_id,
    authorName: c.author_name,
    content: c.content,
    createdAt: new Date(c.created_at),
  }) as TaskComment);
}

/** Create a comment on a task */
export async function createTaskComment(token: string, taskId: string, content: string): Promise<TaskComment> {
  const res = await fetch(`${API_BASE}/api/data/tasks/${taskId}/comments`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error(`Create comment failed: ${res.status}`);
  const body = await res.json();
  const c = body.comment;
  return hydrateDates({
    id: c.id,
    taskId: c.task_id,
    partnerId: c.partner_id,
    authorName: c.author_name ?? c.partner_id,
    content: c.content,
    createdAt: new Date(c.created_at),
  }) as TaskComment;
}

/** Delete a task comment */
export async function deleteTaskComment(token: string, taskId: string, commentId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/data/tasks/${taskId}/comments/${commentId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`Delete comment failed: ${res.status}`);
}

/** Delete a task attachment */
export async function deleteTaskAttachment(
  token: string,
  taskId: string,
  attachmentId: string
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/data/tasks/${taskId}/attachments/${attachmentId}`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
  if (!res.ok) throw new Error(`Delete attachment failed: ${res.status}`);
}
