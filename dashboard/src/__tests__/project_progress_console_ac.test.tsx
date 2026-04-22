import React from "react";
import {
  describe,
  expect,
  it,
  vi,
  afterEach,
  beforeEach,
} from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ProjectOpenWorkPanel } from "@/features/projects/ProjectOpenWorkPanel";
import { ProjectPlansOverview } from "@/features/projects/ProjectPlansOverview";
import { ProjectProgressConsole } from "@/features/projects/ProjectProgressConsole";
import { ProjectRecentProgress } from "@/features/projects/ProjectRecentProgress";
import { buildProjectRecapEntry } from "@/features/projects/projectCopilot";
import {
  buildFallbackRecap,
  buildProjectContinuationPrompt,
} from "@/features/projects/projectPrompt";
import type {
  ProjectProgressPlanSummary,
  ProjectProgressResponse,
  ProjectProgressTaskSummary,
} from "@/lib/api";

const getProjectEntitiesMock = vi.hoisted(() => vi.fn());
const getProjectProgressMock = vi.hoisted(() => vi.fn());
const getTasksByEntityMock = vi.hoisted(() => vi.fn());
const getEntityContextMock = vi.hoisted(() => vi.fn());
const getChildEntitiesMock = vi.hoisted(() => vi.fn());
const getAllBlindspotsMock = vi.hoisted(() => vi.fn());
const mockUser = { getIdToken: vi.fn().mockResolvedValue("token-1") };

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: mockUser,
  }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getProjectEntities: (...args: unknown[]) => getProjectEntitiesMock(...args),
    getProjectProgress: (...args: unknown[]) => getProjectProgressMock(...args),
    getTasksByEntity: (...args: unknown[]) => getTasksByEntityMock(...args),
    getEntityContext: (...args: unknown[]) => getEntityContextMock(...args),
    getChildEntities: (...args: unknown[]) => getChildEntitiesMock(...args),
    getAllBlindspots: (...args: unknown[]) => getAllBlindspotsMock(...args),
    createTask: vi.fn(),
    updateTask: vi.fn(),
    confirmTask: vi.fn(),
    handoffTask: vi.fn(),
  };
});

vi.mock("@/components/TaskBoard", () => ({
  TaskBoard: ({ tasks }: { tasks: Array<{ title: string }> }) => (
    <div data-testid="project-task-board">{tasks.map((task) => task.title).join(",")}</div>
  ),
}));

vi.mock("@/components/TaskCreateDialog", () => ({
  TaskCreateDialog: () => null,
}));

vi.mock("@/features/projects/ProjectRecapRail", () => ({
  ProjectRecapRail: ({
    preset,
    nextStep,
    onRecapChange,
  }: {
    preset: string;
    nextStep: string;
    onRecapChange: (value: string | null) => void;
  }) =>
    (
      <div data-testid="project-recap-panel">
        <button onClick={() => onRecapChange(`AI recap for ${preset}: ${nextStep}`)}>
        deliver-mock-recap
        </button>
      </div>
    ),
}));

function makeTaskSummary(
  overrides: Partial<ProjectProgressTaskSummary> = {}
): ProjectProgressTaskSummary {
  return {
    id: overrides.id ?? "task-1",
    title: overrides.title ?? "Prepare API contract",
    status: overrides.status ?? "todo",
    priority: overrides.priority ?? "medium",
    plan_order: overrides.plan_order ?? null,
    assignee_name: overrides.assignee_name ?? "Avery",
    due_date: overrides.due_date ?? new Date("2026-04-21T00:00:00Z"),
    overdue: overrides.overdue ?? false,
    blocked: overrides.blocked ?? false,
    blocked_reason: overrides.blocked_reason ?? null,
    parent_task_id: overrides.parent_task_id ?? null,
    updated_at: overrides.updated_at ?? new Date("2026-04-21T10:00:00Z"),
    subtasks: overrides.subtasks ?? [],
  };
}

