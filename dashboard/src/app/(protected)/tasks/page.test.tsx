import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const getTasksMock = vi.hoisted(() => vi.fn());
const getAllEntitiesMock = vi.hoisted(() => vi.fn());
const getAllBlindspotsMock = vi.hoisted(() => vi.fn());
const getPlansMock = vi.hoisted(() => vi.fn());
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
  getAllBlindspots: (...args: unknown[]) => getAllBlindspotsMock(...args),
  getPlans: (...args: unknown[]) => getPlansMock(...args),
  createTask: vi.fn(),
  updateTask: vi.fn(),
  confirmTask: vi.fn(),
  handoffTask: vi.fn(),
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
    getAllBlindspotsMock.mockReset();
    getPlansMock.mockReset();
    getPlansMock.mockResolvedValue([]);
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
    getAllBlindspotsMock.mockResolvedValue([]);
    getPlansMock.mockResolvedValue([]);

    const { TasksPage } = await import("./page");
    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByTestId("task-board")).toHaveTextContent("接回真實任務流");
    });
  });

  it("opens create dialog from header action", async () => {
    getTasksMock.mockResolvedValue([]);
    getAllEntitiesMock.mockResolvedValue([]);
    getAllBlindspotsMock.mockResolvedValue([]);
    getPlansMock.mockResolvedValue([]);

    const { TasksPage } = await import("./page");
    render(<TasksPage />);

    fireEvent.click(await screen.findByRole("button", { name: "新任務" }));

    await waitFor(() => {
      expect(screen.getByTestId("task-create-dialog")).toBeInTheDocument();
    });
  });

  it("deduplicates project filter options by normalized project key", async () => {
    const { buildAvailableProjectOptions } = await import("./page");

    const options = buildAvailableProjectOptions(
      [
        {
          id: "task-1",
          title: "task",
          description: "",
          status: "todo",
          priority: "high",
          project: "PACERIZ",
          priorityReason: "",
          assignee: null,
          createdBy: "partner-1",
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
          createdAt: new Date("2026-04-19T00:00:00Z"),
          updatedAt: new Date("2026-04-19T00:00:00Z"),
          completedAt: null,
        },
        {
          id: "task-2",
          title: "task",
          description: "",
          status: "todo",
          priority: "high",
          project: "  paceriz  ",
          priorityReason: "",
          assignee: null,
          createdBy: "partner-1",
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
          createdAt: new Date("2026-04-19T00:00:00Z"),
          updatedAt: new Date("2026-04-19T00:00:00Z"),
          completedAt: null,
        },
      ],
      [
        {
          id: "entity-1",
          name: "Paceriz",
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
      ],
    );

    expect(options).toEqual([{ value: "paceriz", label: "Paceriz" }]);
  });

  it("loads plan labels for grouped tasks when plan ids exist", async () => {
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
        planId: "plan-1",
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
    getAllBlindspotsMock.mockResolvedValue([]);
    getPlansMock.mockResolvedValue([
      {
        id: "plan-1",
        goal: "Ship project progress console",
        status: "active",
        owner: "Barry",
      },
    ]);

    const { TasksPage } = await import("./page");
    render(<TasksPage />);

    await waitFor(() => {
      expect(getPlansMock).toHaveBeenCalledWith("token-1", ["plan-1"]);
    });
  });
});
