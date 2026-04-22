"use client";

// ZenOS · Products page — Zen Ink redesign with real data
// Wired to getProjectEntities + getTasksByEntity + getEntityContext + getChildEntities

import { useEffect, useState, useCallback, useMemo } from "react";
import { useInk } from "@/lib/zen-ink/tokens";
import { Icon, ICONS } from "@/components/zen/Icons";
import { Section } from "@/components/zen/Section";
import { Btn } from "@/components/zen/Btn";
import { Chip } from "@/components/zen/Chip";
import { TaskBoard } from "@/components/TaskBoard";
import { TaskCreateDialog } from "@/components/TaskCreateDialog";
import { PlanCreateDialog } from "@/components/PlanCreateDialog";
import { MilestoneCreateDialog } from "@/components/MilestoneCreateDialog";
import { ProjectProgressConsole } from "@/features/projects/ProjectProgressConsole";
import { useAuth } from "@/lib/auth";
import {
  confirmTask,
  createMilestone,
  createPlan,
  createTask,
  getAllBlindspots,
  getProjectEntities,
  getProjectProgress,
  getTasksByEntity,
  getEntityContext,
  getChildEntities,
  handoffTask,
  updateTask,
} from "@/lib/api";
import type { EntityContextResponse, ProjectProgressResponse } from "@/lib/api";
import type { Blindspot, Entity, Task } from "@/types";

// ─── Status → health mapping ──────────────────────────────────────────────────

type HealthTone = "jade" | "accent" | "muted";

interface HealthInfo {
  tone: HealthTone;
  zh: string;
}

function entityStatusToHealth(status: Entity["status"]): HealthInfo {
  switch (status) {
    case "active":
    case "current":
      return { tone: "jade", zh: "順利" };
    case "paused":
      return { tone: "muted", zh: "暫停" };
    case "stale":
    case "conflict":
      return { tone: "accent", zh: "風險" };
    case "completed":
      return { tone: "muted", zh: "完成" };
    case "draft":
    case "planned":
      return { tone: "muted", zh: "規劃中" };
    default:
      return { tone: "muted", zh: "—" };
  }
}

// ─── Task progress helpers ────────────────────────────────────────────────────

interface TaskProgress {
  done: number;
  total: number;
  pct: number;
}

function isPlaceholderCompletedProject(entity: Entity): boolean {
  return (
    entity.type === "product" &&
    entity.status === "completed" &&
    entity.confirmedByUser === false &&
    entity.sources.length === 0
  );
}

type CreateTaskInput = {
  title: string;
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

function computeProgress(tasks: Task[]): TaskProgress {
  const total = tasks.length;
  const done = tasks.filter((t) => t.status === "done").length;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return { done, total, pct };
}

function formatShortDate(date: Date | null | undefined): string {
  if (!date) return "—";
  return date.toLocaleDateString("zh-TW", { month: "2-digit", day: "2-digit" });
}

// ─── Loading state ────────────────────────────────────────────────────────────

function InkSpinner({ message }: { message: string }) {
  const t = useInk("light");
  const { c, fontMono } = t;
  return (
    <div
      style={{
        padding: "40px 48px 48px",
        maxWidth: 1600,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: 400,
        gap: 16,
      }}
    >
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: "50%",
          border: `2px solid ${c.inkHair}`,
          borderTopColor: c.vermillion,
          animation: "spin 0.8s linear infinite",
        }}
      />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <span
        style={{
          fontFamily: fontMono,
          fontSize: 12,
          color: c.inkMuted,
          letterSpacing: "0.1em",
        }}
      >
        {message}
      </span>
    </div>
  );
}

// ─── Error state ──────────────────────────────────────────────────────────────