function makePlanSummary(
  overrides: Partial<ProjectProgressPlanSummary> = {}
): ProjectProgressPlanSummary {
  return {
    id: overrides.id ?? "plan-1",
    goal: overrides.goal ?? "Launch project progress console",
    status: overrides.status ?? "active",
    owner: overrides.owner ?? "Mina",
    milestones: overrides.milestones ?? [
      { id: "goal-1", name: "Console IA" },
    ],
    tasks_summary: overrides.tasks_summary ?? { total: 5, by_status: { todo: 2, review: 1 } },
    open_count: overrides.open_count ?? 4,
    blocked_count: overrides.blocked_count ?? 1,
    review_count: overrides.review_count ?? 1,
    overdue_count: overrides.overdue_count ?? 1,
    updated_at: overrides.updated_at ?? new Date("2026-04-21T12:00:00Z"),
    next_tasks:
      overrides.next_tasks ??
      [
        makeTaskSummary({
          id: "task-next-1",
          title: "Ship grouped open work",
          plan_order: 2,
        }),
      ],
  };
}

function makeProgressFixture(): ProjectProgressResponse {
  const parentTask = makeTaskSummary({
    id: "task-parent-1",
    title: "Ship grouped open work",
    plan_order: 2,
    status: "review",
    overdue: true,
    subtasks: [
      makeTaskSummary({
        id: "task-sub-1",
        title: "Render nested subtasks",
        status: "todo",
        plan_order: 5,
        parent_task_id: "task-parent-1",
      }),
    ],
  });
  const blockedTask = makeTaskSummary({
    id: "task-blocked-1",
    title: "Resolve API edge case",
    plan_order: 1,
    blocked: true,
    blocked_reason: "Waiting for aggregate contract",
  });

  return {
    project: {
      id: "project-1",
      name: "ZenOS",
      type: "product",
      summary: "Project progress console rollout",
      tags: { what: [], why: "", how: "", who: [] },
      status: "active",
      parentId: null,
      details: null,
      confirmedByUser: true,
      owner: "Owner",
      sources: [],
      visibility: "public",
      lastReviewedAt: null,
      createdAt: new Date("2026-04-18T00:00:00Z"),
      updatedAt: new Date("2026-04-21T12:00:00Z"),
    },
    active_plans: [
      makePlanSummary({
        id: "plan-1",
        goal: "Launch project progress console",
        next_tasks: [parentTask],
      }),
      makePlanSummary({
        id: "plan-2",
        goal: "Project AI recap enablement",
        milestones: [{ id: "goal-2", name: "AI rail rollout" }],
        blocked_count: 1,
        review_count: 0,
        overdue_count: 0,
        next_tasks: [blockedTask],
      }),
    ],
    open_work_groups: [
      {
        plan_id: "plan-1",
        plan_goal: "Launch project progress console",
        plan_status: "active",
        open_count: 2,
        blocked_count: 0,
        review_count: 1,
        overdue_count: 1,
        tasks: [parentTask],
      },
      {
        plan_id: "plan-2",
        plan_goal: "Project AI recap enablement",
        plan_status: "active",
        open_count: 1,
        blocked_count: 1,
        review_count: 0,
        overdue_count: 0,
        tasks: [blockedTask],
      },
    ],
    milestones: [
      { id: "goal-1", name: "Console IA", open_count: 2 },
      { id: "goal-2", name: "AI rail rollout", open_count: 1 },
    ],
    recent_progress: [
      {
        id: "plan-1",
        kind: "plan",
        title: "Launch project progress console",
        subtitle: "plan · updated",
        updated_at: new Date("2026-04-21T12:00:00Z"),
      },
      {
        id: "task-parent-1",
        kind: "task",
        title: "Ship grouped open work",
        subtitle: "task · review",
        updated_at: new Date("2026-04-21T11:30:00Z"),
      },
    ],
  };
}

