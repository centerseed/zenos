/**
 * CRM API layer — all CRM data fetching goes through the ZenOS REST API.
 * Uses the same API_BASE and auth pattern as api.ts.
 */
import {
  apiRequest,
  hydrateDateFields,
  serializeJsonBody,
} from "@/lib/api-client";

const CRM_DATE_FIELDS = new Set([
  "createdAt",
  "updatedAt",
  "expectedCloseDate",
  "signedDate",
  "activityAt",
  "lastActivityAt",
]);

function serializeBody<T>(body: T): string {
  return serializeJsonBody(body);
}

function normalizeCompanyInput(
  data: Record<string, unknown>
): Record<string, unknown> {
  return {
    name: data.name,
    industry: data.industry,
    size_range: data.size_range ?? data.sizeRange,
    region: data.region,
    notes: data.notes,
  };
}

function normalizeContactInput(
  data: Record<string, unknown>
): Record<string, unknown> {
  return {
    company_id: data.company_id ?? data.companyId,
    name: data.name,
    title: data.title,
    email: data.email,
    phone: data.phone,
    notes: data.notes,
  };
}

function normalizeDealInput(data: Record<string, unknown>): Record<string, unknown> {
  return {
    title: data.title,
    company_id: data.company_id ?? data.companyId,
    owner_partner_id: data.owner_partner_id ?? data.ownerPartnerId,
    funnel_stage: data.funnel_stage ?? data.funnelStage,
    amount_twd: data.amount_twd ?? data.amountTwd,
    deal_type: data.deal_type ?? data.dealType,
    source_type: data.source_type ?? data.sourceType,
    referrer: data.referrer,
    expected_close_date: data.expected_close_date ?? data.expectedCloseDate,
    signed_date: data.signed_date ?? data.signedDate,
    scope_description: data.scope_description ?? data.scopeDescription,
    deliverables: data.deliverables,
    notes: data.notes,
    is_closed_lost: data.is_closed_lost ?? data.isClosedLost,
    is_on_hold: data.is_on_hold ?? data.isOnHold,
  };
}

function normalizeActivityInput(
  data: Record<string, unknown>
): Record<string, unknown> {
  return {
    activity_type: data.activity_type ?? data.activityType,
    activity_at: data.activity_at ?? data.activityAt,
    summary: data.summary,
    recorded_by: data.recorded_by ?? data.recordedBy,
  };
}

/** Recursively convert ISO date strings to Date objects */
function hydrateDates<T>(obj: T): T {
  return hydrateDateFields(obj, CRM_DATE_FIELDS);
}

async function apiFetch<T>(
  path: string,
  token: string,
  options?: RequestInit
): Promise<T> {
  const data = await apiRequest<T>(path, {
    ...options,
    body: options?.body ?? undefined,
    token,
  });
  return hydrateDates(data) as T;
}

// ─── Types ───────────────────────────────────────────────────────────────────

export type FunnelStage =
  | "潛在客戶"
  | "需求訪談"
  | "提案報價"
  | "合約議價"
  | "導入中"
  | "結案";

export type DealType = "一次性專案" | "顧問合約" | "Retainer";
export type DealSource = "轉介紹" | "自開發" | "合作夥伴" | "社群" | "活動";
export type ActivityType = "電話" | "Email" | "會議" | "Demo" | "備忘" | "系統";

