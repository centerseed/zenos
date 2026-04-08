import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  getProjectEntities,
  getEntity,
  getChildEntities,
  countChildEntities,
  getAllEntities,
  getRelationships,
  getAllRelationships,
  getBlindspots,
  getAllBlindspots,
  getTasks,
  getTasksByEntity,
  getPartnerMe,
  uploadTaskAttachment,
  uploadToSignedUrl,
  deleteTaskAttachment,
  addLinkAttachment,
  getQualitySignals,
} from "@/lib/api";

const FAKE_TOKEN = "fake-token-abc";
const API_BASE = "https://zenos-mcp-165893875709.asia-east1.run.app";

// Helper to create a mock fetch response
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

// ─── getProjectEntities ───

describe("getProjectEntities", () => {
  it("calls GET /api/data/entities?type=product with auth header", async () => {
    const fakeFetch = mockFetch({ entities: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getProjectEntities(FAKE_TOKEN);

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/entities?type=product`,
      { headers: { Authorization: `Bearer ${FAKE_TOKEN}` } }
    );
  });

  it("returns entity array unwrapped from { entities: [...] } response", async () => {
    const entities = [{ id: "e-1", name: "Test Project", type: "product" }];
    vi.stubGlobal("fetch", mockFetch({ entities }));

    const result = await getProjectEntities(FAKE_TOKEN);
    expect(result).toEqual(entities);
  });
});

// ─── getEntity ───

describe("getEntity", () => {
  it("calls GET /api/data/entities/{id}", async () => {
    const entity = { id: "e-1", name: "Test" };
    const fakeFetch = mockFetch({ entity });
    vi.stubGlobal("fetch", fakeFetch);

    await getEntity(FAKE_TOKEN, "e-1");

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/entities/e-1`,
      expect.any(Object)
    );
  });

  it("returns entity unwrapped from { entity: {...} } response", async () => {
    const entity = { id: "e-1", name: "Test" };
    vi.stubGlobal("fetch", mockFetch({ entity }));

    const result = await getEntity(FAKE_TOKEN, "e-1");
    expect(result).toEqual(entity);
  });

  it("returns null when API returns non-ok status", async () => {
    vi.stubGlobal("fetch", mockFetch({ detail: "Not found" }, false, 404));

    const result = await getEntity(FAKE_TOKEN, "missing-id");
    expect(result).toBeNull();
  });
});

// ─── getChildEntities ───

describe("getChildEntities", () => {
  it("calls GET /api/data/entities/{parentId}/children", async () => {
    const fakeFetch = mockFetch({ entities: [], count: 0 });
    vi.stubGlobal("fetch", fakeFetch);

    await getChildEntities(FAKE_TOKEN, "parent-1");

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/entities/parent-1/children`,
      expect.any(Object)
    );
  });

  it("returns entities array from response", async () => {
    const entities = [{ id: "child-1", name: "Module A", type: "module" }];
    vi.stubGlobal("fetch", mockFetch({ entities, count: 1 }));

    const result = await getChildEntities(FAKE_TOKEN, "parent-1");
    expect(result).toEqual(entities);
  });
});

// ─── countChildEntities ───

describe("countChildEntities", () => {
  it("returns count from children response", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({ entities: [{ id: "c-1" }, { id: "c-2" }], count: 2 })
    );

    const count = await countChildEntities(FAKE_TOKEN, "parent-1");
    expect(count).toBe(2);
  });
});

// ─── getAllEntities ───

describe("getAllEntities", () => {
  it("calls GET /api/data/entities without type filter", async () => {
    const fakeFetch = mockFetch({ entities: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getAllEntities(FAKE_TOKEN);

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/entities`,
      expect.any(Object)
    );
  });

  it("returns entity array unwrapped from { entities: [...] } response", async () => {
    const entities = [{ id: "e-1" }, { id: "e-2" }];
    vi.stubGlobal("fetch", mockFetch({ entities }));

    const result = await getAllEntities(FAKE_TOKEN);
    expect(result).toEqual(entities);
  });
});

// ─── getRelationships ───

