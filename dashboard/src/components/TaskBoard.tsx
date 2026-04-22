"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import type { Entity, Task, TaskStatus } from "@/types";
import { useInk } from "@/lib/zen-ink/tokens";
import { TaskCard } from "./TaskCard";
import { TaskDetailDrawer } from "./TaskDetailDrawer";
import { Dialog } from "@/components/zen/Dialog";
import { Btn } from "@/components/zen/Btn";
import { Divider } from "@/components/zen/Divider";
import { InkMark } from "@/components/zen/InkMark";
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
  onHandoffTask?: (
    taskId: string,
    data: { to_dispatcher: string; reason: string; output_ref?: string | null; notes?: string | null }
  ) => Promise<void>;
}

const DEFAULT_COLUMN_ORDER: TaskStatus[] = ["todo", "in_progress", "review", "done"];

const COLUMN_LABELS: Record<string, string> = {
  todo: "待處理",
  in_progress: "進行中",
  review: "審查中",
  done: "已完成",
};

// Status → Chip-like dot colour for column header indicator
function statusDotColor(status: string, vermillion: string, jade: string, ocher: string, inkFaint: string): string {
  if (status === "done") return jade;
  if (status === "in_progress") return ocher;
  if (status === "review") return vermillion;
  return inkFaint;
}

// ─── DraggableTaskCard ────────────────────────────────────────────────────────

