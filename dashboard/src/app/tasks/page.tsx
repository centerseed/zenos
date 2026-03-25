"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
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
import { getTasks, getProjectEntities } from "@/lib/firestore";
import type { Task, TaskStatus, TaskPriority, Entity, Partner } from "@/types";

type TabKey = "all" | "inbox" | "outbox" | "review";
type ViewMode = "pulse" | "kanban";

const TABS: { key: TabKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "inbox", label: "My Inbox" },
  { key: "outbox", label: "My Outbox" },
  { key: "review", label: "Review" },
];
const API_URL = process.env.NEXT_PUBLIC_MCP_API_URL || "https://zenos-mcp-165893875709.asia-east1.run.app";

function TasksPage() {
  const { user, partner, signOut } = useAuth();
  const taskScopePartnerId = partner?.sharedPartnerId ?? partner?.id ?? null;
  const [viewMode, setViewMode] = useState<ViewMode>("pulse");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>("all");
  const [filterStatuses, setFilterStatuses] = useState<TaskStatus[]>([]);
  const [filterPriority, setFilterPriority] = useState<TaskPriority | null>(null);

  // Load all data for Pulse view
  useEffect(() => {
    const currentUser = user;
    if (!partner || !currentUser) return;

    async function loadPulseData(authUser: NonNullable<typeof user>) {
      try {
        const token = await authUser.getIdToken();
        const fetchedPartnersPromise = fetch(`${API_URL}/api/partners`, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        })
          .then(async (res) => {
            if (!res.ok) {
              const body = await res.json().catch(() => ({ message: "Unknown error" }));
              throw new Error(body.message || body.detail || `Failed: ${res.status}`);
            }
            return res.json() as Promise<{ partners?: Partner[] }>;
          })
          .then((body) => (Array.isArray(body.partners) ? body.partners : []));

        const [fetchedTasks, fetchedEntities, fetchedPartners] = await Promise.all([
          getTasks(taskScopePartnerId),
          getProjectEntities(),
          fetchedPartnersPromise,
        ]);
        setTasks(fetchedTasks);
        setEntities(fetchedEntities);
        setPartners(fetchedPartners);
      } catch (err) {
        console.error("Failed to load pulse data:", err);
        setTasks([]);
        setEntities([]);
        setPartners([]);
      }
      setLoading(false);
    }

    loadPulseData(currentUser);
  }, [partner, taskScopePartnerId, user]);

  // Derive kanban tasks from already-loaded tasks (avoids duplicate Firestore fetch)
  const kanbanTasks = useMemo(() => {
    if (!partner) return tasks;
    switch (activeTab) {
      case "inbox":
        return tasks.filter((t) => t.assignee === partner.id);
      case "outbox":
        return tasks.filter((t) => t.createdBy === partner.id);
      case "review":
        return tasks.filter(
          (t) => t.status === "review" && t.createdBy === partner.id && !t.confirmedByCreator
        );
      default:
        return tasks;
    }
  }, [tasks, partner, activeTab]);

  const filteredKanbanTasks = useMemo(() => {
    let result = kanbanTasks;

    if (filterStatuses.length > 0) {
      result = result.filter((t) => filterStatuses.includes(t.status));
    }

    if (filterPriority) {
      result = result.filter((t) => t.priority === filterPriority);
    }

    return result;
  }, [kanbanTasks, filterStatuses, filterPriority]);

  return (
    <div className="min-h-screen">
      <AppNav />

      <main id="main-content" className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {/* View Mode Toggle */}
        <div className="flex items-center justify-between mb-6 gap-3">
          <h2 className="text-lg font-semibold text-foreground">Tasks</h2>
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
            ) : filteredKanbanTasks.length === 0 ? (
              <div className="text-center py-12 bg-card rounded-lg border border-border">
                <p className="text-muted-foreground">
                  No tasks yet. Create tasks via MCP tools in Claude Code.
                </p>
              </div>
            ) : (
              <TaskBoard tasks={filteredKanbanTasks} />
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