describe("getRelationships", () => {
  it("calls GET /api/data/entities/{entityId}/relationships", async () => {
    const fakeFetch = mockFetch({ relationships: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getRelationships(FAKE_TOKEN, "e-42");

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/entities/e-42/relationships`,
      expect.any(Object)
    );
  });

  it("returns relationships array unwrapped from { relationships: [...] } response", async () => {
    const relationships = [{ id: "r-1", from: "e-1", to: "e-2", type: "depends_on" }];
    vi.stubGlobal("fetch", mockFetch({ relationships }));

    const result = await getRelationships(FAKE_TOKEN, "e-1");
    expect(result).toEqual(relationships);
  });
});

// ─── getAllRelationships ───

describe("getAllRelationships", () => {
  it("calls GET /api/data/relationships", async () => {
    const fakeFetch = mockFetch({ relationships: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getAllRelationships(FAKE_TOKEN);

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/relationships`,
      expect.any(Object)
    );
  });

  it("returns relationships array unwrapped from { relationships: [...] } response", async () => {
    const relationships = [{ id: "r-1" }, { id: "r-2" }];
    vi.stubGlobal("fetch", mockFetch({ relationships }));

    const result = await getAllRelationships(FAKE_TOKEN);
    expect(result).toEqual(relationships);
  });
});

// ─── getBlindspots ───

describe("getBlindspots", () => {
  it("calls GET /api/data/blindspots?entity_id={entityId}", async () => {
    const fakeFetch = mockFetch({ blindspots: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getBlindspots(FAKE_TOKEN, "e-77");

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/blindspots?entity_id=e-77`,
      expect.any(Object)
    );
  });

  it("returns blindspots array unwrapped from { blindspots: [...] } response", async () => {
    const blindspots = [{ id: "b-1", entity_id: "e-77" }];
    vi.stubGlobal("fetch", mockFetch({ blindspots }));

    const result = await getBlindspots(FAKE_TOKEN, "e-77");
    expect(result).toEqual(blindspots);
  });
});

// ─── getAllBlindspots ───

describe("getAllBlindspots", () => {
  it("calls GET /api/data/blindspots without filter", async () => {
    const fakeFetch = mockFetch({ blindspots: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getAllBlindspots(FAKE_TOKEN);

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/blindspots`,
      expect.any(Object)
    );
  });

  it("returns blindspots array unwrapped from { blindspots: [...] } response", async () => {
    const blindspots = [{ id: "b-1" }, { id: "b-2" }];
    vi.stubGlobal("fetch", mockFetch({ blindspots }));

    const result = await getAllBlindspots(FAKE_TOKEN);
    expect(result).toEqual(blindspots);
  });
});

// ─── getTasks ───

describe("getTasks", () => {
  it("calls GET /api/data/tasks without filters", async () => {
    const fakeFetch = mockFetch({ tasks: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getTasks(FAKE_TOKEN);

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/tasks`,
      expect.any(Object)
    );
  });

  it("passes assignee filter as query param", async () => {
    const fakeFetch = mockFetch({ tasks: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getTasks(FAKE_TOKEN, { assignee: "user@example.com" });

    const url = (fakeFetch.mock.calls[0][0] as string);
    expect(url).toContain("assignee=user%40example.com");
  });

  it("passes createdBy filter as created_by query param", async () => {
    const fakeFetch = mockFetch({ tasks: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getTasks(FAKE_TOKEN, { createdBy: "creator@example.com" });

    const url = (fakeFetch.mock.calls[0][0] as string);
    expect(url).toContain("created_by=creator%40example.com");
  });

  it("passes multiple statuses as repeated status params", async () => {
    const fakeFetch = mockFetch({ tasks: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getTasks(FAKE_TOKEN, { statuses: ["todo", "in_progress"] });

    const url = (fakeFetch.mock.calls[0][0] as string);
    expect(url).toContain("status=todo");
    expect(url).toContain("status=in_progress");
  });

  it("returns task array unwrapped from { tasks: [...] } response", async () => {
    const tasks = [{ id: "task-1", title: "Do something", status: "todo" }];
    vi.stubGlobal("fetch", mockFetch({ tasks }));

    const result = await getTasks(FAKE_TOKEN);
    expect(result).toEqual(tasks);
  });

  it("throws when API returns non-ok status", async () => {
    vi.stubGlobal("fetch", mockFetch({ detail: "Unauthorized" }, false, 401));

    await expect(getTasks(FAKE_TOKEN)).rejects.toThrow("401");
  });
});

// ─── getTasksByEntity ───

describe("getTasksByEntity", () => {
  it("calls GET /api/data/tasks/by-entity/{entityId}", async () => {
    const fakeFetch = mockFetch({ tasks: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getTasksByEntity(FAKE_TOKEN, "entity-xyz");

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/tasks/by-entity/entity-xyz`,
      expect.any(Object)
    );
  });

  it("returns task array unwrapped from { tasks: [...] } response", async () => {
    const tasks = [{ id: "t-1", linkedEntities: ["entity-xyz"] }];
    vi.stubGlobal("fetch", mockFetch({ tasks }));

    const result = await getTasksByEntity(FAKE_TOKEN, "entity-xyz");
    expect(result).toEqual(tasks);
  });
});

// ─── getPartnerMe ───

describe("getPartnerMe", () => {
  it("calls GET /api/partner/me with auth header", async () => {
    const partner = { id: "p-1", email: "user@example.com" };
    const fakeFetch = mockFetch({ partner });
    vi.stubGlobal("fetch", fakeFetch);

    await getPartnerMe(FAKE_TOKEN);

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/partner/me`,
      { headers: { Authorization: `Bearer ${FAKE_TOKEN}` } }
    );
  });

  it("returns partner data unwrapped from { partner: {...} } response", async () => {
    const partner = { id: "p-1", email: "user@example.com", isAdmin: false };
    vi.stubGlobal("fetch", mockFetch({ partner }));

    const result = await getPartnerMe(FAKE_TOKEN);
    expect(result).toMatchObject({
      id: "p-1",
      email: "user@example.com",
      isAdmin: false,
      workspaceRole: "member",
      accessMode: "internal",
      authorizedEntityIds: [],
    });
  });

  it("preserves workspaceRole and canonicalizes legacy access fields", async () => {
    const partner = {
      id: "p-guest",
      email: "guest@example.com",
      displayName: "Guest",
      workspaceRole: "guest",
      accessMode: "scoped",
      authorizedEntityIds: ["entity-1"],
      isAdmin: false,
    };
    vi.stubGlobal("fetch", mockFetch({ partner }));

    const result = await getPartnerMe(FAKE_TOKEN);

    expect(result.workspaceRole).toBe("guest");
    expect(result.accessMode).toBe("scoped");
    expect(result.authorizedEntityIds).toEqual(["entity-1"]);
  });

  it("preserves server-provided scoped accessMode when guest has empty entity list", async () => {
    const partner = {
      id: "p-guest-empty",
      email: "guest2@example.com",
      displayName: "Guest No Entities",
      workspaceRole: "guest",
      accessMode: "scoped",
      authorizedEntityIds: [],
      isAdmin: false,
    };
    vi.stubGlobal("fetch", mockFetch({ partner }));

    const result = await getPartnerMe(FAKE_TOKEN);

    expect(result.workspaceRole).toBe("guest");
    expect(result.accessMode).toBe("scoped");
    expect(result.authorizedEntityIds).toEqual([]);
  });
});

// ─── uploadTaskAttachment ───

describe("uploadTaskAttachment", () => {
  it("calls POST /api/data/tasks/{taskId}/attachments with correct body", async () => {
    const responseData = {
      attachment_id: "att-1",
      proxy_url: "/attachments/att-1",
      signed_put_url: "https://storage.googleapis.com/signed",
    };
    const fakeFetch = mockFetch(responseData);
    vi.stubGlobal("fetch", fakeFetch);

    const result = await uploadTaskAttachment(FAKE_TOKEN, "task-123", {
      filename: "photo.png",
      content_type: "image/png",
    });

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/tasks/task-123/attachments`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: `Bearer ${FAKE_TOKEN}`,
          "Content-Type": "application/json",
        }),
      })
    );
    expect(result).toEqual(responseData);
  });

  it("throws when API returns non-ok status", async () => {
    vi.stubGlobal("fetch", mockFetch({}, false, 404));
    await expect(
      uploadTaskAttachment(FAKE_TOKEN, "task-123", {
        filename: "file.pdf",
        content_type: "application/pdf",
      })
    ).rejects.toThrow("404");
  });
});

