"use client";

import { useInk } from "@/lib/zen-ink/tokens";
import type { ProjectProgressMilestone, ProjectProgressPlanSummary } from "@/features/projects/types";

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

function PlanCard({ plan }: { plan: ProjectProgressPlanSummary }) {
  const t = useInk("light");
  const { c, fontHead, fontMono } = t;

  return (
    <article
      data-testid="plan-card"
      style={{
        border: `1px solid ${plan.blocked_count > 0 ? c.vermLine : c.inkHair}`,
        background: plan.blocked_count > 0 ? c.vermSoft : c.paperWarm,
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
                border: `1px solid ${c.inkHairBold}`,
                background: c.surface,
                color: c.inkMuted,
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
    </article>
  );
}

export function ProjectPlansOverview({
  plans,
  milestones,
}: {
  plans: ProjectProgressPlanSummary[];
  milestones: ProjectProgressMilestone[];
}) {
  const t = useInk("light");
  const { c, fontHead, fontMono } = t;
  const { groupedMilestones, unassignedPlans } = buildPlanGroups(plans, milestones);

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
        Milestones → Current Plans
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
                  <PlanCard key={plan.id} plan={plan} />
                ))}
              </div>
            </section>
          ))}

          {unassignedPlans.length > 0 ? (
            <section
              data-testid="plan-milestone-group-unassigned"
              style={{
                border: `1px dashed ${c.inkHairBold}`,
                background: c.paperWarm,
                padding: 16,
              }}
            >
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontFamily: fontHead, fontSize: 20, color: c.ink, fontWeight: 500 }}>
                  未綁 milestone
                </div>
                <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 4 }}>
                  這些 plan 還沒有掛到明確階段
                </div>
              </div>

              <div style={{ display: "grid", gap: 12 }}>
                {unassignedPlans.map((plan) => (
                  <PlanCard key={plan.id} plan={plan} />
                ))}
              </div>
            </section>
          ) : null}
        </div>
      )}
    </section>
  );
}
