import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const getProjectEntitiesMock = vi.hoisted(() => vi.fn());
const getProjectProgressMock = vi.hoisted(() => vi.fn());
const getTasksByEntityMock = vi.hoisted(() => vi.fn());
const getEntityContextMock = vi.hoisted(() => vi.fn());
const getChildEntitiesMock = vi.hoisted(() => vi.fn());
const getAllBlindspotsMock = vi.hoisted(() => vi.fn());
const createTaskMock = vi.hoisted(() => vi.fn());
const createPlanMock = vi.hoisted(() => vi.fn());
const createMilestoneMock = vi.hoisted(() => vi.fn());
const mockUser = { getIdToken: vi.fn().mockResolvedValue("token-1") };

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: mockUser,
  }),
}));

vi.mock("@/lib/api", () => ({
  getProjectEntities: (...args: unknown[]) => getProjectEntitiesMock(...args),
  getProjectProgress: (...args: unknown[]) => getProjectProgressMock(...args),
  getTasksByEntity: (...args: unknown[]) => getTasksByEntityMock(...args),
  getEntityContext: (...args: unknown[]) => getEntityContextMock(...args),
  getChildEntities: (...args: unknown[]) => getChildEntitiesMock(...args),
  getAllBlindspots: (...args: unknown[]) => getAllBlindspotsMock(...args),
  createTask: (...args: unknown[]) => createTaskMock(...args),
  createPlan: (...args: unknown[]) => createPlanMock(...args),
  createMilestone: (...args: unknown[]) => createMilestoneMock(...args),
  updateTask: vi.fn(),
  confirmTask: vi.fn(),
  handoffTask: vi.fn(),
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

vi.mock("@/components/PlanCreateDialog", () => ({
  PlanCreateDialog: ({
    isOpen,
    onCreatePlan,
  }: {
    isOpen: boolean;
    onCreatePlan: (data: { goal: string; status?: "draft" | "active" }) => Promise<void>;
  }) =>
    isOpen ? (
      <button onClick={() => void onCreatePlan({ goal: "Launch project progress console", status: "active" })}>
        create-project-plan
      </button>
    ) : null,
}));

vi.mock("@/components/MilestoneCreateDialog", () => ({
  MilestoneCreateDialog: ({
    isOpen,
    onCreateMilestone,
  }: {
    isOpen: boolean;
    onCreateMilestone: (data: { name: string; status?: "planned" | "active" }) => Promise<void>;
  }) =>
    isOpen ? (
      <button onClick={() => void onCreateMilestone({ name: "P0 上線", status: "active" })}>
        create-project-milestone
      </button>
    ) : null,
}));

vi.mock("@/features/projects/ProjectProgressConsole", () => ({
  ProjectProgressConsole: ({
    onOpenTasks,
    recapRailOpen,
  }: {
    onOpenTasks: () => void;
    recapRailOpen?: boolean;
  }) => (
    <div data-testid="project-progress-console">
      <button onClick={onOpenTasks}>open-task-board</button>
      {recapRailOpen ? <div>project-recap-open</div> : null}
    </div>
  ),
}));

describe("ProjectsPage", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    getProjectEntitiesMock.mockReset();
    getProjectProgressMock.mockReset();
    getTasksByEntityMock.mockReset();
    getEntityContextMock.mockReset();
    getChildEntitiesMock.mockReset();
    getAllBlindspotsMock.mockReset();
    createTaskMock.mockReset();
    createPlanMock.mockReset();
    createMilestoneMock.mockReset();
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
    getProjectProgressMock.mockResolvedValue({
      project: {
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
      active_plans: [],
      open_work_groups: [],
      milestones: [],
      recent_progress: [],
    });
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
    getAllBlindspotsMock.mockResolvedValue([]);
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

  it("keeps project console as default detail view and allows task drill-down", async () => {
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
    getTasksByEntityMock.mockResolvedValue([
      {
        id: "task-1",
        title: "Ship console UI",
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
      },
    ]);
    getProjectProgressMock.mockResolvedValue({
      project: {
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
      active_plans: [],
      open_work_groups: [],
      milestones: [],
      recent_progress: [],
    });
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
    getAllBlindspotsMock.mockResolvedValue([]);

    const { default: ProjectsPage } = await import("./page");
    render(<ProjectsPage />);

    fireEvent.click(await screen.findByRole("button", { name: /ZenOS/ }));

    expect(await screen.findByTestId("project-progress-console")).toBeInTheDocument();
    expect(screen.queryByTestId("project-task-board")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "open-task-board" }));

    expect(await screen.findByTestId("project-task-board")).toHaveTextContent("Ship console UI");
  });

  it("creates project plan scoped to the current product", async () => {
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
    getProjectProgressMock.mockResolvedValue({
      project: {
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
      active_plans: [],
      open_work_groups: [],
      milestones: [],
      recent_progress: [],
    });
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
    getAllBlindspotsMock.mockResolvedValue([]);
    createPlanMock.mockResolvedValue({
      id: "plan-1",
      goal: "Launch project progress console",
      status: "active",
      owner: "Owner",
      project: "ZenOS",
      project_id: "entity-1",
    });

    const { default: ProjectsPage } = await import("./page");
    render(<ProjectsPage />);

    fireEvent.click(await screen.findByRole("button", { name: /ZenOS/ }));
    fireEvent.click(await screen.findByRole("button", { name: "新 Plan" }));
    fireEvent.click(await screen.findByRole("button", { name: "create-project-plan" }));

    await waitFor(() => {
      expect(createPlanMock).toHaveBeenCalledWith(
        "token-1",
        expect.objectContaining({
          goal: "Launch project progress console",
          project: "ZenOS",
          project_id: "entity-1",
          status: "active",
        }),
      );
    });
  });

  it("creates project milestone scoped to the current product", async () => {
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
    getProjectProgressMock.mockResolvedValue({
      project: {
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
      active_plans: [],
      open_work_groups: [],
      milestones: [],
      recent_progress: [],
    });
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
    getAllBlindspotsMock.mockResolvedValue([]);
    createMilestoneMock.mockResolvedValue({
      id: "goal-1",
      name: "P0 上線",
      type: "goal",
      status: "active",
      parentId: "entity-1",
    });

    const { default: ProjectsPage } = await import("./page");
    render(<ProjectsPage />);

    fireEvent.click(await screen.findByRole("button", { name: /ZenOS/ }));
    fireEvent.click(await screen.findByRole("button", { name: "新 Milestone" }));
    fireEvent.click(await screen.findByRole("button", { name: "create-project-milestone" }));

    await waitFor(() => {
      expect(createMilestoneMock).toHaveBeenCalledWith(
        "token-1",
        expect.objectContaining({
          name: "P0 上線",
          project_id: "entity-1",
          owner: "Owner",
          status: "active",
        }),
      );
    });
  });

  it("opens project AI recap from Agent 建議", async () => {
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
    getProjectProgressMock.mockResolvedValue({
      project: {
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
      active_plans: [],
      open_work_groups: [],
      milestones: [],
      recent_progress: [],
    });
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
    getAllBlindspotsMock.mockResolvedValue([]);

    const { default: ProjectsPage } = await import("./page");
    render(<ProjectsPage />);

    fireEvent.click(await screen.findByRole("button", { name: /ZenOS/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Agent 建議" }));

    expect(await screen.findByTestId("project-progress-console")).toBeInTheDocument();
    expect(screen.getByText("project-recap-open")).toBeInTheDocument();
  });
});
