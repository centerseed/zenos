import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const getProjectEntitiesMock = vi.hoisted(() => vi.fn());
const getProjectEntitiesInWorkspaceMock = vi.hoisted(() => vi.fn());
const getProjectProgressMock = vi.hoisted(() => vi.fn());
const getTasksByEntityMock = vi.hoisted(() => vi.fn());
const getEntityContextMock = vi.hoisted(() => vi.fn());
const getChildEntitiesMock = vi.hoisted(() => vi.fn());
const getAllBlindspotsMock = vi.hoisted(() => vi.fn());
const createTaskMock = vi.hoisted(() => vi.fn());
const createPlanMock = vi.hoisted(() => vi.fn());
const createMilestoneMock = vi.hoisted(() => vi.fn());
const applyHomeWorkspaceBootstrapMock = vi.hoisted(() => vi.fn());
const refetchPartnerMock = vi.hoisted(() => vi.fn());
const mockUser = { getIdToken: vi.fn().mockResolvedValue("token-1") };
const mockPartner = {
  id: "guest-home-id",
  email: "guest@test.com",
  displayName: "Guest User",
  isAdmin: false,
  workspaceRole: "owner",
  accessMode: "internal",
  status: "active",
  sharedPartnerId: null,
  preferences: {},
};

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: mockUser,
    partner: mockPartner,
    refetchPartner: refetchPartnerMock,
  }),
}));

vi.mock("@/lib/api", () => ({
  getProjectEntities: (...args: unknown[]) => getProjectEntitiesMock(...args),
  getProjectEntitiesInWorkspace: (...args: unknown[]) => getProjectEntitiesInWorkspaceMock(...args),
  getProjectProgress: (...args: unknown[]) => getProjectProgressMock(...args),
  getTasksByEntity: (...args: unknown[]) => getTasksByEntityMock(...args),
  getEntityContext: (...args: unknown[]) => getEntityContextMock(...args),
  getChildEntities: (...args: unknown[]) => getChildEntitiesMock(...args),
  getAllBlindspots: (...args: unknown[]) => getAllBlindspotsMock(...args),
  createTask: (...args: unknown[]) => createTaskMock(...args),
  createPlan: (...args: unknown[]) => createPlanMock(...args),
  createMilestone: (...args: unknown[]) => createMilestoneMock(...args),
  applyHomeWorkspaceBootstrap: (...args: unknown[]) => applyHomeWorkspaceBootstrapMock(...args),
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
    onAssistantUpdate,
  }: {
    onOpenTasks: () => void;
    onAssistantUpdate?: () => void;
  }) => (
    <div data-testid="project-progress-console">
      <button onClick={onOpenTasks}>open-task-board</button>
      <button onClick={() => onAssistantUpdate?.()}>assistant-updated</button>
      <div>project-copilot-inline</div>
    </div>
  ),
}));

