"use client";

import { useMemo, useState } from "react";
import { useInk } from "@/lib/zen-ink/tokens";
import type {
  ProjectProgressMilestone,
  ProjectProgressOpenWorkGroup,
  ProjectProgressPlanSummary,
  ProjectProgressTaskSummary,
} from "@/features/projects/types";

function formatShortDate(value: Date | null | undefined): string {
  if (!value) return "—";
  return value.toLocaleDateString("zh-TW", { month: "2-digit", day: "2-digit" });
}

function buildPlanGroups(
  plans: ProjectProgressPlanSummary[],
  milestones: ProjectProgressMilestone[],
) {
  const milestoneBuckets = new Map<
    string,
    {
      id: string;
      name: string;
      open_count: number;
      plans: ProjectProgressPlanSummary[];
    }
  >();

  for (const milestone of milestones) {
    milestoneBuckets.set(milestone.id, { ...milestone, plans: [] });
  }

  const fallbackMilestones = new Map<string, { id: string; name: string; open_count: number }>();
  for (const plan of plans) {
    for (const milestone of plan.milestones) {
      if (!milestoneBuckets.has(milestone.id)) {
        fallbackMilestones.set(milestone.id, {
          id: milestone.id,
          name: milestone.name,
          open_count: 0,
        });
      }
    }
  }

  const orderedMilestoneIds = [
    ...milestones.map((milestone) => milestone.id),
    ...Array.from(fallbackMilestones.keys()).sort((left, right) => {
      const leftName = fallbackMilestones.get(left)?.name || "";
      const rightName = fallbackMilestones.get(right)?.name || "";
      return leftName.localeCompare(rightName, "zh-Hant");
    }),
  ];

  for (const [milestoneId, milestone] of fallbackMilestones.entries()) {
    milestoneBuckets.set(milestoneId, { ...milestone, plans: [] });
  }

  const unassignedPlans: ProjectProgressPlanSummary[] = [];
  for (const plan of plans) {
    const primaryMilestoneId = orderedMilestoneIds.find((milestoneId) =>
      plan.milestones.some((milestone) => milestone.id === milestoneId),
    );
    if (!primaryMilestoneId) {
      unassignedPlans.push(plan);
      continue;
    }
    milestoneBuckets.get(primaryMilestoneId)?.plans.push(plan);
  }

  const groupedMilestones = orderedMilestoneIds
    .map((milestoneId) => milestoneBuckets.get(milestoneId))
    .filter((value): value is NonNullable<typeof value> => Boolean(value))
    .filter((bucket) => bucket.plans.length > 0);

  return { groupedMilestones, unassignedPlans };
}

function formatOrder(task: ProjectProgressTaskSummary, fallbackIndex: number) {
  const value = task.plan_order ?? fallbackIndex + 1;
  return String(value).padStart(2, "0");
}

function statusTone(task: ProjectProgressTaskSummary) {
  if (task.blocked) return "danger";
  if (task.status === "review") return "warning";
  if (task.overdue) return "danger";
  if (task.status === "in_progress") return "active";
  return "neutral";
}

