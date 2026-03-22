import {
  collection,
  query,
  where,
  getDocs,
  doc,
  getDoc,
} from "firebase/firestore";
import { getDbInstance } from "./firebase";
import type { Entity, Relationship, Blindspot, DocumentEntry, Task } from "@/types";

export function toEntity(id: string, data: Record<string, unknown>): Entity {
  return {
    id,
    name: data.name as string,
    type: data.type as Entity["type"],
    summary: data.summary as string,
    tags: data.tags as Entity["tags"],
    status: (data.status as Entity["status"]) ?? "active",
    parentId: (data.parentId as string) ?? null,
    details: (data.details as Record<string, unknown>) ?? null,
    confirmedByUser: (data.confirmedByUser as boolean) ?? false,
    createdAt: (data.createdAt as { toDate: () => Date })?.toDate?.() ?? new Date(),
    updatedAt: (data.updatedAt as { toDate: () => Date })?.toDate?.() ?? new Date(),
  };
}

/** Fetch all product entities */
export async function getProjectEntities(): Promise<Entity[]> {
  const q = query(
    collection(getDbInstance(), "entities"),
    where("type", "==", "product")
  );
  const snapshot = await getDocs(q);
  return snapshot.docs.map((d) => toEntity(d.id, d.data()));
}

/** Fetch a single entity by ID */
export async function getEntity(entityId: string): Promise<Entity | null> {
  const ref = doc(getDbInstance(), "entities", entityId);
  const snapshot = await getDoc(ref);
  if (!snapshot.exists()) return null;
  return toEntity(snapshot.id, snapshot.data());
}

/** Fetch child entities (modules, goals) of a product */
export async function getChildEntities(parentId: string): Promise<Entity[]> {
  const q = query(
    collection(getDbInstance(), "entities"),
    where("parentId", "==", parentId)
  );
  const snapshot = await getDocs(q);
  return snapshot.docs.map((d) => toEntity(d.id, d.data()));
}

/** Count child entities of a product */
export async function countChildEntities(parentId: string): Promise<number> {
  const q = query(
    collection(getDbInstance(), "entities"),
    where("parentId", "==", parentId)
  );
  const snapshot = await getDocs(q);
  return snapshot.size;
}

/** Fetch relationships for an entity */
export async function getRelationships(entityId: string): Promise<Relationship[]> {
  const snapshot = await getDocs(
    collection(getDbInstance(), "entities", entityId, "relationships")
  );
  return snapshot.docs.map((d) => {
    const data = d.data();
    return {
      id: d.id,
      sourceEntityId: data.sourceEntityId as string,
      targetId: data.targetId as string,
      type: data.type as Relationship["type"],
      description: data.description as string,
      confirmedByUser: (data.confirmedByUser as boolean) ?? false,
    };
  });
}

/** Fetch blindspots related to an entity */
export async function getBlindspots(entityId: string): Promise<Blindspot[]> {
  const q = query(
    collection(getDbInstance(), "blindspots"),
    where("relatedEntityIds", "array-contains", entityId)
  );
  const snapshot = await getDocs(q);
  return snapshot.docs.map((d) => {
    const data = d.data();
    return {
      id: d.id,
      description: data.description as string,
      severity: data.severity as Blindspot["severity"],
      relatedEntityIds: (data.relatedEntityIds as string[]) ?? [],
      suggestedAction: data.suggestedAction as string,
      status: (data.status as Blindspot["status"]) ?? "open",
      confirmedByUser: (data.confirmedByUser as boolean) ?? false,
      createdAt: (data.createdAt as { toDate: () => Date })?.toDate?.() ?? new Date(),
    };
  });
}

/** Count documents linked to an entity */
export async function countDocuments(entityId: string): Promise<number> {
  const q = query(
    collection(getDbInstance(), "documents"),
    where("linkedEntityIds", "array-contains", entityId)
  );
  const snapshot = await getDocs(q);
  return snapshot.size;
}

export function toTask(id: string, data: Record<string, unknown>): Task {
  return {
    id,
    title: data.title as string,
    description: (data.description as string) ?? "",
    status: data.status as Task["status"],
    priority: (data.priority as Task["priority"]) ?? "medium",
    priorityReason: (data.priorityReason as string) ?? "",
    assignee: (data.assignee as string) ?? null,
    createdBy: (data.createdBy as string) ?? "",
    linkedEntities: (data.linkedEntities as string[]) ?? [],
    linkedProtocol: (data.linkedProtocol as string) ?? null,
    linkedBlindspot: (data.linkedBlindspot as string) ?? null,
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

/** Fetch tasks with optional filters */
export async function getTasks(filters?: {
  statuses?: string[];
  assignee?: string;
  createdBy?: string;
}): Promise<Task[]> {
  const constraints = [];

  if (filters?.statuses && filters.statuses.length > 0) {
    // Firestore 'in' query limited to 10 values per clause
    // If more than 10, we need to batch — but TaskStatus only has 8 values so this is safe
    constraints.push(where("status", "in", filters.statuses));
  } else {
    // Default: exclude archived
    const defaultStatuses = ["backlog", "todo", "in_progress", "review", "done", "blocked", "cancelled"];
    constraints.push(where("status", "in", defaultStatuses));
  }

  if (filters?.assignee) {
    constraints.push(where("assignee", "==", filters.assignee));
  }

  if (filters?.createdBy) {
    constraints.push(where("createdBy", "==", filters.createdBy));
  }

  const q = query(collection(getDbInstance(), "tasks"), ...constraints);
  const snapshot = await getDocs(q);
  return snapshot.docs.map((d) => toTask(d.id, d.data()));
}

/** Fetch tasks linked to an entity */
export async function getTasksByEntity(entityId: string): Promise<Task[]> {
  const q = query(
    collection(getDbInstance(), "tasks"),
    where("linkedEntities", "array-contains", entityId)
  );
  const snapshot = await getDocs(q);
  return snapshot.docs.map((d) => toTask(d.id, d.data()));
}