// ─── uploadToSignedUrl ───

describe("uploadToSignedUrl", () => {
  it("calls PUT on signed URL with file body", async () => {
    const fakeFetch = mockFetch({});
    vi.stubGlobal("fetch", fakeFetch);

    const file = new File(["test"], "test.txt", { type: "text/plain" });
    await uploadToSignedUrl("https://storage.googleapis.com/signed", file);

    expect(fakeFetch).toHaveBeenCalledWith(
      "https://storage.googleapis.com/signed",
      expect.objectContaining({
        method: "PUT",
        headers: { "Content-Type": "text/plain" },
        body: file,
      })
    );
  });

  it("throws when GCS returns non-ok status", async () => {
    vi.stubGlobal("fetch", mockFetch({}, false, 403));
    const file = new File(["test"], "test.txt", { type: "text/plain" });
    await expect(
      uploadToSignedUrl("https://storage.googleapis.com/signed", file)
    ).rejects.toThrow("403");
  });
});

// ─── deleteTaskAttachment ───

describe("deleteTaskAttachment", () => {
  it("calls DELETE /api/data/tasks/{taskId}/attachments/{attachmentId}", async () => {
    const fakeFetch = mockFetch({ ok: true });
    vi.stubGlobal("fetch", fakeFetch);

    await deleteTaskAttachment(FAKE_TOKEN, "task-123", "att-1");

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/tasks/task-123/attachments/att-1`,
      expect.objectContaining({
        method: "DELETE",
        headers: { Authorization: `Bearer ${FAKE_TOKEN}` },
      })
    );
  });

  it("throws when API returns non-ok status", async () => {
    vi.stubGlobal("fetch", mockFetch({}, false, 500));
    await expect(
      deleteTaskAttachment(FAKE_TOKEN, "task-123", "att-1")
    ).rejects.toThrow("500");
  });
});

// ─── addLinkAttachment ───

describe("addLinkAttachment", () => {
  it("calls POST /api/data/tasks/{taskId}/attachments with type:link and url", async () => {
    const responseData = { attachment_id: "att-link-1" };
    const fakeFetch = mockFetch(responseData);
    vi.stubGlobal("fetch", fakeFetch);

    const result = await addLinkAttachment(FAKE_TOKEN, "task-123", {
      url: "https://example.com/doc",
    });

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/tasks/task-123/attachments`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: `Bearer ${FAKE_TOKEN}`,
          "Content-Type": "application/json",
        }),
      })
    );
    const body = JSON.parse((fakeFetch.mock.calls[0][1] as RequestInit).body as string);
    expect(body.type).toBe("link");
    expect(body.url).toBe("https://example.com/doc");
    expect(result).toEqual(responseData);
  });

  it("throws when API returns non-ok status", async () => {
    vi.stubGlobal("fetch", mockFetch({}, false, 400));
    await expect(
      addLinkAttachment(FAKE_TOKEN, "task-123", { url: "" })
    ).rejects.toThrow("400");
  });
});

