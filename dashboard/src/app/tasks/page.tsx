"use client";

import { useEffect, useState, useMemo, useCallback, useRef } from "react";
import { useAuth } from "@/lib/auth";
import { AuthGuard } from "@/components/AuthGuard";
import { AppNav } from "@/components/AppNav";
import { TaskBoard } from "@/components/TaskBoard";
import { TaskFilters } from "@/components/TaskFilters";
import { PulseBar } from "@/components/PulseBar";
import { ProjectProgress } from "@/components/ProjectProgress";
import { PeopleMatrix } from "@/components/PeopleMatrix";
import { ActivityTimeline } from "@/components/ActivityTimeline";
import { LoadingState } from "@/components/LoadingState";
import { getTasks, getProjectEntities, getAllEntities, createTask, updateTask, confirmTask } from "@/lib/api";
import { RefreshCw, Plus } from "lucide-react";
import type { Task, TaskStatus, TaskPriority, Entity, Partner } from "@/types";
import { TaskCreateDialog } from "@/components/TaskCreateDialog";

type TabKey = "all" | "inbox" | "outbox" | "review";
type ViewMode = "pulse" | "kanban";

const TABS: { key: TabKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "inbox", label: "Inbox" },
  { key: "outbox", label: "Outbox" },
  { key: "review", label: "Review" },
];

const API_URL =
  process.env.NEXT_PUBLIC_MCP_API_URL ||
  "https://zenos-mcp-165893875709.asia-east1.run.app";

/** Build server-side filter params for a kanban tab. */
function tabFilters(
  tab: TabKey,
  partnerId: string
): Parameters<typeof getTasks>[1] {
  switch (tab) {
    case "inbox":
      return { assignee: partnerId };
    case "outbox":
      return { createdBy: partnerId };
    case "review":
      return { statuses: ["review"] };
    default:
      return undefined;
  }
}

