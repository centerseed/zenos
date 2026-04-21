"use client";

import { useInk } from "@/lib/zen-ink/tokens";
import type { ProjectProgressPlanSummary } from "@/features/projects/types";

function formatShortDate(value: Date | null | undefined): string {
  if (!value) return "—";
  return value.toLocaleDateString("zh-TW", { month: "2-digit", day: "2-digit" });
}

export function ProjectPlansOverview({
  plans,
}: {
  plans: ProjectProgressPlanSummary[];
}) {
  const t = useInk("light");
  const { c, fontHead, fontMono } = t;

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
        Current Plans
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
          {plans.map((plan) => (
            <article
              key={plan.id}
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
          ))}
        </div>
      )}
    </section>
  );
}

