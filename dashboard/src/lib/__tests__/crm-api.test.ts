import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  getDeals,
  patchDealStage,
  getCompanies,
  createCompany,
  updateCompany,
  createContact,
  getDealActivities,
  createActivity,
  fetchDealAiEntries,
  createAiInsight,
  deleteBriefing,
  updateBriefing,
  updateCommitmentStatus,
} from "@/lib/crm-api";
import type { Deal, Company, Activity, AiInsight, DealAiEntries } from "@/lib/crm-api";

const FAKE_TOKEN = "fake-crm-token";
const API_BASE = "https://zenos-mcp-s5oifosv3a-de.a.run.app";

function mockFetch(body: unknown, ok = true, status = 200) {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    json: vi.fn().mockResolvedValue(body),
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ─── getDeals ────────────────────────────────────────────────────────────────

describe("getDeals", () => {
  it("calls GET /api/crm/deals without query string by default", async () => {
    const fakeFetch = mockFetch({ deals: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getDeals(FAKE_TOKEN);

    const [url] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/crm/deals`);
  });

  it("appends include_inactive=true when requested", async () => {
    const fakeFetch = mockFetch({ deals: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getDeals(FAKE_TOKEN, true);

    const [url] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/crm/deals?include_inactive=true`);
  });

  it("returns deals array unwrapped from { deals: [...] } response", async () => {
    const deals: Partial<Deal>[] = [
      { id: "d-1", title: "台積電 AI 顧問", funnelStage: "需求訪談" },
    ];
    vi.stubGlobal("fetch", mockFetch({ deals }));

    const result = await getDeals(FAKE_TOKEN);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("d-1");
    expect(result[0].title).toBe("台積電 AI 顧問");
  });

  it("hydrates createdAt ISO string to Date object", async () => {
    const isoString = "2026-03-01T00:00:00.000Z";
    const deals = [
      {
        id: "d-1",
        title: "Test",
        funnelStage: "潛在客戶",
        createdAt: isoString,
        updatedAt: isoString,
        deliverables: [],
        isClosedLost: false,
        isOnHold: false,
      },
    ];
    vi.stubGlobal("fetch", mockFetch({ deals }));

    const result = await getDeals(FAKE_TOKEN);
    expect(result[0].createdAt).toBeInstanceOf(Date);
  });

  it("sends Authorization header with Bearer token", async () => {
    const fakeFetch = mockFetch({ deals: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getDeals(FAKE_TOKEN);

    const [, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect((options.headers as Record<string, string>)["Authorization"]).toBe(
      `Bearer ${FAKE_TOKEN}`
    );
  });

  it("throws when API returns non-ok status", async () => {
    vi.stubGlobal("fetch", mockFetch({ detail: "Unauthorized" }, false, 401));

    await expect(getDeals(FAKE_TOKEN)).rejects.toThrow("401");
  });
});

// ─── patchDealStage ───────────────────────────────────────────────────────────

describe("patchDealStage", () => {
  it("calls PATCH /api/crm/deals/{id}/stage with correct body", async () => {
    const updatedDeal: Partial<Deal> = {
      id: "d-1",
      title: "Test Deal",
      funnelStage: "提案報價",
      deliverables: [],
      isClosedLost: false,
      isOnHold: false,
    };
    const fakeFetch = mockFetch(updatedDeal);
    vi.stubGlobal("fetch", fakeFetch);

    await patchDealStage(FAKE_TOKEN, "d-1", "提案報價");

    const [url, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/crm/deals/d-1/stage`);
    expect(options.method).toBe("PATCH");
    expect(JSON.parse(options.body as string)).toEqual({ stage: "提案報價" });
  });

  it("returns updated deal with new funnelStage", async () => {
    const updatedDeal: Partial<Deal> = {
      id: "d-1",
      title: "Test Deal",
      funnelStage: "合約議價",
      deliverables: [],
      isClosedLost: false,
      isOnHold: false,
    };
    vi.stubGlobal("fetch", mockFetch(updatedDeal));

    const result = await patchDealStage(FAKE_TOKEN, "d-1", "合約議價");
    expect(result.funnelStage).toBe("合約議價");
  });

  it("sends serialized stage payload", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({ id: "d-1", funnelStage: "結案", deliverables: [], isClosedLost: false, isOnHold: false })
    );

    await patchDealStage(FAKE_TOKEN, "d-1", "結案");

    const [, options] = (vi.mocked(fetch) as ReturnType<typeof vi.fn>).mock
      .calls[0] as [string, RequestInit];
    expect(options.body).toBe(JSON.stringify({ stage: "結案" }));
  });

  it("throws when API returns non-ok status", async () => {
    vi.stubGlobal("fetch", mockFetch({ detail: "Not Found" }, false, 404));

    await expect(patchDealStage(FAKE_TOKEN, "missing", "結案")).rejects.toThrow(
      "404"
    );
  });
});

// ─── getCompanies ─────────────────────────────────────────────────────────────

describe("getCompanies", () => {
  it("calls GET /api/crm/companies", async () => {
    const fakeFetch = mockFetch({ companies: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getCompanies(FAKE_TOKEN);

    const [url] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/crm/companies`);
  });

  it("returns companies array from response", async () => {
    const companies: Partial<Company>[] = [
      { id: "c-1", name: "台灣科技公司" },
    ];
    vi.stubGlobal("fetch", mockFetch({ companies }));

    const result = await getCompanies(FAKE_TOKEN);
    expect(result[0].name).toBe("台灣科技公司");
  });
});

// ─── createCompany ────────────────────────────────────────────────────────────

describe("createCompany", () => {
  it("calls POST /api/crm/companies with JSON body", async () => {
    const newCompany = { name: "新創公司", industry: "科技" };
    const fakeFetch = mockFetch({
      id: "c-new",
      ...newCompany,
      partnerId: "p-1",
      createdAt: "2026-03-01T00:00:00Z",
      updatedAt: "2026-03-01T00:00:00Z",
    });
    vi.stubGlobal("fetch", fakeFetch);

    await createCompany(FAKE_TOKEN, newCompany);

    const [url, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/crm/companies`);
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body as string)).toEqual(newCompany);
  });

  it("normalizes camelCase company fields to snake_case", async () => {
    const fakeFetch = mockFetch({
      id: "c-new",
      name: "新創公司",
      sizeRange: "1-10",
      partnerId: "p-1",
      createdAt: "2026-03-01T00:00:00Z",
      updatedAt: "2026-03-01T00:00:00Z",
    });
    vi.stubGlobal("fetch", fakeFetch);

    await createCompany(FAKE_TOKEN, { name: "新創公司", sizeRange: "1-10" } as any);

    const [, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(options.body as string)).toEqual({
      name: "新創公司",
      industry: undefined,
      size_range: "1-10",
      region: undefined,
      notes: undefined,
    });
  });
});

describe("updateCompany", () => {
  it("normalizes camelCase update payload to snake_case", async () => {
    const fakeFetch = mockFetch({
      id: "c-1",
      name: "台灣科技公司",
      sizeRange: "11-50",
      partnerId: "p-1",
      createdAt: "2026-03-01T00:00:00Z",
      updatedAt: "2026-03-02T00:00:00Z",
    });
    vi.stubGlobal("fetch", fakeFetch);

    await updateCompany(FAKE_TOKEN, "c-1", { sizeRange: "11-50" } as any);

    const [, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(options.body as string)).toEqual({
      name: undefined,
      industry: undefined,
      size_range: "11-50",
      region: undefined,
      notes: undefined,
    });
  });
});

describe("createContact", () => {
  it("normalizes camelCase contact fields to snake_case", async () => {
    const fakeFetch = mockFetch({
      id: "ct-1",
      companyId: "c-1",
      name: "王小明",
      partnerId: "p-1",
      createdAt: "2026-03-01T00:00:00Z",
      updatedAt: "2026-03-01T00:00:00Z",
    });
    vi.stubGlobal("fetch", fakeFetch);

    await createContact(FAKE_TOKEN, {
      companyId: "c-1",
      name: "王小明",
      email: "wang@example.com",
    } as any);

    const [, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(options.body as string)).toEqual({
      company_id: "c-1",
      name: "王小明",
      title: undefined,
      email: "wang@example.com",
      phone: undefined,
      notes: undefined,
    });
  });
});

// ─── getDealActivities ────────────────────────────────────────────────────────

describe("getDealActivities", () => {
  it("calls GET /api/crm/deals/{dealId}/activities", async () => {
    const fakeFetch = mockFetch({ activities: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getDealActivities(FAKE_TOKEN, "deal-123");

    const [url] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/crm/deals/deal-123/activities`);
  });

  it("hydrates activityAt ISO string to Date", async () => {
    const activities: Partial<Activity>[] = [
      {
        id: "a-1",
        activityType: "會議",
        activityAt: "2026-03-15T10:00:00.000Z" as unknown as Date,
        summary: "初次會議",
        isSystem: false,
      },
    ];
    vi.stubGlobal("fetch", mockFetch({ activities }));

    const result = await getDealActivities(FAKE_TOKEN, "deal-123");
    expect(result[0].activityAt).toBeInstanceOf(Date);
  });
});

// ─── createActivity ───────────────────────────────────────────────────────────

describe("createActivity", () => {
  it("calls POST /api/crm/deals/{dealId}/activities with data", async () => {
    const activityData = {
      activityType: "電話" as const,
      activityAt: new Date("2026-03-15T10:00:00Z"),
      summary: "電話確認需求",
      recordedBy: "partner-id",
    };
    const fakeFetch = mockFetch({
      id: "a-new",
      dealId: "d-1",
      ...activityData,
      isSystem: false,
      createdAt: "2026-03-15T10:00:00Z",
    });
    vi.stubGlobal("fetch", fakeFetch);

    await createActivity(FAKE_TOKEN, "d-1", activityData);

    const [url, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/crm/deals/d-1/activities`);
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body as string)).toEqual({
      activity_type: "電話",
      activity_at: "2026-03-15T10:00:00.000Z",
      summary: "電話確認需求",
      recorded_by: "partner-id",
    });
  });
});

// ─── fetchDealAiEntries ───────────────────────────────────────────────────────

const fakeDebrief: AiInsight = {
  id: "ins-1",
  dealId: "d-1",
  activityId: "a-1",
  insightType: "debrief",
  content: "## 關鍵決策\n- 確認需求",
  metadata: { key_decisions: ["確認需求"] },
  status: "active",
  createdAt: "2026-03-15T10:00:00Z",
};

const fakeCommitment: AiInsight = {
  id: "ins-2",
  dealId: "d-1",
  activityId: "a-1",
  insightType: "commitment",
  content: "寄報價單",
  metadata: { content: "寄報價單", owner: "us", deadline: "2026-03-20" },
  status: "open",
  createdAt: "2026-03-15T10:00:00Z",
};

const fakeBriefing: AiInsight = {
  id: "ins-0",
  dealId: "d-1",
  activityId: null,
  insightType: "briefing",
  content: "這是一份已存 briefing",
  metadata: {
    title: "會議準備 2026/03/15 10:00",
    chat_history: [{ role: "assistant", content: "這是一份已存 briefing" }],
  },
  status: "active",
  createdAt: "2026-03-15T09:00:00Z",
};

describe("fetchDealAiEntries", () => {
  it("calls GET /api/crm/deals/{dealId}/ai-entries", async () => {
    const fakeFetch = mockFetch({ briefings: [], debriefs: [], commitments: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await fetchDealAiEntries(FAKE_TOKEN, "d-1");

    const [url] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/crm/deals/d-1/ai-entries`);
  });

  it("returns briefings, debriefs and commitments from response", async () => {
    const body: DealAiEntries = {
      briefings: [fakeBriefing],
      debriefs: [fakeDebrief],
      commitments: [fakeCommitment],
    };
    vi.stubGlobal("fetch", mockFetch(body));

    const result = await fetchDealAiEntries(FAKE_TOKEN, "d-1");
    expect(result.briefings).toHaveLength(1);
    expect(result.briefings[0].id).toBe("ins-0");
    expect(result.debriefs).toHaveLength(1);
    expect(result.debriefs[0].id).toBe("ins-1");
    expect(result.commitments).toHaveLength(1);
    expect(result.commitments[0].id).toBe("ins-2");
  });

  it("sends Authorization header with Bearer token", async () => {
    const fakeFetch = mockFetch({ briefings: [], debriefs: [], commitments: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await fetchDealAiEntries(FAKE_TOKEN, "d-1");

    const [, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect((options.headers as Record<string, string>)["Authorization"]).toBe(
      `Bearer ${FAKE_TOKEN}`
    );
  });

  it("throws when API returns non-ok status", async () => {
    vi.stubGlobal("fetch", mockFetch({ detail: "Not Found" }, false, 404));
    await expect(fetchDealAiEntries(FAKE_TOKEN, "d-missing")).rejects.toThrow("404");
  });
});

// ─── createAiInsight ─────────────────────────────────────────────────────────

describe("createAiInsight", () => {
  it("calls POST /api/crm/deals/{dealId}/ai-insights", async () => {
    const fakeFetch = mockFetch(fakeDebrief);
    vi.stubGlobal("fetch", fakeFetch);

    await createAiInsight(FAKE_TOKEN, "d-1", {
      insightType: "debrief",
      content: "## 關鍵決策\n- test",
      metadata: { key_decisions: ["test"] },
      activityId: "a-1",
    });

    const [url, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/crm/deals/d-1/ai-insights`);
    expect(options.method).toBe("POST");
  });

  it("converts camelCase fields to snake_case in body", async () => {
    const fakeFetch = mockFetch(fakeDebrief);
    vi.stubGlobal("fetch", fakeFetch);

    await createAiInsight(FAKE_TOKEN, "d-1", {
      insightType: "debrief",
      content: "content text",
      metadata: { key: "value" },
      activityId: "a-1",
    });

    const [, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(options.body as string);
    expect(body).toHaveProperty("insight_type", "debrief");
    expect(body).toHaveProperty("activity_id", "a-1");
    expect(body).not.toHaveProperty("insightType");
    expect(body).not.toHaveProperty("activityId");
  });

  it("omits activity_id when not provided", async () => {
    const fakeFetch = mockFetch(fakeDebrief);
    vi.stubGlobal("fetch", fakeFetch);

    await createAiInsight(FAKE_TOKEN, "d-1", {
      insightType: "debrief",
      content: "content text",
      metadata: {},
    });

    const [, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(options.body as string);
    expect(body).not.toHaveProperty("activity_id");
  });

  it("returns saved insight from response", async () => {
    vi.stubGlobal("fetch", mockFetch(fakeDebrief));

    const result = await createAiInsight(FAKE_TOKEN, "d-1", {
      insightType: "debrief",
      content: "content",
      metadata: {},
    });
    expect(result.id).toBe("ins-1");
    expect(result.insightType).toBe("debrief");
  });

  it("throws when API returns non-ok status", async () => {
    vi.stubGlobal("fetch", mockFetch({ detail: "Validation Error" }, false, 422));
    await expect(
      createAiInsight(FAKE_TOKEN, "d-1", {
        insightType: "debrief",
        content: "",
        metadata: {},
      })
    ).rejects.toThrow("422");
  });
});

// ─── updateBriefing ──────────────────────────────────────────────────────────

describe("updateBriefing", () => {
  it("calls PATCH /api/crm/briefings/{insightId}", async () => {
    const fakeFetch = mockFetch(fakeBriefing);
    vi.stubGlobal("fetch", fakeFetch);

    await updateBriefing(FAKE_TOKEN, "ins-0", {
      content: "updated briefing",
      metadata: { title: "新標題" },
    });

    const [url, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/crm/briefings/ins-0`);
    expect(options.method).toBe("PATCH");
    expect(JSON.parse(options.body as string)).toEqual({
      content: "updated briefing",
      metadata: { title: "新標題" },
    });
  });
});

// ─── deleteBriefing ──────────────────────────────────────────────────────────

describe("deleteBriefing", () => {
  it("calls DELETE /api/crm/briefings/{insightId}", async () => {
    const fakeFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: vi.fn(),
    });
    vi.stubGlobal("fetch", fakeFetch);

    await deleteBriefing(FAKE_TOKEN, "ins-0");

    const [url, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/crm/briefings/ins-0`);
    expect(options.method).toBe("DELETE");
  });
});

// ─── updateCommitmentStatus ───────────────────────────────────────────────────

describe("updateCommitmentStatus", () => {
  it("calls PATCH /api/crm/commitments/{insightId}", async () => {
    const fakeFetch = mockFetch({ ...fakeCommitment, status: "done" });
    vi.stubGlobal("fetch", fakeFetch);

    await updateCommitmentStatus(FAKE_TOKEN, "ins-2", "done");

    const [url, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/crm/commitments/ins-2`);
    expect(options.method).toBe("PATCH");
  });

  it("sends status in body", async () => {
    const fakeFetch = mockFetch({ ...fakeCommitment, status: "done" });
    vi.stubGlobal("fetch", fakeFetch);

    await updateCommitmentStatus(FAKE_TOKEN, "ins-2", "done");

    const [, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(options.body as string)).toEqual({ status: "done" });
  });

  it("can mark a commitment as open", async () => {
    const fakeFetch = mockFetch({ ...fakeCommitment, status: "open" });
    vi.stubGlobal("fetch", fakeFetch);

    await updateCommitmentStatus(FAKE_TOKEN, "ins-2", "open");

    const [, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(options.body as string)).toEqual({ status: "open" });
  });

  it("returns updated insight with new status", async () => {
    vi.stubGlobal("fetch", mockFetch({ ...fakeCommitment, status: "done" }));

    const result = await updateCommitmentStatus(FAKE_TOKEN, "ins-2", "done");
    expect(result.status).toBe("done");
  });

  it("throws when API returns non-ok status", async () => {
    vi.stubGlobal("fetch", mockFetch({ detail: "Not Found" }, false, 404));
    await expect(
      updateCommitmentStatus(FAKE_TOKEN, "missing", "done")
    ).rejects.toThrow("404");
  });
});