function TasksPage() {
  const { user, partner } = useAuth();
  const [viewMode, setViewMode] = useState<ViewMode>("kanban");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [allEntities, setAllEntities] = useState<Entity[]>([]);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>("all");
  const [filterStatuses, setFilterStatuses] = useState<TaskStatus[]>([]);
  const [filterPriority, setFilterPriority] = useState<TaskPriority | null>(null);
  const [filterProject, setFilterProject] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [newTaskCount, setNewTaskCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const prevTaskIdsRef = useRef<Set<string>>(new Set());

  // Initial load: all tasks + entities + partners list
  useEffect(() => {
    if (!user || !partner) return;

    async function loadData() {
      try {
        const token = await user!.getIdToken();

        const fetchedPartnersPromise = fetch(`${API_URL}/api/partners`, {
          headers: { Authorization: `Bearer ${token}` },
        })
          .then(async (res) => {
            if (!res.ok) {
              const body = await res
                .json()
                .catch(() => ({ message: "Unknown error" }));
              throw new Error(
                body.message || body.detail || `Failed: ${res.status}`
              );
            }
            return res.json() as Promise<{ partners?: Partner[] }>;
          })
          .then((body) => (Array.isArray(body.partners) ? body.partners : []));

        const [fetchedTasks, fetchedEntities, fetchedPartners, fetchedAllEntities] =
          await Promise.all([
            getTasks(token),
            getProjectEntities(token),
            fetchedPartnersPromise,
            getAllEntities(token),
          ]);

        setTasks(fetchedTasks);
        setEntities(fetchedEntities);
        setAllEntities(fetchedAllEntities);
        setPartners(fetchedPartners);
      } catch (err) {
        console.error("Failed to load data:", err);
        setTasks([]);
        setEntities([]);
        setPartners([]);
        setError(err instanceof Error ? err.message : "載入失敗");
      }
      setLoading(false);
    }

    loadData();
  }, [user, partner]);

  // Track new tasks (for agent-created notification)
  useEffect(() => {
    if (tasks.length === 0) return;
    const currentIds = new Set(tasks.map((t) => t.id));
    if (prevTaskIdsRef.current.size > 0) {
      let count = 0;
      for (const id of currentIds) {
        if (!prevTaskIdsRef.current.has(id)) count++;
      }
      if (count > 0) setNewTaskCount(count);
    }
    prevTaskIdsRef.current = currentIds;
  }, [tasks]);

  // Manual refresh (for agent-created tasks)
  const handleRefresh = useCallback(async () => {
    if (!user || !partner) return;
    setRefreshing(true);
    setError(null);
    try {
      const token = await user.getIdToken();
      const filters = viewMode === "kanban" ? tabFilters(activeTab, partner.id) : undefined;
      const [fetchedTasks, fetchedAllEntities] = await Promise.all([
        getTasks(token, filters),
        getAllEntities(token),
      ]);
      setTasks(fetchedTasks);
      setAllEntities(fetchedAllEntities);
    } catch (err) {
      console.error("Failed to refresh:", err);
      setError(err instanceof Error ? err.message : "刷新失敗");
    }
    setRefreshing(false);
    setTimeout(() => setNewTaskCount(0), 3000);
  }, [user, partner, viewMode, activeTab]);

  // Re-fetch tasks when kanban tab changes (server-side scoping)
  useEffect(() => {
    if (viewMode !== "kanban" || !user || !partner) return;

    async function loadTabTasks() {
      setLoading(true);
      try {
        const token = await user!.getIdToken();
        const filters = tabFilters(activeTab, partner!.id);
        const fetched = await getTasks(token, filters);
        setTasks(fetched);
      } catch (err) {
        console.error("Failed to load tab tasks:", err);
        setTasks([]);
      }
      setLoading(false);
    }

    loadTabTasks();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, viewMode]);

  // Build partner name lookup for legacy ID strings
  const partnerNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const p of partners) {
      map[p.id] = p.displayName;
      map[p.displayName.toLowerCase()] = p.displayName;
    }
    if (!map["pm"]) map["pm"] = "PM";
    return map;
  }, [partners]);

  // Build entity name lookup for rich card tags
  const entityNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const e of allEntities) {
      map[e.id] = e.name;
    }
    return map;
  }, [allEntities]);

  const entitiesById = useMemo(() => {
    const map: Record<string, Entity> = {};
    for (const e of allEntities) {
      map[e.id] = e;
    }
    return map;
  }, [allEntities]);

  const availableProjects = useMemo(() => {
    const projects = new Set<string>();
    for (const t of tasks) {
      if (t.project) projects.add(t.project);
    }
    return Array.from(projects).sort();
  }, [tasks]);

  // ─── Mutation handlers ────────────────────────────────────────────────────

  const handleCreateTask = useCallback(async (data: {
    title: string;
    description?: string;
    priority?: string;
    assignee?: string;
    due_date?: string;
    project?: string;
  }) => {
    if (!user) throw new Error("未登入");
    const token = await user.getIdToken();
    const newTask = await createTask(token, data);
    setTasks(prev => [newTask, ...prev]);
  }, [user]);

  const handleUpdateTask = useCallback(async (taskId: string, updates: Record<string, unknown>) => {
    if (!user) throw new Error("未登入");
    // Optimistic update
    setTasks(prev => prev.map(t => t.id === taskId ? { ...t, ...updates } as Task : t));
    try {
      const token = await user.getIdToken();
      const updated = await updateTask(token, taskId, updates as Parameters<typeof updateTask>[2]);
      setTasks(prev => prev.map(t => t.id === taskId ? updated : t));
    } catch (err) {
      // Rollback: re-fetch just that task's state by refreshing
      console.error("Failed to update task:", err);
      throw err;
    }
  }, [user]);

  const handleConfirmTask = useCallback(async (taskId: string, data: { action: "approve" | "reject"; rejection_reason?: string }) => {
    if (!user) throw new Error("未登入");
    const token = await user.getIdToken();
    const updated = await confirmTask(token, taskId, data);
    setTasks(prev => prev.map(t => t.id === taskId ? updated : t));
  }, [user]);

  const handleStatusChange = useCallback(async (taskId: string, newStatus: string) => {
    await handleUpdateTask(taskId, { status: newStatus });
  }, [handleUpdateTask]);

  const filteredTasks = useMemo(() => {
    if (!tasks) return [];
    
    return tasks.map(t => {
      const cId = t.createdBy?.toLowerCase();
      const aId = t.assignee?.toLowerCase();
      const actorPartnerId = (t.sourceMetadata?.actor_partner_id as string | undefined)?.toLowerCase();
      const createdByLooksLikePartnerId = Boolean(cId && /^[0-9a-f]{32}$/.test(cId));
      const createdViaAgent =
        t.sourceMetadata?.created_via_agent !== undefined
          ? Boolean(t.sourceMetadata?.created_via_agent)
          : !createdByLooksLikePartnerId;
      const rawAgentName =
        typeof t.sourceMetadata?.agent_name === "string"
          ? t.sourceMetadata.agent_name.trim()
          : "";
      const normalizedAgentName = rawAgentName
        ? rawAgentName.replace(/-agent$/i, "")
        : "agent";
      
      const ownerName =
        (actorPartnerId ? partnerNames[actorPartnerId] : null) ||
        (createdByLooksLikePartnerId && cId ? partnerNames[cId] : null) ||
        (partner?.displayName || null) ||
        t.creatorName ||
        t.createdBy;
      const cName = createdViaAgent
        ? `${normalizedAgentName}(by ${ownerName})`
        : ownerName;
      const aName = t.assigneeName || (aId ? partnerNames[aId] : null) || t.assignee;
      
      return {
        ...t,
        creatorName: cName,
        assigneeName: aName
      };
    })
    .filter(t => {
      if (filterStatuses.length > 0 && !filterStatuses.includes(t.status)) return false;
      if (filterPriority && t.priority !== filterPriority) return false;
      if (filterProject && t.project !== filterProject) return false;
      return true;
    });
  }, [tasks, partnerNames, filterStatuses, filterPriority, filterProject, partner?.displayName]);

  return (
    <div className="min-h-screen">
      <AppNav />

      <main id="main-content" className={`mx-auto px-4 sm:px-6 py-4 transition-all duration-300 ${viewMode === "kanban" ? "max-w-[1600px]" : "max-w-7xl"}`}>
        
        {/* Compressed Single Line Header */}
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 mb-6 bg-card/20 p-2 rounded-xl border border-border/40 backdrop-blur-sm">
          
          <div className="flex items-center gap-4">
            {/* New Task Button */}
            <button
              onClick={() => setShowCreateDialog(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              新增任務
            </button>

            {/* Refresh Button */}
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="p-2 rounded-lg hover:bg-secondary transition-colors disabled:opacity-50 cursor-pointer relative group border border-border/50"
              aria-label="Refresh tasks"
            >
              <RefreshCw className={`w-4 h-4 text-muted-foreground group-hover:text-foreground ${refreshing ? "animate-spin" : ""}`} />
              {newTaskCount > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-bold flex items-center justify-center animate-bounce">
                  {newTaskCount}
                </span>
              )}
            </button>

            {/* Tabs - Now in the same line */}
            <div className="flex items-center bg-background/50 rounded-lg p-1 border border-border/50">
              {TABS.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`px-3 py-1 text-xs font-bold rounded-md transition-all duration-200 cursor-pointer uppercase tracking-tighter ${
                    activeTab === tab.key
                      ? "bg-blue-600 text-white shadow-sm"
                      : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Filters - Now in the same line */}
          <div className="flex-1 flex items-center justify-center">
            <TaskFilters
              selectedStatuses={filterStatuses}
              selectedPriority={filterPriority}
              selectedProject={filterProject}
              availableProjects={availableProjects}
              onStatusChange={setFilterStatuses}
              onPriorityChange={setFilterPriority}
              onProjectChange={setFilterProject}
            />
          </div>

          {/* View Toggle */}
          <div className="flex items-center rounded-lg overflow-hidden border border-border/50 p-1 bg-background/50">
            <button
              onClick={() => setViewMode("pulse")}
              className={`px-3 py-1 text-xs font-bold rounded-md cursor-pointer transition-all ${
                viewMode === "pulse"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-secondary"
              }`}
            >
              Pulse
            </button>
            <button
              onClick={() => setViewMode("kanban")}
              className={`px-3 py-1 text-xs font-bold rounded-md cursor-pointer transition-all ${
                viewMode === "kanban"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-secondary"
              }`}
            >
              Kanban
            </button>
          </div>
        </div>

        {/* Pulse View */}
        {viewMode === "pulse" && (
          <>
            {loading ? (
              <LoadingState label="Loading pulse data..." />
            ) : (
              <div className="space-y-6">
                <PulseBar tasks={tasks} />
                <ProjectProgress tasks={tasks} entities={entities} />
                <PeopleMatrix tasks={tasks} entities={entities} partners={partners} />
                <ActivityTimeline tasks={tasks} partners={partners} entities={entities} />
              </div>
            )}
          </>
        )}

        {/* Kanban View */}
        {viewMode === "kanban" && (
          <>
            {/* Board */}
            {loading ? (
              <LoadingState label="Loading tasks..." />
            ) : error ? (
              <div className="text-center py-12 bg-card rounded-lg border border-red-900/30">
                <p className="text-red-400 mb-3">{error}</p>
                <button
                  onClick={handleRefresh}
                  className="text-sm text-blue-400 hover:text-blue-300 underline cursor-pointer"
                >
                  重試
                </button>
              </div>
            ) : filteredTasks.length === 0 && tasks.length > 0 ? (
              <div className="text-center py-12 bg-card rounded-lg border border-border">
                <p className="text-muted-foreground">
                  目前篩選無結果。嘗試調整篩選條件。
                </p>
              </div>
            ) : filteredTasks.length === 0 ? (
              <div className="text-center py-12 bg-card rounded-lg border border-border">
                <p className="text-muted-foreground">
                  尚無任務。透過 MCP tools 或 Agent 建立任務。
                </p>
              </div>
            ) : (
              <TaskBoard
                tasks={filteredTasks}
                entityNames={entityNames}
                entitiesById={entitiesById}
                visibleStatuses={filterStatuses}
                onStatusChange={handleStatusChange}
                onUpdateTask={handleUpdateTask}
                onConfirmTask={handleConfirmTask}
              />
            )}
          </>
        )}
      </main>

      <TaskCreateDialog
        isOpen={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
        onCreateTask={handleCreateTask}
      />
    </div>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <TasksPage />
    </AuthGuard>
  );
}