function InkErrorCard({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  const t = useInk("light");
  const { c, fontMono } = t;
  return (
    <div style={{ padding: "40px 48px 48px", maxWidth: 1600 }}>
      <div
        style={{
          background: c.surface,
          border: `1px solid ${c.vermLine}`,
          borderRadius: 2,
          padding: 24,
          display: "flex",
          flexDirection: "column",
          gap: 12,
          maxWidth: 480,
        }}
      >
        <span
          style={{
            fontFamily: fontMono,
            fontSize: 10,
            color: c.vermillion,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
          }}
        >
          載入失敗
        </span>
        <p style={{ fontSize: 13, color: c.ink, margin: 0, lineHeight: 1.6 }}>
          {message}
        </p>
        <Btn t={t} variant="outline" onClick={onRetry}>
          重試
        </Btn>
      </div>
    </div>
  );
}

// ─── Products List ────────────────────────────────────────────────────────────

interface ProjectWithProgress {
  entity: Entity;
  progress: TaskProgress | null; // null = still loading
}

function InkProjectsList({
  projects,
  onOpen,
}: {
  projects: ProjectWithProgress[];
  onOpen: (id: string) => void;
}) {
  const t = useInk("light");
  const { c, fontHead, fontMono, fontBody } = t;

  // ── KPI strip computation ──────────────────────────────────────────────────

  const activeCount = projects.filter(
    (p) => p.entity.status === "active" || p.entity.status === "current"
  ).length;

  let totalDone = 0;
  let totalTasks = 0;
  let progressReady = true;
  for (const p of projects) {
    if (p.progress === null) {
      progressReady = false;
      break;
    }
    totalDone += p.progress.done;
    totalTasks += p.progress.total;
  }
  const overallPct =
    progressReady && totalTasks > 0
      ? `${Math.round((totalDone / totalTasks) * 100)}%`
      : progressReady
      ? "—"
      : "…";

  const kpiItems = [
    { k: "進行中", v: String(activeCount), sub: "—" },
    { k: "本週到期", v: "—", sub: "—" },
    { k: "整體進度", v: overallPct, sub: "—" },
    { k: "待分派任務", v: "—", sub: "—" },
  ];

  return (
    <div style={{ padding: "40px 48px 60px", maxWidth: 1600 }}>
      <Section
        t={t}
        eyebrow="WORK · 產品"
        title="產品"
        en="Products"
        subtitle="所有進行中的產品主軸與其推進狀態。這一頁對應的是 L1 product，不是 L3 project。"
        right={
          <div style={{ display: "flex", gap: 10 }}>
            <Btn t={t} variant="ghost" icon={ICONS.filter}>
              篩選
            </Btn>
            <Btn t={t} variant="outline" icon={ICONS.spark}>
              Agent 盤點
            </Btn>
            <Btn t={t} variant="seal" icon={ICONS.plus}>
              新產品
            </Btn>
          </div>
        }
      />

      {/* KPI strip */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 1,
          background: c.inkHair,
          border: `1px solid ${c.inkHair}`,
          marginBottom: 28,
        }}
      >
        {kpiItems.map((s, i) => (
          <div key={i} style={{ background: c.surface, padding: "16px 18px" }}>
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
              {s.k}
            </div>
            <div
              style={{
                fontFamily: fontHead,
                fontSize: 28,
                fontWeight: 500,
                color: c.ink,
                letterSpacing: "0.02em",
              }}
            >
              {s.v}
            </div>
            <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 2 }}>
              {s.sub}
            </div>
          </div>
        ))}
      </div>

      {/* Empty state */}
      {projects.length === 0 && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            minHeight: 320,
            gap: 10,
            color: c.inkFaint,
            fontFamily: fontMono,
            fontSize: 13,
            letterSpacing: "0.08em",
          }}
        >
          目前沒有產品
        </div>
      )}

      {/* Project cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gap: 14,
        }}
      >
        {projects.map(({ entity: proj, progress }) => {
          const h = entityStatusToHealth(proj.status);
          const accent = c.vermillion; // product type = vermillion
          const ownerLetter = proj.owner ? proj.owner[0] : "—";
          const pct = progress ? progress.pct : null;
          const doneLabel =
            progress !== null
              ? `${progress.done}/${progress.total}`
              : "…";
          const pctLabel =
            pct !== null ? `${pct}%` : "…";
          const code = proj.id.slice(0, 8).toUpperCase();

          return (
            <button
              key={proj.id}
              onClick={() => onOpen(proj.id)}
              style={{
                padding: 0,
                background: c.surface,
                border: `1px solid ${c.inkHair}`,
                borderRadius: 2,
                textAlign: "left",
                cursor: "pointer",
                fontFamily: fontBody,
                color: c.ink,
                transition: "all .15s",
                overflow: "hidden",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.borderColor =
                  c.inkHairBold;
                (e.currentTarget as HTMLButtonElement).style.background =
                  c.surfaceHi;
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.borderColor =
                  c.inkHair;
                (e.currentTarget as HTMLButtonElement).style.background =
                  c.surface;
              }}
            >
              <div
                style={{
                  padding: "18px 20px 16px",
                  borderLeft: `3px solid ${accent}`,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    justifyContent: "space-between",
                    gap: 14,
                    marginBottom: 10,
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        marginBottom: 6,
                      }}
                    >
                      <span
                        style={{
                          fontFamily: fontMono,
                          fontSize: 10,
                          color: c.inkFaint,
                          letterSpacing: "0.16em",
                        }}
                      >
                        {code}
                      </span>
                      <Chip t={t} tone={h.tone} dot>
                        {h.zh}
                      </Chip>
                    </div>
                    <div
                      style={{
                        fontFamily: fontHead,
                        fontSize: 17,
                        fontWeight: 500,
                        color: c.ink,
                        letterSpacing: "0.02em",
                        lineHeight: 1.35,
                      }}
                    >
                      {proj.name}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: c.inkMuted,
                        marginTop: 6,
                        lineHeight: 1.55,
                      }}
                    >
                      {proj.summary || "—"}
                    </div>
                  </div>
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: "50%",
                      background: c.vermSoft,
                      border: `1px solid ${c.vermLine}`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontFamily: fontHead,
                      fontSize: 12,
                      color: c.vermillion,
                      fontWeight: 500,
                    }}
                  >
                    {ownerLetter}
                  </div>
                </div>

                {/* progress bar */}
                <div style={{ marginTop: 14 }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "baseline",
                      marginBottom: 6,
                    }}
                  >
                    <span
                      style={{
                        fontFamily: fontMono,
                        fontSize: 10,
                        color: c.inkFaint,
                        letterSpacing: "0.12em",
                        textTransform: "uppercase",
                      }}
                    >
                      進度 · {doneLabel}
                    </span>
                    <span
                      style={{
                        fontFamily: fontMono,
                        fontSize: 11,
                        color: c.ink,
                        fontWeight: 500,
                      }}
                    >
                      {pctLabel}
                    </span>
                  </div>
                  <div
                    style={{
                      height: 3,
                      background: c.inkHair,
                      position: "relative",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        position: "absolute",
                        inset: 0,
                        width: pct !== null ? `${pct}%` : "0%",
                        background: accent,
                      }}
                    />
                  </div>
                </div>

                <div
                  style={{
                    marginTop: 14,
                    paddingTop: 12,
                    borderTop: `1px solid ${c.inkHair}`,
                    display: "flex",
                    gap: 18,
                    fontSize: 11,
                    color: c.inkMuted,
                  }}
                >
                  <span>
                    <span style={{ color: c.inkFaint, marginRight: 4 }}>
                      成員
                    </span>
                    —
                  </span>
                  <span>
                    <span style={{ color: c.inkFaint, marginRight: 4 }}>
                      任務
                    </span>
                    {progress !== null ? progress.total : "…"}
                  </span>
                  <span>
                    <span style={{ color: c.inkFaint, marginRight: 4 }}>
                      文件
                    </span>
                    —
                  </span>
                  <span style={{ flex: 1 }} />
                  <span
                    style={{
                      fontFamily: fontMono,
                      color: c.inkMuted,
                      letterSpacing: "0.04em",
                    }}
                  >
                    —
                  </span>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Project Detail ───────────────────────────────────────────────────────────

