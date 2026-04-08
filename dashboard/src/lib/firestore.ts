/**
 * Pure data transformation helpers.
 * Firestore SDK has been removed — all data fetching now goes through @/lib/api.
 * These helpers remain here for backwards-compatibility with existing tests.
 */
import type { Entity, Relationship, Blindspot, Task, Partner } from "@/types";

export function toEntity(id: string, data: Record<string, unknown>): Entity {
  // Normalize tags.what and tags.who to always be arrays
  const rawTags = (data.tags ?? {}) as Record<string, unknown>;
  const normalizeTagList = (val: unknown): string | string[] => {
    if (Array.isArray(val)) return val as string[];
    if (typeof val === "string") return val;
    return [];
  };
  const tags = {
    what: normalizeTagList(rawTags.what),
    why: (rawTags.why as string) ?? "",
    how: (rawTags.how as string) ?? "",
    who: normalizeTagList(rawTags.who),
  };

  return {
    id,
    name: data.name as string,
    type: data.type as Entity["type"],
    summary: data.summary as string,
    tags,
    status: (data.status as Entity["status"]) ?? "active",
    parentId: (data.parentId as string) ?? null,
    details: (data.details as Record<string, unknown>) ?? null,
    confirmedByUser: (data.confirmedByUser as boolean) ?? false,
    owner: (data.owner as string) ?? null,
    sources: (data.sources as Entity["sources"]) ?? [],
    visibility: (data.visibility as Entity["visibility"]) ?? "public",
    lastReviewedAt: (data.lastReviewedAt as { toDate?: () => Date })?.toDate?.() ?? null,
    createdAt: (data.createdAt as { toDate: () => Date })?.toDate?.() ?? new Date(),
    updatedAt: (data.updatedAt as { toDate: () => Date })?.toDate?.() ?? new Date(),
  };
}

export function toTask(id: string, data: Record<string, unknown>): Task {
  return {
    id,
    title: data.title as string,
    description: (data.description as string) ?? "",
    status: data.status as Task["status"],
    priority: (data.priority as Task["priority"]) ?? "medium",
    project: (data.project as string) ?? "",
    priorityReason: (data.priorityReason as string) ?? "",
    assignee: (data.assignee as string) ?? null,
    createdBy: (data.createdBy as string) ?? "",
    linkedEntities: (data.linkedEntities as string[]) ?? [],
    linkedProtocol: (data.linkedProtocol as string) ?? null,
    linkedBlindspot: (data.linkedBlindspot as string) ?? null,
    sourceType: (data.sourceType as string) ?? "",
    contextSummary: (data.contextSummary as string) ?? "",
    dueDate: (data.dueDate as { toDate?: () => Date })?.toDate?.() ?? null,
    blockedBy: (data.blockedBy as string[]) ?? [],
    blockedReason: (data.blockedReason as string) ?? null,
    acceptanceCriteria: (data.acceptanceCriteria as string[]) ?? [],
    confirmedByCreator: (data.confirmedByCreator as boolean) ?? false,
    rejectionReason: (data.rejectionReason as string) ?? null,
    result: (data.result as string) ?? null,
    completedBy: (data.completedBy as string) ?? null,
    createdAt: (data.createdAt as { toDate?: () => Date })?.toDate?.() ?? new Date(),
    updatedAt: (data.updatedAt as { toDate?: () => Date })?.toDate?.() ?? new Date(),
    completedAt: (data.completedAt as { toDate?: () => Date })?.toDate?.() ?? null,
  };
}

export function toPartner(id: string, data: Record<string, unknown>): Partner {
  const accessMode = data.accessMode ?? data.access_mode;
  const normalizedAccessMode =
    accessMode === "internal" || accessMode === "scoped" || accessMode === "unassigned"
      ? accessMode
      : undefined;
  return {
    id,
    email: data.email as string,
    displayName: data.displayName as string,
    apiKey: data.apiKey as string,
    authorizedEntityIds: (data.authorizedEntityIds as string[]) ?? [],
    sharedPartnerId: (data.sharedPartnerId as string) ?? null,
    accessMode:
      ((normalizedAccessMode === "scoped" && ((data.authorizedEntityIds as string[]) ?? []).length === 0)
        ? "unassigned"
        : normalizedAccessMode) ??
      (((data.isAdmin as boolean) ?? false)
        ? "internal"
        : ((data.authorizedEntityIds as string[]) ?? []).length > 0
          ? "scoped"
          : "unassigned"),
    isAdmin: (data.isAdmin as boolean) ?? false,
    status: (data.status as Partner["status"]) ?? "active",
    invitedBy: (data.invitedBy as string) ?? null,
    createdAt: (data.createdAt as { toDate?: () => Date })?.toDate?.() ?? new Date(),
    updatedAt: (data.updatedAt as { toDate?: () => Date })?.toDate?.() ?? new Date(),
  };
}
