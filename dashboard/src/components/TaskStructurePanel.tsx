"use client";

import React from "react";
import type { Task } from "@/types";
import { useInk } from "@/lib/zen-ink/tokens";

interface TaskStructurePanelProps {
  currentTask: Task;
  planName?: string | null;
  parentTask?: Task | null;
  siblingTasks: Task[];
  childSubtasks: Task[];
  topLevelPlanTasks: Task[];
  planTasks: Task[];
  onSelectRelatedTask?: (task: Task) => void;
}

function formatTaskOrder(order: number | null | undefined): string {
  if (!Number.isFinite(order)) return "—";
  return String(order).padStart(2, "0");
}

export function TaskStructurePanel({
  currentTask,
  planName,
  parentTask,
  siblingTasks,
  childSubtasks,
  topLevelPlanTasks,
  planTasks,
  onSelectRelatedTask,
}: TaskStructurePanelProps) {
  const t = useInk("light");
  const { c } = t;
  const buttonBase: React.CSSProperties = {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 12,
    width: "100%",
    textAlign: "left",
    padding: "10px 12px",
    background: c.surface,
    border: `1px solid ${c.inkHair}`,
    borderRadius: t.radius,
    cursor: onSelectRelatedTask ? "pointer" : "default",
  };

  const renderRelatedTaskButton = (
    relatedTask: Task,
    options?: { active?: boolean; secondary?: string; nested?: boolean }
  ) => (
    <button
      key={relatedTask.id}
      type="button"
      onClick={() => onSelectRelatedTask?.(relatedTask)}
      disabled={!onSelectRelatedTask}
      style={{
        ...buttonBase,
        background: options?.active ? c.paperWarm : options?.nested ? c.paper : c.surface,
        borderColor: options?.active ? c.vermLine : c.inkHair,
        paddingLeft: options?.nested ? 16 : 12,
        opacity: onSelectRelatedTask ? 1 : 0.96,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10, minWidth: 0 }}>
        <span
          style={{
            fontFamily: t.fontMono,
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            color: options?.active ? c.vermillion : c.inkMuted,
            flexShrink: 0,
            paddingTop: 2,
          }}
        >
          {formatTaskOrder(relatedTask.planOrder)}
        </span>
        <div style={{ minWidth: 0, display: "flex", flexDirection: "column", gap: 4 }}>
          <span
            style={{
              fontFamily: t.fontBody,
              fontSize: options?.nested ? 12 : 13,
              fontWeight: options?.active ? 600 : 500,
              color: c.ink,
              lineHeight: 1.45,
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {relatedTask.title}
          </span>
          {options?.secondary && (
            <span style={{ fontFamily: t.fontBody, fontSize: 11, color: c.inkFaint }}>
              {options.secondary}
            </span>
          )}
        </div>
      </div>
      <span
        style={{
          fontFamily: t.fontMono,
          fontSize: 10,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: options?.active ? c.vermillion : c.inkFaint,
          flexShrink: 0,
          paddingTop: 2,
        }}
      >
        {options?.active ? "Current" : relatedTask.parentTaskId ? "Subtask" : "Task"}
      </span>
    </button>
  );

  return (
    <div data-testid="task-structure-panel" style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ width: 3, height: 16, borderRadius: 999, background: c.vermillion, flexShrink: 0 }} />
        <span
          style={{
            fontFamily: t.fontMono,
            fontSize: 10,
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.16em",
            color: c.inkMuted,
          }}
        >
          Structure
        </span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.2fr 1fr",
          gap: 16,
          alignItems: "start",
        }}
      >
        <div
          style={{
            background: c.paperWarm,
            border: `1px solid ${c.inkHair}`,
            borderRadius: t.radius,
            padding: 16,
            display: "flex",
            flexDirection: "column",
            gap: 14,
          }}
        >
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 10 }}>
            <Metric label="Plan" value={planName || "未掛 plan"} />
            <Metric label="Current" value={`#${formatTaskOrder(currentTask.planOrder)}`} accent />
            <Metric label="Parent" value={parentTask ? parentTask.title : "Top-level task"} />
            <Metric label="Children" value={String(childSubtasks.length)} />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <MicroLabel label="Current Task" />
            {renderRelatedTaskButton(currentTask, { active: true, secondary: `${currentTask.status} · ${currentTask.priority}` })}
          </div>

          {parentTask && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <MicroLabel label="Parent Task" />
              {renderRelatedTaskButton(parentTask, { secondary: "Open parent task" })}
            </div>
          )}

          {siblingTasks.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <MicroLabel label="Same Level" />
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {siblingTasks.map((item) => renderRelatedTaskButton(item))}
              </div>
            </div>
          )}

          {childSubtasks.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <MicroLabel label="Subtasks" />
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                  paddingLeft: 14,
                  borderLeft: `2px solid ${c.vermLine}`,
                }}
              >
                {childSubtasks.map((item) =>
                  renderRelatedTaskButton(item, { nested: true, secondary: `${item.status} · ${item.priority}` })
                )}
              </div>
            </div>
          )}
        </div>

        {topLevelPlanTasks.length > 0 && (
          <div
            style={{
              background: c.surface,
              border: `1px solid ${c.inkHair}`,
              borderRadius: t.radius,
              padding: 16,
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}
          >
            <MicroLabel label="Plan Outline" />
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {topLevelPlanTasks.map((item) => {
                const descendants = planTasks.filter((candidate) => candidate.parentTaskId === item.id);
                const isCurrentTop = item.id === currentTask.id || currentTask.parentTaskId === item.id;
                return (
                  <div
                    key={item.id}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                      padding: 12,
                      borderRadius: t.radius,
                      background: isCurrentTop ? c.paperWarm : c.paper,
                      border: `1px solid ${isCurrentTop ? c.vermLine : c.inkHair}`,
                    }}
                  >
                    {renderRelatedTaskButton(item, {
                      active: item.id === currentTask.id,
                      secondary: descendants.length > 0 ? `${descendants.length} subtasks` : undefined,
                    })}
                    {descendants.length > 0 && (
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: 6,
                          paddingLeft: 14,
                          borderLeft: `1px solid ${c.inkHair}`,
                        }}
                      >
                        {descendants.map((subtask) =>
                          renderRelatedTaskButton(subtask, {
                            active: subtask.id === currentTask.id,
                            nested: true,
                          })
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <div
        style={{
          fontFamily: "var(--font-mono, ui-monospace, monospace)",
          fontSize: 9,
          textTransform: "uppercase",
          letterSpacing: "0.14em",
          color: "var(--zen-ink-faint, #8f867b)",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: label === "Current" ? "var(--font-mono, ui-monospace, monospace)" : "var(--font-body, Georgia, serif)",
          fontSize: label === "Current" ? 15 : 12,
          fontWeight: accent ? 700 : 500,
          color: accent ? "var(--zen-vermillion, #b54732)" : "var(--zen-ink, #2c2723)",
          lineHeight: 1.5,
          marginTop: 4,
        }}
      >
        {value}
      </div>
    </div>
  );
}

function MicroLabel({ label }: { label: string }) {
  return (
    <div
      style={{
        fontFamily: "var(--font-mono, ui-monospace, monospace)",
        fontSize: 9,
        textTransform: "uppercase",
        letterSpacing: "0.14em",
        color: "var(--zen-ink-faint, #8f867b)",
      }}
    >
      {label}
    </div>
  );
}
