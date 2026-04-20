import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const getProjectEntitiesMock = vi.hoisted(() => vi.fn());
const getTasksByEntityMock = vi.hoisted(() => vi.fn());
const getEntityContextMock = vi.hoisted(() => vi.fn());
const getChildEntitiesMock = vi.hoisted(() => vi.fn());
const createTaskMock = vi.hoisted(() => vi.fn());
const mockUser = { getIdToken: vi.fn().mockResolvedValue("token-1") };

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: mockUser,
  }),
}));

vi.mock("@/lib/api", () => ({
  getProjectEntities: (...args: unknown[]) => getProjectEntitiesMock(...args),
  getTasksByEntity: (...args: unknown[]) => getTasksByEntityMock(...args),
  getEntityContext: (...args: unknown[]) => getEntityContextMock(...args),
  getChildEntities: (...args: unknown[]) => getChildEntitiesMock(...args),
  createTask: (...args: unknown[]) => createTaskMock(...args),
  updateTask: vi.fn(),
  confirmTask: vi.fn(),
}));

vi.mock("@/components/TaskBoard", () => ({
  TaskBoard: ({ tasks }: { tasks: Array<{ title: string }> }) => (
    <div data-testid="project-task-board">{tasks.map((task) => task.title).join(",")}</div>
  ),
}));

vi.mock("@/components/TaskCreateDialog", () => ({
  TaskCreateDialog: ({
    isOpen,
    onCreateTask,
  }: {
    isOpen: boolean;
    onCreateTask: (data: { title: string }) => Promise<void>;
  }) =>
    isOpen ? (
      <button onClick={() => void onCreateTask({ title: "Project Task" })}>
        create-project-task
      </button>
    ) : null,
}));

describe("ProjectsPage", () => {
  beforeEach(() => {
    getProjectEntitiesMock.mockReset();
    getTasksByEntityMock.mockReset();
    getEntityContextMock.mockReset();
    getChildEntitiesMock.mockReset();
    createTaskMock.mockReset();
  });

  it("creates project task with linked_entities", async () => {
    getProjectEntitiesMock.mockResolvedValue([
      {
        id: "entity-1",
        name: "ZenOS",
        type: "product",
        summary: "summary",
        tags: { what: [], why: "", how: "", who: [] },
        status: "active",
        parentId: null,
        details: null,
        confirmedByUser: true,
        owner: "Owner",
        sources: [],
        visibility: "public",
        lastReviewedAt: null,
        createdAt: new Date("2026-04-19T00:00:00Z"),
        updatedAt: new Date("2026-04-19T00:00:00Z"),
      },
    ]);
    getTasksByEntityMock.mockResolvedValue([]);
    getEntityContextMock.mockResolvedValue({
      entity: {
        id: "entity-1",
        name: "ZenOS",
        type: "product",
        summary: "summary",
        tags: { what: [], why: "", how: "", who: [] },
        status: "active",
        parentId: null,
        details: null,
        confirmedByUser: true,
        owner: "Owner",
        sources: [],
        visibility: "public",
        lastReviewedAt: null,
        createdAt: new Date("2026-04-19T00:00:00Z"),
        updatedAt: new Date("2026-04-19T00:00:00Z"),
      },
      impact_chain: [],
      reverse_impact_chain: [],
    });
    getChildEntitiesMock.mockResolvedValue([]);
    createTaskMock.mockResolvedValue({
      id: "task-1",
      title: "Project Task",
      description: "",
      status: "todo",
      priority: "medium",
      project: "ZenOS",
      priorityReason: "",
      assignee: null,
      createdBy: "partner-1",
      linkedEntities: ["entity-1"],
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
      createdAt: new Date("2026-04-19T00:00:00Z"),
      updatedAt: new Date("2026-04-19T00:00:00Z"),
      completedAt: null,
    });

    const { default: ProjectsPage } = await import("./page");
    render(<ProjectsPage />);

    fireEvent.click(await screen.findByRole("button", { name: /ZenOS/ }));
    fireEvent.click(await screen.findByRole("button", { name: "新任務" }));
    fireEvent.click(await screen.findByRole("button", { name: "create-project-task" }));

    await waitFor(() => {
      expect(createTaskMock).toHaveBeenCalledWith(
        "token-1",
        expect.objectContaining({
          title: "Project Task",
          project: "ZenOS",
          linked_entities: ["entity-1"],
        }),
      );
    });
  });
});
