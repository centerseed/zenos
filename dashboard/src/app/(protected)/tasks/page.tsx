"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useInk } from "@/lib/zen-ink/tokens";
import { Section } from "@/components/zen/Section";
import { Btn } from "@/components/zen/Btn";
import { Chip } from "@/components/zen/Chip";
import { ICONS } from "@/components/zen/Icons";
import { TaskBoard } from "@/components/TaskBoard";
import { TaskFilters } from "@/components/TaskFilters";
import { TaskCreateDialog } from "@/components/TaskCreateDialog";
import { TaskHubRecap } from "@/features/tasks/TaskHubRecap";
import { ProductHealthList } from "@/features/tasks/ProductHealthList";
import { MilestonePlanRadar } from "@/features/tasks/MilestonePlanRadar";
import { TaskHubMorningPanel } from "@/features/tasks/TaskHubMorningPanel";
import { TaskHubRail } from "@/features/tasks/TaskHubRail";
import {
  buildProjectFocusHref,
  buildTaskHubSnapshot,
  clearTaskHubNavigationState,
  readTaskHubNavigationState,
  storeTaskHubNavigationState,
  type TaskHubFocus,
  type TaskHubNavigationState,
} from "@/features/tasks/taskHub";
import {
  confirmTask,
  createTask,
  getAllBlindspots,
  getAllEntities,
  getPlans,
  getTasks,
  handoffTask,
  updateTask,
} from "@/lib/api";
import type { PlanSummary } from "@/lib/api";
import type { Blindspot, Entity, Task, TaskPriority, TaskStatus } from "@/types";

type CreateTaskInput = {
  title: string;
  product_id: string;
  description?: string;
  priority?: string;
  assignee?: string;
  due_date?: string;
  project?: string;
  linked_entities?: string[];
  acceptance_criteria?: string[];
  assignee_role_id?: string | null;
  linked_protocol?: string | null;
  linked_blindspot?: string | null;
  blocked_by?: string[];
  blocked_reason?: string | null;
  plan_id?: string | null;
  plan_order?: number | null;
  depends_on_task_ids?: string[];
  parent_task_id?: string | null;
  dispatcher?: string | null;
  source_metadata?: Record<string, unknown>;
};

type ProjectFilterOption = {
  value: string;
  label: string;
};

export function normalizeProjectKey(value: string | null | undefined): string {
  if (!value) return "";
  return value.normalize("NFKC").trim().replace(/\s+/g, " ").toLocaleLowerCase();
}

function resolveTaskProjectLabel(task: Task, entitiesById: Record<string, Entity>): string | null {
  if (task.productId) {
    return entitiesById[task.productId]?.name ?? task.project ?? null;
  }
  return task.project?.trim() || null;
}

