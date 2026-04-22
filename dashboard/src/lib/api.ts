/**
 * API layer — all data fetching goes through the ZenOS REST API.
 * Replaces direct Firestore SDK calls. All functions require a Firebase ID token.
 */
import type { BundleHighlight, Entity, Relationship, Blindspot, Task, TaskComment, Partner, QualitySignals, ImpactChainHop } from "@/types";
import { getPartnerWorkspaceRole } from "@/lib/partner";
import {
  API_BASE,
  apiRequest,
  hydrateDateFields,
  setActiveWorkspaceId,
} from "@/lib/api-client";

export { API_BASE, setActiveWorkspaceId };

const DATE_FIELDS = new Set([
  "createdAt", "updatedAt", "completedAt", "dueDate", "lastReviewedAt", "generatedAt",
  "summaryUpdatedAt", "highlightsUpdatedAt",
  "lastAppliedAt",
  "summary_updated_at", "highlights_updated_at", "last_published_at", "due_date",
  "updated_at", "cached_at",
]);

/** Recursively convert ISO date strings to Date objects in-place */
function hydrateDates<T>(obj: T): T {
  return hydrateDateFields(obj, DATE_FIELDS);
}

async function apiFetch<T>(
  path: string,
  token: string,
  options?: { cache?: RequestCache }
): Promise<T> {
  const data = await apiRequest<T>(path, {
    cache: options?.cache,
    token,
  });
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
    activeWorkspaceId:
      typeof data.activeWorkspaceId === "string" ? data.activeWorkspaceId : null,
    homeWorkspaceId:
      typeof data.homeWorkspaceId === "string" ? data.homeWorkspaceId : null,
    availableWorkspaces: Array.isArray(data.availableWorkspaces)
      ? data.availableWorkspaces
          .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
          .map((item) => ({
            id: String(item.id ?? ""),
            name: String(item.name ?? ""),
            hasUpdate: Boolean(item.hasUpdate),
          }))
          .filter((item) => item.id && item.name)
      : undefined,
    sharedPartnerId: data.sharedPartnerId ?? data.shared_partner_id ?? null,
  }) as unknown as Partner;
}

function unwrapTaskPayload(payload: { task?: Task } | Task): Task {
  if ("id" in payload) {
    return payload;
  }
  if (payload.task) {
    return payload.task;
  }
  throw new Error("Task payload missing task");
}

function normalizeTagList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .filter((item): item is string => typeof item === "string")
      .map((item) => item.trim().toLowerCase())
      .filter(Boolean);
  }
  if (typeof value === "string" && value.trim()) {
    return [value.trim().toLowerCase()];
  }
  return [];
}

function isProbablyTestRoot(entity: Entity): boolean {
  return /\btest\b|dogfood|demo/i.test(entity.name);
}

function isLegacyCrmProductProxy(entity: Entity): boolean {
  if (entity.type !== "product") return false;
  const whatTags = normalizeTagList(entity.tags?.what);
  if (whatTags.includes("company")) return true;

  const details = entity.details && typeof entity.details === "object" ? entity.details : {};
  return ["crm_company_id", "crm_record_id", "company_id", "crm_snapshot"].some((key) =>
    Object.prototype.hasOwnProperty.call(details, key)
  );
}

function isShareableRootEntity(entity: Entity): boolean {
  const isSupportedType = entity.type === "product" || entity.type === "company";
  const isRoot = !entity.parentId && (entity.level === 1 || entity.level == null);
  return (
    isSupportedType &&
    isRoot &&
    entity.status === "active" &&
    entity.visibility === "public" &&
    !isProbablyTestRoot(entity) &&
    !isLegacyCrmProductProxy(entity)
  );
}

/** Fetch project entities or shareable L1 roots used by Team sharing. */
export async function getProjectEntities(
  token: string,
  options?: { scope?: "projects" | "shareableRoots" }
): Promise<Entity[]> {
  if (options?.scope === "shareableRoots") {
    const res = await apiFetch<{ entities: Entity[] }>("/api/data/entities", token);
    return (res.entities ?? []).filter(isShareableRootEntity);
  }

  const res = await apiFetch<{ entities: Entity[] }>("/api/data/entities?type=product", token);
  return res.entities;
}

