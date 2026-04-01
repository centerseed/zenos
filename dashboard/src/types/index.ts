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

/** Quality signal: entity searched frequently but rarely accessed */
export interface SearchUnusedSignal {
  entity_id: string;
  entity_name: string;
  search_count: number;
  get_count: number;
  unused_ratio: number;
  flagged: true;
}

/** Quality signal: entity summary has poor semantic quality */
export interface SummaryPoorSignal {
  entity_id: string;
  entity_name: string;
  quality_score: "poor" | "needs_improvement" | "good";
  has_technical_keywords: boolean;
  has_challenge_context: boolean;
  is_too_generic: boolean;
  marketing_ratio: number;
}

export interface QualitySignals {
  search_unused: SearchUnusedSignal[];
  summary_poor: SummaryPoorSignal[];
}

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
  attachments?: Array<{
    id: string;
    type?: "image" | "file" | "link";
    filename?: string;
    content_type?: string;
    url?: string;
    description?: string;
    proxy_url?: string;
    uploaded_by?: string;
    created_at?: string;
  }>;
  createdAt: Date;
  updatedAt: Date;
  completedAt: Date | null;
}
