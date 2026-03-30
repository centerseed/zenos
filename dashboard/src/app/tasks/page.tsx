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
import { getTasks, getProjectEntities, getAllEntities } from "@/lib/api";
import { RefreshCw } from "lucide-react";
import type { Task, TaskStatus, TaskPriority, Entity, Partner } from "@/types";

type TabKey = "all" | "inbox" | "outbox" | "review";
type ViewMode = "pulse" | "kanban";

const TABS: { key: TabKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "inbox", label: "My Inbox" },
  { key: "outbox", label: "My Outbox" },
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
  const [viewMode, setViewMode] = useState<ViewMode>("pulse");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [allEntities, setAllEntities] = useState<Entity[]>([]);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>("all");
  const [filterStatuses, setFilterStatuses] = useState<TaskStatus[]>([]);
  const [filterPriority, setFilterPriority] = useState<TaskPriority | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [newTaskCount, setNewTaskCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
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

  const filteredTasks = useMemo(() => {
    let result = tasks;

    if (filterStatuses.length > 0) {
      result = result.filter((t) => filterStatuses.includes(t.status));
    }

    if (filterPriority) {
      result = result.filter((t) => t.priority === filterPriority);
    }

    return result;
  }, [tasks, filterStatuses, filterPriority]);

  return (
    <div className="min-h-screen">
      <AppNav />

      <main id="main-content" className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {/* View Mode Toggle */}
        <div className="flex items-center justify-between mb-6 gap-3">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-foreground">Tasks</h2>

            {/* Refresh Button (P1-3: show after agent creates tasks) */}
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="p-1.5 rounded-lg hover:bg-secondary transition-colors disabled:opacity-50 cursor-pointer relative"
              aria-label="Refresh tasks"
              title="刷新任務列表（Agent 建票後點此查看最新任務）"
            >
              <RefreshCw className={`w-4 h-4 text-muted-foreground ${refreshing ? "animate-spin" : ""}`} />
              {newTaskCount > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-bold flex items-center justify-center animate-bounce">
                  {newTaskCount}
                </span>
              )}
            </button>
          </div>
          <div className="flex items-center rounded-lg overflow-hidden border border-border">
            <button
              onClick={() => setViewMode("pulse")}
              aria-label="Switch to pulse view"
              className={`px-4 py-2 text-sm font-medium cursor-pointer transition-colors ${
                viewMode === "pulse"
                  ? "bg-primary text-primary-foreground"
                  : "bg-card text-muted-foreground hover:bg-secondary"
              }`}
            >
              Pulse
            </button>
            <button
              onClick={() => setViewMode("kanban")}
              aria-label="Switch to kanban view"
              className={`px-4 py-2 text-sm font-medium cursor-pointer transition-colors ${
                viewMode === "kanban"
                  ? "bg-primary text-primary-foreground"
                  : "bg-card text-muted-foreground hover:bg-secondary"
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
            {/* Tabs */}
            <div className="flex items-center gap-1 mb-4 border-b border-border overflow-x-auto">
              {TABS.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  aria-label={`Filter tasks by ${tab.label}`}
                  className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px cursor-pointer transition-colors ${
                    activeTab === tab.key
                      ? "border-blue-500 text-blue-400"
                      : "border-transparent text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Filters */}
            <div className="mb-6">
              <TaskFilters
                selectedStatuses={filterStatuses}
                selectedPriority={filterPriority}
                onStatusChange={setFilterStatuses}
                onPriorityChange={setFilterPriority}
              />
            </div>

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
              />
            )}
          </>
        )}
      </main>
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
