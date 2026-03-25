import { describe, it, expect, vi, beforeEach } from "vitest";
import { collection, query, where, getDocs } from "firebase/firestore";
import { getDbInstance } from "@/lib/firebase";
import { getTasks, getTasksByEntity } from "@/lib/firestore";

// Firebase modules are mocked globally in setup.ts.
// Here we set up specific return values per test.

const mockCollection = vi.mocked(collection);
const mockQuery = vi.mocked(query);
const mockWhere = vi.mocked(where);
const mockGetDocs = vi.mocked(getDocs);
const mockGetDbInstance = vi.mocked(getDbInstance);

beforeEach(() => {
  vi.clearAllMocks();
  // getDbInstance returns a fake db object; its value doesn't matter since
  // collection/query/getDocs are all mocked.
  mockGetDbInstance.mockReturnValue({} as ReturnType<typeof getDbInstance>);
  mockCollection.mockReturnValue("mock-collection-ref" as unknown as ReturnType<typeof collection>);
  mockQuery.mockReturnValue("mock-query-ref" as unknown as ReturnType<typeof query>);
  mockWhere.mockReturnValue("mock-where-clause" as unknown as ReturnType<typeof where>);
});

// ---------------------------------------------------------------------------
// getTasks
// ---------------------------------------------------------------------------

describe("getTasks", () => {
  it("returns [] immediately when partnerId is null — no Firestore query issued", async () => {
    const result = await getTasks(null);
    expect(result).toEqual([]);
    expect(mockGetDocs).not.toHaveBeenCalled();
  });

  it("returns [] immediately when partnerId is empty string — no Firestore query issued", async () => {
    const result = await getTasks("");
    expect(result).toEqual([]);
    expect(mockGetDocs).not.toHaveBeenCalled();
  });

  it("queries partners/{partnerId}/tasks when a valid partnerId is provided", async () => {
    mockGetDocs.mockResolvedValueOnce({ docs: [] } as unknown as Awaited<ReturnType<typeof getDocs>>);

    await getTasks("partner-abc");

    expect(mockCollection).toHaveBeenCalledWith(expect.anything(), "partners/partner-abc/tasks");
  });

  it("returns mapped tasks from Firestore snapshot", async () => {
    const fakeDoc = {
      id: "task-1",
      data: () => ({
        title: "Build feature",
        status: "todo",
        priority: "high",
        createdBy: "user-1",
        assignee: null,
        linkedEntities: [],
        blockedBy: [],
        acceptanceCriteria: [],
        createdAt: { toDate: () => new Date("2026-03-01") },
        updatedAt: { toDate: () => new Date("2026-03-20") },
        completedAt: null,
      }),
    };
    mockGetDocs.mockResolvedValueOnce({ docs: [fakeDoc] } as unknown as Awaited<ReturnType<typeof getDocs>>);

    const result = await getTasks("partner-abc");

    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("task-1");
    expect(result[0].title).toBe("Build feature");
    expect(result[0].status).toBe("todo");
  });

  it("applies default status filter (exclude archived) when no statuses filter given", async () => {
    mockGetDocs.mockResolvedValueOnce({ docs: [] } as unknown as Awaited<ReturnType<typeof getDocs>>);

    await getTasks("partner-abc");

    expect(mockWhere).toHaveBeenCalledWith(
      "status",
      "in",
      ["backlog", "todo", "in_progress", "review", "done", "blocked", "cancelled"]
    );
  });

  it("applies custom statuses filter when provided", async () => {
    mockGetDocs.mockResolvedValueOnce({ docs: [] } as unknown as Awaited<ReturnType<typeof getDocs>>);

    await getTasks("partner-abc", { statuses: ["todo", "in_progress"] });

    expect(mockWhere).toHaveBeenCalledWith("status", "in", ["todo", "in_progress"]);
  });
});

// ---------------------------------------------------------------------------
// getTasksByEntity
// ---------------------------------------------------------------------------

describe("getTasksByEntity", () => {
  it("returns [] immediately when partnerId is null — no Firestore query issued", async () => {
    const result = await getTasksByEntity(null, "entity-1");
    expect(result).toEqual([]);
    expect(mockGetDocs).not.toHaveBeenCalled();
  });

  it("returns [] immediately when partnerId is empty string — no Firestore query issued", async () => {
    const result = await getTasksByEntity("", "entity-1");
    expect(result).toEqual([]);
    expect(mockGetDocs).not.toHaveBeenCalled();
  });

  it("queries partners/{partnerId}/tasks when a valid partnerId is provided", async () => {
    mockGetDocs.mockResolvedValueOnce({ docs: [] } as unknown as Awaited<ReturnType<typeof getDocs>>);

    await getTasksByEntity("partner-abc", "entity-1");

    expect(mockCollection).toHaveBeenCalledWith(expect.anything(), "partners/partner-abc/tasks");
    expect(mockWhere).toHaveBeenCalledWith("linkedEntities", "array-contains", "entity-1");
  });

  it("returns mapped tasks from Firestore snapshot", async () => {
    const fakeDoc = {
      id: "task-2",
      data: () => ({
        title: "Linked task",
        status: "in_progress",
        linkedEntities: ["entity-1"],
        createdAt: { toDate: () => new Date("2026-03-01") },
        updatedAt: { toDate: () => new Date("2026-03-20") },
        completedAt: null,
      }),
    };
    mockGetDocs.mockResolvedValueOnce({ docs: [fakeDoc] } as unknown as Awaited<ReturnType<typeof getDocs>>);

    const result = await getTasksByEntity("partner-abc", "entity-1");

    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("task-2");
    expect(result[0].linkedEntities).toContain("entity-1");
  });
});