interface DetailData {
  context: EntityContextResponse | null;
  progress: ProjectProgressResponse;
  tasks: Task[];
  children: Entity[];
  blindspots: Blindspot[];
}

function InkProjectDetail({
  entityId,
  onBack,
}: {
  entityId: string;
  onBack: () => void;
}) {
  const t = useInk("light");
  const { c, fontHead, fontMono, fontBody } = t;
  const { user } = useAuth();
  const [tab, setTab] = useState("overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<DetailData | null>(null);
  const [createKind, setCreateKind] = useState<"task" | "plan" | "milestone" | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [projectRecapOpen, setProjectRecapOpen] = useState(false);

  const fetchDetail = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const token = await user.getIdToken();
      const [context, progress, tasks, children, blindspots] = await Promise.all([
        getEntityContext(token, entityId),
        getProjectProgress(token, entityId),
        getTasksByEntity(token, entityId),
        getChildEntities(token, entityId),
        getAllBlindspots(token).catch(() => [] as Blindspot[]),
      ]);
      setDetail({ context, progress, tasks, children, blindspots });
    } catch (err) {
      console.error("[ProjectDetail] fetch failed:", err);
      setError(err instanceof Error ? err.message : "載入失敗");
    } finally {
      setLoading(false);
    }
  }, [user, entityId]);

  useEffect(() => {
    void fetchDetail();
  }, [fetchDetail]);

  useEffect(() => {
    setTab("overview");
    setCreateKind(null);
    setMutationError(null);
    setProjectRecapOpen(false);
  }, [entityId]);

  const replaceTask = useCallback((nextTask: Task) => {
    setDetail((prev) => {
      if (!prev) return prev;
      const exists = prev.tasks.some((task) => task.id === nextTask.id);
      return {
        ...prev,
        tasks: exists
          ? prev.tasks.map((task) => (task.id === nextTask.id ? nextTask : task))
          : [nextTask, ...prev.tasks],
      };
    });
  }, []);

  const handleAssistantUpdate = useCallback(() => {
    void fetchDetail();
  }, [fetchDetail]);

  const entity = detail?.context?.entity ?? null;
  const progressDetail = detail?.progress ?? null;
  const tasks = detail?.tasks ?? [];
  const children = detail?.children ?? [];
  const blindspots = detail?.blindspots ?? [];
  const progress = computeProgress(tasks);
  const h = entity ? entityStatusToHealth(entity.status) : { tone: "muted" as HealthTone, zh: "—" };
  const accent = c.vermillion;
  const code = entity ? entity.id.slice(0, 8).toUpperCase() : "—";
  const ownerLetter = entity?.owner ? entity.owner[0] : "—";
  const documents = useMemo(
    () => children.filter((child) => child.type === "document"),
    [children],
  );
  const relatedEntities = useMemo(
    () => children.filter((child) => child.type !== "document"),
    [children],
  );
  const entityNames = useMemo(
    () =>
      Object.fromEntries(
        [entity, ...children]
          .filter((value): value is Entity => Boolean(value))
          .map((value) => [value.id, value.name]),
      ),
    [children, entity],
  );
  const entitiesById = useMemo(
    () =>
      Object.fromEntries(
        [entity, ...children]
          .filter((value): value is Entity => Boolean(value))
          .map((value) => [value.id, value]),
      ),
    [children, entity],
  );
  const members = useMemo(() => {
    const seen = new Set<string>();
    const next: Array<{ name: string; role: string }> = [];
    if (entity?.owner) {
      seen.add(entity.owner);
      next.push({ name: entity.owner, role: "Owner" });
    }
    for (const task of tasks) {
      const name = task.assigneeName || task.assignee || task.creatorName || task.createdBy;
      if (!name || seen.has(name)) continue;
      seen.add(name);
      next.push({ name, role: task.assignee ? "Assignee" : "Creator" });
    }
    return next;
  }, [entity, tasks]);
  const timeline = useMemo(() => {
    const taskEvents = tasks.map((task) => ({
      id: `task-${task.id}`,
      title: task.title,
      subtitle: `Task · ${task.status}`,
      date: task.updatedAt,
    }));
    const childEvents = children.map((child) => ({
      id: `entity-${child.id}`,
      title: child.name,
      subtitle: `${child.type} · ${child.status}`,
      date: child.updatedAt,
    }));
    return [...taskEvents, ...childEvents]
      .sort((a, b) => b.date.getTime() - a.date.getTime())
      .slice(0, 8);
  }, [children, tasks]);
  const nearestDueTask = useMemo(() => {
    return tasks
      .filter((task) => task.status !== "done" && task.dueDate)
      .sort((a, b) => (a.dueDate?.getTime() ?? Number.MAX_SAFE_INTEGER) - (b.dueDate?.getTime() ?? Number.MAX_SAFE_INTEGER))[0] ?? null;
  }, [tasks]);

  const handleCreateTask = useCallback(async (data: CreateTaskInput) => {
    if (!user || !entity) return;
    setMutationError(null);
    try {
      const token = await user.getIdToken();
      const created = await createTask(token, {
        ...data,
        project: data.project ?? entity.name,
        linked_entities: Array.from(new Set([entity.id, ...(data.linked_entities ?? [])])),
      });
      replaceTask(created);
      setTab("tasks");
      setCreateKind(null);
    } catch (err) {
      setMutationError(err instanceof Error ? err.message : "建立任務失敗");
      throw err;
    }
  }, [entity, replaceTask, user]);

  const handleCreatePlan = useCallback(async (data: {
    goal: string;
    owner?: string | null;
    entry_criteria?: string | null;
    exit_criteria?: string | null;
    status?: "draft" | "active";
  }) => {
    if (!user || !entity) return;
    setMutationError(null);
    try {
      const token = await user.getIdToken();
      await createPlan(token, {
        ...data,
        project: entity.name,
        project_id: entity.id,
      });
      setCreateKind(null);
      await fetchDetail();
    } catch (err) {
      setMutationError(err instanceof Error ? err.message : "建立 plan 失敗");
      throw err;
    }
  }, [entity, fetchDetail, user]);

  const handleCreateMilestone = useCallback(async (data: {
    name: string;
    summary?: string;
    status?: "planned" | "active";
  }) => {
    if (!user || !entity) return;
    setMutationError(null);
    try {
      const token = await user.getIdToken();
      await createMilestone(token, {
        ...data,
        project_id: entity.id,
        owner: entity.owner ?? null,
      });
      setCreateKind(null);
      await fetchDetail();
    } catch (err) {
      setMutationError(err instanceof Error ? err.message : "建立 milestone 失敗");
      throw err;
    }
  }, [entity, fetchDetail, user]);

  const handleUpdateTask = useCallback(async (taskId: string, updates: Record<string, unknown>) => {
    if (!user) return;
    setMutationError(null);
    try {
      const token = await user.getIdToken();
      const updated = await updateTask(token, taskId, updates as Parameters<typeof updateTask>[2]);
      replaceTask(updated);
    } catch (err) {
      setMutationError(err instanceof Error ? err.message : "更新任務失敗");
      throw err;
    }
  }, [replaceTask, user]);

  const handleStatusChange = useCallback(async (taskId: string, status: string) => {
    await handleUpdateTask(taskId, { status });
  }, [handleUpdateTask]);

  const handleConfirmTask = useCallback(
    async (taskId: string, data: { action: "approve" | "reject"; rejection_reason?: string }) => {
      if (!user) return;
      setMutationError(null);
      try {
        const token = await user.getIdToken();
        const updated = await confirmTask(token, taskId, data);
        replaceTask(updated);
      } catch (err) {
        setMutationError(err instanceof Error ? err.message : "驗收任務失敗");
        throw err;
      }
    },
    [replaceTask, user],
  );

  const handleHandoffTask = useCallback(
    async (taskId: string, data: { to_dispatcher: string; reason: string; output_ref?: string | null; notes?: string | null }) => {
      if (!user) return;
      setMutationError(null);
      try {
        const token = await user.getIdToken();
        const updated = await handoffTask(token, taskId, data);
        replaceTask(updated);
      } catch (err) {
        setMutationError(err instanceof Error ? err.message : "交棒任務失敗");
        throw err;
      }
    },
    [replaceTask, user],
  );

  if (loading) {
    return <InkSpinner message="載入產品資料…" />;
  }

  if (error) {
    return (
      <InkErrorCard
        message={error}
        onRetry={fetchDetail}
      />
    );
  }

  return (
    <>
      <div style={{ padding: "32px 48px 60px", maxWidth: 1600 }}>
        <button
          onClick={onBack}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            background: "transparent",
            border: "none",
            color: c.inkMuted,
            cursor: "pointer",
            fontFamily: fontBody,
            fontSize: 12,
            padding: "4px 8px 4px 0",
            marginBottom: 18,
          }}
        >
          <Icon d="M19 12H5M12 19l-7-7 7-7" size={14} /> 返回產品
        </button>

        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 24,
            marginBottom: 22,
          }}
        >
          <div style={{ flex: 1 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                marginBottom: 8,
              }}
            >
              <span
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  color: c.inkFaint,
                  letterSpacing: "0.2em",
                }}
              >
                PROJECT · {code}
              </span>
              <Chip t={t} tone={h.tone} dot>
                {h.zh}
              </Chip>
            </div>
            <h1
              style={{
                fontFamily: fontHead,
                fontSize: 34,
                fontWeight: 500,
                color: c.ink,
                margin: 0,
                letterSpacing: "0.02em",
              }}
            >
              {entity?.name ?? "—"}
            </h1>
            <p
              style={{
                fontSize: 13,
                color: c.inkMuted,
                margin: "10px 0 0",
                maxWidth: 700,
                lineHeight: 1.7,
              }}
            >
              {entity?.summary || "—"}
            </p>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Btn t={t} variant="ghost" size="sm" icon={ICONS.doc} onClick={() => setTab("docs")}>
              Brief
            </Btn>
            <Btn
              t={t}
              variant="outline"
              size="sm"
              icon={ICONS.spark}
              onClick={() => {
                setTab("overview");
                setProjectRecapOpen(true);
              }}
            >
              Agent 建議
            </Btn>
            <Btn t={t} variant="ghost" size="sm" icon={ICONS.plus} onClick={() => setCreateKind("milestone")}>
              新 Milestone
            </Btn>
            <Btn t={t} variant="outline" size="sm" icon={ICONS.plus} onClick={() => setCreateKind("plan")}>
              新 Plan
            </Btn>
            <Btn t={t} variant="ink" size="sm" icon={ICONS.plus} onClick={() => setCreateKind("task")}>
              新任務
            </Btn>
          </div>
        </div>

        {mutationError ? (
          <div
            style={{
              background: c.surface,
              border: `1px solid ${c.vermLine}`,
              color: c.vermillion,
              padding: "10px 14px",
              marginBottom: 16,
              fontSize: 12,
            }}
          >
            {mutationError}
          </div>
        ) : null}

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr) 2fr",
            gap: 1,
            background: c.inkHair,
            border: `1px solid ${c.inkHair}`,
            marginBottom: 24,
          }}
        >
          {[
            { k: "負責人", v: entity?.owner ?? "—", sub: "—" },
            { k: "任務", v: `${progress.done}/${progress.total}`, sub: `${progress.pct}% 完成` },
            { k: "文件", v: String(documents.length), sub: `${relatedEntities.length} 關聯節點` },
            {
              k: "截止",
              v: nearestDueTask ? formatShortDate(nearestDueTask.dueDate) : "—",
              sub: nearestDueTask ? nearestDueTask.title : "—",
            },
          ].map((item) => (
            <div key={item.k} style={{ background: c.surface, padding: "14px 16px" }}>
              <div
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  color: c.inkFaint,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  marginBottom: 6,
                }}
              >
                {item.k}
              </div>
              <div
                style={{
                  fontFamily: fontHead,
                  fontSize: 20,
                  fontWeight: 500,
                  color: c.ink,
                  letterSpacing: "0.02em",
                }}
              >
                {item.v}
              </div>
              <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 2 }}>
                {item.sub}
              </div>
            </div>
          ))}
          <div
            style={{
              background: c.surface,
              padding: "14px 20px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
            }}
          >
            <div
              style={{
                fontFamily: fontMono,
                fontSize: 10,
                color: c.inkFaint,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                marginBottom: 10,
              }}
            >
              進度軌跡
            </div>
            <div
              style={{
                height: 4,
                background: c.inkHair,
                position: "relative",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  width: `${progress.pct}%`,
                  background: accent,
                }}
              />
            </div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginTop: 6,
              }}
            >
              <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint }}>
                {progress.done} done
              </span>
              <span
                style={{
                  fontFamily: fontHead,
                  fontSize: 13,
                  color: c.ink,
                  fontWeight: 500,
                }}
              >
                {progress.pct}%
              </span>
              <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint }}>
                {progress.total} total
              </span>
            </div>
          </div>
        </div>

        <div
          style={{
            display: "flex",
            gap: 0,
            marginBottom: 20,
            borderBottom: `1px solid ${c.inkHair}`,
          }}
        >
          {(
            [
              ["overview", "總覽"],
              ["tasks", "任務"],
              ["docs", "文件"],
              ["members", "成員"],
              ["timeline", "時程"],
            ] as [string, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              style={{
                padding: "10px 18px",
                background: "transparent",
                border: "none",
                borderBottom:
                  tab === key
                    ? `2px solid ${c.vermillion}`
                    : "2px solid transparent",
                marginBottom: -1,
                cursor: "pointer",
                fontFamily: fontBody,
                fontSize: 13,
                color: tab === key ? c.ink : c.inkMuted,
                fontWeight: tab === key ? 500 : 400,
                letterSpacing: "0.04em",
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "overview" ? (
          progressDetail ? (
            <ProjectProgressConsole
              progress={progressDetail}
              onOpenTasks={() => setTab("tasks")}
              recapRailOpen={projectRecapOpen}
              onRecapRailOpenChange={setProjectRecapOpen}
              onAssistantUpdate={handleAssistantUpdate}
            />
          ) : null
        ) : null}

        {tab === "tasks" ? (
          tasks.length === 0 ? (
            <div
              style={{
                minHeight: 220,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: c.surface,
                border: `1px solid ${c.inkHair}`,
                color: c.inkFaint,
                fontFamily: fontMono,
                letterSpacing: "0.08em",
              }}
            >
              這個產品目前沒有任務
            </div>
          ) : (
            <TaskBoard
              tasks={tasks}
              entityNames={entityNames}
              entitiesById={entitiesById}
              onStatusChange={handleStatusChange}
              onUpdateTask={handleUpdateTask}
              onConfirmTask={handleConfirmTask}
              onHandoffTask={handleHandoffTask}
            />
          )
        ) : null}

        {tab === "docs" ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
              gap: 14,
            }}
          >
            {documents.length === 0 ? (
              <div
                style={{
                  minHeight: 180,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: c.surface,
                  border: `1px solid ${c.inkHair}`,
                  color: c.inkFaint,
                  fontFamily: fontMono,
                }}
              >
                尚未掛上文件
              </div>
            ) : (
              documents.map((doc) => (
                <div
                  key={doc.id}
                  style={{
                    background: c.surface,
                    border: `1px solid ${c.inkHair}`,
                    padding: 18,
                  }}
                >
                  <div style={{ fontSize: 14, color: c.ink, fontWeight: 500 }}>{doc.name}</div>
                  <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 4 }}>
                    {doc.status} · {formatShortDate(doc.updatedAt)}
                  </div>
                  <div style={{ fontSize: 12, color: c.inkMuted, marginTop: 10, lineHeight: 1.6 }}>
                    {doc.summary || "—"}
                  </div>
                </div>
              ))
            )}
          </div>
        ) : null}

        {tab === "members" ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
              gap: 14,
            }}
          >
            {members.length === 0 ? (
              <div
                style={{
                  minHeight: 180,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: c.surface,
                  border: `1px solid ${c.inkHair}`,
                  color: c.inkFaint,
                  fontFamily: fontMono,
                }}
              >
                尚未辨識成員
              </div>
            ) : (
              members.map((member) => (
                <div
                  key={member.name}
                  style={{
                    background: c.surface,
                    border: `1px solid ${c.inkHair}`,
                    padding: 18,
                  }}
                >
                  <div style={{ fontSize: 14, color: c.ink, fontWeight: 500 }}>{member.name}</div>
                  <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 4 }}>{member.role}</div>
                </div>
              ))
            )}
          </div>
        ) : null}

        {tab === "timeline" ? (
          <div
            style={{
              background: c.surface,
              border: `1px solid ${c.inkHair}`,
              padding: 20,
              display: "flex",
              flexDirection: "column",
              gap: 14,
            }}
          >
            {timeline.length === 0 ? (
              <div
                style={{
                  minHeight: 180,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: c.inkFaint,
                  fontFamily: fontMono,
                }}
              >
                尚無近期更新
              </div>
            ) : (
              timeline.map((item) => (
                <div
                  key={item.id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                    paddingBottom: 12,
                    borderBottom: `1px solid ${c.inkHair}`,
                  }}
                >
                  <div>
                    <div style={{ fontSize: 13, color: c.ink, fontWeight: 500 }}>{item.title}</div>
                    <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 3 }}>{item.subtitle}</div>
                  </div>
                  <div
                    style={{
                      fontFamily: fontMono,
                      fontSize: 10,
                      color: c.inkFaint,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {formatShortDate(item.date)}
                  </div>
                </div>
              ))
            )}
          </div>
        ) : null}
      </div>

      <TaskCreateDialog
        isOpen={createKind === "task"}
        onClose={() => setCreateKind(null)}
        onCreateTask={handleCreateTask}
        entities={[entity, ...children].filter((value): value is Entity => Boolean(value))}
        blindspots={blindspots}
      />
      <PlanCreateDialog
        isOpen={createKind === "plan"}
        onClose={() => setCreateKind(null)}
        onCreatePlan={handleCreatePlan}
        defaultOwner={entity?.owner ?? null}
      />
      <MilestoneCreateDialog
        isOpen={createKind === "milestone"}
        onClose={() => setCreateKind(null)}
        onCreateMilestone={handleCreateMilestone}
      />
    </>
  );
}