function makePageTask() {
  return {
    id: "task-1",
    title: "Ship console UI",
    description: "",
    status: "todo",
    priority: "medium",
    project: "ZenOS",
    priorityReason: "",
    assignee: null,
    createdBy: "partner-1",
    linkedEntities: ["project-1"],
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
  };
}

describe("SPEC-project-progress-console acceptance tests", () => {
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
    vi.restoreAllMocks();
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  it("AC-PPC-01: Given 某產品底下有兩個 active plans When 使用者進入 /projects/[id] Then 第一層可見區域必須直接顯示這兩個 plans，而不是只顯示 task 摘要或空態", async function acPpc01ActivePlansFirstFold() {
    render(
      <ProjectPlansOverview
        plans={makeProgressFixture().active_plans}
        milestones={makeProgressFixture().milestones}
        groups={makeProgressFixture().open_work_groups}
      />
    );

    const cards = screen.getAllByTestId("plan-card");
    expect(cards).toHaveLength(2);
    expect(screen.getByText("Launch project progress console")).toBeInTheDocument();
    expect(screen.getByText("Project AI recap enablement")).toBeInTheDocument();
  });

  it("AC-PPC-02: Given 某 plan 有 goal、未完成 task、blocked task、review task When 查看 plan 卡 Then 必須直接看到 plan 名稱、未完成數、blocked 數、review 數與最近更新時間", async function acPpc02PlanCardMetrics() {
    render(
      <ProjectPlansOverview
        plans={[makeProgressFixture().active_plans[0]]}
        milestones={[makeProgressFixture().milestones[0]]}
        groups={[makeProgressFixture().open_work_groups[0]]}
      />
    );
    const card = screen.getByTestId("plan-card");
    const metrics = within(card).getAllByText("Open");

    expect(within(card).getByText("Launch project progress console")).toBeInTheDocument();
    expect(metrics.length).toBeGreaterThan(0);
    expect(within(card).getByText("Blocked")).toBeInTheDocument();
    expect(within(card).getByText("Review")).toBeInTheDocument();
    expect(within(card).getByText("Overdue")).toBeInTheDocument();
    expect(within(card).getByText("4")).toBeInTheDocument();
    expect(within(card).getAllByText("1")).toHaveLength(3);
    expect(within(card).getByText(/最近更新/)).toBeInTheDocument();
  });

  it("AC-PPC-03: Given 某產品沒有任何 active plan When 進入 /projects/[id] Then 畫面必須明確顯示「目前沒有進行中的 plan」空態，而不是只剩空白 task 區", async function acPpc03NoActivePlanEmptyState() {
    render(<ProjectPlansOverview plans={[]} milestones={[]} groups={[]} />);

    expect(screen.getByText("目前沒有進行中的 plan")).toBeInTheDocument();
  });

  it("AC-PPC-04: Given 某產品底下有多張未完成 task，且分屬不同 plan When 使用者查看 open work 區 Then task 必須依 plan 分組呈現，而不是單一混合列表", async function acPpc04OpenWorkGroupedByPlan() {
    render(
      <ProjectOpenWorkPanel
        groups={makeProgressFixture().open_work_groups}
        onOpenTasks={() => {}}
      />
    );

    const groups = screen.getAllByTestId("open-work-group");
    expect(groups).toHaveLength(2);
    expect(within(groups[0]).getByText("Launch project progress console")).toBeInTheDocument();
    expect(within(groups[1]).getByText("Project AI recap enablement")).toBeInTheDocument();
  });

  it("AC-PPC-05: Given 某 parent task 底下有 subtasks When 使用者查看產品頁的 open work 區 Then subtask 必須附屬於 parent task 顯示，不得與其他主 task 平鋪在同一層", async function acPpc05SubtasksNestedUnderParent() {
    render(
      <ProjectOpenWorkPanel
        groups={[makeProgressFixture().open_work_groups[0]]}
        onOpenTasks={() => {}}
      />
    );

    expect(screen.getAllByTestId("open-work-task")).toHaveLength(1);
    expect(screen.getByText("Ship grouped open work")).toBeInTheDocument();
    expect(screen.getAllByTestId("open-work-subtask")).toHaveLength(1);
    expect(screen.getByTestId("open-work-subtask-header")).toHaveTextContent("Subtasks");
    expect(screen.getByTestId("open-work-task-order")).toHaveTextContent("02");
    expect(screen.getByTestId("open-work-subtask-order")).toHaveTextContent("05");
    expect(screen.getByText("Render nested subtasks")).toBeInTheDocument();
  });

  it("AC-PPC-06: Given 某 plan 有 blocked / review / overdue 的 task When 查看該 plan 的 open work 區 Then 必須能直接辨識這三種風險或狀態，不需先進 task 詳情", async function acPpc06RiskSignalsVisible() {
    render(
      <ProjectOpenWorkPanel
        groups={makeProgressFixture().open_work_groups}
        onOpenTasks={() => {}}
      />
    );

    expect(screen.getAllByText("blocked").length).toBeGreaterThan(0);
    expect(screen.getAllByText("review").length).toBeGreaterThan(0);
    expect(screen.getAllByText("overdue").length).toBeGreaterThan(0);
  });

  it("AC-PPC-06A: Given task 帶 plan_order 與 subtasks When 查看 Current Plans Then 必須顯示順序編號與可展開 subtask 清單", async function acPpc06aPlanOrderAndSubtasksInPlanCard() {
    const progress = makeProgressFixture();
    render(
      <ProjectPlansOverview
        plans={[progress.active_plans[0]]}
        milestones={[progress.milestones[0]]}
        groups={[progress.open_work_groups[0]]}
      />
    );

    const row = screen.getByTestId("plan-task-row");
    expect(within(row).getByText("02")).toBeInTheDocument();
    expect(within(row).getByText("1 subtask")).toBeInTheDocument();

    fireEvent.click(within(row).getByTestId("plan-task-toggle"));

    expect(screen.getByTestId("plan-subtask-list")).toBeInTheDocument();
    expect(screen.getByTestId("plan-subtask-header")).toHaveTextContent("Subtasks");
    expect(screen.getByText("Render nested subtasks")).toBeInTheDocument();
    expect(screen.getByText("05")).toBeInTheDocument();
  });

  it("AC-PPC-07: Given 某產品有 active plans、未完成 task 與 blocker When 使用者觸發 AI recap Then AI 輸出必須同時涵蓋進度、plans、blockers、建議下一步與待決策點", async function acPpc07AiRecapContract() {
    const entry = buildProjectRecapEntry({
      progress: makeProgressFixture(),
      preset: "claude_code",
      nextStep: "Ship grouped open work",
    });
    const prompt = entry.build_prompt("");

    expect(prompt).toContain("1. 目前所在 milestone / 階段");
    expect(prompt).toContain("2. 正在進行的 plans 與 task 結構");
    expect(prompt).toContain("3. blockers、風險與卡點");
    expect(prompt).toContain("4. 建議下一步");
    expect(prompt).toContain("5. 如果需要，直接回答使用者對 task / subtask / plan 的操作問題");
    expect(entry.context_pack.active_plans).toBeTruthy();
    expect(entry.context_pack.requested_next_step).toBe("Ship grouped open work");
    expect(entry.context_pack.open_work_groups).toBeTruthy();
    expect(entry.context_pack.milestones).toBeTruthy();
  });

  it("AC-PPC-08: Given 產品目前無 active plan 或 open work 很少 When 觸發 AI recap Then AI 仍必須回覆當前狀態與下一步建議，不得只回傳「無資料」", async function acPpc08AiRecapHandlesSparseState() {
    const sparseProgress: ProjectProgressResponse = {
      ...makeProgressFixture(),
      active_plans: [],
      open_work_groups: [],
      milestones: [],
      recent_progress: [],
    };

    const fallback = buildFallbackRecap(sparseProgress);
    const entry = buildProjectRecapEntry({
      progress: sparseProgress,
      preset: "codex",
      nextStep: "Review current progress",
    });

    expect(fallback).toContain("0 active plan(s)");
    expect(fallback).not.toContain("無資料");
    expect(entry.build_prompt("")).toContain("still explain the current state and give a concrete next step");
  });

  it("AC-PPC-08A: Given helper 要建立多步驟工作流 When 產品頁 bootstrap Claude Code Then contract 必須要求先建 plan，再用 plan_id 與 plan_order 建 task", async function acPpc08aPlanFirstContract() {
    const entry = buildProjectRecapEntry({
      progress: makeProgressFixture(),
      preset: "claude_code",
      nextStep: "Review current progress",
    });

    expect(entry.claude_code_bootstrap?.execution_contract).toEqual(
      expect.arrayContaining([
        expect.stringContaining("create a real plan first"),
        expect.stringContaining("plan_id and plan_order"),
      ])
    );
  });

  it("AC-PPC-09: Given 使用者已生成 AI recap，並選定下一步方向 When 點擊 copy prompt Then 系統必須提供一份包含 root context、active plans、open work、blockers、AI recap 與下一步目標的可複製 prompt", async function acPpc09CopyPromptContainsContinuationContext() {
    const prompt = buildProjectContinuationPrompt(makeProgressFixture(), {
      preset: "claude_code",
      recap: "This week shipped grouped open work and needs one root-level decision.",
      nextStep: "Resolve API edge case",
    });

    expect(prompt).toContain("Root: ZenOS");
    expect(prompt).toContain("[Active Plans]");
    expect(prompt).toContain("[Open Work]");
    expect(prompt).toContain("[Blockers]");
    expect(prompt).toContain("[AI Recap]");
    expect(prompt).toContain("This week shipped grouped open work");
    expect(prompt).toContain("[Next Step]");
    expect(prompt).toContain("Resolve API edge case");
  });

  it("AC-PPC-10: Given 同一個產品頁面 When 使用者進入產品頁 Then 右欄只保留 task copilot 與 helper 狀態，不再塞 prompt toolbar", async function acPpc10TaskCopilotRailOnly() {
    render(
      <ProjectProgressConsole
        progress={makeProgressFixture()}
        onOpenTasks={() => {}}
      />
    );

    expect(screen.getByTestId("project-recap-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("project-recap-toolbar")).not.toBeInTheDocument();
    expect(screen.queryByText("複製 continuation prompt")).not.toBeInTheDocument();
  });

  it("AC-PPC-11: Given 使用者進入 /projects/[id] When 畫面載入完成 Then 第一層必須先看到 plan / open work / AI copilot，而不是完整 task board", async function acPpc11ProjectPageNotTaskBoardFirstView() {
    const progress = makeProgressFixture();
    getProjectEntitiesMock.mockResolvedValue([progress.project]);
    getProjectProgressMock.mockResolvedValue(progress);
    getTasksByEntityMock.mockResolvedValue([makePageTask()]);
    getEntityContextMock.mockResolvedValue({
      entity: progress.project,
      impact_chain: [],
      reverse_impact_chain: [],
    });
    getChildEntitiesMock.mockResolvedValue([]);
    getAllBlindspotsMock.mockResolvedValue([]);

    const { default: ProjectsPage } = await import("@/app/(protected)/projects/page");
    render(<ProjectsPage />);

    fireEvent.click(await screen.findByRole("button", { name: /ZenOS/ }));

    expect(await screen.findByTestId("project-progress-console")).toBeInTheDocument();
    expect(screen.getByTestId("project-milestone-strip")).toBeInTheDocument();
    expect(screen.getByTestId("project-plans-overview")).toBeInTheDocument();
    expect(screen.getByTestId("project-open-work-panel")).toBeInTheDocument();
    expect(screen.getByTestId("project-recap-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("project-task-board")).not.toBeInTheDocument();
  });

  it("AC-PPC-12: Given 使用者需要操作單張 task 狀態或編輯欄位 When 從產品頁 drill down Then 可以進入 task 層，但 /projects/[id] 本身的主視角不得被 task 操作 UI 取代", async function acPpc12TaskDrillDownWithoutReplacingConsole() {
    const progress = makeProgressFixture();
    getProjectEntitiesMock.mockResolvedValue([progress.project]);
    getProjectProgressMock.mockResolvedValue(progress);
    getTasksByEntityMock.mockResolvedValue([makePageTask()]);
    getEntityContextMock.mockResolvedValue({
      entity: progress.project,
      impact_chain: [],
      reverse_impact_chain: [],
    });
    getChildEntitiesMock.mockResolvedValue([]);
    getAllBlindspotsMock.mockResolvedValue([]);

    const { default: ProjectsPage } = await import("@/app/(protected)/projects/page");
    render(<ProjectsPage />);

    fireEvent.click(await screen.findByRole("button", { name: /ZenOS/ }));
    expect(await screen.findByTestId("project-progress-console")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "查看任務板" }));

    expect(await screen.findByTestId("project-task-board")).toHaveTextContent("Ship console UI");
  });

  it("AC-PPC-13: Given 某產品底下的 open work 連到不同 milestone When 查看產品頁 Then 使用者必須能辨識目前主要工作落在哪個 milestone 或階段，而不是只看到無脈絡的 plan/task", async function acPpc13MilestoneStageVisible() {
    const progress = makeProgressFixture();
    render(
      <ProjectPlansOverview
        plans={progress.active_plans}
        milestones={progress.milestones}
        groups={progress.open_work_groups}
      />
    );

    const groups = screen.getAllByTestId("plan-milestone-group");
    expect(groups).toHaveLength(2);
    expect(within(groups[0]).getAllByText("Console IA").length).toBeGreaterThan(0);
    expect(within(groups[0]).getByText("Launch project progress console")).toBeInTheDocument();
    expect(within(groups[1]).getAllByText("AI rail rollout").length).toBeGreaterThan(0);
    expect(within(groups[1]).getByText("Project AI recap enablement")).toBeInTheDocument();
  });

  it("AC-PPC-14: Given 某產品最近一週有 task 狀態推進、review、handoff 或 plan 更新 When 查看產品頁 Then 應可看到近期推進摘要，而不是只能靠 task 卡片猜測", async function acPpc14RecentProgressSummaryVisible() {
    render(<ProjectRecentProgress items={makeProgressFixture().recent_progress} />);

    expect(screen.getByText("Launch project progress console")).toBeInTheDocument();
    expect(screen.getByText("Ship grouped open work")).toBeInTheDocument();
    expect(screen.getByText("plan · updated")).toBeInTheDocument();
    expect(screen.getByText("task · review")).toBeInTheDocument();
  });

  it("AC-PPC-15: Given 近期推進摘要仍有價值 When 產品頁改成 copilot-first Then recent progress 應保留在主內容區，不佔右欄 AI 視窗", async function acPpc15RecentProgressStaysInMainColumn() {
    render(
      <ProjectProgressConsole
        progress={makeProgressFixture()}
        onOpenTasks={() => {}}
      />
    );

    expect(screen.getAllByText("Launch project progress console").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Ship grouped open work").length).toBeGreaterThan(0);
    expect(screen.getByTestId("project-recap-panel")).toBeInTheDocument();
  });

  it("AC-PPC-16: Given 產品頁主內容很長 When 使用者向下捲動 Then 右側 task copilot 應固定在 viewport 內而不是跟主內容一起滑走", async function acPpc16RecapRailStickyColumn() {
    render(
      <ProjectProgressConsole
        progress={makeProgressFixture()}
        onOpenTasks={() => {}}
      />
    );

    expect(screen.getByTestId("project-recap-rail-column")).toHaveStyle({
      position: "sticky",
      top: "20px",
      alignSelf: "start",
      maxHeight: "calc(100vh - 40px)",
    });
  });
});