function DraggableTaskCard({
  task,
  onSelect,
  entityNames,
  shouldSuppressSelection,
}: {
  task: Task;
  onSelect: (t: Task) => void;
  entityNames: Record<string, string>;
  shouldSuppressSelection: () => boolean;
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: task.id,
    data: { task },
  });

  const handleSelect = React.useCallback(
    (nextTask: Task) => {
      if (shouldSuppressSelection()) return;
      onSelect(nextTask);
    },
    [onSelect, shouldSuppressSelection]
  );

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      onClickCapture={(event) => {
        if (!shouldSuppressSelection()) return;
        event.preventDefault();
        event.stopPropagation();
      }}
      onPointerUpCapture={(event) => {
        if (!shouldSuppressSelection()) return;
        event.preventDefault();
        event.stopPropagation();
      }}
      onMouseUpCapture={(event) => {
        if (!shouldSuppressSelection()) return;
        event.preventDefault();
        event.stopPropagation();
      }}
      style={{
        cursor: "grab",
        opacity: isDragging ? 0.4 : 1,
        outline: "none",
      }}
    >
      <TaskCard task={task} onSelect={handleSelect} entityNames={entityNames} />
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
  const t = useInk("light");
  const { c } = t;
  const { setNodeRef, isOver } = useDroppable({ id: status });

  return (
    <div
      ref={setNodeRef}
      style={{
        background: isOver ? c.vermSoft : c.paperWarm,
        border: `1px solid ${isOver ? c.vermillion : c.inkHair}`,
        borderTop: "none",
        borderRadius: `0 0 ${t.radius}px ${t.radius}px`,
        padding: 10,
        display: "flex",
        flexDirection: "column",
        gap: 10,
        flex: 1,
        overflowY: "auto",
        minHeight: 200,
        // B3-06: drag-over ring = 2px vermillion border (set above via isOver)
        transition: "background 0.15s, border-color 0.15s",
      }}
    >
      {isEmpty ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "48px 0",
            opacity: isOver ? 0.6 : 0.3,
          }}
        >
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: "50%",
              border: `2px dashed ${isOver ? c.vermillion : c.inkMuted}`,
              marginBottom: 10,
            }}
          />
          <p
            style={{
              fontFamily: t.fontBody,
              fontSize: 10,
              fontWeight: 500,
              color: c.inkMuted,
            }}
          >
            目前沒有任務
          </p>
        </div>
      ) : (
        children
      )}
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
  onHandoffTask,
}: TaskBoardProps) {
  const t = useInk("light");
  const { c, fontBody, fontMono, radius } = t;

  const [internalSelectedTask, setInternalSelectedTask] = useState<Task | null>(null);
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [suppressSelection, setSuppressSelection] = useState(false);
  // B3-02: warn dialog state for bad status jumps
  const [pendingDrag, setPendingDrag] = useState<{ taskId: string; newStatus: string } | null>(null);
  const [dragWarning, setDragWarning] = useState<string | null>(null);
  const suppressTimeoutRef = useRef<number | null>(null);
  const suppressSelectionUntilRef = useRef(0);

  const selectedTask =
    controlledSelectedTask !== undefined ? controlledSelectedTask : internalSelectedTask;
  const setSelectedTask = (task: Task | null) => {
    if (onSelectTask) {
      onSelectTask(task);
      return;
    }
    setInternalSelectedTask(task);
  };

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  const armSelectionSuppression = React.useCallback((durationMs = 450) => {
    const until = Date.now() + durationMs;
    suppressSelectionUntilRef.current = until;
    setSuppressSelection(true);
    if (suppressTimeoutRef.current !== null) {
      window.clearTimeout(suppressTimeoutRef.current);
    }
    suppressTimeoutRef.current = window.setTimeout(() => {
      if (Date.now() >= suppressSelectionUntilRef.current) {
        setSuppressSelection(false);
      }
      suppressTimeoutRef.current = null;
    }, durationMs);
  }, []);

  const shouldSuppressSelection = React.useCallback(() => {
    return suppressSelection || Date.now() < suppressSelectionUntilRef.current;
  }, [suppressSelection]);

  const activeColumns = useMemo(() => {
    if (visibleStatuses.length > 0) {
      return DEFAULT_COLUMN_ORDER.filter((s) => visibleStatuses.includes(s));
    }
    return DEFAULT_COLUMN_ORDER;
  }, [visibleStatuses]);

  // Group by status, then by planId within status
  const boardData = useMemo(() => {
    const data: Record<string, { planId: string | null; tasks: Task[] }[]> = {};

    for (const status of DEFAULT_COLUMN_ORDER) {
      let statusTasks = tasks.filter((t) => t.status === status);

      if (status === "done") {
        statusTasks.sort((a, b) => {
          const timeA = a.completedAt?.getTime() || a.updatedAt.getTime();
          const timeB = b.completedAt?.getTime() || b.updatedAt.getTime();
          return timeB - timeA;
        });
      }

      const planGroups: Record<string, Task[]> = {};
      const noPlanTasks: Task[] = [];

      for (const task of statusTasks) {
        if (task.planId) {
          if (!planGroups[task.planId]) planGroups[task.planId] = [];
          planGroups[task.planId].push(task);
        } else {
          noPlanTasks.push(task);
        }
      }

      const sortedGroups = Object.entries(planGroups)
        .map(([planId, groupTasks]) => ({
          planId,
          tasks: groupTasks.sort((a, b) => (a.planOrder ?? 0) - (b.planOrder ?? 0)),
        }))
        .sort((a, b) => a.planId.localeCompare(b.planId));

      let finalGroups = [
        ...sortedGroups,
        ...(noPlanTasks.length > 0
          ? [
              {
                planId: null,
                tasks: noPlanTasks.sort((a, b) => {
                  if (status === "done") return 0;
                  const pMap: Record<string, number> = {
                    critical: 0,
                    high: 1,
                    medium: 2,
                    low: 3,
                  };
                  return pMap[a.priority] - pMap[b.priority];
                }),
              },
            ]
          : []),
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
    if (suppressTimeoutRef.current !== null) {
      window.clearTimeout(suppressTimeoutRef.current);
      suppressTimeoutRef.current = null;
    }
    setSuppressSelection(false);
    const task = event.active.data.current?.task as Task | undefined;
    if (task) setActiveTask(task);
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveTask(null);
    armSelectionSuppression();
    const { active, over } = event;
    if (!over || !onStatusChange) return;

    const taskId = active.id as string;
    const newStatus = over.id as string;
    const task = tasks.find((t) => t.id === taskId);
    if (!task || task.status === newStatus) return;

    // Warning: todo → done (skipping stages)
    if (task.status === "todo" && newStatus === "done") {
      setDragWarning("建議先經過 in_progress 和 review，確定要直接完成？");
      setPendingDrag({ taskId, newStatus });
      return;
    }
    // review requires a result; open the task instead of offering a fake force path
    if (newStatus === "review" && !task.result?.trim()) {
      setSelectedTask(task);
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

  function cancelDrag() {
    setPendingDrag(null);
    setDragWarning(null);
  }

  useEffect(() => {
    return () => {
      if (suppressTimeoutRef.current !== null) {
        window.clearTimeout(suppressTimeoutRef.current);
      }
    };
  }, []);

  const selectedTaskUpToDate = useMemo(() => {
    if (!selectedTask) return null;
    return tasks.find((t) => t.id === selectedTask.id) ?? selectedTask;
  }, [selectedTask, tasks]);

  return (
    <>
      <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 20,
            paddingBottom: 24,
            overflowX: "auto",
          }}
        >
          <div
            style={{
              display: "flex",
              gap: 20,
              minWidth: "fit-content",
            }}
          >
            {activeColumns.map((status) => {
              const groups = boardData[status] || [];
              const totalCountInView = groups.reduce((acc, g) => acc + g.tasks.length, 0);
              const totalCountActual = tasks.filter((t) => t.status === status).length;
              const dotColor = statusDotColor(status, c.vermillion, c.jade, c.ocher, c.inkFaint);

              return (
                <div
                  key={status}
                  style={{
                    width: 320,
                    flexShrink: 0,
                    display: "flex",
                    flexDirection: "column",
                    maxHeight: "calc(100vh - 140px)",
                  }}
                >
                  {/* Column header */}
                  <div
                    style={{
                      background: c.surface,
                      border: `1px solid ${c.inkHair}`,
                      borderBottom: "none",
                      borderRadius: `${radius}px ${radius}px 0 0`,
                      padding: "10px 14px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                      {/* Status dot */}
                      <span
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: "50%",
                          background: dotColor,
                          flexShrink: 0,
                        }}
                      />
                      <span
                        style={{
                          fontFamily: fontMono,
                          fontSize: 10,
                          fontWeight: 400,
                          letterSpacing: "0.18em",
                          textTransform: "uppercase",
                          color: c.inkMuted,
                        }}
                      >
                        {COLUMN_LABELS[status] ?? status}
                      </span>
                      {(status === "todo" || status === "done") && totalCountActual > 20 && (
                        <span
                          style={{
                            fontFamily: fontBody,
                            fontSize: 9,
                            color: c.inkFaint,
                          }}
                        >
                          (Top 20)
                        </span>
                      )}
                    </div>
                    <span
                      style={{
                        fontFamily: fontMono,
                        fontSize: 10,
                        fontWeight: 400,
                        color: c.inkFaint,
                        background: c.paperWarm,
                        border: `1px solid ${c.inkHair}`,
                        borderRadius: radius,
                        padding: "1px 7px",
                      }}
                    >
                      {totalCountActual}
                    </span>
                  </div>

                  <DroppableColumn status={status} isEmpty={totalCountInView === 0}>
                    {groups.map((group, gIdx) => (
                      <div key={group.planId || `no-plan-${gIdx}`} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                        {/* B3-08: Plan group header — InkMark + Divider */}
                        {group.planId && (
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 6,
                              padding: "4px 2px 2px",
                            }}
                          >
                            <InkMark size={14} ink={c.inkMuted} seal={c.vermillion} sealInk={c.paper} />
                            <span
                              style={{
                                fontFamily: fontMono,
                                fontSize: 9,
                                letterSpacing: "0.14em",
                                textTransform: "uppercase",
                                color: c.inkMuted,
                                maxWidth: 180,
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {entityNames[group.planId] || group.planId.slice(-6)}
                            </span>
                            <div style={{ flex: 1 }}>
                              <Divider ink={c.inkHair} />
                            </div>
                          </div>
                        )}
                        {/* Plan group task list */}
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: 8,
                            paddingLeft: group.planId ? 6 : 0,
                            borderLeft: group.planId ? `1px solid ${c.inkHair}` : "none",
                          }}
                        >
                          {group.tasks.map((task) => (
                            <DraggableTaskCard
                              key={task.id}
                              task={task}
                              onSelect={setSelectedTask}
                              entityNames={entityNames}
                              shouldSuppressSelection={shouldSuppressSelection}
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
        </div>

        <DragOverlay>
          {activeTask && (
            <div style={{ opacity: 0.85, transform: "rotate(1deg) scale(1.03)", boxShadow: "0 24px 60px rgba(58,52,44,0.12)" }}>
              <TaskCard task={activeTask} onSelect={() => {}} entityNames={entityNames} />
            </div>
          )}
        </DragOverlay>
      </DndContext>

      {/* B3-02: Drag warning — zen/Dialog */}
      <Dialog
        t={t}
        open={!!dragWarning}
        onOpenChange={(v) => { if (!v) cancelDrag(); }}
        title="確認操作"
        size="sm"
        footer={
          <>
            <Btn t={t} variant="ghost" onClick={cancelDrag}>
              取消
            </Btn>
            <Btn t={t} variant="seal" onClick={confirmDrag}>
              強制執行
            </Btn>
          </>
        }
      >
        <p
          style={{
            fontFamily: t.fontBody,
            fontSize: 13,
            lineHeight: 1.6,
            color: c.inkMuted,
            margin: 0,
          }}
        >
          {dragWarning}
        </p>
      </Dialog>

      <TaskDetailDrawer
        task={selectedTaskUpToDate}
        onClose={() => setSelectedTask(null)}
        allTasks={tasks}
        entityNames={entityNames}
        entitiesById={entitiesById}
        onSelectRelatedTask={setSelectedTask}
        onUpdateTask={onUpdateTask}
        onConfirmTask={onConfirmTask}
        onHandoffTask={onHandoffTask}
      />
    </>
  );
}