export function buildAvailableProjectOptions(tasks: Task[], entities: Entity[]): ProjectFilterOption[] {
  const projects = new Map<string, string>();
  const entitiesById = Object.fromEntries(entities.map((entity) => [entity.id, entity]));

  for (const entity of entities) {
    if (entity.type !== "product" && entity.type !== "company" && entity.type !== "project") continue;
    const label = entity.name?.trim();
    const key = normalizeProjectKey(label);
    if (!key || projects.has(key)) continue;
    projects.set(key, label);
  }

  for (const task of tasks) {
    const label = resolveTaskProjectLabel(task, entitiesById)?.trim();
    if (!label) continue;
    const key = normalizeProjectKey(label);
    if (!key || projects.has(key)) continue;
    projects.set(key, label);
  }

  return Array.from(projects.entries())
    .map(([value, label]) => ({ value, label }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

function EmptyScopePrompt() {
  const t = useInk("light");
  const { c, fontBody, fontMono } = t;

  return (
    <div style={{ padding: "40px 48px 60px", maxWidth: 1600 }}>
      <div
        style={{
          maxWidth: 540,
          background: c.surface,
          border: `1px solid ${c.vermLine}`,
          borderRadius: 2,
          padding: 24,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        <span
          style={{
            fontFamily: fontMono,
            fontSize: 10,
            color: c.vermillion,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
          }}
        >
          Access Scope
        </span>
        <p
          style={{
            margin: 0,
            fontFamily: fontBody,
            fontSize: 13,
            lineHeight: 1.7,
            color: c.ink,
          }}
        >
          您的帳號尚未設定存取空間，請聯繫管理員協助配置 workspace 或授權的知識節點。
        </p>
      </div>
    </div>
  );
}

function LoadingState({ message }: { message: string }) {
  const t = useInk("light");
  const { c, fontMono } = t;

  return (
    <div
      style={{
        padding: "40px 48px 60px",
        minHeight: 360,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <span
        style={{
          fontFamily: fontMono,
          fontSize: 12,
          color: c.inkMuted,
          letterSpacing: "0.12em",
        }}
      >
        {message}
      </span>
    </div>
  );
}

function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  const t = useInk("light");
  const { c, fontBody, fontMono } = t;

  return (
    <div style={{ padding: "40px 48px 60px", maxWidth: 1600 }}>
      <div
        style={{
          maxWidth: 520,
          background: c.surface,
          border: `1px solid ${c.vermLine}`,
          borderRadius: 2,
          padding: 24,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        <span
          style={{
            fontFamily: fontMono,
            fontSize: 10,
            color: c.vermillion,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
          }}
        >
          Tasks Load Failed
        </span>
        <p
          style={{
            margin: 0,
            fontFamily: fontBody,
            fontSize: 13,
            lineHeight: 1.7,
            color: c.ink,
          }}
        >
          {message}
        </p>
        <div>
          <Btn t={t} variant="outline" onClick={onRetry}>
            重試
          </Btn>
        </div>
      </div>
    </div>
  );
}

function isEmptyScopedGuest(
  workspaceRole: string | null | undefined,
  accessMode: string | null | undefined,
  authorizedEntityIds: string[] | undefined,
) {
  return (
    workspaceRole === "guest" &&
    accessMode === "unassigned" &&
    (authorizedEntityIds?.length ?? 0) === 0
  );
}

export function TasksPage() {
  const { user, partner } = useAuth();
  const router = useRouter();
  const t = useInk("light");
  const { c, fontHead, fontMono } = t;

  const [tasks, setTasks] = useState<Task[]>([]);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [blindspots, setBlindspots] = useState<Blindspot[]>([]);
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [selectedStatuses, setSelectedStatuses] = useState<TaskStatus[]>([]);
  const [selectedPriority, setSelectedPriority] = useState<TaskPriority | null>(null);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [selectedDispatcher, setSelectedDispatcher] = useState<string | null>(null);
  const [selectedBlockedMode, setSelectedBlockedMode] = useState<"all" | "blocked" | "unblocked">("all");
  const [hubRailOpen, setHubRailOpen] = useState(false);
  const [pendingNavRestore, setPendingNavRestore] = useState<TaskHubNavigationState | null>(() =>
    readTaskHubNavigationState(),
  );
  const boardSectionRef = useRef<HTMLDivElement | null>(null);

  const fetchData = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const token = await user.getIdToken();
      const [fetchedTasks, fetchedEntities, fetchedBlindspots] = await Promise.all([
        getTasks(token),
        getAllEntities(token),
        getAllBlindspots(token).catch(() => [] as Blindspot[]),
      ]);
      const planIds = Array.from(
        new Set(
          fetchedTasks
            .map((task) => task.planId)
            .filter((planId): planId is string => Boolean(planId?.trim())),
        ),
      );
      const fetchedPlans = planIds.length > 0 ? await getPlans(token, planIds) : [];
      setTasks(fetchedTasks);
      setEntities(fetchedEntities);
      setBlindspots(fetchedBlindspots);
      setPlans(fetchedPlans);
    } catch (err) {
      setError(err instanceof Error ? err.message : "任務載入失敗");
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  const handleAssistantUpdate = useCallback((_recap: string) => {
    void fetchData();
  }, [fetchData]);

  const entityNames = useMemo(
    () => ({
      ...Object.fromEntries(entities.map((entity) => [entity.id, entity.name])),
      ...Object.fromEntries(plans.map((plan) => [plan.id, plan.goal])),
    }),
    [entities, plans],
  );
  const entitiesById = useMemo(
    () => Object.fromEntries(entities.map((entity) => [entity.id, entity])),
    [entities],
  );

  const availableProjects = useMemo(
    () => buildAvailableProjectOptions(tasks, entities),
    [entities, tasks],
  );

  const availableDispatchers = useMemo(() => {
    const set = new Set<string>();
    for (const task of tasks) {
      if (task.dispatcher?.trim()) set.add(task.dispatcher.trim());
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [tasks]);

  const filteredTasks = useMemo(() => {
    return tasks.filter((task) => {
      if (selectedStatuses.length > 0 && !selectedStatuses.includes(task.status)) {
        return false;
      }
      if (selectedPriority && task.priority !== selectedPriority) {
        return false;
      }
      const taskProjectLabel = resolveTaskProjectLabel(task, entitiesById);
      if (selectedProject && normalizeProjectKey(taskProjectLabel) !== selectedProject) {
        return false;
      }
      if (selectedDispatcher && task.dispatcher !== selectedDispatcher) {
        return false;
      }
      const isBlocked = task.blockedBy.length > 0 || Boolean(task.blockedReason);
      if (selectedBlockedMode === "blocked" && !isBlocked) {
        return false;
      }
      if (selectedBlockedMode === "unblocked" && isBlocked) {
        return false;
      }
      return true;
    });
  }, [entitiesById, selectedBlockedMode, selectedDispatcher, selectedPriority, selectedProject, selectedStatuses, tasks]);

  const visibleStatuses = useMemo(
    () => selectedStatuses.filter((status) => status !== "cancelled"),
    [selectedStatuses],
  );
  const taskHubSnapshot = useMemo(
    () => buildTaskHubSnapshot({ entities, tasks, plans }),
    [entities, plans, tasks],
  );

  const totalTasks = filteredTasks.length;
  const reviewCount = filteredTasks.filter((task) => task.status === "review").length;
  const overdueCount = filteredTasks.filter(
    (task) => task.dueDate && task.dueDate.getTime() < Date.now() && task.status !== "done",
  ).length;
  const mineCount = filteredTasks.filter((task) => {
    const selfIds = [partner?.id, partner?.displayName, user?.email].filter(Boolean);
    return selfIds.some((value) => value && (task.assignee === value || task.assigneeName === value));
  }).length;
  const myTasks = filteredTasks.filter((task) => {
    const selfIds = [partner?.id, partner?.displayName, user?.email].filter(Boolean);
    return selfIds.some((value) => value && (task.assignee === value || task.assigneeName === value));
  });
  const myReviewCount = myTasks.filter((task) => task.status === "review").length;
  const myBlockedCount = myTasks.filter((task) => task.blockedBy.length > 0 || Boolean(task.blockedReason)).length;
  const myOverdueCount = myTasks.filter(
    (task) => task.dueDate && task.dueDate.getTime() < Date.now() && task.status !== "done",
  ).length;
  const filterSnapshot = useMemo(() => {
    const next: string[] = [];
    if (selectedStatuses.length > 0) {
      next.push(`Status · ${selectedStatuses.join(", ")}`);
    }
    if (selectedPriority) {
      next.push(`Priority · ${selectedPriority}`);
    }
    if (selectedProject) {
      const current = availableProjects.find((item) => item.value === selectedProject);
      next.push(`Product · ${current?.label ?? selectedProject}`);
    }
    if (selectedDispatcher) {
      next.push(`Dispatcher · ${selectedDispatcher}`);
    }
    if (selectedBlockedMode === "blocked") {
      next.push("Blocked only");
    } else if (selectedBlockedMode === "unblocked") {
      next.push("Unblocked only");
    }
    return next;
  }, [
    availableProjects,
    selectedBlockedMode,
    selectedDispatcher,
    selectedPriority,
    selectedProject,
    selectedStatuses,
  ]);

  const handleCreateTask = useCallback(async (data: CreateTaskInput) => {
    if (!user) return;
    const token = await user.getIdToken();
    const created = await createTask(token, data);
    setTasks((prev) => [created, ...prev]);
  }, [user]);

  const replaceTask = useCallback((nextTask: Task) => {
    setTasks((prev) => prev.map((task) => (task.id === nextTask.id ? nextTask : task)));
  }, []);

  const handleStatusChange = useCallback(async (taskId: string, status: string) => {
    if (!user) return;
    const token = await user.getIdToken();
    const updated = await updateTask(token, taskId, { status });
    replaceTask(updated);
  }, [replaceTask, user]);

  const handleUpdateTask = useCallback(async (taskId: string, updates: Record<string, unknown>) => {
    if (!user) return;
    const token = await user.getIdToken();
    const updated = await updateTask(token, taskId, updates as Parameters<typeof updateTask>[2]);
    replaceTask(updated);
  }, [replaceTask, user]);

  const handleConfirmTask = useCallback(
    async (taskId: string, data: { action: "approve" | "reject"; rejection_reason?: string }) => {
      if (!user) return;
      const token = await user.getIdToken();
      const updated = await confirmTask(token, taskId, data);
      replaceTask(updated);
    },
    [replaceTask, user],
  );

  const handleHandoffTask = useCallback(
    async (taskId: string, data: { to_dispatcher: string; reason: string; output_ref?: string | null; notes?: string | null }) => {
      if (!user) return;
      const token = await user.getIdToken();
      const updated = await handoffTask(token, taskId, data);
      replaceTask(updated);
    },
    [replaceTask, user],
  );

  useEffect(() => {
    if (loading || !pendingNavRestore) return;

    setSelectedStatuses(pendingNavRestore.selectedStatuses);
    setSelectedPriority(pendingNavRestore.selectedPriority);
    setSelectedProject(pendingNavRestore.selectedProject);
    setSelectedDispatcher(pendingNavRestore.selectedDispatcher);
    setSelectedBlockedMode(pendingNavRestore.selectedBlockedMode);
    window.requestAnimationFrame(() => {
      if (typeof window.scrollTo === "function") {
        window.scrollTo({ top: pendingNavRestore.scrollY, behavior: "auto" });
      }
      clearTaskHubNavigationState();
      setPendingNavRestore(null);
    });
  }, [loading, pendingNavRestore]);

  const openExecutionBoard = useCallback(() => {
    boardSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const navigateToProject = useCallback(
    (productId: string, focus?: TaskHubFocus) => {
      storeTaskHubNavigationState({
        selectedStatuses,
        selectedPriority,
        selectedProject,
        selectedDispatcher,
        selectedBlockedMode,
        scrollY: typeof window !== "undefined" ? window.scrollY : 0,
      });
      router.push(buildProjectFocusHref(productId, focus));
    },
    [router, selectedBlockedMode, selectedDispatcher, selectedPriority, selectedProject, selectedStatuses],
  );

  if (isEmptyScopedGuest(partner?.workspaceRole, partner?.accessMode, partner?.authorizedEntityIds)) {
    return <EmptyScopePrompt />;
  }

  if (loading) {
    return <LoadingState message="載入任務…" />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={fetchData} />;
  }

  return (
    <>
      <div style={{ padding: "40px 48px 60px", maxWidth: 1600 }}>
        <Section
          t={t}
          eyebrow="WORK · 任務"
          title="任務中樞"
          en="Task Hub"
          subtitle="先看所有產品的 milestone / plan / risk recap，再往下進到單一產品與執行板。"
          right={
            <div style={{ display: "flex", gap: 10 }}>
              <Btn
                t={t}
                variant="outline"
                icon={ICONS.spark}
                onClick={() => setHubRailOpen(true)}
              >
                Task Copilot
              </Btn>
              <Btn
                t={t}
                variant="ghost"
                icon={ICONS.filter}
                onClick={() => {
                  setSelectedStatuses([]);
                  setSelectedPriority(null);
                  setSelectedProject(null);
                  setSelectedDispatcher(null);
                  setSelectedBlockedMode("all");
                }}
              >
                清空篩選
              </Btn>
              <Btn
                t={t}
                variant="seal"
                icon={ICONS.plus}
                onClick={() => setCreating(true)}
              >
                新任務
              </Btn>
            </div>
          }
        />

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 1.45fr) minmax(320px, 0.8fr)",
            gap: 20,
            alignItems: "start",
            marginBottom: 28,
          }}
        >
          <div style={{ display: "grid", gap: 16 }}>
            <TaskHubRecap snapshot={taskHubSnapshot} onOpenBoard={openExecutionBoard} />
            <TaskHubMorningPanel
              snapshot={taskHubSnapshot}
              mySummary={{
                openCount: mineCount,
                reviewCount: myReviewCount,
                blockedCount: myBlockedCount,
                overdueCount: myOverdueCount,
              }}
              filterSummary={filterSnapshot}
            />
            <ProductHealthList
              snapshot={taskHubSnapshot}
              onOpenProduct={(productId) => navigateToProject(productId)}
              onOpenFocus={navigateToProject}
            />
            <MilestonePlanRadar snapshot={taskHubSnapshot} onOpenFocus={navigateToProject} />
          </div>

          <div
            style={{
              position: "sticky",
              top: 20,
              alignSelf: "start",
            }}
          >
            <TaskHubRail
              snapshot={taskHubSnapshot}
              open={hubRailOpen}
              onOpenChange={setHubRailOpen}
              onAssistantUpdate={handleAssistantUpdate}
            />
          </div>
        </div>

        <div
          ref={boardSectionRef}
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
            gap: 1,
            background: c.inkHair,
            border: `1px solid ${c.inkHair}`,
            marginBottom: 24,
          }}
        >
          {[
            { label: "全部任務", value: String(totalTasks) },
            { label: "待審查", value: String(reviewCount) },
            { label: "逾期", value: String(overdueCount) },
            { label: "我的", value: String(mineCount) },
          ].map((item) => (
            <div key={item.label} style={{ background: c.surface, padding: "14px 16px" }}>
              <div
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  color: c.inkFaint,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  marginBottom: 8,
                }}
              >
                {item.label}
              </div>
              <div
                style={{
                  fontFamily: fontHead,
                  fontSize: 28,
                  fontWeight: 500,
                  color: c.ink,
                }}
              >
                {item.value}
              </div>
            </div>
          ))}
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 16,
            marginBottom: 20,
            flexWrap: "wrap",
          }}
        >
          <div
            style={{
              fontFamily: fontMono,
              fontSize: 10,
              color: c.inkFaint,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
            }}
          >
            Execution Board
          </div>
          <TaskFilters
            selectedStatuses={selectedStatuses}
            selectedPriority={selectedPriority}
            selectedProject={selectedProject}
            selectedDispatcher={selectedDispatcher}
            selectedBlockedMode={selectedBlockedMode}
            availableProjects={availableProjects}
            availableDispatchers={availableDispatchers}
            onStatusChange={setSelectedStatuses}
            onPriorityChange={setSelectedPriority}
            onProjectChange={setSelectedProject}
            onDispatcherChange={setSelectedDispatcher}
            onBlockedModeChange={setSelectedBlockedMode}
          />
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Chip t={t} tone="muted">{`全部 ${totalTasks}`}</Chip>
            <Chip t={t} tone="ocher">{`Review ${reviewCount}`}</Chip>
            <Chip t={t} tone={overdueCount > 0 ? "accent" : "jade"}>{`逾期 ${overdueCount}`}</Chip>
          </div>
        </div>

        {filteredTasks.length === 0 ? (
          <div
            style={{
              background: c.surface,
              border: `1px solid ${c.inkHair}`,
              borderRadius: 2,
              minHeight: 220,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexDirection: "column",
              gap: 10,
            }}
          >
            <span
              style={{
                fontFamily: fontHead,
                fontSize: 22,
                color: c.ink,
                fontWeight: 500,
              }}
            >
              目前沒有符合條件的任務
            </span>
            <span
              style={{
                fontFamily: fontMono,
                fontSize: 11,
                color: c.inkMuted,
                letterSpacing: "0.1em",
              }}
            >
              調整篩選或建立新任務
            </span>
          </div>
        ) : (
          <TaskBoard
            tasks={filteredTasks}
            entityNames={entityNames}
            entitiesById={entitiesById}
            visibleStatuses={visibleStatuses}
            onStatusChange={handleStatusChange}
            onUpdateTask={handleUpdateTask}
            onConfirmTask={handleConfirmTask}
            onHandoffTask={handleHandoffTask}
          />
        )}
      </div>

      <TaskCreateDialog
        isOpen={creating}
        onClose={() => setCreating(false)}
        onCreateTask={handleCreateTask}
        entities={entities}
        blindspots={blindspots}
      />
    </>
  );
}

export default TasksPage;
