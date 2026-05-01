"use client";

import { useInk } from "@/lib/zen-ink/tokens";
import type { TaskHubFocus, TaskHubSnapshot } from "@/features/tasks/taskHub";

export function MilestonePlanRadar({
  snapshot,
  onOpenFocus,
}: {
  snapshot: TaskHubSnapshot;
  onOpenFocus: (productId: string, focus: TaskHubFocus) => void;
}) {
  const t = useInk("light");
  const { c, fontMono } = t;

  if (snapshot.radar.length === 0) return null;

  return (
    <section
      data-testid="milestone-plan-radar"
      style={{
        background: c.surface,
        border: `1px solid ${c.inkHair}`,
        padding: 20,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 12,
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
          Milestone / Plan Radar
        </div>
        <div style={{ fontSize: 11, color: c.inkMuted }}>優先列出 blocked / overdue / review 的焦點</div>
      </div>

      {snapshot.radar.length === 0 ? (
        <div style={{ fontSize: 12, color: c.inkMuted }}>目前沒有高風險 milestone 或 plan。</div>
      ) : (
        <div style={{ display: "grid", gap: 10 }}>
          {snapshot.radar.map((item) => (
            <button
              key={item.id}
              type="button"
              data-testid="task-hub-radar-item"
              onClick={() => onOpenFocus(item.productId, item.focus)}
              style={{
                border: `1px solid ${item.blockedCount > 0 || item.overdueCount > 0 ? c.vermLine : c.inkHair}`,
                background: item.blockedCount > 0 || item.overdueCount > 0 ? c.vermSoft : c.paperWarm,
                padding: 14,
                cursor: "pointer",
                textAlign: "left",
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: c.ink }}>{item.title}</div>
                  <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 4 }}>{item.subtitle}</div>
                </div>
                <div
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    color: c.inkFaint,
                    textTransform: "uppercase",
                    letterSpacing: "0.14em",
                    whiteSpace: "nowrap",
                  }}
                >
                  {item.kind}
                </div>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
                <RiskLabel label={`${item.openCount} open`} />
                <RiskLabel label={`${item.blockedCount} blocked`} danger={item.blockedCount > 0} />
                <RiskLabel label={`${item.reviewCount} review`} warning={item.reviewCount > 0} />
                <RiskLabel label={`${item.overdueCount} overdue`} danger={item.overdueCount > 0} />
              </div>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function RiskLabel({
  label,
  danger = false,
  warning = false,
}: {
  label: string;
  danger?: boolean;
  warning?: boolean;
}) {
  const color = danger ? "#b63a2c" : warning ? "#8e6a2d" : "#8e8679";
  return (
    <span
      style={{
        border: `1px solid ${danger ? "rgba(182,58,44,0.24)" : warning ? "rgba(180,132,50,0.28)" : "rgba(142,134,121,0.25)"}`,
        background: danger ? "rgba(182,58,44,0.08)" : warning ? "rgba(180,132,50,0.10)" : "#f7f2e7",
        color,
        padding: "4px 8px",
        fontSize: 10,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
      }}
    >
      {label}
    </span>
  );
}
