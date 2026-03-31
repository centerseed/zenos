// Firestore document types — field names match Firestore camelCase convention

export interface Partner {
  id: string;
  email: string;
  displayName: string;
  apiKey: string;
  authorizedEntityIds: string[];
  sharedPartnerId?: string | null;
  isAdmin: boolean;
  status: "active" | "suspended" | "invited";
  roles?: string[];
  department?: string;
  invitedBy: string | null;
  createdAt: Date;
  updatedAt: Date;
}

export interface Tags {
  what: string | string[];
  why: string;
  how: string;
  who: string | string[];
}

export interface Source {
  uri: string;
  label: string;
  type: string;
}

export interface Entity {
  id: string;
  name: string;
  type: "product" | "module" | "goal" | "role" | "project" | "document";
  summary: string;
  tags: Tags;
  status: "active" | "paused" | "completed" | "planned" | "current" | "stale" | "draft" | "conflict";
  level?: number | null;
  parentId: string | null;
  details: Record<string, unknown> | null;
  confirmedByUser: boolean;
  owner: string | null;
  sources: Source[];
  visibility: "public" | "restricted" | "role-restricted" | "confidential";
  visibleToRoles?: string[];
  visibleToMembers?: string[];
  visibleToDepartments?: string[];
  lastReviewedAt: Date | null;
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

/** @deprecated Use Entity with type="document" instead */
export type DocumentEntry = Entity;

export type TaskStatus = "todo" | "in_progress" | "review" | "done" | "cancelled";
export type TaskPriority = "critical" | "high" | "medium" | "low";

export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  project: string;
  priorityReason: string;
  assignee: string | null;
  assigneeName?: string | null;
  assigneeRoleId?: string | null;
  planId?: string | null;
  planOrder?: number | null;
  dependsOnTaskIds?: string[];
  createdBy: string;
  creatorName?: string | null;
  linkedEntities: string[];
  linkedProtocol: string | null;
  linkedBlindspot: string | null;
  sourceType: string;
  sourceMetadata?: {
    created_via_agent?: boolean;
    agent_name?: string;
    actor_partner_id?: string;
    provenance?: Array<{
      type?: string;
      label?: string;
      snippet?: string;
      image_url?: string;
      sheet_ref?: string;
      url?: string;
    }>;
    sync_sources?: string[];
    [key: string]: unknown;
  };
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
