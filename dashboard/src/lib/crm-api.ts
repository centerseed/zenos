/**
 * CRM API layer — all CRM data fetching goes through the ZenOS REST API.
 * Uses the same API_BASE and auth pattern as api.ts.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_MCP_API_URL ||
  "https://zenos-mcp-165893875709.asia-east1.run.app";

const CRM_DATE_FIELDS = new Set([
  "createdAt",
  "updatedAt",
  "expectedCloseDate",
  "signedDate",
  "activityAt",
]);

/** Recursively convert ISO date strings to Date objects */
function hydrateDates<T>(obj: T): T {
  if (obj === null || obj === undefined) return obj;
  if (Array.isArray(obj)) {
    obj.forEach(hydrateDates);
    return obj;
  }
  if (typeof obj === "object") {
    for (const [key, val] of Object.entries(obj as Record<string, unknown>)) {
      if (CRM_DATE_FIELDS.has(key) && typeof val === "string") {
        (obj as Record<string, unknown>)[key] = new Date(val);
      } else if (val !== null && typeof val === "object") {
        hydrateDates(val);
      }
    }
  }
  return obj;
}

async function apiFetch<T>(
  path: string,
  token: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(options?.body ? { "Content-Type": "application/json" } : {}),
      ...options?.headers,
    },
  });
  if (!res.ok) throw new Error(`API ${path}: ${res.status}`);
  const data = await res.json();
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
  amountTwd?: number;
  dealType?: DealType;
  sourceType?: DealSource;
  referrer?: string;
  expectedCloseDate?: Date;
  signedDate?: Date;
  scopeDescription?: string;
  deliverables: string[];
  notes?: string;
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
    body: JSON.stringify(data),
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
    body: JSON.stringify(data),
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
    body: JSON.stringify(data),
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
    body: JSON.stringify(data),
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
    body: JSON.stringify(data),
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
    body: JSON.stringify({ stage }),
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
    body: JSON.stringify(data),
  });
}