function TaskRiskPill({
  label,
  tone,
}: {
  label: string;
  tone: "danger" | "warning" | "active" | "neutral";
}) {
  const t = useInk("light");
  const { c } = t;
  const palette = {
    danger: { border: c.vermLine, background: c.vermSoft, color: c.vermillion },
    warning: {
      border: "rgba(180, 132, 50, 0.28)",
      background: "rgba(180, 132, 50, 0.10)",
      color: c.ocher,
    },
    active: {
      border: "rgba(95, 122, 69, 0.24)",
      background: "rgba(95, 122, 69, 0.08)",
      color: c.jade,
    },
    neutral: { border: c.inkHairBold, background: c.surface, color: c.inkMuted },
  } as const;
  const current = palette[tone];

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

function TaskSubtaskList({ subtasks }: { subtasks: ProjectProgressTaskSummary[] }) {
  const t = useInk("light");
  const { c, fontMono } = t;

  return (
    <div
      data-testid="plan-subtask-list"
      style={{
        display: "grid",
        gap: 10,
        marginTop: 14,
        marginLeft: 30,
        padding: "14px 16px 14px 18px",
        borderLeft: `3px solid ${c.inkHairBold}`,
        background: c.paperWarm,
      }}
    >
      <div
        data-testid="plan-subtask-header"
        style={{
          fontFamily: fontMono,
          fontSize: 10,
          color: c.inkFaint,
          letterSpacing: "0.16em",
          textTransform: "uppercase",
        }}
      >
        Subtasks
      </div>
      {subtasks.map((subtask, index) => (
        <div
          key={subtask.id}
          data-testid="plan-subtask-item"
          style={{
            display: "grid",
            gridTemplateColumns: "40px minmax(0, 1fr)",
            gap: 12,
            border: `1px solid ${c.inkHair}`,
            background: c.surface,
            padding: "12px 14px",
          }}
        >
          <div
            style={{
              fontFamily: fontMono,
              fontSize: 10,
              color: c.inkFaint,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              paddingTop: 2,
            }}
          >
            {formatOrder(subtask, index)}
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13, color: c.ink, fontWeight: 500 }}>{subtask.title}</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
              <TaskRiskPill label={subtask.status} tone={statusTone(subtask)} />
              {subtask.blocked ? <TaskRiskPill label="blocked" tone="danger" /> : null}
              {subtask.overdue ? <TaskRiskPill label="overdue" tone="danger" /> : null}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function PlanTaskRow({
  task,
  fallbackIndex,
}: {
  task: ProjectProgressTaskSummary;
  fallbackIndex: number;
}) {
  const t = useInk("light");
  const { c, fontMono } = t;
  const [open, setOpen] = useState(false);

  return (
    <div
      data-testid="plan-task-row"
      style={{
        border: `1px solid ${c.inkHair}`,
        background: c.surface,
      }}
    >
      <button
        type="button"
        data-testid="plan-task-toggle"
        onClick={() => setOpen((value) => !value)}
        style={{
          width: "100%",
          display: "grid",
          gridTemplateColumns: "52px minmax(0, 1fr) auto",
          gap: 12,
          padding: "14px 16px",
          textAlign: "left",
          border: "none",
          background: "transparent",
          cursor: task.subtasks.length > 0 ? "pointer" : "default",
        }}
      >
        <div
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
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 14, color: c.ink, fontWeight: 500 }}>{task.title}</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
            <TaskRiskPill label={task.status} tone={statusTone(task)} />
            {task.blocked ? <TaskRiskPill label="blocked" tone="danger" /> : null}
            {task.overdue ? <TaskRiskPill label="overdue" tone="danger" /> : null}
            {task.subtasks.length > 0 ? (
              <TaskRiskPill
                label={`${task.subtasks.length} subtask${task.subtasks.length > 1 ? "s" : ""}`}
                tone="neutral"
              />
            ) : null}
          </div>
        </div>
        <div
          style={{
            fontFamily: fontMono,
            fontSize: 10,
            color: c.inkFaint,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            whiteSpace: "nowrap",
            alignSelf: "center",
          }}
        >
          {task.subtasks.length > 0 ? (open ? "Hide" : "Open") : "Task"}
        </div>
      </button>
      {open && task.subtasks.length > 0 ? (
        <div style={{ padding: "0 16px 14px 16px" }}>
          <TaskSubtaskList subtasks={task.subtasks} />
        </div>
      ) : null}
    </div>
  );
}

function PlanCard({
  plan,
  taskGroup,
  focusedPlanId,
  focusedMilestoneId,
}: {
  plan: ProjectProgressPlanSummary;
  taskGroup?: ProjectProgressOpenWorkGroup;
  focusedPlanId?: string | null;
  focusedMilestoneId?: string | null;
}) {
  const t = useInk("light");
  const { c, fontHead, fontMono } = t;
  const topLevelTasks = taskGroup?.tasks ?? [];

  return (
    <article
      data-testid="plan-card"
      style={{
        border: `1px solid ${plan.id === focusedPlanId ? c.vermillion : plan.blocked_count > 0 ? c.vermLine : c.inkHair}`,
        background: plan.id === focusedPlanId ? c.surface : plan.blocked_count > 0 ? c.vermSoft : c.paperWarm,
        padding: 16,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
        <div>
          <div
            style={{
              fontFamily: fontHead,
              fontSize: 18,
              color: c.ink,
              fontWeight: 500,
            }}
          >
            {plan.goal}
          </div>
          <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 4 }}>
            {plan.status} · 最近更新 {formatShortDate(plan.updated_at)}
          </div>
        </div>
        <div
          style={{
            fontFamily: fontMono,
            fontSize: 10,
            color: c.inkFaint,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            whiteSpace: "nowrap",
          }}
        >
          {plan.owner || "Unassigned"}
        </div>
      </div>

      {plan.milestones.length > 0 ? (
        <div
          data-testid="plan-milestone-chip-group"
          style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}
        >
          {plan.milestones.map((milestone) => (
            <span
              key={milestone.id}
              style={{
                border: `1px solid ${milestone.id === focusedMilestoneId ? c.vermillion : c.inkHairBold}`,
                background: milestone.id === focusedMilestoneId ? c.vermSoft : c.surface,
                color: milestone.id === focusedMilestoneId ? c.ink : c.inkMuted,
                padding: "4px 8px",
                fontSize: 10,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              {milestone.name}
            </span>
          ))}
        </div>
      ) : null}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
          gap: 10,
          marginTop: 14,
        }}
      >
        {[
          { label: "Open", value: plan.open_count },
          { label: "Blocked", value: plan.blocked_count },
          { label: "Review", value: plan.review_count },
          { label: "Overdue", value: plan.overdue_count },
        ].map((item) => (
          <div key={item.label} style={{ background: c.surface, padding: "10px 12px" }}>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint }}>{item.label}</div>
            <div style={{ fontFamily: fontHead, fontSize: 20, color: c.ink, marginTop: 4 }}>
              {item.value}
            </div>
          </div>
        ))}
      </div>

      {topLevelTasks.length > 0 ? (
        <div style={{ marginTop: 16, display: "grid", gap: 10 }}>
          <div
            style={{
              fontFamily: fontMono,
              fontSize: 10,
              color: c.inkFaint,
              letterSpacing: "0.16em",
              textTransform: "uppercase",
            }}
          >
            Task Breakdown
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {topLevelTasks.map((task, index) => (
              <PlanTaskRow key={task.id} task={task} fallbackIndex={index} />
            ))}
          </div>
        </div>
      ) : null}
    </article>
  );
}

