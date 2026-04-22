/**
 * Tests for task mutation API functions and core UI logic.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createTask, updateTask, confirmTask } from "@/lib/api";

const FAKE_TOKEN = "fake-token-abc";
const API_BASE = "https://zenos-mcp-s5oifosv3a-de.a.run.app";

function mockFetch(body: unknown, ok = true, status = 200) {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    json: vi.fn().mockResolvedValue(body),
  });
}

const fakeTask = {
  id: "task-1",
  title: "Test Task",
  description: "",
  status: "todo",
  priority: "medium",
  project: "TestProject",
  priorityReason: "",
  assignee: null,
  planId: null,
  planOrder: null,
  createdBy: "user-1",
  linkedEntities: [],
  linkedProtocol: null,
  linkedBlindspot: null,
  sourceType: "manual",
  contextSummary: "",
  dueDate: null,
  blockedBy: [],
  blockedReason: null,
  acceptanceCriteria: [],
  confirmedByCreator: false,
  rejectionReason: null,
  result: null,
  completedBy: null,
  createdAt: "2024-01-01T00:00:00Z",
  updatedAt: "2024-01-01T00:00:00Z",
  completedAt: null,
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ─── createTask ───────────────────────────────────────────────────────────────

describe("createTask", () => {
  it("calls POST /api/data/tasks with title and auth header", async () => {
    const fakeFetch = mockFetch({ task: fakeTask });
    vi.stubGlobal("fetch", fakeFetch);

    await createTask(FAKE_TOKEN, { title: "Test Task", product_id: "product-1" });

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/tasks`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: `Bearer ${FAKE_TOKEN}`,
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({ title: "Test Task", product_id: "product-1" }),
      })
    );
  });

  it("sends all optional fields when provided", async () => {
    const fakeFetch = mockFetch({ task: fakeTask });
    vi.stubGlobal("fetch", fakeFetch);

    await createTask(FAKE_TOKEN, {
      title: "My Task",
      product_id: "product-1",
      description: "desc",
      priority: "high",
      assignee: "user-2",
      due_date: "2024-12-31",
      project: "Proj",
      linked_entities: ["entity-1"],
    });

    const call = fakeFetch.mock.calls[0];
    const body = JSON.parse(call[1].body);
    expect(body).toMatchObject({
      title: "My Task",
      product_id: "product-1",
      description: "desc",
      priority: "high",
      assignee: "user-2",
      due_date: "2024-12-31",
      project: "Proj",
      linked_entities: ["entity-1"],
    });
  });

  it("returns a Task object (hydrating dates)", async () => {
    const fakeFetch = mockFetch({ task: fakeTask });
    vi.stubGlobal("fetch", fakeFetch);

    const result = await createTask(FAKE_TOKEN, { title: "Test", product_id: "product-1" });
    expect(result.id).toBe("task-1");
    expect(result.createdAt).toBeInstanceOf(Date);
  });

  it("handles bare response (no wrapper .task field)", async () => {
    const fakeFetch = mockFetch(fakeTask);
    vi.stubGlobal("fetch", fakeFetch);

    const result = await createTask(FAKE_TOKEN, { title: "Test", product_id: "product-1" });
    expect(result.id).toBe("task-1");
  });

  it("throws when API returns non-ok status", async () => {
    const fakeFetch = mockFetch({}, false, 400);
    vi.stubGlobal("fetch", fakeFetch);

    await expect(createTask(FAKE_TOKEN, { title: "x", product_id: "product-1" })).rejects.toThrow(
      "API /api/data/tasks: 400"
    );
  });
});

// ─── updateTask ───────────────────────────────────────────────────────────────

describe("updateTask", () => {
  it("calls PATCH /api/data/tasks/{id} with updates", async () => {
    const updated = { ...fakeTask, status: "in_progress" };
    const fakeFetch = mockFetch({ task: updated });
    vi.stubGlobal("fetch", fakeFetch);

    await updateTask(FAKE_TOKEN, "task-1", { status: "in_progress" });

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/tasks/task-1`,
      expect.objectContaining({
        method: "PATCH",
        headers: expect.objectContaining({ Authorization: `Bearer ${FAKE_TOKEN}` }),
        body: JSON.stringify({ status: "in_progress" }),
      })
    );
  });

  it("returns updated task with hydrated dates", async () => {
    const updated = { ...fakeTask, status: "in_progress" };
    const fakeFetch = mockFetch({ task: updated });
    vi.stubGlobal("fetch", fakeFetch);

    const result = await updateTask(FAKE_TOKEN, "task-1", { status: "in_progress" });
    expect(result.status).toBe("in_progress");
    expect(result.createdAt).toBeInstanceOf(Date);
  });

  it("supports null due_date (clearing due date)", async () => {
    const fakeFetch = mockFetch({ task: { ...fakeTask, dueDate: null } });
    vi.stubGlobal("fetch", fakeFetch);

    await updateTask(FAKE_TOKEN, "task-1", { due_date: null });

    const body = JSON.parse(fakeFetch.mock.calls[0][1].body);
    expect(body.due_date).toBeNull();
  });

  it("throws on API error", async () => {
    const fakeFetch = mockFetch({}, false, 404);
    vi.stubGlobal("fetch", fakeFetch);

    await expect(updateTask(FAKE_TOKEN, "task-1", { status: "done" })).rejects.toThrow(
      "API /api/data/tasks/task-1: 404"
    );
  });
});

// ─── confirmTask ─────────────────────────────────────────────────────────────

describe("confirmTask", () => {
  it("calls POST /api/data/tasks/{id}/confirm with approve action", async () => {
    const approved = { ...fakeTask, status: "done" };
    const fakeFetch = mockFetch({ task: approved });
    vi.stubGlobal("fetch", fakeFetch);

    await confirmTask(FAKE_TOKEN, "task-1", { action: "approve" });

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/data/tasks/task-1/confirm`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ action: "approve" }),
      })
    );
  });

  it("sends rejection_reason when rejecting", async () => {
    const rejected = { ...fakeTask, status: "todo", rejectionReason: "Not ready" };
    const fakeFetch = mockFetch({ task: rejected });
    vi.stubGlobal("fetch", fakeFetch);

    await confirmTask(FAKE_TOKEN, "task-1", { action: "reject", rejection_reason: "Not ready" });

    const body = JSON.parse(fakeFetch.mock.calls[0][1].body);
    expect(body).toEqual({ action: "reject", rejection_reason: "Not ready" });
  });

  it("returns updated task", async () => {
    const done = { ...fakeTask, status: "done" };
    const fakeFetch = mockFetch({ task: done });
    vi.stubGlobal("fetch", fakeFetch);

    const result = await confirmTask(FAKE_TOKEN, "task-1", { action: "approve" });
    expect(result.status).toBe("done");
  });

  it("throws on API error", async () => {
    const fakeFetch = mockFetch({}, false, 403);
    vi.stubGlobal("fetch", fakeFetch);

    await expect(confirmTask(FAKE_TOKEN, "task-1", { action: "approve" })).rejects.toThrow(
      "API /api/data/tasks/task-1/confirm: 403"
    );
  });
});

// ─── Status transition logic ──────────────────────────────────────────────────

describe("STATUS_TRANSITIONS logic", () => {
  const STATUS_TRANSITIONS: Record<string, string[]> = {
    todo: ["in_progress"],
    in_progress: ["todo", "review"],
    review: ["in_progress", "done"],
    done: [],
    cancelled: [],
    blocked: ["todo", "in_progress"],
  };

  it("todo can only go to in_progress (not skip to done directly via normal path)", () => {
    expect(STATUS_TRANSITIONS["todo"]).toContain("in_progress");
    expect(STATUS_TRANSITIONS["todo"]).not.toContain("done");
  });

  it("in_progress can go to todo or review", () => {
    expect(STATUS_TRANSITIONS["in_progress"]).toContain("todo");
    expect(STATUS_TRANSITIONS["in_progress"]).toContain("review");
  });

  it("review can go to in_progress or done", () => {
    expect(STATUS_TRANSITIONS["review"]).toContain("in_progress");
    expect(STATUS_TRANSITIONS["review"]).toContain("done");
  });

  it("done has no transitions", () => {
    expect(STATUS_TRANSITIONS["done"]).toHaveLength(0);
  });

  it("cancelled has no transitions", () => {
    expect(STATUS_TRANSITIONS["cancelled"]).toHaveLength(0);
  });
});

// ─── Warning trigger logic ────────────────────────────────────────────────────

describe("Warning trigger logic", () => {
  function shouldWarn(fromStatus: string, toStatus: string, hasResult: boolean): string | null {
    if (fromStatus === "todo" && toStatus === "done") {
      return "建議先經過 in_progress 和 review";
    }
    if (toStatus === "review" && !hasResult) {
      return "建議填寫任務成果後再送審";
    }
    return null;
  }

  it("warns when jumping from todo directly to done", () => {
    expect(shouldWarn("todo", "done", false)).toBeTruthy();
  });

  it("warns when moving to review without a result", () => {
    expect(shouldWarn("in_progress", "review", false)).toBeTruthy();
  });

  it("does not warn when moving to review with a result filled", () => {
    expect(shouldWarn("in_progress", "review", true)).toBeNull();
  });

  it("does not warn for normal in_progress -> todo transition", () => {
    expect(shouldWarn("in_progress", "todo", false)).toBeNull();
  });

  it("does not warn for review -> done transition", () => {
    expect(shouldWarn("review", "done", false)).toBeNull();
  });
});
