import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const getTasksMock = vi.hoisted(() => vi.fn());
const getAllEntitiesMock = vi.hoisted(() => vi.fn());
const mockUser = { email: "owner@test.com", getIdToken: vi.fn().mockResolvedValue("token-1") };
const mockPartner = {
  id: "partner-1",
  displayName: "Owner",
  workspaceRole: "owner",
  accessMode: "internal",
  authorizedEntityIds: [],
};

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: mockUser,
    partner: mockPartner,
  }),
}));

vi.mock("@/lib/api", () => ({
  getTasks: (...args: unknown[]) => getTasksMock(...args),
  getAllEntities: (...args: unknown[]) => getAllEntitiesMock(...args),
  createTask: vi.fn(),
  updateTask: vi.fn(),
  confirmTask: vi.fn(),
}));

vi.mock("@/components/TaskBoard", () => ({
  TaskBoard: ({ tasks }: { tasks: Array<{ title: string }> }) => (
    <div data-testid="task-board">{tasks.map((task) => task.title).join(",")}</div>
  ),
}));

vi.mock("@/components/TaskFilters", () => ({
  TaskFilters: () => <div data-testid="task-filters" />,
}));

vi.mock("@/components/TaskCreateDialog", () => ({
  TaskCreateDialog: ({ isOpen }: { isOpen: boolean }) =>
    isOpen ? <div data-testid="task-create-dialog">task-create-dialog</div> : null,
}));

describe("TasksPage", () => {
  beforeEach(() => {
    getTasksMock.mockReset();
    getAllEntitiesMock.mockReset();
  });

  it("loads real tasks into TaskBoard", async () => {
    getTasksMock.mockResolvedValue([
      {
        id: "task-1",
        title: "接回真實任務流",
        description: "",
        status: "todo",
        priority: "high",
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
      },
    ]);
    getAllEntitiesMock.mockResolvedValue([
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

    const { TasksPage } = await import("./page");
    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByTestId("task-board")).toHaveTextContent("接回真實任務流");
    });
  });

  it("opens create dialog from header action", async () => {
    getTasksMock.mockResolvedValue([]);
    getAllEntitiesMock.mockResolvedValue([]);

    const { TasksPage } = await import("./page");
    render(<TasksPage />);

    fireEvent.click(await screen.findByRole("button", { name: "新任務" }));

    await waitFor(() => {
      expect(screen.getByTestId("task-create-dialog")).toBeInTheDocument();
    });
  });
});
