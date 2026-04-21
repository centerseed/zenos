"use client";

import { useInk } from "@/lib/zen-ink/tokens";
import type { ProjectProgressOpenWorkGroup, ProjectProgressTaskSummary } from "@/features/projects/types";

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
}: {
  task: ProjectProgressTaskSummary;
  depth?: number;
}) {
  const t = useInk("light");
  const { c } = t;

  return (
    <div data-testid={depth === 0 ? "open-work-task" : "open-work-subtask"} style={{ marginLeft: depth * 18 }}>
      <div
        style={{
          border: `1px solid ${c.inkHair}`,
          background: c.surface,
          padding: "12px 14px",
          marginTop: depth === 0 ? 0 : 10,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
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
        <div data-testid="subtask-group" style={{ marginTop: 8 }}>
          {task.subtasks.map((subtask) => (
            <TaskRow key={subtask.id} task={subtask} depth={depth + 1} />
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
                {group.tasks.map((task) => (
                  <TaskRow key={task.id} task={task} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