export async function getProjectEntitiesInWorkspace(token: string, workspaceId: string): Promise<Entity[]> {
  const res = await apiRequest<{ entities: Entity[] }>("/api/data/entities?type=product", {
    headers: { "X-Active-Workspace-Id": workspaceId },
    token,
    useWorkspace: false,
  });
  return hydrateDates(res.entities ?? []) as Entity[];
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

export interface GraphContextDocument {
  id: string;
  doc_id: string;
  title: string;
  type: string;
  status: string;
  summary: string;
  updated_at?: Date | null;
}

export interface GraphContextNeighbor {
  id: string;
  name: string;
  type: string;
  level: number | null;
  status: string;
  summary: string;
  updated_at?: Date | null;
  distance: number;
  tags: {
    what: string[];
    why: string;
    how: string;
    who: string[];
  };
  documents: GraphContextDocument[];
}

export interface GraphContextResponse {
  seed: {
    id: string;
    name: string;
    type: string;
    level: number | null;
    status: string;
    summary: string;
    updated_at?: Date | null;
    tags: {
      what: string[];
      why: string;
      how: string;
      who: string[];
    };
  };
  fallback_mode: "normal" | "l1_tags_only";
  neighbors: GraphContextNeighbor[];
  partial: boolean;
  errors?: string[];
  truncated: boolean;
  truncation_details: {
    dropped_l2: number;
    dropped_l3: number;
    summary_truncated: number;
  };
  estimated_tokens: number;
  cached_at: Date;
}

export interface ProjectProgressTaskSummary {
  id: string;
  title: string;
  status: string;
  priority: string;
  plan_order: number | null;
  assignee_name: string | null;
  due_date: Date | null;
  overdue: boolean;
  blocked: boolean;
  blocked_reason: string | null;
  parent_task_id: string | null;
  updated_at: Date | null;
  subtasks: ProjectProgressTaskSummary[];
}

export interface ProjectProgressPlanSummary {
  id: string;
  goal: string;
  status: string;
  owner: string | null;
  milestones: Array<{
    id: string;
    name: string;
  }>;
  tasks_summary: {
    total?: number;
    by_status?: Record<string, number>;
  };
  open_count: number;
  blocked_count: number;
  review_count: number;
  overdue_count: number;
  updated_at: Date | null;
  next_tasks: ProjectProgressTaskSummary[];
}

export interface ProjectProgressOpenWorkGroup {
  plan_id: string | null;
  plan_goal: string | null;
  plan_status: string | null;
  open_count: number;
  blocked_count: number;
  review_count: number;
  overdue_count: number;
  tasks: ProjectProgressTaskSummary[];
}

export interface ProjectProgressMilestone {
  id: string;
  name: string;
  open_count: number;
}

export interface ProjectRecentProgressItem {
  id: string;
  kind: "task" | "plan" | "entity";
  title: string;
  subtitle: string;
  updated_at: Date | null;
}

export interface ProjectProgressResponse {
  project: Entity;
  active_plans: ProjectProgressPlanSummary[];
  open_work_groups: ProjectProgressOpenWorkGroup[];
  milestones: ProjectProgressMilestone[];
  recent_progress: ProjectRecentProgressItem[];
}

function normalizeProjectProgress(
  response: ProjectProgressResponse
): ProjectProgressResponse {
  const activePlans = (response.active_plans ?? [])
    .map((plan) => ({
      ...plan,
      milestones: Array.isArray(plan.milestones) ? plan.milestones : [],
      next_tasks: Array.isArray(plan.next_tasks) ? plan.next_tasks : [],
    }))
    .filter((plan) => plan.open_count > 0);
  const visiblePlanIds = new Set(activePlans.map((plan) => plan.id));
  const openWorkGroups = (response.open_work_groups ?? [])
    .map((group) => ({
      ...group,
      tasks: Array.isArray(group.tasks) ? group.tasks : [],
    }))
    .filter((group) => group.open_count > 0);
  const milestones = (response.milestones ?? []).filter((milestone) => milestone.open_count > 0);
  const recentProgress = (response.recent_progress ?? []).filter((item) => {
    if (item.kind !== "plan") return true;
    return visiblePlanIds.has(item.id);
  });
  return {
    ...response,
    active_plans: activePlans,
    open_work_groups: openWorkGroups,
    milestones,
    recent_progress: recentProgress,
  };
}

export interface PlanSummary {
  id: string;
  goal: string;
  status: string;
  owner: string | null;
  entry_criteria?: string | null;
  exit_criteria?: string | null;
  project?: string | null;
  project_id?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
  result?: string | null;
  created_at?: Date | null;
  updated_at?: Date | null;
  tasks_summary?: {
    total?: number;
    by_status?: Record<string, number>;
  };
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

export async function getCoworkGraphContext(
  token: string,
  params: {
    seedId: string;
    budgetTokens?: number;
    includeDocs?: boolean;
  }
): Promise<GraphContextResponse | null> {
  const search = new URLSearchParams({ seed_id: params.seedId });
  if (typeof params.budgetTokens === "number") {
    search.set("budget_tokens", String(params.budgetTokens));
  }
  if (params.includeDocs === false) {
    search.set("include_docs", "false");
  }
  try {
    return await apiFetch<GraphContextResponse>(`/api/cowork/graph-context?${search.toString()}`, token);
  } catch {
    return null;
  }
}

export interface DocumentDeliveryResponse {
  document: {
    id: string;
    name: string;
    summary: string;
    visibility: Entity["visibility"];
    sources: Entity["sources"];
    doc_role?: "single" | "index" | null;
    bundle_highlights?: BundleHighlight[];
    highlights_updated_at?: Date | null;
    change_summary?: string | null;
    summary_updated_at?: Date | null;
    canonical_path?: string | null;
    primary_snapshot_revision_id?: string | null;
    last_published_at?: Date | null;
    delivery_status?: "ready" | "stale" | "blocked" | null;
    latest_revision?: Record<string, unknown> | null;
  };
}

export interface DocumentContentResponse {
  doc_id: string;
  canonical_path?: string | null;
  delivery_status?: "ready" | "stale" | "blocked" | null;
  revision?: Record<string, unknown> | null;
  content_type: string;
  content: string;
}

export async function getDocumentDelivery(
  token: string,
  docId: string
): Promise<DocumentDeliveryResponse | null> {
  try {
    return await apiFetch<DocumentDeliveryResponse>(`/api/docs/${docId}`, token);
  } catch {
    return null;
  }
}

export async function getDocumentContent(
  token: string,
  docId: string
): Promise<DocumentContentResponse | null> {
  try {
    return await apiFetch<DocumentContentResponse>(`/api/docs/${docId}/content`, token);
  } catch {
    return null;
  }
}

export async function publishDocumentSnapshot(
  token: string,
  docId: string
): Promise<{ revision_id: string; canonical_path: string } | null> {
  try {
    const result = await apiRequest<{ revision_id: string; canonical_path: string }>(
      `/api/docs/${docId}/publish`,
      {
        method: "POST",
        token,
      }
    );
    return hydrateDates(result);
  } catch {
    return null;
  }
}

export async function saveDocumentMarkdown(
  token: string,
  docId: string,
  content: string,
  opts: { base_revision_id: string; source_id?: string; source_version_ref?: string }
): Promise<{ revision_id: string; canonical_path: string } | null> {
  try {
    const result = await apiRequest<{ revision_id: string; canonical_path: string }>(
      `/api/docs/${docId}/content`,
      {
        json: {
          base_revision_id: opts.base_revision_id,
          content,
          ...(opts?.source_id ? { source_id: opts.source_id } : {}),
          ...(opts?.source_version_ref ? { source_version_ref: opts.source_version_ref } : {}),
        },
        method: "POST",
        token,
      }
    );
    return hydrateDates(result);
  } catch {
    return null;
  }
}

export async function updateDocumentVisibility(
  token: string,
  docId: string,
  visibility: Entity["visibility"]
): Promise<{ visibility: Entity["visibility"]; warnings?: string[] } | null> {
  try {
    const result = await apiRequest<{ visibility: Entity["visibility"]; warnings?: string[] }>(
      `/api/docs/${docId}/access`,
      {
        json: { visibility },
        method: "PATCH",
        token,
      }
    );
    return hydrateDates(result);
  } catch {
    return null;
  }
}

export async function createDocumentShareLink(
  token: string,
  docId: string,
  opts?: { expires_in_hours?: number; max_access_count?: number }
): Promise<{ token_id: string; share_url: string; expires_at: Date } | null> {
  try {
    const result = await apiRequest<{ token_id: string; share_url: string; expires_at: Date }>(
      `/api/docs/${docId}/share-links`,
      {
        json: opts ?? {},
        method: "POST",
        token,
      }
    );
    return hydrateDates(result);
  } catch {
    return null;
  }
}

export async function revokeDocumentShareLink(
  token: string,
  tokenId: string
): Promise<boolean> {
  try {
    await apiRequest(`/api/docs/share-links/${tokenId}`, {
      method: "DELETE",
      responseType: "void",
      token,
    });
    return true;
  } catch {
    return false;
  }
}

export async function getSharedDocumentByToken(
  token: string
): Promise<{ doc: { id: string; name: string }; content: string } | null> {
  try {
    const result = await apiRequest<{ doc: { id: string; name: string }; content: string }>(
      `/s/${encodeURIComponent(token)}`,
      {
        retryWithSameOrigin: true,
        useWorkspace: false,
      }
    );
    return hydrateDates(result);
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

export async function getPlans(
  token: string,
  planIds?: string[],
): Promise<PlanSummary[]> {
  const params = new URLSearchParams();
  for (const planId of planIds ?? []) {
    if (planId?.trim()) params.append("id", planId.trim());
  }
  const qs = params.toString();
  const res = await apiFetch<{ plans: PlanSummary[] }>(`/api/data/plans${qs ? `?${qs}` : ""}`, token);
  return res.plans;
}

export async function createPlan(
  token: string,
  data: {
    goal: string;
    owner?: string | null;
    entry_criteria?: string | null;
    exit_criteria?: string | null;
    project?: string | null;
    project_id?: string | null;
    status?: "draft" | "active";
  },
): Promise<PlanSummary> {
  const res = await apiRequest<{ plan: PlanSummary }>("/api/data/plans", {
    json: data,
    method: "POST",
    token,
  });
  return hydrateDates(res.plan) as PlanSummary;
}

export async function createMilestone(
  token: string,
  data: {
    name: string;
    summary?: string;
    project_id: string;
    status?: "planned" | "active";
    owner?: string | null;
  },
): Promise<Entity> {
  const res = await apiRequest<{ milestone: Entity }>("/api/data/milestones", {
    json: data,
    method: "POST",
    token,
  });
  return hydrateDates(res.milestone) as Entity;
}

/** Fetch project progress aggregate payload for the project console. */
export async function getProjectProgress(
  token: string,
  entityId: string
): Promise<ProjectProgressResponse> {
  const response = await apiFetch<ProjectProgressResponse>(`/api/data/projects/${entityId}/progress`, token, {
    cache: "no-store",
  });
  return normalizeProjectProgress(response);
}

/** Fetch the current partner (auth) */
export async function getPartnerMe(token: string): Promise<Partner> {
  const res = await apiFetch<{ partner: Partner }>("/api/partner/me", token, { cache: "no-store" });
  return normalizePartner(res.partner as unknown as Record<string, unknown>);
}

export async function getPreferences(token: string): Promise<import("@/types").PartnerPreferences> {
  const res = await apiFetch<{ preferences: import("@/types").PartnerPreferences }>("/api/partner/preferences", token);
  return res.preferences ?? {};
}

export async function updatePreferences(
  token: string,
  patch: import("@/types").PartnerPreferences,
): Promise<import("@/types").PartnerPreferences> {
  const data = await apiRequest<{ preferences: import("@/types").PartnerPreferences }>(
    "/api/partner/preferences",
    {
      json: patch,
      method: "PATCH",
      token,
    }
  );
  return data.preferences ?? {};
}

export async function checkGoogleWorkspaceConnectorHealth(
  token: string,
  config?: {
    sidecar_base_url?: string;
    sidecar_token?: string;
  },
): Promise<{
  ok: boolean;
  status: string;
  message?: string;
  capability?: Record<string, unknown> | null;
}> {
  return apiRequest("/api/connectors/google-workspace/health", {
    json: config ?? {},
    method: "POST",
    token,
  });
}

export async function getPartners(token: string): Promise<Partner[]> {
  const res = await apiFetch<{ partners: Partner[] }>("/api/partners", token);
  return (res.partners ?? []).map((partner) => normalizePartner(partner as unknown as Record<string, unknown>));
}

export async function activatePartner(token: string): Promise<void> {
  await apiRequest("/api/partners/activate", {
    method: "POST",
    responseType: "void",
    token,
  });
}

export async function invitePartner(
  token: string,
  data: {
    email: string;
    department: string;
    workspace_role?: "member" | "guest";
    accessMode?: Partner["accessMode"];
    access_mode?: Partner["accessMode"];
    authorized_entity_ids?: string[];
    home_workspace_bootstrap_entity_ids?: string[];
  }
): Promise<void> {
  await apiRequest("/api/partners/invite", {
    json: data,
    method: "POST",
    responseType: "void",
    token,
  });
}

export async function deletePartner(token: string, partnerId: string): Promise<void> {
  await apiRequest(`/api/partners/${partnerId}`, {
    method: "DELETE",
    responseType: "void",
    token,
  });
}

export async function updatePartnerStatus(
  token: string,
  partnerId: string,
  status: "active" | "suspended"
): Promise<void> {
  await apiRequest(`/api/partners/${partnerId}/status`, {
    json: { status },
    method: "PUT",
    responseType: "void",
    token,
  });
}

export async function updatePartnerScope(
  token: string,
  partnerId: string,
  data: {
    roles: string[];
    department: string;
    workspaceRole?: "member" | "guest";
    accessMode?: Partner["accessMode"];
    authorizedEntityIds?: string[];
    homeWorkspaceBootstrapEntityIds?: string[];
  }
): Promise<Partner> {
  const result = await apiRequest<Record<string, unknown>>(`/api/partners/${partnerId}/scope`, {
    json: {
      ...data,
      workspace_role: data.workspaceRole,
      access_mode: data.accessMode,
      authorized_entity_ids: data.authorizedEntityIds,
      home_workspace_bootstrap_entity_ids: data.homeWorkspaceBootstrapEntityIds,
    },
    method: "PUT",
    token,
  });
  return normalizePartner(result);
}

export async function applyHomeWorkspaceBootstrap(token: string): Promise<{
  applied_source_entity_ids: string[];
  copied_root_entity_ids: string[];
  copied_entity_count: number;
  copied_relationship_count: number;
  skipped_source_entity_ids: string[];
}> {
  return apiRequest("/api/partner/home-bootstrap/apply", {
    method: "POST",
    token,
  });
}

export async function getDepartments(token: string): Promise<string[]> {
  const res = await apiFetch<{ departments: string[] }>("/api/departments", token);
  return res.departments;
}

export async function createDepartment(token: string, name: string): Promise<string[]> {
  const data = await apiRequest<{ departments: string[] }>("/api/departments", {
    json: { name },
    method: "POST",
    token,
  });
  return data.departments ?? [];
}

export async function renameDepartment(token: string, currentName: string, nextName: string): Promise<string[]> {
  const data = await apiRequest<{ departments: string[] }>(
    `/api/departments/${encodeURIComponent(currentName)}`,
    {
      json: { name: nextName },
      method: "PUT",
      token,
    }
  );
  return data.departments ?? [];
}

export async function deleteDepartment(token: string, name: string, fallback = "all"): Promise<string[]> {
  const data = await apiRequest<{ departments: string[] }>(
    `/api/departments/${encodeURIComponent(name)}?fallback=${encodeURIComponent(fallback)}`,
    {
      method: "DELETE",
      token,
    }
  );
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
  await apiRequest(`/api/entities/${entityId}/visibility`, {
    json: data,
    method: "PUT",
    responseType: "void",
    token,
  });
}

/** Request a signed upload URL for a task attachment */
export async function uploadTaskAttachment(
  token: string,
  taskId: string,
  data: { filename: string; content_type: string; description?: string }
): Promise<{ attachment_id: string; proxy_url: string; signed_put_url: string }> {
  return apiRequest<{ attachment_id: string; proxy_url: string; signed_put_url: string }>(
    `/api/data/tasks/${taskId}/attachments`,
    {
      json: data,
      method: "POST",
      token,
    }
  );
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
  return apiRequest<{ attachment_id: string }>(`/api/data/tasks/${taskId}/attachments`, {
    json: { type: "link", ...data },
    method: "POST",
    token,
  });
}

/** Fetch quality signals: search_unused and summary_poor flags */
export async function getQualitySignals(token: string): Promise<QualitySignals> {
  return apiFetch<QualitySignals>("/api/data/quality-signals", token);
}

/** Fetch governance health level for the current workspace */
export async function getGovernanceHealth(token: string): Promise<{
  overall_level: "green" | "yellow" | "red";
  cached_at: string | null;
  stale: boolean;
}> {
  return apiFetch("/api/data/governance-health", token);
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
    linked_entities?: string[];
    acceptance_criteria?: string[];
    assignee_role_id?: string | null;
    linked_protocol?: string | null;
    linked_blindspot?: string | null;
    blocked_by?: string[];
    blocked_reason?: string | null;
    plan_id?: string | null;
    plan_order?: number | null;
    depends_on_task_ids?: string[];
    parent_task_id?: string | null;
    dispatcher?: string | null;
    source_metadata?: Record<string, unknown>;
  }
): Promise<Task> {
  const body = await apiRequest<{ task?: Task } | Task>("/api/data/tasks", {
    json: data,
    method: "POST",
    token,
  });
  return hydrateDates(unwrapTaskPayload(body)) as Task;
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
    assignee?: string | null;
    due_date?: string | null;
    result?: string;
    acceptance_criteria?: string[];
    assignee_role_id?: string | null;
    linked_entities?: string[];
    linked_protocol?: string | null;
    linked_blindspot?: string | null;
    blocked_by?: string[];
    blocked_reason?: string | null;
    plan_id?: string | null;
    plan_order?: number | null;
    depends_on_task_ids?: string[];
    parent_task_id?: string | null;
    dispatcher?: string | null;
    source_metadata?: Record<string, unknown>;
  }
): Promise<Task> {
  const body = await apiRequest<{ task?: Task } | Task>(`/api/data/tasks/${taskId}`, {
    json: updates,
    method: "PATCH",
    token,
  });
  return hydrateDates(unwrapTaskPayload(body)) as Task;
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
  const body = await apiRequest<{ task?: Task } | Task>(`/api/data/tasks/${taskId}/confirm`, {
    json: data,
    method: "POST",
    token,
  });
  return hydrateDates(unwrapTaskPayload(body)) as Task;
}

/** Hand off a task to a different dispatcher (agent:* or human[:id]). */
export async function handoffTask(
  token: string,
  taskId: string,
  data: {
    to_dispatcher: string;
    reason: string;
    output_ref?: string | null;
    notes?: string | null;
  }
): Promise<Task> {
  const body = await apiRequest<{ task?: Task } | Task>(`/api/data/tasks/${taskId}/handoff`, {
    json: data,
    method: "POST",
    token,
  });
  return hydrateDates(unwrapTaskPayload(body)) as Task;
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
  const body = await apiRequest<{ comment: Record<string, string> }>(`/api/data/tasks/${taskId}/comments`, {
    json: { content },
    method: "POST",
    token,
  });
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
  await apiRequest(`/api/data/tasks/${taskId}/comments/${commentId}`, {
    method: "DELETE",
    responseType: "void",
    token,
  });
}

// ─── Docs CRUD ────────────────────────────────────────────────────────────────

/** List all document entities for the current workspace */
export async function listDocs(token: string): Promise<import("@/types").Entity[]> {
  const res = await apiFetch<{ entities: import("@/types").Entity[] }>(
    "/api/data/entities?type=document",
    token
  );
  return res.entities ?? [];
}

export interface CreateDocResult {
  entity: import("@/types").Entity;
  doc_id: string;
  base_revision_id: string;
}

/**
 * Create a new native document entity.
 * Sets doc_role=index, status=draft, adds first zenos_native source.
 * The backend auto-generates canonical_path=/docs/{doc_id} and an initial revision.
 */
export async function createDoc(
  token: string,
  opts?: { name?: string; product_id?: string }
): Promise<CreateDocResult> {
  const result = await apiRequest<CreateDocResult>("/api/docs", {
    json: {
      name: opts?.name ?? "未命名文件",
      doc_role: "index",
      status: "draft",
      ...(opts?.product_id ? { product_id: opts.product_id } : {}),
    },
    method: "POST",
    token,
  });
  return hydrateDates(result) as CreateDocResult;
}

/** Delete a task attachment */
export async function deleteTaskAttachment(
  token: string,
  taskId: string,
  attachmentId: string
): Promise<void> {
  await apiRequest(`/api/data/tasks/${taskId}/attachments/${attachmentId}`, {
    method: "DELETE",
    responseType: "void",
    token,
  });
}
