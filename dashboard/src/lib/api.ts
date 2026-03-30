/**
 * API layer — all data fetching goes through the ZenOS REST API.
 * Replaces direct Firestore SDK calls. All functions require a Firebase ID token.
 */
import type { Entity, Relationship, Blindspot, Task, Partner } from "@/types";

const API_BASE =
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
  return res.partner;
}

export async function updatePartnerScope(
  token: string,
  partnerId: string,
  data: { roles: string[]; department: string }
): Promise<Partner> {
  const res = await fetch(`${API_BASE}/api/partners/${partnerId}/scope`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`API /api/partners/${partnerId}/scope: ${res.status}`);
  return hydrateDates(await res.json()) as Partner;
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