// ─── Page entry ───────────────────────────────────────────────────────────────

export default function ProjectsPage() {
  const { user } = useAuth();

  const [entities, setEntities] = useState<Entity[]>([]);
  // Map from entityId to TaskProgress (null = not yet loaded)
  const [progressMap, setProgressMap] = useState<
    Map<string, TaskProgress | null>
  >(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [bootstrapNames, setBootstrapNames] = useState<string[]>([]);
  const [bootstrapLoading, setBootstrapLoading] = useState(false);
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);

  const bootstrapPref = partner?.preferences?.homeWorkspaceBootstrap;
  const pendingBootstrapSourceIds = useMemo(
    () =>
      (bootstrapPref?.state === "pending" ? bootstrapPref.sourceEntityIds ?? [] : []).filter(
        (value, index, arr) => Boolean(value) && arr.indexOf(value) === index,
      ),
    [bootstrapPref?.sourceEntityIds, bootstrapPref?.state],
  );
  const showBootstrapBanner =
    activeWorkspace.isHomeWorkspace &&
    pendingBootstrapSourceIds.length > 0 &&
    Boolean(bootstrapPref?.sourceWorkspaceId);

  const readOpenIdFromUrl = useCallback(() => {
    if (typeof window === "undefined") return null;
    const value = new URLSearchParams(window.location.search).get("id");
    return value && value.trim() ? value : null;
  }, []);

  const syncOpenIdFromUrl = useCallback(() => {
    setOpenId(readOpenIdFromUrl());
  }, [readOpenIdFromUrl]);

  const updateOpenId = useCallback((nextId: string | null) => {
    setOpenId(nextId);
    if (typeof window === "undefined") return;

    const url = new URL(window.location.href);
    if (nextId) {
      url.searchParams.set("id", nextId);
      window.history.pushState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
      window.scrollTo({ top: 0, behavior: "auto" });
      return;
    }

    url.searchParams.delete("id");
    window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
    window.scrollTo({ top: 0, behavior: "auto" });
  }, []);

  const fetchProjects = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const token = await user.getIdToken();
      const fetched = await getProjectEntities(token);
      const visibleProjects = fetched.filter((entity) => !isPlaceholderCompletedProject(entity));
      setEntities(visibleProjects);

      // Initialize all progress slots as null (loading)
      const initMap = new Map<string, TaskProgress | null>();
      for (const e of visibleProjects) {
        initMap.set(e.id, null);
      }
      setProgressMap(new Map(initMap));

      // Fetch tasks for each project in parallel; update progress as they resolve
      const taskFetches = visibleProjects.map(async (e) => {
        try {
          const tasks = await getTasksByEntity(token, e.id);
          const prog = computeProgress(tasks);
          setProgressMap((prev) => {
            const next = new Map(prev);
            next.set(e.id, prog);
            return next;
          });
        } catch {
          // On per-entity task fetch failure, show 0/0
          setProgressMap((prev) => {
            const next = new Map(prev);
            next.set(e.id, { done: 0, total: 0, pct: 0 });
            return next;
          });
        }
      });

      // Don't await — let them update progressively
      void Promise.all(taskFetches);
    } catch (err) {
      console.error("[ProjectsPage] fetch failed:", err);
      setError(err instanceof Error ? err.message : "載入失敗");
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    if (!user || !showBootstrapBanner || !bootstrapPref?.sourceWorkspaceId) {
      setBootstrapNames([]);
      setBootstrapError(null);
      return;
    }

    let cancelled = false;
    const loadBootstrapNames = async () => {
      try {
        const token = await user.getIdToken();
        const products = await getProjectEntitiesInWorkspace(token, bootstrapPref.sourceWorkspaceId!);
        const names = pendingBootstrapSourceIds
          .map((entityId) => products.find((entity) => entity.id === entityId)?.name)
          .filter((value): value is string => Boolean(value));
        if (!cancelled) {
          setBootstrapNames(names);
        }
      } catch (err) {
        console.error("[ProjectsPage] failed to load bootstrap sources:", err);
        if (!cancelled) {
          setBootstrapError("待匯入來源暫時無法讀取，請稍後再試。");
          setBootstrapNames([]);
        }
      }
    };

    setBootstrapError(null);
    void loadBootstrapNames();
    return () => {
      cancelled = true;
    };
  }, [
    bootstrapPref?.sourceWorkspaceId,
    pendingBootstrapSourceIds,
    showBootstrapBanner,
    user,
  ]);

  useEffect(() => {
    syncOpenIdFromUrl();
    if (typeof window === "undefined") return;
    window.addEventListener("popstate", syncOpenIdFromUrl);
    return () => window.removeEventListener("popstate", syncOpenIdFromUrl);
  }, [syncOpenIdFromUrl]);

  if (loading) {
    return <InkSpinner message="載入產品…" />;
  }

  if (error) {
    return <InkErrorCard message={error} onRetry={fetchProjects} />;
  }

  if (openId) {
    return (
      <InkProjectDetail
        entityId={openId}
        onBack={() => updateOpenId(null)}
      />
    );
  }

  const projects: ProjectWithProgress[] = entities.map((e) => ({
    entity: e,
    progress: progressMap.get(e.id) ?? null,
  }));

  const handleApplyBootstrap = async () => {
    if (!user) return;
    setBootstrapLoading(true);
    setBootstrapError(null);
    try {
      const token = await user.getIdToken();
      await applyHomeWorkspaceBootstrap(token);
      await refetchPartner();
      await fetchProjects();
    } catch (err) {
      console.error("[ProjectsPage] bootstrap apply failed:", err);
      setBootstrapError(err instanceof Error ? err.message : "匯入失敗");
    } finally {
      setBootstrapLoading(false);
    }
  };

  return (
    <InkProjectsList
      projects={projects}
      bootstrapBanner={
        showBootstrapBanner ? (
          <HomeWorkspaceBootstrapBanner
            productNames={bootstrapNames.length > 0 ? bootstrapNames : pendingBootstrapSourceIds}
            loading={bootstrapLoading}
            error={bootstrapError}
            onApply={handleApplyBootstrap}
          />
        ) : undefined
      }
      onOpen={updateOpenId}
    />
  );
}