// ─── getQualitySignals ───

describe("getQualitySignals", () => {
  it("calls GET /api/data/quality-signals with auth header", async () => {
    const body = { search_unused: [], summary_poor: [] };
    const fakeFetch = mockFetch(body);
    vi.stubGlobal("fetch", fakeFetch);

    await getQualitySignals(FAKE_TOKEN);

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/quality-signals`,
      { headers: { Authorization: `Bearer ${FAKE_TOKEN}` } }
    );
  });

  it("returns search_unused and summary_poor arrays from response", async () => {
    const signal = {
      entity_id: "e-1",
      entity_name: "Auth Module",
      search_count: 10,
      get_count: 1,
      unused_ratio: 0.9,
      flagged: true as const,
    };
    const summaryFlag = {
      entity_id: "e-2",
      entity_name: "Core Module",
      quality_score: "poor" as const,
      has_technical_keywords: false,
      has_challenge_context: false,
      is_too_generic: true,
      marketing_ratio: 0.1,
    };
    const body = { search_unused: [signal], summary_poor: [summaryFlag] };
    vi.stubGlobal("fetch", mockFetch(body));

    const result = await getQualitySignals(FAKE_TOKEN);
    expect(result.search_unused).toHaveLength(1);
    expect(result.search_unused[0].entity_id).toBe("e-1");
    expect(result.summary_poor).toHaveLength(1);
    expect(result.summary_poor[0].quality_score).toBe("poor");
  });

  it("throws on non-ok response", async () => {
    vi.stubGlobal("fetch", mockFetch({}, false, 401));
    await expect(getQualitySignals(FAKE_TOKEN)).rejects.toThrow("401");
  });
});

// ─── Authorization header ───

describe("apiFetch authorization", () => {
  it("always sends Bearer token in Authorization header", async () => {
    const fakeFetch = mockFetch({ entities: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getAllEntities("my-secret-token");

    const [, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect((options.headers as Record<string, string>)["Authorization"]).toBe(
      "Bearer my-secret-token"
    );
  });
});