export function ProjectPlansOverview({
  plans,
  milestones,
  groups,
  focusedPlanId,
  focusedMilestoneId,
}: {
  plans: ProjectProgressPlanSummary[];
  milestones: ProjectProgressMilestone[];
  groups: ProjectProgressOpenWorkGroup[];
  focusedPlanId?: string | null;
  focusedMilestoneId?: string | null;
}) {
  const t = useInk("light");
  const { c, fontHead, fontMono } = t;
  const { groupedMilestones, unassignedPlans } = buildPlanGroups(plans, milestones);
  const groupsByPlan = useMemo(
    () => new Map(groups.map((group) => [group.plan_id || "", group])),
    [groups],
  );

  return (
    <section
      data-testid="project-plans-overview"
      style={{
        background: c.surface,
        border: `1px solid ${c.inkHair}`,
        padding: 20,
      }}
    >
      <div
        style={{
          fontFamily: fontMono,
          fontSize: 10,
          color: c.inkFaint,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          marginBottom: 14,
        }}
      >
        Milestones → Plans → Task Breakdown
      </div>

      {plans.length === 0 ? (
        <div
          style={{
            minHeight: 108,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: c.inkMuted,
            fontSize: 13,
          }}
        >
          目前沒有進行中的 plan
        </div>
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          {groupedMilestones.map((bucket) => (
            <section
              key={bucket.id}
              data-testid="plan-milestone-group"
              style={{
                border: `1px solid ${c.inkHair}`,
                background: c.surface,
                padding: 16,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
                <div>
                  <div style={{ fontFamily: fontHead, fontSize: 20, color: c.ink, fontWeight: 500 }}>
                    {bucket.name}
                  </div>
                  <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 4 }}>
                    {bucket.plans.length} plan · {bucket.open_count} open item(s)
                  </div>
                </div>
                <div
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    color: c.inkFaint,
                    letterSpacing: "0.12em",
                    textTransform: "uppercase",
                    whiteSpace: "nowrap",
                  }}
                >
                  Milestone
                </div>
              </div>

              <div style={{ display: "grid", gap: 12 }}>
                {bucket.plans.map((plan) => (
                  <PlanCard
                    key={plan.id}
                    plan={plan}
                    taskGroup={groupsByPlan.get(plan.id)}
                    focusedPlanId={focusedPlanId}
                    focusedMilestoneId={focusedMilestoneId}
                  />
                ))}
              </div>
            </section>
          ))}

          {unassignedPlans.length > 0 ? (
            <section
              data-testid="plan-milestone-group-unassigned"
              style={{
                border: `1px solid ${c.inkHair}`,
                background: c.surface,
                padding: 16,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
                <div>
                  <div style={{ fontFamily: fontHead, fontSize: 20, color: c.ink, fontWeight: 500 }}>
                    Unassigned
                  </div>
                  <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 4 }}>
                    尚未對齊 milestone 的 plans
                  </div>
                </div>
                <div
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    color: c.inkFaint,
                    letterSpacing: "0.12em",
                    textTransform: "uppercase",
                    whiteSpace: "nowrap",
                  }}
                >
                  Plan
                </div>
              </div>
              <div style={{ display: "grid", gap: 12 }}>
                {unassignedPlans.map((plan) => (
                  <PlanCard
                    key={plan.id}
                    plan={plan}
                    taskGroup={groupsByPlan.get(plan.id)}
                    focusedPlanId={focusedPlanId}
                    focusedMilestoneId={focusedMilestoneId}
                  />
                ))}
              </div>
            </section>
          ) : null}
        </div>
      )}
    </section>
  );
}
