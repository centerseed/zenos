"use client";

import { useState, useMemo } from "react";
import type { Entity, Task, TaskStatus } from "@/types";
import { TaskCard } from "./TaskCard";
import { TaskDetailDrawer } from "./TaskDetailDrawer";
import { Layers } from "lucide-react";

interface TaskBoardProps {
  tasks: Task[];
  entityNames?: Record<string, string>;
  entitiesById?: Record<string, Entity>;
  visibleStatuses?: TaskStatus[]; // New prop to support dynamic filtering
}

// Default order: simplified lifecycle
const DEFAULT_COLUMN_ORDER: TaskStatus[] = [
  "todo",
  "in_progress",
  "review",
  "done",
];

const COLUMN_LABELS: Record<string, string> = {
  todo: "TODO",
  in_progress: "IN PROGRESS",
  review: "REVIEW",
  done: "DONE",
};

const COLUMN_HEADER_COLORS: Record<string, string> = {
  todo: "bg-blue-900/50 text-blue-400",
  in_progress: "bg-yellow-900/50 text-yellow-400",
  review: "bg-purple-900/50 text-purple-400",
  done: "bg-green-900/50 text-green-400",
};

export function TaskBoard({
  tasks,
  entityNames = {},
  entitiesById = {},
  visibleStatuses = [],
}: TaskBoardProps) {
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);

  // Use selected statuses from filter, or fall back to default order
  const activeColumns = useMemo(() => {
    if (visibleStatuses.length > 0) {
      return DEFAULT_COLUMN_ORDER.filter(s => visibleStatuses.includes(s));
    }
    return DEFAULT_COLUMN_ORDER;
  }, [visibleStatuses]);

  // Group by status, then by planId within status
  const boardData = useMemo(() => {
    const data: Record<string, { planId: string | null; tasks: Task[] }[]> = {};
    
    for (const status of DEFAULT_COLUMN_ORDER) {
      let statusTasks = tasks.filter(t => t.status === status);
      
      // Sorting logic per column
      if (status === "done") {
        // Done: Recent first
        statusTasks.sort((a, b) => {
          const timeA = a.completedAt?.getTime() || a.updatedAt.getTime();
          const timeB = b.completedAt?.getTime() || b.updatedAt.getTime();
          return timeB - timeA;
        });
      }

      const planGroups: Record<string, Task[]> = {};
      const noPlanTasks: Task[] = [];
      
      for (const t of statusTasks) {
        if (t.planId) {
          if (!planGroups[t.planId]) planGroups[t.planId] = [];
          planGroups[t.planId].push(t);
        } else {
          noPlanTasks.push(t);
        }
      }
      
      const sortedGroups = Object.entries(planGroups).map(([planId, groupTasks]) => ({
        planId,
        tasks: groupTasks.sort((a, b) => (a.planOrder ?? 0) - (b.planOrder ?? 0))
      })).sort((a, b) => a.planId.localeCompare(b.planId));
      
      let finalGroups = [
        ...sortedGroups,
        ...(noPlanTasks.length > 0 ? [{ planId: null, tasks: noPlanTasks.sort((a, b) => {
          if (status === "done") return 0; // Already sorted above
          const pMap: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
          return pMap[a.priority] - pMap[b.priority];
        }) }] : [])
      ];

      // Limit Todo and Done to top 20
      if (status === "todo" || status === "done") {
        let count = 0;
        const limitedGroups = [];
        for (const g of finalGroups) {
          if (count >= 20) break;
          const remaining = 20 - count;
          if (g.tasks.length <= remaining) {
            limitedGroups.push(g);
            count += g.tasks.length;
          } else {
            limitedGroups.push({ ...g, tasks: g.tasks.slice(0, remaining) });
            count = 20;
          }
        }
        finalGroups = limitedGroups;
      }
      
      data[status] = finalGroups;
    }
    return data;
  }, [tasks]);

  return (
    <>
      <div className="flex flex-col md:flex-row gap-5 md:overflow-x-auto pb-6 scrollbar-thin scrollbar-thumb-muted-foreground/20 scrollbar-track-transparent">
        {activeColumns.map((status) => {
          const groups = boardData[status] || [];
          const totalCountInView = groups.reduce((acc, g) => acc + g.tasks.length, 0);
          const totalCountActual = tasks.filter(t => t.status === status).length;
          
          return (
            <div key={status} className="w-full md:flex-shrink-0 md:w-[320px] flex flex-col h-full max-h-[calc(100vh-140px)]">
              <div
                className={`rounded-t-xl px-4 py-3 flex items-center justify-between shadow-sm z-10 ${COLUMN_HEADER_COLORS[status] ?? "bg-secondary text-muted-foreground"}`}
              >
                <span className="text-[11px] font-bold uppercase tracking-widest">
                  {COLUMN_LABELS[status] ?? status}
                  {(status === "todo" || status === "done") && totalCountActual > 20 && (
                    <span className="ml-1 opacity-60 normal-case font-normal text-[9px]">(Top 20)</span>
                  )}
                </span>
                <span className="text-[10px] font-bold rounded-full bg-white/10 px-2 py-0.5 border border-white/5">
                  {totalCountActual}
                </span>
              </div>
              
              <div className="bg-card/40 backdrop-blur-sm rounded-b-xl p-2.5 space-y-4 flex-1 overflow-y-auto border-x border-b border-border/60 shadow-inner min-h-[200px]">
                {totalCountInView === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 opacity-30">
                    <div className="w-10 h-10 rounded-full border-2 border-dashed border-muted-foreground mb-3" />
                    <p className="text-[10px] font-medium uppercase tracking-tighter">No tasks</p>
                  </div>
                ) : (
                  groups.map((group, gIdx) => (
                    <div key={group.planId || `no-plan-${gIdx}`} className="space-y-2">
                      {group.planId && (
                        <div className="flex items-center gap-1.5 px-1 py-1 mb-1">
                          <Layers className="w-3 h-3 text-purple-400" />
                          <span className="text-[10px] font-bold text-purple-400/90 uppercase tracking-tighter truncate max-w-[200px]">
                            Plan: {entityNames[group.planId] || group.planId.slice(-6)}
                          </span>
                          <div className="flex-1 h-[1px] bg-purple-500/20" />
                        </div>
                      )}
                      <div className={`space-y-2.5 ${group.planId ? "pl-1 border-l border-purple-500/20" : ""}`}>
                        {group.tasks.map((task) => (
                          <TaskCard
                            key={task.id}
                            task={task}
                            onSelect={setSelectedTask}
                            entityNames={entityNames}
                          />
                        ))}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>

      <TaskDetailDrawer
        task={selectedTask}
        onClose={() => setSelectedTask(null)}
        entityNames={entityNames}
        entitiesById={entitiesById}
      />
    </>
  );
}
