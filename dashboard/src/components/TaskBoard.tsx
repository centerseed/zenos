"use client";

import { useState, useMemo } from "react";
import type { Entity, Task, TaskStatus } from "@/types";
import { TaskCard } from "./TaskCard";
import { TaskDetailDrawer } from "./TaskDetailDrawer";
import { Layers, AlertTriangle } from "lucide-react";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
  useDraggable,
} from "@dnd-kit/core";

interface TaskBoardProps {
  tasks: Task[];
  entityNames?: Record<string, string>;
  entitiesById?: Record<string, Entity>;
  visibleStatuses?: TaskStatus[];
  selectedTask?: Task | null;
  onSelectTask?: (task: Task | null) => void;
  onStatusChange?: (taskId: string, newStatus: string) => Promise<void>;
  onUpdateTask?: (taskId: string, updates: Record<string, unknown>) => Promise<void>;
  onConfirmTask?: (taskId: string, data: { action: "approve" | "reject"; rejection_reason?: string }) => Promise<void>;
}

const DEFAULT_COLUMN_ORDER: TaskStatus[] = [
  "todo",
  "in_progress",
  "review",
  "done",
];

const COLUMN_LABELS: Record<string, string> = {
  todo: "待處理",
  in_progress: "進行中",
  review: "審查中",
  done: "已完成",
};

const COLUMN_HEADER_COLORS: Record<string, string> = {
  todo: "bg-blue-900/50 text-blue-400",
  in_progress: "bg-yellow-900/50 text-yellow-400",
  review: "bg-purple-900/50 text-purple-400",
  done: "bg-green-900/50 text-green-400",
};

// ─── DraggableTaskCard ────────────────────────────────────────────────────────

function DraggableTaskCard({
  task,
  onSelect,
  entityNames,
}: {
  task: Task;
  onSelect: (t: Task) => void;
  entityNames: Record<string, string>;
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: task.id,
    data: { task },
  });

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className={`cursor-grab active:cursor-grabbing ${isDragging ? "opacity-40" : ""}`}
    >
      <TaskCard
        task={task}
        onSelect={onSelect}
        entityNames={entityNames}
      />
    </div>
  );
}

// ─── DroppableColumn ──────────────────────────────────────────────────────────

function DroppableColumn({
  status,
  children,
  isEmpty,
}: {
  status: string;
  children: React.ReactNode;
  isEmpty: boolean;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status });

  return (
    <div
      ref={setNodeRef}
      className={`bg-card/40 backdrop-blur-sm rounded-b-xl p-2.5 space-y-4 flex-1 overflow-y-auto border-x border-b border-border/60 shadow-inner min-h-[200px] transition-all ${
        isOver ? "ring-2 ring-primary/40 bg-primary/5" : ""
      }`}
    >
      {isEmpty ? (
        <div className={`flex flex-col items-center justify-center py-12 transition-opacity ${isOver ? "opacity-60" : "opacity-30"}`}>
          <div className={`w-10 h-10 rounded-full border-2 border-dashed mb-3 ${isOver ? "border-primary/60" : "border-muted-foreground"}`} />
          <p className="text-[10px] font-medium tracking-tight">目前沒有任務</p>
        </div>
      ) : children}
    </div>
  );
}

// ─── TaskBoard ────────────────────────────────────────────────────────────────

