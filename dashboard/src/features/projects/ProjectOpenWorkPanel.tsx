"use client";

import { useInk } from "@/lib/zen-ink/tokens";
import type { ProjectProgressOpenWorkGroup, ProjectProgressTaskSummary } from "@/features/projects/types";

function formatOrder(task: ProjectProgressTaskSummary, fallbackIndex: number) {
  const value = task.plan_order ?? fallbackIndex + 1;
  return String(value).padStart(2, "0");
}

function RiskBadge({
  label,
  tone,
}: {
  label: string;
  tone: "danger" | "warning" | "neutral";
}) {
  const t = useInk("light");
  const { c } = t;
  const styles = {
    danger: { border: c.vermLine, background: c.vermSoft, color: c.vermillion },
    warning: {
      border: "rgba(180, 132, 50, 0.28)",
      background: "rgba(180, 132, 50, 0.10)",
      color: c.ocher,
    },
    neutral: { border: c.inkHairBold, background: c.surface, color: c.inkMuted },
  } as const;
  const current = styles[tone];
  return (
    <span
      style={{
        border: `1px solid ${current.border}`,
        background: current.background,
        color: current.color,
        padding: "3px 8px",
        fontSize: 10,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
      }}
    >
      {label}
    </span>
  );
}

function TaskRow({
  task,
  depth = 0,
  fallbackIndex = 0,
}: {
  task: ProjectProgressTaskSummary;
  depth?: number;
  fallbackIndex?: number;
}) {
  const t = useInk("light");
  const { c, fontMono } = t;
  const isSubtask = depth > 0;

  return (
    <div
      data-testid={isSubtask ? "open-work-subtask" : "open-work-task"}
      style={{
        marginLeft: isSubtask ? 24 : 0,
        borderLeft: isSubtask ? `3px solid ${c.inkHairBold}` : "none",
        paddingLeft: isSubtask ? 14 : 0,
      }}
    >
      <div
        style={{
          border: `1px solid ${c.inkHair}`,
          background: isSubtask ? c.paperWarm : c.surface,
          padding: "12px 14px",
          marginTop: depth === 0 ? 0 : 10,
        }}
      >
        <div style={{ display: "grid", gridTemplateColumns: "42px minmax(0, 1fr) auto", gap: 12 }}>
          <div
            data-testid={isSubtask ? "open-work-subtask-order" : "open-work-task-order"}
            style={{
              fontFamily: fontMono,
              fontSize: 10,
              color: c.inkFaint,
              letterSpacing: "0.16em",
              textTransform: "uppercase",
              paddingTop: 2,
            }}
          >
            {formatOrder(task, fallbackIndex)}
          </div>
          <div>
            <div style={{ fontSize: 13, color: c.ink, fontWeight: 500 }}>{task.title}</div>
            <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 4 }}>
              {task.status}
              {task.blocked_reason ? ` · ${task.blocked_reason}` : ""}
            </div>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "flex-end" }}>
            {task.blocked ? <RiskBadge label="blocked" tone="danger" /> : null}
            {task.status === "review" ? <RiskBadge label="review" tone="warning" /> : null}
            {task.overdue ? <RiskBadge label="overdue" tone="danger" /> : null}
          </div>
        </div>
      </div>
      {task.subtasks.length > 0 ? (
        <div
          data-testid="subtask-group"
          style={{
            marginTop: 8,
            padding: "10px 0 0 0",
          }}
        >
          <div
            data-testid="open-work-subtask-header"
            style={{
              fontFamily: fontMono,
              fontSize: 10,
              color: c.inkFaint,
              letterSpacing: "0.16em",
              textTransform: "uppercase",
              margin: "0 0 6px 38px",
            }}
          >
            Subtasks
          </div>
          {task.subtasks.map((subtask, index) => (
            <TaskRow key={subtask.id} task={subtask} depth={depth + 1} fallbackIndex={index} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function ProjectOpenWorkPanel({
  groups,
  onOpenTasks,
}: {
  groups: ProjectProgressOpenWorkGroup[];
  onOpenTasks: () => void;
}) {
  const t = useInk("light");
  const { c, fontMono } = t;

  return (
    <section
      data-testid="project-open-work-panel"
      style={{
        background: c.surface,
        border: `1px solid ${c.inkHair}`,
        padding: 20,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 14,
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
          Open Work
        </div>
        <button
          type="button"
          onClick={onOpenTasks}
          style={{
            border: `1px solid ${c.inkHairBold}`,
            background: c.paperWarm,
            padding: "6px 10px",
            fontSize: 11,
            color: c.ink,
            cursor: "pointer",
          }}
        >
          查看任務板
        </button>
      </div>

      {groups.length === 0 ? (
        <div style={{ minHeight: 96, display: "flex", alignItems: "center", justifyContent: "center", color: c.inkMuted }}>
          目前沒有未完成工作
        </div>
      ) : (
        <div style={{ display: "grid", gap: 18 }}>
          {groups.map((group) => (
            <div key={group.plan_id || group.plan_goal || "unassigned"} data-testid="open-work-group">
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 10 }}>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 500, color: c.ink }}>
                    {group.plan_goal || "Unassigned work"}
                  </div>
                  <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 3 }}>
                    {group.open_count} open · {group.blocked_count} blocked · {group.review_count} review · {group.overdue_count} overdue
                  </div>
                </div>
              </div>
              <div style={{ display: "grid", gap: 10 }}>
                {group.tasks.map((task, index) => (
                  <TaskRow key={task.id} task={task} fallbackIndex={index} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