describe("ProjectsPage", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    window.history.replaceState({}, "", "/projects");
    Object.defineProperty(window, "scrollTo", {
      writable: true,
      value: vi.fn(),
    });
    getProjectEntitiesMock.mockReset();
    getProjectProgressMock.mockReset();
    getTasksByEntityMock.mockReset();
    getEntityContextMock.mockReset();
    getChildEntitiesMock.mockReset();
    getAllBlindspotsMock.mockReset();
    createTaskMock.mockReset();
    createPlanMock.mockReset();
    createMilestoneMock.mockReset();
    getProjectEntitiesInWorkspaceMock.mockReset();
    applyHomeWorkspaceBootstrapMock.mockReset();
    refetchPartnerMock.mockReset();
    Object.assign(mockPartner, {
      id: "guest-home-id",
      email: "guest@test.com",
      displayName: "Guest User",
      isAdmin: false,
      workspaceRole: "owner",
      accessMode: "internal",
      status: "active",
      sharedPartnerId: null,
      preferences: {},
    });
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

  it("hides completed placeholder products from the projects list", async () => {
    getProjectEntitiesMock.mockResolvedValue([
      {
        id: "entity-real",
        name: "個人",
        type: "product",
        summary: "real project",
        tags: { what: [], why: "", how: "", who: [] },
        status: "active",
        parentId: null,
        details: null,
        confirmedByUser: true,
        owner: "Barry",
        sources: [],
        visibility: "public",
        lastReviewedAt: null,
        createdAt: new Date("2026-04-19T00:00:00Z"),
        updatedAt: new Date("2026-04-19T00:00:00Z"),
      },
      {
        id: "entity-fake",
        name: "GRACE ONE",
        type: "product",
        summary: "placeholder",
        tags: { what: [], why: "", how: "", who: [] },
        status: "completed",
        parentId: "company-1",
        details: null,
        confirmedByUser: false,
        owner: null,
        sources: [],
        visibility: "confidential",
        lastReviewedAt: null,
        createdAt: new Date("2026-03-31T00:00:00Z"),
        updatedAt: new Date("2026-04-21T00:00:00Z"),
      },
    ]);
    getTasksByEntityMock.mockResolvedValue([]);

    const { default: ProjectsPage } = await import("./page");
    render(<ProjectsPage />);

    expect(await screen.findByText("個人")).toBeInTheDocument();
    expect(screen.queryByText("GRACE ONE")).not.toBeInTheDocument();
  });

  it("shows bootstrap CTA in home workspace and applies pending bootstrap", async () => {
    Object.assign(mockPartner, {
      preferences: {
        homeWorkspaceBootstrap: {
          sourceWorkspaceId: "owner-shared-id",
          sourceEntityIds: ["product-1"],
          state: "pending",
        },
      },
    });
    getProjectEntitiesMock.mockResolvedValue([]);
    getProjectEntitiesInWorkspaceMock.mockResolvedValue([
      {
        id: "product-1",
        name: "合作案 A",
        type: "product",
        summary: "shared source",
        tags: { what: [], why: "", how: "", who: [] },
        status: "active",
        parentId: null,
        details: null,
        confirmedByUser: true,
        owner: "Barry",
        sources: [],
        visibility: "public",
        lastReviewedAt: null,
        createdAt: new Date("2026-04-19T00:00:00Z"),
        updatedAt: new Date("2026-04-19T00:00:00Z"),
      },
    ]);
    applyHomeWorkspaceBootstrapMock.mockResolvedValue({
      copied_root_entity_ids: ["copied-1"],
      copied_entity_count: 3,
      copied_relationship_count: 2,
      skipped_source_entity_ids: [],
    });
    refetchPartnerMock.mockResolvedValue(undefined);

    const { default: ProjectsPage } = await import("./page");
    render(<ProjectsPage />);

    expect(await screen.findByText("可匯入的起始產品")).toBeInTheDocument();
    expect(screen.getByText("合作案 A")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "匯入到 Home Workspace" }));

    await waitFor(() => {
      expect(applyHomeWorkspaceBootstrapMock).toHaveBeenCalledWith("token-1");
      expect(refetchPartnerMock).toHaveBeenCalled();
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

  it("focuses the inline project copilot from Agent 建議", async () => {
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
    expect(screen.getByText("project-copilot-inline")).toBeInTheDocument();
  });

  it("refreshes project detail after helper updates the recap", async () => {
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
    await screen.findByTestId("project-progress-console");
    const initialProgressCalls = getProjectProgressMock.mock.calls.length;
    const initialTaskCalls = getTasksByEntityMock.mock.calls.length;
    const initialContextCalls = getEntityContextMock.mock.calls.length;
    expect(getProjectProgressMock).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "assistant-updated" }));

    await waitFor(() => {
      expect(getProjectProgressMock.mock.calls.length).toBeGreaterThan(initialProgressCalls);
      expect(getTasksByEntityMock.mock.calls.length).toBeGreaterThan(initialTaskCalls);
      expect(getEntityContextMock.mock.calls.length).toBeGreaterThan(initialContextCalls);
    });
  });

  it("keeps selected project in url state so refresh/deep-link still opens detail", async () => {
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
    const { unmount } = render(<ProjectsPage />);

    fireEvent.click(await screen.findByRole("button", { name: /ZenOS/ }));
    expect(window.location.search).toContain("id=entity-1");
    expect(await screen.findByTestId("project-progress-console")).toBeInTheDocument();

    unmount();
    render(<ProjectsPage />);

    expect(await screen.findByTestId("project-progress-console")).toBeInTheDocument();
    expect(getProjectProgressMock).toHaveBeenCalledWith("token-1", "entity-1");
  });
});