export function TaskBoard({
  tasks,
  entityNames = {},
  entitiesById = {},
  visibleStatuses = [],
  selectedTask: controlledSelectedTask,
  onSelectTask,
  onStatusChange,
  onUpdateTask,
  onConfirmTask,
}: TaskBoardProps) {
  const [internalSelectedTask, setInternalSelectedTask] = useState<Task | null>(null);
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  // Warning dialog for bad status jumps
  const [pendingDrag, setPendingDrag] = useState<{ taskId: string; newStatus: string } | null>(null);
  const [dragWarning, setDragWarning] = useState<string | null>(null);

  const selectedTask = controlledSelectedTask !== undefined ? controlledSelectedTask : internalSelectedTask;
  const setSelectedTask = (task: Task | null) => {
    if (onSelectTask) {
      onSelectTask(task);
      return;
    }
    setInternalSelectedTask(task);
  };

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

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

      if (status === "done") {
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
        tasks: groupTasks.sort((a, b) => (a.planOrder ?? 0) - (b.planOrder ?? 0)),
      })).sort((a, b) => a.planId.localeCompare(b.planId));

      let finalGroups = [
        ...sortedGroups,
        ...(noPlanTasks.length > 0 ? [{ planId: null, tasks: noPlanTasks.sort((a, b) => {
          if (status === "done") return 0;
          const pMap: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
          return pMap[a.priority] - pMap[b.priority];
        }) }] : []),
      ];

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

  function handleDragStart(event: DragStartEvent) {
    const task = event.active.data.current?.task as Task | undefined;
    if (task) setActiveTask(task);
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveTask(null);
    const { active, over } = event;
    if (!over || !onStatusChange) return;

    const taskId = active.id as string;
    const newStatus = over.id as string;
    const task = tasks.find(t => t.id === taskId);
    if (!task || task.status === newStatus) return;

    // Warning: todo → done (skipping stages)
    if (task.status === "todo" && newStatus === "done") {
      setDragWarning("建議先經過 in_progress 和 review，確定要直接完成？");
      setPendingDrag({ taskId, newStatus });
      return;
    }
    // Warning: moving to review with no result
    if (newStatus === "review" && !task.result) {
      setDragWarning("建議填寫任務成果後再送審，確定要送審？");
      setPendingDrag({ taskId, newStatus });
      return;
    }

    onStatusChange(taskId, newStatus);
  }

  function confirmDrag() {
    if (!pendingDrag || !onStatusChange) return;
    onStatusChange(pendingDrag.taskId, pendingDrag.newStatus);
    setPendingDrag(null);
    setDragWarning(null);
  }

  // Update selected task when tasks array changes (after optimistic update)
  const selectedTaskUpToDate = useMemo(() => {
    if (!selectedTask) return null;
    return tasks.find(t => t.id === selectedTask.id) ?? selectedTask;
  }, [selectedTask, tasks]);

  return (
    <>
      <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
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

                <DroppableColumn status={status} isEmpty={totalCountInView === 0}>
                  {groups.map((group, gIdx) => (
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
                          <DraggableTaskCard
                            key={task.id}
                            task={task}
                            onSelect={setSelectedTask}
                            entityNames={entityNames}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                </DroppableColumn>
              </div>
            );
          })}
        </div>

        <DragOverlay>
          {activeTask && (
            <div className="opacity-80 rotate-1 scale-[1.03] shadow-2xl">
              <TaskCard
                task={activeTask}
                onSelect={() => {}}
                entityNames={entityNames}
              />
            </div>
          )}
        </DragOverlay>
      </DndContext>

      {/* Drag warning dialog */}
      {dragWarning && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-card border border-border rounded-2xl p-6 mx-4 max-w-sm w-full space-y-4 shadow-2xl">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-foreground">{dragWarning}</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={confirmDrag}
                className="flex-1 px-3 py-2 text-xs font-bold bg-yellow-600 text-white rounded-lg hover:bg-yellow-700"
              >
                強制執行
              </button>
              <button
                onClick={() => { setPendingDrag(null); setDragWarning(null); }}
                className="flex-1 px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground rounded-lg hover:bg-secondary"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      <TaskDetailDrawer
        task={selectedTaskUpToDate}
        onClose={() => setSelectedTask(null)}
        entityNames={entityNames}
        entitiesById={entitiesById}
        onUpdateTask={onUpdateTask}
        onConfirmTask={onConfirmTask}
      />
    </>
  );
}
