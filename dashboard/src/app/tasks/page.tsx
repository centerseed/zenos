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
import { getTasks, getProjectEntities, getAllPartners } from "@/lib/firestore";
import type { Task, TaskStatus, TaskPriority, Entity, Partner } from "@/types";

type TabKey = "all" | "inbox" | "outbox" | "review";
type ViewMode = "pulse" | "kanban";

const TABS: { key: TabKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "inbox", label: "My Inbox" },
  { key: "outbox", label: "My Outbox" },
  { key: "review", label: "Review" },
];

function TasksPage() {
  const { partner, signOut } = useAuth();
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
    if (!partner) return;

    async function loadPulseData() {
      try {
        const [fetchedTasks, fetchedEntities, fetchedPartners] = await Promise.all([
          getTasks(),
          getProjectEntities(),
          getAllPartners(),
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

    loadPulseData();
  }, [partner]);

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

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* View Mode Toggle */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-white">Tasks</h2>
          <div className="flex items-center rounded-lg overflow-hidden border border-[#1F1F23]">
            <button
              onClick={() => setViewMode("pulse")}
              className={`px-4 py-2 text-sm font-medium cursor-pointer transition-colors ${
                viewMode === "pulse"
                  ? "bg-white text-[#0A0A0B]"
                  : "bg-[#111113] text-[#71717A] hover:bg-[#1F1F23]"
              }`}
            >
              Pulse
            </button>
            <button
              onClick={() => setViewMode("kanban")}
              className={`px-4 py-2 text-sm font-medium cursor-pointer transition-colors ${
                viewMode === "kanban"
                  ? "bg-white text-[#0A0A0B]"
                  : "bg-[#111113] text-[#71717A] hover:bg-[#1F1F23]"
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
              <div className="text-[#71717A] text-sm">Loading pulse data...</div>
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
            <div className="flex items-center gap-1 mb-4 border-b border-[#1F1F23]">
              {TABS.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px cursor-pointer transition-colors ${
                    activeTab === tab.key
                      ? "border-blue-500 text-blue-400"
                      : "border-transparent text-[#71717A] hover:text-white"
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
              <div className="text-[#71717A] text-sm">Loading tasks...</div>
            ) : filteredKanbanTasks.length === 0 ? (
              <div className="text-center py-12 bg-[#111113] rounded-lg border border-[#1F1F23]">
                <p className="text-[#71717A]">
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
