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
  getPlans,
  getProjectProgress,
  getPartnerMe,
  updatePartnerScope,
  uploadTaskAttachment,
  uploadToSignedUrl,
  deleteTaskAttachment,
  addLinkAttachment,
  getQualitySignals,
  getDocumentDelivery,
  getDocumentContent,
  publishDocumentSnapshot,
  saveDocumentMarkdown,
  updateDocumentVisibility,
  createDocumentShareLink,
  revokeDocumentShareLink,
  getSharedDocumentByToken,
} from "@/lib/api";

const FAKE_TOKEN = "fake-token-abc";
const API_BASE = "https://zenos-mcp-s5oifosv3a-de.a.run.app";

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

// ─── getPlans ───

describe("getPlans", () => {
  it("calls GET /api/data/plans with repeated id params", async () => {
    const fakeFetch = mockFetch({ plans: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getPlans(FAKE_TOKEN, ["plan-1", "plan-2"]);

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/plans?id=plan-1&id=plan-2`,
      expect.any(Object)
    );
  });

  it("returns plan array unwrapped from { plans: [...] } response", async () => {
    const plans = [{ id: "plan-1", goal: "Ship aggregate", status: "active" }];
    vi.stubGlobal("fetch", mockFetch({ plans }));

    const result = await getPlans(FAKE_TOKEN, ["plan-1"]);
    expect(result).toEqual(plans);
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

// ─── getProjectProgress ───

describe("getProjectProgress", () => {
  it("calls GET /api/data/projects/{id}/progress", async () => {
    const fakeFetch = mockFetch({
      project: { id: "proj-1", name: "Console", type: "product" },
      active_plans: [],
      open_work_groups: [],
      milestones: [],
      recent_progress: [],
    });
    vi.stubGlobal("fetch", fakeFetch);

    await getProjectProgress(FAKE_TOKEN, "proj-1");

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/projects/proj-1/progress`,
      expect.objectContaining({ cache: "no-store" })
    );
  });

  it("hydrates nested snake_case date fields in the aggregate payload", async () => {
    vi.stubGlobal("fetch", mockFetch({
      project: {
        id: "proj-1",
        name: "Console",
        type: "product",
        updatedAt: "2026-04-21T00:00:00+00:00",
      },
      active_plans: [
        {
          id: "plan-1",
          goal: "Ship S01",
          status: "active",
          owner: "Barry",
          tasks_summary: { total: 3, by_status: { todo: 1 } },
          open_count: 3,
          blocked_count: 1,
          review_count: 1,
          overdue_count: 1,
          updated_at: "2026-04-21T01:00:00+00:00",
          next_tasks: [
            {
              id: "task-1",
              title: "Backend aggregate",
              status: "blocked",
              priority: "high",
              plan_order: 2,
              assignee_name: "Dev",
              due_date: "2026-04-20T00:00:00+00:00",
              overdue: true,
              blocked: true,
              blocked_reason: "Waiting on schema",
              parent_task_id: null,
              updated_at: "2026-04-21T02:00:00+00:00",
              subtasks: [],
            },
          ],
        },
      ],
      open_work_groups: [],
      milestones: [],
      recent_progress: [
        {
          id: "task-1",
          kind: "task",
          title: "Backend aggregate",
          subtitle: "Task · blocked",
          updated_at: "2026-04-21T02:00:00+00:00",
        },
      ],
    }));

    const result = await getProjectProgress(FAKE_TOKEN, "proj-1");
    expect(result.active_plans[0]?.updated_at).toBeInstanceOf(Date);
    expect(result.active_plans[0]?.next_tasks[0]?.due_date).toBeInstanceOf(Date);
    expect(result.active_plans[0]?.next_tasks[0]?.plan_order).toBe(2);
    expect(result.recent_progress[0]?.updated_at).toBeInstanceOf(Date);
    expect(result.project.updatedAt).toBeInstanceOf(Date);
  });

  it("filters empty active plans from stale aggregate payloads", async () => {
    vi.stubGlobal("fetch", mockFetch({
      project: {
        id: "proj-1",
        name: "Console",
        type: "product",
      },
      active_plans: [
        {
          id: "plan-empty",
          goal: "Already shipped",
          status: "active",
          owner: "Barry",
          tasks_summary: { total: 1, by_status: { done: 1 } },
          open_count: 0,
          blocked_count: 0,
          review_count: 0,
          overdue_count: 0,
          updated_at: "2026-04-21T01:00:00+00:00",
          next_tasks: [],
          milestones: [],
        },
      ],
      open_work_groups: [
        {
          plan_id: "plan-empty",
          plan_goal: "Already shipped",
          plan_status: "active",
          open_count: 0,
          blocked_count: 0,
          review_count: 0,
          overdue_count: 0,
          tasks: [],
        },
      ],
      milestones: [
        { id: "goal-1", name: "Alpha", open_count: 0 },
      ],
      recent_progress: [
        {
          id: "plan-empty",
          kind: "plan",
          title: "Already shipped",
          subtitle: "plan · updated",
          updated_at: "2026-04-21T02:00:00+00:00",
        },
        {
          id: "task-1",
          kind: "task",
          title: "Shipped task",
          subtitle: "task · done",
          updated_at: "2026-04-21T03:00:00+00:00",
        },
      ],
    }));

    const result = await getProjectProgress(FAKE_TOKEN, "proj-1");

    expect(result.active_plans).toEqual([]);
    expect(result.open_work_groups).toEqual([]);
    expect(result.milestones).toEqual([]);
    expect(result.recent_progress.map((item) => item.id)).toEqual(["task-1"]);
  });

  it("normalizes missing milestone arrays on active plans", async () => {
    vi.stubGlobal("fetch", mockFetch({
      project: {
        id: "proj-1",
        name: "Console",
        type: "product",
      },
      active_plans: [
        {
          id: "plan-1",
          goal: "Ship S01",
          goal: "Ship S01",
          status: "active",
          owner: "Barry",
          tasks_summary: { total: 1, by_status: { todo: 1 } },
          open_count: 1,
          blocked_count: 0,
          review_count: 0,
          overdue_count: 0,
          updated_at: "2026-04-21T01:00:00+00:00",
          next_tasks: [],
        },
      ],
      open_work_groups: [],
      milestones: [],
      recent_progress: [],
    }));

    const result = await getProjectProgress(FAKE_TOKEN, "proj-1");

    expect(result.active_plans[0]?.milestones).toEqual([]);
    expect(result.active_plans[0]?.next_tasks).toEqual([]);
  });
});

// ─── getPartnerMe ───

describe("getPartnerMe", () => {
  it("calls GET /api/partner/me with auth header and no-store cache", async () => {
    const partner = { id: "p-1", email: "user@example.com" };
    const fakeFetch = mockFetch({ partner });
    vi.stubGlobal("fetch", fakeFetch);

    await getPartnerMe(FAKE_TOKEN);

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/partner/me`,
      {
        cache: "no-store",
        headers: { Authorization: `Bearer ${FAKE_TOKEN}` },
      }
    );
  });

  it("includes active workspace header when one is stored", async () => {
    const partner = { id: "p-1", email: "user@example.com" };
    const fakeFetch = mockFetch({ partner });
    vi.stubGlobal("fetch", fakeFetch);
    const originalLocalStorage = window.localStorage;
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: {
        getItem: vi.fn((key: string) => key === "zenos.activeWorkspaceId" ? "workspace-123" : null),
      },
    });

    try {
      await getPartnerMe(FAKE_TOKEN);

      expect(fakeFetch).toHaveBeenCalledWith(
        `${API_BASE}/api/partner/me`,
        {
          cache: "no-store",
          headers: {
            Authorization: `Bearer ${FAKE_TOKEN}`,
            "X-Active-Workspace-Id": "workspace-123",
          },
        }
      );
    } finally {
      Object.defineProperty(window, "localStorage", {
        configurable: true,
        value: originalLocalStorage,
      });
    }
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

describe("updatePartnerScope", () => {
  it("sends authorized_entity_ids in the request body", async () => {
    const partner = {
      id: "p-guest",
      email: "guest@example.com",
      displayName: "Guest",
      workspaceRole: "guest",
      accessMode: "scoped",
      authorizedEntityIds: ["entity-1", "entity-2"],
      isAdmin: false,
    };
    const fakeFetch = mockFetch(partner);
    vi.stubGlobal("fetch", fakeFetch);

    await updatePartnerScope(FAKE_TOKEN, "p-guest", {
      roles: ["engineering"],
      department: "all",
      workspaceRole: "guest",
      accessMode: "scoped",
      authorizedEntityIds: ["entity-1", "entity-2"],
    });

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/partners/p-guest/scope`,
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({
          roles: ["engineering"],
          department: "all",
          workspaceRole: "guest",
          accessMode: "scoped",
          authorizedEntityIds: ["entity-1", "entity-2"],
          workspace_role: "guest",
          access_mode: "scoped",
          authorized_entity_ids: ["entity-1", "entity-2"],
        }),
      })
    );
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

// ─── Document Delivery APIs ───

describe("document delivery APIs", () => {
  it("calls GET /api/docs/{docId} for getDocumentDelivery", async () => {
    const fakeFetch = mockFetch({ document: { id: "doc-1" } });
    vi.stubGlobal("fetch", fakeFetch);

    await getDocumentDelivery(FAKE_TOKEN, "doc-1");

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/docs/doc-1`,
      expect.objectContaining({
        headers: { Authorization: `Bearer ${FAKE_TOKEN}` },
      })
    );
  });

  it("calls GET /api/docs/{docId}/content for getDocumentContent", async () => {
    const fakeFetch = mockFetch({ doc_id: "doc-1", content_type: "text/markdown", content: "# hi" });
    vi.stubGlobal("fetch", fakeFetch);

    await getDocumentContent(FAKE_TOKEN, "doc-1");

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/docs/doc-1/content`,
      expect.objectContaining({
        headers: { Authorization: `Bearer ${FAKE_TOKEN}` },
      })
    );
  });

  it("calls POST /api/docs/{docId}/publish for publishDocumentSnapshot", async () => {
    const fakeFetch = mockFetch({ revision_id: "rev-1", canonical_path: "/docs/doc-1" });
    vi.stubGlobal("fetch", fakeFetch);

    await publishDocumentSnapshot(FAKE_TOKEN, "doc-1");

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/docs/doc-1/publish`,
      expect.objectContaining({
        method: "POST",
        headers: { Authorization: `Bearer ${FAKE_TOKEN}` },
      })
    );
  });

  it("calls PATCH /api/docs/{docId}/access with visibility payload", async () => {
    const fakeFetch = mockFetch({ visibility: "restricted" });
    vi.stubGlobal("fetch", fakeFetch);

    await updateDocumentVisibility(FAKE_TOKEN, "doc-1", "restricted");

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/docs/doc-1/access`,
      expect.objectContaining({
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${FAKE_TOKEN}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ visibility: "restricted" }),
      })
    );
  });

  it("calls POST /api/docs/{docId}/content with markdown payload", async () => {
    const fakeFetch = mockFetch({ revision_id: "rev-2", canonical_path: "/docs/doc-1" });
    vi.stubGlobal("fetch", fakeFetch);

    await saveDocumentMarkdown(FAKE_TOKEN, "doc-1", "# hello", {
      base_revision_id: "rev-1",
      source_id: "manual-source",
      source_version_ref: "manual-v1",
    });

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/docs/doc-1/content`,
      expect.objectContaining({
        method: "POST",
        headers: {
          Authorization: `Bearer ${FAKE_TOKEN}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          base_revision_id: "rev-1",
          content: "# hello",
          source_id: "manual-source",
          source_version_ref: "manual-v1",
        }),
      })
    );
  });

  it("calls POST /api/docs/{docId}/share-links with options", async () => {
    const fakeFetch = mockFetch({
      token_id: "tok-1",
      share_url: "/s?token=abc",
      expires_at: "2026-04-11T00:00:00Z",
    });
    vi.stubGlobal("fetch", fakeFetch);

    await createDocumentShareLink(FAKE_TOKEN, "doc-1", { expires_in_hours: 24, max_access_count: 5 });

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/docs/doc-1/share-links`,
      expect.objectContaining({
        method: "POST",
        headers: {
          Authorization: `Bearer ${FAKE_TOKEN}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ expires_in_hours: 24, max_access_count: 5 }),
      })
    );
  });

  it("calls DELETE /api/docs/share-links/{tokenId} for revokeDocumentShareLink", async () => {
    const fakeFetch = mockFetch({});
    vi.stubGlobal("fetch", fakeFetch);

    await revokeDocumentShareLink(FAKE_TOKEN, "tok-1");

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/docs/share-links/tok-1`,
      expect.objectContaining({
        method: "DELETE",
        headers: { Authorization: `Bearer ${FAKE_TOKEN}` },
      })
    );
  });

  it("URL-encodes token in getSharedDocumentByToken", async () => {
    const fakeFetch = mockFetch({ doc: { id: "doc-1", name: "Doc" }, content: "# shared" });
    vi.stubGlobal("fetch", fakeFetch);

    await getSharedDocumentByToken("abc/def==");

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/s/abc%2Fdef%3D%3D`,
      expect.objectContaining({
        headers: {},
      })
    );
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
