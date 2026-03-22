// Firestore document types — field names match Firestore camelCase convention

export interface Partner {
  id: string;
  email: string;
  displayName: string;
  apiKey: string;
  authorizedEntityIds: string[];
  isAdmin: boolean;
  status: "active" | "suspended";
  createdAt: Date;
  updatedAt: Date;
}

export interface Tags {
  what: string;
  why: string;
  how: string;
  who: string;
}

export interface Entity {
  id: string;
  name: string;
  type: "product" | "module" | "goal" | "role" | "project";
  summary: string;
  tags: Tags;
  status: "active" | "paused" | "completed" | "planned";
  parentId: string | null;
  details: Record<string, unknown> | null;
  confirmedByUser: boolean;
  createdAt: Date;
  updatedAt: Date;
}

export interface Relationship {
  id: string;
  sourceEntityId: string;
  targetId: string;
  type: "depends_on" | "serves" | "owned_by" | "part_of" | "blocks" | "related_to";
  description: string;
  confirmedByUser: boolean;
}

export interface Blindspot {
  id: string;
  description: string;
  severity: "red" | "yellow" | "green";
  relatedEntityIds: string[];
  suggestedAction: string;
  status: "open" | "acknowledged" | "resolved";
  confirmedByUser: boolean;
  createdAt: Date;
}

export interface DocumentEntry {
  id: string;
  title: string;
  summary: string;
  linkedEntityIds: string[];
  status: "current" | "stale" | "archived" | "draft" | "conflict";
  confirmedByUser: boolean;
}

export type TaskStatus = "backlog" | "todo" | "in_progress" | "review" | "done" | "archived" | "blocked" | "cancelled";
export type TaskPriority = "critical" | "high" | "medium" | "low";

export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  priorityReason: string;
  assignee: string | null;
  createdBy: string;
  linkedEntities: string[];
  linkedProtocol: string | null;
  linkedBlindspot: string | null;
  sourceType: string;
  contextSummary: string;
  dueDate: Date | null;
  blockedBy: string[];
  blockedReason: string | null;
  acceptanceCriteria: string[];
  confirmedByCreator: boolean;
  rejectionReason: string | null;
  result: string | null;
  completedBy: string | null;
  createdAt: Date;
  updatedAt: Date;
  completedAt: Date | null;
}