export interface Company {
  id: string;
  partnerId: string;
  name: string;
  industry?: string;
  sizeRange?: string;
  region?: string;
  notes?: string;
  zenosEntityId?: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface Contact {
  id: string;
  partnerId: string;
  companyId: string;
  name: string;
  title?: string;
  email?: string;
  phone?: string;
  notes?: string;
  zenosEntityId?: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface Deal {
  id: string;
  partnerId: string;
  title: string;
  companyId: string;
  ownerPartnerId: string;
  funnelStage: FunnelStage;
  amountTwd?: number | null;
  dealType?: DealType;
  sourceType?: DealSource;
  referrer?: string;
  expectedCloseDate?: Date | null;
  signedDate?: Date | null;
  scopeDescription?: string;
  deliverables: string[];
  notes?: string;
  lastActivityAt?: Date | null;
  isClosedLost: boolean;
  isOnHold: boolean;
  createdAt: Date;
  updatedAt: Date;
}

export interface Activity {
  id: string;
  partnerId: string;
  dealId: string;
  activityType: ActivityType;
  activityAt: Date;
  summary: string;
  recordedBy: string;
  isSystem: boolean;
  createdAt: Date;
}

// ─── Company ─────────────────────────────────────────────────────────────────

export async function getCompanies(token: string): Promise<Company[]> {
  const res = await apiFetch<{ companies: Company[] }>(
    "/api/crm/companies",
    token
  );
  return res.companies;
}

export async function createCompany(
  token: string,
  data: Omit<Company, "id" | "partnerId" | "createdAt" | "updatedAt">
): Promise<Company> {
  return apiFetch<Company>("/api/crm/companies", token, {
    method: "POST",
    body: serializeBody(normalizeCompanyInput(data as Record<string, unknown>)),
  });
}

export async function getCompany(token: string, id: string): Promise<Company> {
  return apiFetch<Company>(`/api/crm/companies/${id}`, token);
}

export async function updateCompany(
  token: string,
  id: string,
  data: Partial<Omit<Company, "id" | "partnerId" | "createdAt" | "updatedAt">>
): Promise<Company> {
  return apiFetch<Company>(`/api/crm/companies/${id}`, token, {
    method: "PUT",
    body: serializeBody(normalizeCompanyInput(data as Record<string, unknown>)),
  });
}

export async function getCompanyContacts(
  token: string,
  companyId: string
): Promise<Contact[]> {
  const res = await apiFetch<{ contacts: Contact[] }>(
    `/api/crm/companies/${companyId}/contacts`,
    token
  );
  return res.contacts;
}

export async function getCompanyDeals(
  token: string,
  companyId: string
): Promise<Deal[]> {
  const res = await apiFetch<{ deals: Deal[] }>(
    `/api/crm/companies/${companyId}/deals`,
    token
  );
  return res.deals;
}

// ─── Contact ─────────────────────────────────────────────────────────────────

export async function createContact(
  token: string,
  data: Omit<Contact, "id" | "partnerId" | "createdAt" | "updatedAt">
): Promise<Contact> {
  return apiFetch<Contact>("/api/crm/contacts", token, {
    method: "POST",
    body: serializeBody(normalizeContactInput(data as Record<string, unknown>)),
  });
}

export async function getContact(
  token: string,
  id: string
): Promise<Contact> {
  return apiFetch<Contact>(`/api/crm/contacts/${id}`, token);
}

export async function updateContact(
  token: string,
  id: string,
  data: Partial<Omit<Contact, "id" | "partnerId" | "createdAt" | "updatedAt">>
): Promise<Contact> {
  return apiFetch<Contact>(`/api/crm/contacts/${id}`, token, {
    method: "PUT",
    body: serializeBody(normalizeContactInput(data as Record<string, unknown>)),
  });
}

// ─── Deal ─────────────────────────────────────────────────────────────────────

export async function getDeals(
  token: string,
  includeInactive = false
): Promise<Deal[]> {
  const qs = includeInactive ? "?include_inactive=true" : "";
  const res = await apiFetch<{ deals: Deal[] }>(
    `/api/crm/deals${qs}`,
    token
  );
  return res.deals;
}

export async function createDeal(
  token: string,
  data: Omit<Deal, "id" | "partnerId" | "createdAt" | "updatedAt">
): Promise<Deal> {
  return apiFetch<Deal>("/api/crm/deals", token, {
    method: "POST",
    body: serializeBody(normalizeDealInput(data as Record<string, unknown>)),
  });
}

export async function getDeal(token: string, id: string): Promise<Deal> {
  return apiFetch<Deal>(`/api/crm/deals/${id}`, token);
}

export async function patchDealStage(
  token: string,
  id: string,
  stage: FunnelStage
): Promise<Deal> {
  return apiFetch<Deal>(`/api/crm/deals/${id}/stage`, token, {
    method: "PATCH",
    body: serializeBody({ stage }),
  });
}

// ─── Insights ────────────────────────────────────────────────────────────────

export interface StaleWarning {
  type: "stale_warning";
  deal_id: string;
  deal_title: string;
  company_name: string | null;
  days_stale: number;
  stage: string;
  threshold_days: number;
  suggestion: string;
}

export interface PipelineSummary {
  active_deals: number;
  estimated_monthly_close_twd: number;
  deals_needing_attention: number;
}

export interface CrmInsights {
  insights: StaleWarning[];
  pipeline_summary: PipelineSummary;
}

export async function fetchInsights(token: string): Promise<CrmInsights> {
  return apiFetch<CrmInsights>("/api/crm/insights", token);
}

// ─── Stale Thresholds ─────────────────────────────────────────────────────────

export type StaleThresholds = Record<string, number>;

export async function fetchStaleThresholds(token: string): Promise<StaleThresholds> {
  return apiFetch<StaleThresholds>("/api/crm/settings/stale-thresholds", token);
}

export async function updateStaleThresholds(
  token: string,
  thresholds: StaleThresholds
): Promise<StaleThresholds> {
  return apiFetch<StaleThresholds>("/api/crm/settings/stale-thresholds", token, {
    method: "PUT",
    body: JSON.stringify(thresholds),
  });
}

// ─── Activity ─────────────────────────────────────────────────────────────────

export async function getDealActivities(
  token: string,
  dealId: string
): Promise<Activity[]> {
  const res = await apiFetch<{ activities: Activity[] }>(
    `/api/crm/deals/${dealId}/activities`,
    token
  );
  return res.activities;
}

export async function createActivity(
  token: string,
  dealId: string,
  data: Omit<Activity, "id" | "partnerId" | "dealId" | "isSystem" | "createdAt">
): Promise<Activity> {
  return apiFetch<Activity>(`/api/crm/deals/${dealId}/activities`, token, {
    method: "POST",
    body: serializeBody(normalizeActivityInput(data as Record<string, unknown>)),
  });
}

// ─── AI Insights ──────────────────────────────────────────────────────────────

export interface AiInsight {
  id: string;
  dealId: string;
  activityId: string | null;
  insightType: "briefing" | "debrief" | "commitment";
  content: string;
  metadata: Record<string, unknown>;
  status: string;
  createdAt: string;
}

export interface DealAiEntries {
  briefings: AiInsight[];
  debriefs: AiInsight[];
  commitments: AiInsight[];
}

/**
 * Fetch all AI entries (briefings + debriefs + commitments) for a deal.
 * GET /api/crm/deals/{dealId}/ai-entries
 * Response is already camelCase.
 */
export async function fetchDealAiEntries(
  token: string,
  dealId: string
): Promise<DealAiEntries> {
  return apiFetch<DealAiEntries>(`/api/crm/deals/${dealId}/ai-entries`, token);
}

/**
 * Save a new AI insight (debrief or commitment) for a deal.
 * POST /api/crm/deals/{dealId}/ai-insights
 * Body is snake_case (consistent with createDeal / createActivity pattern).
 */
export async function createAiInsight(
  token: string,
  dealId: string,
  data: {
    insightType: "briefing" | "debrief" | "commitment";
    content: string;
    metadata: Record<string, unknown>;
    activityId?: string;
  }
): Promise<AiInsight> {
  const body = {
    insight_type: data.insightType,
    content: data.content,
    metadata: data.metadata,
    ...(data.activityId !== undefined ? { activity_id: data.activityId } : {}),
  };
  return apiFetch<AiInsight>(`/api/crm/deals/${dealId}/ai-insights`, token, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/**
 * Update a saved briefing snapshot.
 * PATCH /api/crm/briefings/{insightId}
 */
export async function updateBriefing(
  token: string,
  insightId: string,
  data: {
    content?: string;
    metadata?: Record<string, unknown>;
  }
): Promise<AiInsight> {
  return apiFetch<AiInsight>(`/api/crm/briefings/${insightId}`, token, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/**
 * Delete a saved briefing snapshot.
 * DELETE /api/crm/briefings/{insightId}
 */
export async function deleteBriefing(
  token: string,
  insightId: string
): Promise<void> {
  await apiFetch<unknown>(`/api/crm/briefings/${insightId}`, token, {
    method: "DELETE",
  });
}

/**
 * Update commitment status (open → done or vice-versa).
 * PATCH /api/crm/commitments/{insightId}
 */
export async function updateCommitmentStatus(
  token: string,
  insightId: string,
  status: "open" | "done"
): Promise<AiInsight> {
  return apiFetch<AiInsight>(`/api/crm/commitments/${insightId}`, token, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}
